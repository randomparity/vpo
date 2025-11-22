"""Interface definitions for transcription plugins."""

from typing import Protocol, runtime_checkable


class TranscriptionError(Exception):
    """Base exception for transcription-related errors."""

    pass


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

        Returns:
            True if feature is supported.
        """
        ...


# Import here to avoid circular import at module level
from video_policy_orchestrator.transcription.models import (  # noqa: E402
    TranscriptionResult,
)

__all__ = ["TranscriptionError", "TranscriptionPlugin", "TranscriptionResult"]
