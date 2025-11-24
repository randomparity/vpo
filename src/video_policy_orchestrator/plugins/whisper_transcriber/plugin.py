"""Whisper-based transcription plugin implementation.

This is a reference implementation using OpenAI's Whisper for local,
offline transcription and language detection.
"""

from datetime import datetime, timezone

from video_policy_orchestrator.language import normalize_language
from video_policy_orchestrator.transcription.interface import TranscriptionError
from video_policy_orchestrator.transcription.models import (
    TrackClassification,
    TranscriptionConfig,
    TranscriptionResult,
    detect_commentary_type,
)


class PluginDependencyError(TranscriptionError):
    """Raised when a required plugin dependency is not installed."""

    pass


def _get_whisper():
    """Lazy load whisper module.

    Returns:
        The whisper module.

    Raises:
        PluginDependencyError: If whisper is not installed.
    """
    try:
        import whisper

        return whisper
    except ImportError:
        raise PluginDependencyError(
            "Whisper plugin requires 'openai-whisper' package. "
            "Install with: pip install openai-whisper"
        )


def _find_wav_data_offset(audio_data: bytes) -> int:
    """Find the offset to the 'data' chunk in a WAV file.

    WAV files have variable-length headers due to optional chunks like LIST.
    This function properly parses the RIFF structure to find where audio
    data actually starts.

    Args:
        audio_data: Raw WAV file bytes.

    Returns:
        Byte offset where PCM audio data begins.

    Raises:
        ValueError: If the data is not a valid WAV file.
    """
    import struct

    if len(audio_data) < 44:
        raise ValueError("Audio data too short to be a valid WAV file")

    # Verify RIFF header
    if audio_data[0:4] != b"RIFF" or audio_data[8:12] != b"WAVE":
        raise ValueError("Not a valid WAV file")

    # Iterate through chunks to find 'data'
    pos = 12  # Start after RIFF header
    while pos < len(audio_data) - 8:
        chunk_id = audio_data[pos : pos + 4]
        chunk_size = struct.unpack("<I", audio_data[pos + 4 : pos + 8])[0]

        if chunk_id == b"data":
            return pos + 8  # Data starts after chunk header

        # Move to next chunk (header size + chunk size, word-aligned)
        pos += 8 + chunk_size
        if chunk_size % 2:  # Word alignment
            pos += 1

    raise ValueError("No 'data' chunk found in WAV file")


class WhisperTranscriptionPlugin:
    """Whisper-based transcription plugin.

    Provides local, offline transcription and language detection
    using OpenAI's Whisper models.
    """

    def __init__(self, config: TranscriptionConfig | None = None) -> None:
        """Initialize the plugin.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self._config = config or TranscriptionConfig()
        self._model = None
        self._device = "cpu"  # Will be set properly in _load_model()
        self._name = "whisper-local"
        self._version = "1.0.0"

    @property
    def name(self) -> str:
        """Plugin identifier."""
        return self._name

    @property
    def version(self) -> str:
        """Plugin version string."""
        return self._version

    def _load_model(self):
        """Load the Whisper model lazily.

        Returns:
            Loaded Whisper model.
        """
        if self._model is None:
            whisper = _get_whisper()
            self._device = "cuda" if self._config.gpu_enabled else "cpu"
            try:
                import torch

                if self._device == "cuda" and not torch.cuda.is_available():
                    self._device = "cpu"
            except ImportError:
                self._device = "cpu"

            self._model = whisper.load_model(
                self._config.model_size, device=self._device
            )
        return self._model

    def detect_language(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """Detect language from audio data.

        Args:
            audio_data: Raw audio bytes (WAV format, mono, 16kHz).
            sample_rate: Sample rate of audio data.

        Returns:
            TranscriptionResult with detected_language and confidence_score.

        Raises:
            TranscriptionError: If detection fails.
        """
        try:
            whisper = _get_whisper()
            model = self._load_model()

            # Load audio from bytes
            import numpy as np

            # Parse WAV header to find actual audio data
            data_offset = _find_wav_data_offset(audio_data)
            raw_audio = np.frombuffer(audio_data[data_offset:], dtype=np.int16)
            audio = raw_audio.astype(np.float32) / 32768.0

            # Pad/trim to 30 seconds for language detection
            audio = whisper.pad_or_trim(audio)

            # Make log-Mel spectrogram
            mel = whisper.log_mel_spectrogram(audio).to(model.device)

            # Detect language
            _, probs = model.detect_language(mel)

            # Get top language and confidence
            # Whisper returns ISO 639-1 codes (e.g., "en", "de")
            detected_lang_raw = max(probs, key=probs.get)
            confidence = float(probs[detected_lang_raw])

            # Normalize to project standard (ISO 639-2/B by default)
            detected_lang = normalize_language(detected_lang_raw)

            now = datetime.now(timezone.utc)
            return TranscriptionResult(
                track_id=0,  # Will be set by caller
                detected_language=detected_lang,
                confidence_score=confidence,
                track_type=TrackClassification.MAIN,
                transcript_sample=None,
                plugin_name=self.name,
                created_at=now,
                updated_at=now,
            )
        except PluginDependencyError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Language detection failed: {e}") from e

    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Full transcription with optional language hint.

        Args:
            audio_data: Raw audio bytes (WAV format, mono, 16kHz).
            sample_rate: Sample rate of audio data.
            language: Optional language hint (ISO 639-1/639-2 code).

        Returns:
            TranscriptionResult with transcript_sample and detected_language.

        Raises:
            TranscriptionError: If transcription fails.
        """
        try:
            _get_whisper()  # Ensure whisper is available
            model = self._load_model()

            # Load audio from bytes
            import numpy as np

            # Parse WAV header to find actual audio data
            data_offset = _find_wav_data_offset(audio_data)
            raw_audio = np.frombuffer(audio_data[data_offset:], dtype=np.int16)
            audio = raw_audio.astype(np.float32) / 32768.0

            # Transcribe (use fp16=False on CPU to avoid warning)
            fp16 = self._device == "cuda"
            result = model.transcribe(audio, language=language, fp16=fp16)

            # Extract sample (first ~100 chars)
            transcript = result.get("text", "").strip()
            transcript_sample = transcript[:100] if transcript else None

            # Whisper returns ISO 639-1 codes, normalize to project standard
            detected_lang_raw = result.get("language", language)
            detected_lang = normalize_language(detected_lang_raw)

            # Confidence scoring based on transcript quality
            # Empty or very short transcripts indicate no speech was detected,
            # which means the language detection is unreliable
            if not transcript:
                # No speech detected - very low confidence
                confidence = 0.3
            elif len(transcript) < 20:
                # Very short transcript - low confidence
                confidence = 0.5
            elif len(transcript) < 50:
                # Short transcript - moderate confidence
                confidence = 0.7
            else:
                # Substantial transcript - high confidence
                confidence = 0.9

            # Detect track type using transcript analysis
            # Note: title is not available here, so we pass None
            track_type = detect_commentary_type(None, transcript_sample)

            now = datetime.now(timezone.utc)
            return TranscriptionResult(
                track_id=0,  # Will be set by caller
                detected_language=detected_lang,
                confidence_score=confidence,
                track_type=track_type,
                transcript_sample=transcript_sample,
                plugin_name=self.name,
                created_at=now,
                updated_at=now,
            )
        except PluginDependencyError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}") from e

    def supports_feature(self, feature: str) -> bool:
        """Check if plugin supports a feature.

        Args:
            feature: Feature name to check.

        Returns:
            True if feature is supported.
        """
        supported = {
            "transcription": True,
            "gpu": self._config.gpu_enabled,
            "language_detection": True,
        }
        return supported.get(feature, False)
