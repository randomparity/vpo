"""Interface definitions for transcription plugins."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class TranscriptionError(Exception):
    """Base exception for transcription-related errors."""

    pass


@dataclass
class MultiLanguageDetectionConfig:
    """Configuration for multi-language detection.

    Controls how audio tracks are sampled and analyzed for language detection.

    Attributes:
        num_samples: Number of positions to sample (default: 5).
        sample_duration: Duration of each sample in seconds (default: 30).
        min_speech_ratio: Minimum speech-to-silence ratio to consider valid.
        confidence_threshold: Minimum confidence score to accept a language
            detection result (default: 0.85).
    """

    num_samples: int = 5
    sample_duration: float = 30.0
    min_speech_ratio: float = 0.1
    confidence_threshold: float = 0.85

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.num_samples < 1:
            raise ValueError("num_samples must be at least 1")
        if self.sample_duration <= 0:
            raise ValueError("sample_duration must be positive")
        if not 0.0 <= self.min_speech_ratio <= 1.0:
            raise ValueError("min_speech_ratio must be between 0.0 and 1.0")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")


@dataclass
class MultiLanguageDetectionResult:
    """Result of multi-language detection for a single audio sample.

    Returned by detect_multi_language() for each sample position.
    Used to build aggregated LanguageAnalysisResult.

    Attributes:
        position: Sample start position in seconds.
        language: Detected ISO 639-2/B language code (or None if no speech).
        confidence: Detection confidence (0.0 to 1.0).
        has_speech: Whether speech was detected in the sample.
    """

    position: float
    language: str | None
    confidence: float
    has_speech: bool = True
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate result."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@runtime_checkable
class TranscriptionPlugin(Protocol):
    """Protocol for transcription plugins.

    Plugins must implement language detection. Full transcription
    is optional and indicated via supports_feature().
    """

    @property
    def name(self) -> str:
        """Plugin identifier."""
        ...

    @property
    def version(self) -> str:
        """Plugin version string."""
        ...

    def detect_language(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> "TranscriptionResult":
        """Detect language from audio data.

        Args:
            audio_data: Raw audio bytes (WAV format, mono).
            sample_rate: Sample rate of audio data (default 16kHz).

        Returns:
            TranscriptionResult with detected_language and confidence_score.

        Raises:
            TranscriptionError: If detection fails.
        """
        ...

    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> "TranscriptionResult":
        """Full transcription with optional language hint.

        Args:
            audio_data: Raw audio bytes (WAV format, mono).
            sample_rate: Sample rate of audio data (default 16kHz).
            language: Optional language hint (ISO 639-1/639-2 code).

        Returns:
            TranscriptionResult with transcript_sample and detected_language.

        Raises:
            TranscriptionError: If transcription fails.
        """
        ...

    def supports_feature(self, feature: str) -> bool:
        """Check if plugin supports a feature.

        Args:
            feature: Feature name to check. Known features:
                - "transcription": Full transcription support
                - "gpu": GPU acceleration support
                - "multi_language_detection": Multi-language detection support
                - "acoustic_analysis": Acoustic profile extraction support

        Returns:
            True if feature is supported.
        """
        ...

    def detect_multi_language(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> MultiLanguageDetectionResult:
        """Detect language from a single audio sample for multi-language analysis.

        Unlike detect_language(), this method is designed for aggregation:
        - Returns position-aware results for building LanguageSegments
        - Reports whether speech was detected (for speech ratio calculation)
        - Designed to be called multiple times at different positions

        Args:
            audio_data: Raw audio bytes (WAV format, mono, 16kHz).
            sample_rate: Sample rate of audio data.

        Returns:
            MultiLanguageDetectionResult with position, language, and speech info.

        Raises:
            TranscriptionError: If detection fails.
        """
        ...

    def get_acoustic_profile(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> "AcousticAnalysisResult | None":
        """Extract acoustic profile for track classification.

        Optional method for plugins that support acoustic analysis.
        Use supports_feature("acoustic_analysis") to check availability.

        Extracts:
        - Speech density (ratio of speech frames to total)
        - Dynamic range (peak-to-average ratio in dB)
        - Voice count estimate (number of distinct speakers)
        - Background audio detection (film audio underneath commentary)
        - Average pause duration

        Args:
            audio_data: Raw audio bytes (WAV format, mono, 16kHz).
            sample_rate: Sample rate of audio data.

        Returns:
            AcousticAnalysisResult with profile data, or None if not supported.

        Raises:
            TranscriptionError: If analysis fails.
        """
        ...


# Import here to avoid circular import at module level
from video_policy_orchestrator.transcription.models import (  # noqa: E402
    AcousticAnalysisResult,
    TranscriptionResult,
)

__all__ = [
    "AcousticAnalysisResult",
    "MultiLanguageDetectionConfig",
    "MultiLanguageDetectionResult",
    "TranscriptionError",
    "TranscriptionPlugin",
    "TranscriptionResult",
]
