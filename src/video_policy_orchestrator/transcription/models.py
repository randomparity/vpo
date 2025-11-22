"""Data models for transcription module."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TrackClassification(Enum):
    """Classification of audio track purpose."""

    MAIN = "main"  # Primary audio track
    COMMENTARY = "commentary"  # Director/cast commentary
    ALTERNATE = "alternate"  # Alternate mix, isolated score, etc.


@dataclass
class TranscriptionResult:
    """Result of transcription analysis for a single audio track."""

    track_id: int
    detected_language: str | None
    confidence_score: float
    track_type: TrackClassification
    transcript_sample: str | None
    plugin_name: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, "
                f"got {self.confidence_score}"
            )
        if not self.plugin_name:
            raise ValueError("plugin_name must be non-empty")

    @classmethod
    def from_record(cls, record: "TranscriptionResultRecord") -> "TranscriptionResult":
        """Create domain model from database record.

        Args:
            record: Database record to convert.

        Returns:
            TranscriptionResult domain model.
        """
        return cls(
            track_id=record.track_id,
            detected_language=record.detected_language,
            confidence_score=record.confidence_score,
            track_type=TrackClassification(record.track_type),
            transcript_sample=record.transcript_sample,
            plugin_name=record.plugin_name,
            created_at=datetime.fromisoformat(record.created_at),
            updated_at=datetime.fromisoformat(record.updated_at),
        )


# Import at bottom to avoid circular import
from video_policy_orchestrator.db.models import (  # noqa: E402
    TranscriptionResultRecord,
)


@dataclass
class TranscriptionConfig:
    """User configuration for transcription behavior."""

    enabled_plugin: str | None = None  # Plugin to use (None = auto-detect)
    model_size: str = "base"  # Whisper model: tiny, base, small, medium, large
    sample_duration: int = 60  # Seconds to sample (0 = full track)
    gpu_enabled: bool = True  # Use GPU if available

    def __post_init__(self) -> None:
        """Validate configuration."""
        valid_model_sizes = {"tiny", "base", "small", "medium", "large"}
        if self.model_size not in valid_model_sizes:
            raise ValueError(
                f"model_size must be one of {valid_model_sizes}, got {self.model_size}"
            )
        if self.sample_duration < 0:
            raise ValueError(
                f"sample_duration must be non-negative, got {self.sample_duration}"
            )


# Keywords for commentary detection (metadata-based)
COMMENTARY_KEYWORDS = [
    "commentary",
    "director",
    "cast",
    "crew",
    "behind the scenes",
    "making of",
    "bts",
    "isolated",
    "alternate",
    "composer",
]

# Patterns for transcript-based commentary detection
COMMENTARY_TRANSCRIPT_PATTERNS = [
    # Director/cast commentary phrases
    r"\bthis scene\b.*\bwe\b",
    r"\bwhen we (shot|filmed|made)\b",
    r"\bI (remember|think|wanted)\b",
    r"\bthe (actor|actress|director)\b",
    r"\bon set\b",
    r"\bthe script\b",
    r"\bthe original\b.*\bversion\b",
    # Interview-style patterns
    r"\bwhat (made|inspired)\b.*\byou\b",
    r"\btell us about\b",
]


def is_commentary_by_metadata(title: str | None) -> bool:
    """Check if track title suggests commentary based on keywords.

    Args:
        title: Track title to check.

    Returns:
        True if title matches any commentary keyword.
    """
    if not title:
        return False

    title_lower = title.lower()
    return any(keyword in title_lower for keyword in COMMENTARY_KEYWORDS)


def detect_commentary_type(
    title: str | None,
    transcript_sample: str | None,
) -> TrackClassification:
    """Detect track classification using metadata and transcript analysis.

    Uses a two-stage detection approach:
    1. Metadata-based: Check track title for commentary keywords
    2. Transcript-based: Analyze transcript sample for commentary patterns

    Args:
        title: Track title (metadata).
        transcript_sample: Optional transcript text sample.

    Returns:
        TrackClassification (MAIN, COMMENTARY, or ALTERNATE).
    """
    import re

    # Stage 1: Metadata-based detection
    if is_commentary_by_metadata(title):
        return TrackClassification.COMMENTARY

    # Stage 2: Transcript-based detection (if sample available)
    if transcript_sample:
        sample_lower = transcript_sample.lower()

        # Count matches against commentary patterns
        match_count = 0
        for pattern in COMMENTARY_TRANSCRIPT_PATTERNS:
            if re.search(pattern, sample_lower, re.IGNORECASE):
                match_count += 1

        # If 2+ patterns match, likely commentary
        if match_count >= 2:
            return TrackClassification.COMMENTARY

    # Default: Main audio track
    return TrackClassification.MAIN
