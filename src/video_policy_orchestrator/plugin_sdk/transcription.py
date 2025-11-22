"""SDK helpers for transcription plugin authors.

This module provides base classes and utilities to help plugin authors
create transcription plugins for VPO.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from video_policy_orchestrator.transcription.interface import (
    TranscriptionError,
    TranscriptionPlugin,
)
from video_policy_orchestrator.transcription.models import (
    TrackClassification,
    TranscriptionResult,
)


class TranscriptionPluginBase(ABC):
    """Abstract base class for transcription plugins.

    Provides a convenient base for implementing the TranscriptionPlugin
    protocol with sensible defaults and helper methods.

    Example:
        class MyTranscriptionPlugin(TranscriptionPluginBase):
            def __init__(self):
                super().__init__(
                    name="my-plugin",
                    version="1.0.0",
                    supported_features={"language_detection", "transcription"},
                )

            def detect_language(self, audio_data, sample_rate=16000):
                # Your implementation here
                pass

            def transcribe(self, audio_data, sample_rate=16000, language=None):
                # Your implementation here
                pass
    """

    def __init__(
        self,
        name: str,
        version: str,
        supported_features: set[str] | None = None,
    ) -> None:
        """Initialize the plugin base.

        Args:
            name: Unique plugin identifier.
            version: Plugin version string (e.g., "1.0.0").
            supported_features: Set of supported feature names.
                Common features: "language_detection", "transcription", "gpu"
        """
        self._name = name
        self._version = version
        self._supported_features = supported_features or {"language_detection"}

    @property
    def name(self) -> str:
        """Plugin identifier."""
        return self._name

    @property
    def version(self) -> str:
        """Plugin version string."""
        return self._version

    @abstractmethod
    def detect_language(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """Detect language from audio data.

        Subclasses must implement this method.

        Args:
            audio_data: Raw audio bytes (WAV format, mono).
            sample_rate: Sample rate of audio data (default 16kHz).

        Returns:
            TranscriptionResult with detected_language and confidence_score.

        Raises:
            TranscriptionError: If detection fails.
        """
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Full transcription with optional language hint.

        Subclasses must implement this method.

        Args:
            audio_data: Raw audio bytes (WAV format, mono).
            sample_rate: Sample rate of audio data (default 16kHz).
            language: Optional language hint (ISO 639-1/639-2 code).

        Returns:
            TranscriptionResult with transcript_sample and detected_language.

        Raises:
            TranscriptionError: If transcription fails.
        """
        pass

    def supports_feature(self, feature: str) -> bool:
        """Check if plugin supports a feature.

        Args:
            feature: Feature name to check.

        Returns:
            True if feature is supported.
        """
        return feature in self._supported_features

    def create_result(
        self,
        *,
        detected_language: str | None = None,
        confidence_score: float,
        track_type: TrackClassification = TrackClassification.MAIN,
        transcript_sample: str | None = None,
    ) -> TranscriptionResult:
        """Helper to create a TranscriptionResult.

        Creates a properly formatted result with current timestamps
        and plugin name automatically filled in.

        Args:
            detected_language: ISO language code (e.g., "en", "fr").
            confidence_score: Confidence level 0.0-1.0.
            track_type: Classification of the track.
            transcript_sample: Optional transcript excerpt.

        Returns:
            TranscriptionResult ready for storage.
        """
        now = datetime.now(timezone.utc)
        return TranscriptionResult(
            track_id=0,  # Caller will set this
            detected_language=detected_language,
            confidence_score=confidence_score,
            track_type=track_type,
            transcript_sample=transcript_sample,
            plugin_name=self.name,
            created_at=now,
            updated_at=now,
        )


# Re-export common types for plugin authors
__all__ = [
    "TrackClassification",
    "TranscriptionError",
    "TranscriptionPlugin",
    "TranscriptionPluginBase",
    "TranscriptionResult",
]
