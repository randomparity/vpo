"""Data models for transcription module."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TrackClassification(Enum):
    """Classification of audio track purpose.

    Detection priority:
    1. MUSIC/SFX: Identified by metadata keywords (title)
    2. NON_SPEECH: Detected via transcription analysis (no speech/low confidence)
    3. COMMENTARY: Identified by metadata keywords or transcript content
    4. ALTERNATE: Identified as non-main dialog track
    5. MAIN: Default for dialog tracks
    """

    MAIN = "main"  # Primary audio track with dialog
    COMMENTARY = "commentary"  # Director/cast commentary
    ALTERNATE = "alternate"  # Alternate mix with dialog
    MUSIC = "music"  # Score, soundtrack (metadata-identified)
    SFX = "sfx"  # Sound effects, ambient (metadata-identified)
    NON_SPEECH = "non_speech"  # Unlabeled track detected as no speech


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
    sample_duration: int = 30  # Seconds to sample (0 = full track)
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
    "composer",
]

# Keywords for music track detection (metadata-based)
MUSIC_KEYWORDS = [
    "music",
    "score",
    "soundtrack",
    "isolated score",
    "m&e",
    "music and effects",
    "ost",
    "theme",
    "instrumental",
    "orchestra",
    "songs only",
]

# Keywords for SFX track detection (metadata-based)
SFX_KEYWORDS = [
    "sfx",
    "sound effects",
    "effects only",
    "ambient",
    "foley",
    "environmental",
    "sounds only",
    "effects",
    "atmosphere",
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

# Hallucination patterns - Whisper outputs these on silence/music
# These indicate the transcription is not meaningful speech
HALLUCINATION_PATTERNS = [
    r"thank you for (watching|listening)",
    r"please subscribe",
    r"please like and subscribe",
    r"don't forget to subscribe",
    r"see you (in the )?next (video|time)",
    r"^\s*\[?(music|applause|silence|laughter|sigh|sighing)\]?\s*$",
    r"^\s*♪+\s*$",  # Music note symbols
    r"^\s*\.+\s*$",  # Just dots/ellipsis
    r"^\s*$",  # Empty string
]

# Threshold values for music/non-speech detection
MUSIC_CONFIDENCE_CEILING = 0.4  # Whisper returns ~0.3-0.4 on music
SPEECH_RATIO_THRESHOLD = 0.15  # Below this = no meaningful speech
TRANSCRIPT_MIN_LENGTH = 10  # Filter out very short hallucinations


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


def is_music_by_metadata(title: str | None) -> bool:
    """Check if track title suggests music track based on keywords.

    Args:
        title: Track title to check.

    Returns:
        True if title matches any music keyword.
    """
    if not title:
        return False

    title_lower = title.lower()
    return any(keyword in title_lower for keyword in MUSIC_KEYWORDS)


def is_sfx_by_metadata(title: str | None) -> bool:
    """Check if track title suggests SFX track based on keywords.

    Args:
        title: Track title to check.

    Returns:
        True if title matches any SFX keyword.
    """
    if not title:
        return False

    title_lower = title.lower()
    # Check for SFX keywords, but avoid false positives
    # "effects" alone is too broad - require "sound effects" or "effects only"
    for keyword in SFX_KEYWORDS:
        if keyword in title_lower:
            # Special case: "effects" alone could be visual effects
            if keyword == "effects" and "sound" not in title_lower:
                continue
            return True
    return False


def is_hallucination(transcript_sample: str | None) -> bool:
    """Check if transcript appears to be a Whisper hallucination.

    Whisper produces characteristic output when transcribing non-speech
    audio (music, silence, ambient sounds). Common hallucinations include
    YouTube-style outros and single-word descriptions in brackets.

    Args:
        transcript_sample: Transcript text to check.

    Returns:
        True if transcript matches hallucination patterns.
    """
    import re

    if not transcript_sample:
        return True  # Empty transcript = likely no speech

    # Very short transcripts are suspicious
    if len(transcript_sample.strip()) < TRANSCRIPT_MIN_LENGTH:
        return True

    sample_lower = transcript_sample.lower().strip()

    for pattern in HALLUCINATION_PATTERNS:
        if re.search(pattern, sample_lower, re.IGNORECASE):
            return True

    return False


def detect_commentary_type(
    title: str | None,
    transcript_sample: str | None,
) -> TrackClassification:
    """Detect track classification using metadata and transcript analysis.

    DEPRECATED: Use detect_track_classification() instead for full support
    of music, sfx, and non-speech track types.

    Uses a two-stage detection approach:
    1. Metadata-based: Check track title for commentary keywords
    2. Transcript-based: Analyze transcript sample for commentary patterns

    Args:
        title: Track title (metadata).
        transcript_sample: Optional transcript text sample.

    Returns:
        TrackClassification (MAIN, COMMENTARY, or ALTERNATE).
    """
    # Delegate to the full detection function with default parameters
    return detect_track_classification(
        title=title,
        transcript_sample=transcript_sample,
        has_speech=True,
        confidence=1.0,
    )


def detect_track_classification(
    title: str | None,
    transcript_sample: str | None,
    has_speech: bool = True,
    confidence: float = 1.0,
) -> TrackClassification:
    """Detect track type using combined signals.

    Detection priority:
    1. Metadata keywords (most reliable - SFX/MUSIC/COMMENTARY)
    2. Speech detection + confidence (for unlabeled tracks)
    3. Transcript analysis (for commentary detection)

    Args:
        title: Track title (metadata).
        transcript_sample: Optional transcript text sample.
        has_speech: Whether VAD detected speech in the track.
        confidence: Transcription confidence score (0.0-1.0).

    Returns:
        TrackClassification enum value.
    """
    import re

    # Stage 1: Metadata-based detection (most reliable)
    # Check SFX first - more specific than music
    if is_sfx_by_metadata(title):
        return TrackClassification.SFX

    # Check music keywords
    if is_music_by_metadata(title):
        return TrackClassification.MUSIC

    # Check commentary keywords
    if is_commentary_by_metadata(title):
        return TrackClassification.COMMENTARY

    # Stage 2: No-speech detection (unlabeled non-speech tracks)
    # Low confidence + hallucination pattern = likely non-speech
    if not has_speech or (
        confidence < MUSIC_CONFIDENCE_CEILING and is_hallucination(transcript_sample)
    ):
        return TrackClassification.NON_SPEECH

    # Stage 3: Transcript-based commentary detection
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

    # Default: Main audio track (has speech)
    return TrackClassification.MAIN
