"""Core enums and constants for policy types.

This module contains fundamental enums and constants used throughout
the policy system. These have no dependencies on other policy types.
"""

from enum import Enum


class TrackType(Enum):
    """Track type classification for policy ordering."""

    VIDEO = "video"
    AUDIO_MAIN = "audio_main"
    AUDIO_ALTERNATE = "audio_alternate"
    AUDIO_COMMENTARY = "audio_commentary"
    AUDIO_MUSIC = "audio_music"  # Music score, soundtrack (metadata-identified)
    AUDIO_SFX = "audio_sfx"  # Sound effects, ambient (metadata-identified)
    AUDIO_NON_SPEECH = "audio_non_speech"  # Unlabeled track detected as no speech
    SUBTITLE_MAIN = "subtitle_main"
    SUBTITLE_FORCED = "subtitle_forced"
    SUBTITLE_COMMENTARY = "subtitle_commentary"
    ATTACHMENT = "attachment"


class ActionType(Enum):
    """Types of changes that can be planned."""

    REORDER = "reorder"  # Change track positions
    SET_DEFAULT = "set_default"  # Set default flag to true
    CLEAR_DEFAULT = "clear_default"  # Set default flag to false
    SET_FORCED = "set_forced"  # Set forced flag to true
    CLEAR_FORCED = "clear_forced"  # Set forced flag to false
    SET_TITLE = "set_title"  # Change track title
    SET_LANGUAGE = "set_language"  # Change language tag
    TRANSCODE = "transcode"  # Transcode video/audio
    MOVE = "move"  # Move file to new location


class OperationType(Enum):
    """Types of operations that can appear in a phase.

    Operations within a phase execute in canonical order (as defined below).
    This ordering ensures dependencies are respected (e.g., filters run
    before track_order, synthesis runs before transcode).
    """

    CONTAINER = "container"
    AUDIO_FILTER = "audio_filter"
    SUBTITLE_FILTER = "subtitle_filter"
    ATTACHMENT_FILTER = "attachment_filter"
    TRACK_ORDER = "track_order"
    DEFAULT_FLAGS = "default_flags"
    CONDITIONAL = "conditional"
    AUDIO_SYNTHESIS = "audio_synthesis"
    TRANSCODE = "transcode"
    FILE_TIMESTAMP = "file_timestamp"
    TRANSCRIPTION = "transcription"


# Canonical execution order for operations within a phase
# This tuple defines the order in which operations are dispatched
CANONICAL_OPERATION_ORDER: tuple[OperationType, ...] = (
    OperationType.CONTAINER,
    OperationType.AUDIO_FILTER,
    OperationType.SUBTITLE_FILTER,
    OperationType.ATTACHMENT_FILTER,
    OperationType.TRACK_ORDER,
    OperationType.DEFAULT_FLAGS,
    OperationType.CONDITIONAL,
    OperationType.AUDIO_SYNTHESIS,
    OperationType.TRANSCODE,
    OperationType.FILE_TIMESTAMP,
    OperationType.TRANSCRIPTION,
)


class OnErrorMode(Enum):
    """How to handle errors during phase execution.

    Controls behavior when an operation or phase fails.
    """

    SKIP = "skip"  # Stop processing this file, continue batch
    CONTINUE = "continue"  # Log error, continue to next phase
    FAIL = "fail"  # Stop entire batch processing


class PhaseOutcome(Enum):
    """Outcome of a phase after execution or skip evaluation.

    Used for dependency resolution and workflow tracking.
    """

    PENDING = "pending"  # Not yet evaluated (initial state)
    COMPLETED = "completed"  # Phase executed successfully
    FAILED = "failed"  # Phase executed but encountered an error
    SKIPPED = "skipped"  # Phase was skipped (condition, dependency, or error mode)


class SkipReasonType(Enum):
    """Types of reasons a phase can be skipped.

    Used in SkipReason to categorize why a phase was skipped.
    """

    CONDITION = "condition"  # skip_when condition matched
    DEPENDENCY = "dependency"  # Dependency phase did not complete
    ERROR_MODE = "error_mode"  # Skipped due to on_error: skip after failure
    RUN_IF = "run_if"  # run_if condition not satisfied


# Default track order matching the policy schema
DEFAULT_TRACK_ORDER: tuple[TrackType, ...] = (
    TrackType.VIDEO,
    TrackType.AUDIO_MAIN,
    TrackType.AUDIO_ALTERNATE,
    TrackType.AUDIO_MUSIC,
    TrackType.AUDIO_SFX,
    TrackType.AUDIO_NON_SPEECH,
    TrackType.SUBTITLE_MAIN,
    TrackType.SUBTITLE_FORCED,
    TrackType.AUDIO_COMMENTARY,
    TrackType.SUBTITLE_COMMENTARY,
    TrackType.ATTACHMENT,
)

# Valid video codecs for transcoding
VALID_VIDEO_CODECS = frozenset({"h264", "hevc", "vp9", "av1"})

# Codecs that are incompatible with MP4 container
# These codecs cannot be stored in MP4 without transcoding
MP4_INCOMPATIBLE_CODECS = frozenset(
    {
        # Lossless audio codecs
        "truehd",
        "dts-hd ma",
        "dts-hd.ma",
        "dtshd",
        "mlp",
        # Subtitle formats not supported in MP4
        "hdmv_pgs_subtitle",
        "pgssub",
        "pgs",
        "dvd_subtitle",
        "dvdsub",
        "vobsub",
        # Advanced subtitle formats
        "ass",
        "ssa",
        "subrip",  # SRT needs conversion to mov_text
        # Attachment types (not supported in MP4)
        "ttf",
        "otf",
        "application/x-truetype-font",
    }
)

# Valid audio codecs for transcoding
VALID_AUDIO_CODECS = frozenset(
    {
        "aac",
        "ac3",
        "eac3",
        "flac",
        "opus",
        "mp3",
        "truehd",
        "dts",
        "pcm_s16le",
        "pcm_s24le",
    }
)

# Valid resolution presets
VALID_RESOLUTIONS = frozenset({"480p", "720p", "1080p", "1440p", "4k", "8k"})

# Resolution to max dimension mapping
RESOLUTION_MAP = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
    "8k": (7680, 4320),
}
