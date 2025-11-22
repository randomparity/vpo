"""Whisper-based transcription plugin implementation.

This is a reference implementation using OpenAI's Whisper for local,
offline transcription and language detection.
"""

from datetime import datetime, timezone

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
            device = "cuda" if self._config.gpu_enabled else "cpu"
            try:
                import torch

                if device == "cuda" and not torch.cuda.is_available():
                    device = "cpu"
            except ImportError:
                device = "cpu"

            self._model = whisper.load_model(self._config.model_size, device=device)
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
            import io

            import numpy as np

            # Parse WAV header to get to raw PCM data
            audio_file = io.BytesIO(audio_data)
            # Skip WAV header (44 bytes for standard WAV)
            audio_file.seek(44)
            raw_audio = np.frombuffer(audio_file.read(), dtype=np.int16)
            audio = raw_audio.astype(np.float32) / 32768.0

            # Pad/trim to 30 seconds for language detection
            audio = whisper.pad_or_trim(audio)

            # Make log-Mel spectrogram
            mel = whisper.log_mel_spectrogram(audio).to(model.device)

            # Detect language
            _, probs = model.detect_language(mel)

            # Get top language and confidence
            detected_lang = max(probs, key=probs.get)
            confidence = float(probs[detected_lang])

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
            import io

            import numpy as np

            audio_file = io.BytesIO(audio_data)
            audio_file.seek(44)  # Skip WAV header
            raw_audio = np.frombuffer(audio_file.read(), dtype=np.int16)
            audio = raw_audio.astype(np.float32) / 32768.0

            # Transcribe
            result = model.transcribe(audio, language=language)

            # Extract sample (first ~100 chars)
            transcript = result.get("text", "")
            transcript_sample = transcript[:100] if transcript else None

            detected_lang = result.get("language", language)
            # Whisper doesn't provide confidence for transcription, use 0.9 as default
            confidence = 0.9 if detected_lang else 0.0

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
