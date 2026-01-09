"""Data models for track classification.

This module contains domain models for audio track classification:
- AcousticProfile: Extracted audio characteristics for classification
- TrackClassificationResult: Complete classification result for an audio track
- Exception classes for classification errors
"""

from dataclasses import dataclass, field
from datetime import datetime

from vpo.db.types import (
    CommentaryStatus,
    DetectionMethod,
    OriginalDubbedStatus,
)


@dataclass(frozen=True)
class AcousticProfile:
    """Extracted audio characteristics for classification.

    Captures acoustic features used to classify audio tracks,
    particularly for commentary detection.

    Attributes:
        speech_density: Ratio of speech frames to total frames (0.0-1.0).
            High values (>0.7) indicate potential commentary.
        avg_pause_duration: Average silence duration in seconds.
            Commentary typically has conversational pauses.
        voice_count_estimate: Estimated number of distinct speakers.
            Commentary typically has 1-3 consistent voices.
        dynamic_range_db: Peak-to-average ratio in decibels.
            Commentary has lower dynamic range (<15 dB).
        has_background_audio: Whether film audio is detected underneath.
            Commentary often plays over the film audio.
    """

    speech_density: float
    avg_pause_duration: float
    voice_count_estimate: int
    dynamic_range_db: float
    has_background_audio: bool

    def __post_init__(self) -> None:
        """Validate field constraints."""
        if not 0.0 <= self.speech_density <= 1.0:
            raise ValueError(
                f"speech_density must be between 0.0 and 1.0, got {self.speech_density}"
            )
        if self.avg_pause_duration < 0.0:
            raise ValueError(
                f"avg_pause_duration must be non-negative, "
                f"got {self.avg_pause_duration}"
            )
        if self.voice_count_estimate < 0:
            raise ValueError(
                f"voice_count_estimate must be non-negative, "
                f"got {self.voice_count_estimate}"
            )
        if self.dynamic_range_db < 0.0:
            raise ValueError(
                f"dynamic_range_db must be non-negative, got {self.dynamic_range_db}"
            )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "speech_density": self.speech_density,
            "avg_pause_duration": self.avg_pause_duration,
            "voice_count_estimate": self.voice_count_estimate,
            "dynamic_range_db": self.dynamic_range_db,
            "has_background_audio": self.has_background_audio,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AcousticProfile":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            speech_density=data["speech_density"],
            avg_pause_duration=data["avg_pause_duration"],
            voice_count_estimate=data["voice_count_estimate"],
            dynamic_range_db=data["dynamic_range_db"],
            has_background_audio=data["has_background_audio"],
        )


@dataclass
class TrackClassificationResult:
    """Complete classification result for an audio track.

    Contains the classification determination along with confidence,
    detection method, and optional acoustic profile data.

    Attributes:
        track_id: Database ID of the classified audio track.
        file_hash: Content hash of the file for cache validation.
        original_dubbed_status: Classification as original, dubbed, or unknown.
        commentary_status: Classification as commentary, main, or unknown.
        confidence: Classification confidence score (0.0-1.0).
        detection_method: How the classification was determined.
        acoustic_profile: Acoustic analysis results (if performed).
        language: Track language (ISO 639-2) for condition matching.
        created_at: UTC timestamp when created.
        updated_at: UTC timestamp when last updated.
    """

    track_id: int
    file_hash: str
    original_dubbed_status: OriginalDubbedStatus
    commentary_status: CommentaryStatus
    confidence: float
    detection_method: DetectionMethod
    acoustic_profile: AcousticProfile | None = None
    language: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate field constraints."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


class ClassificationError(Exception):
    """Classification operation failed.

    Raised when classification cannot be completed due to an error
    in the classification process.
    """

    pass


class InsufficientDataError(ClassificationError):
    """Track has insufficient data for reliable classification.

    Raised when there is not enough data (metadata, acoustic signals)
    to perform a reliable classification of the track.
    """

    pass
