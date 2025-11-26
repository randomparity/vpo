"""Policy engine data models.

This module defines dataclasses for policy configuration and execution plans.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class TrackType(Enum):
    """Track type classification for policy ordering."""

    VIDEO = "video"
    AUDIO_MAIN = "audio_main"
    AUDIO_ALTERNATE = "audio_alternate"
    AUDIO_COMMENTARY = "audio_commentary"
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


@dataclass(frozen=True)
class AudioPreservationRule:
    """Rule for handling a specific audio codec.

    Used to define fine-grained control over audio codec handling
    beyond the simple preserve/transcode list.
    """

    codec_pattern: str  # Codec name or pattern (e.g., "truehd", "dts*")
    action: str  # "preserve", "transcode", "remove"
    transcode_to: str | None = None  # Target codec if action=transcode
    transcode_bitrate: str | None = None  # Target bitrate if action=transcode

    def __post_init__(self) -> None:
        """Validate the rule configuration."""
        valid_actions = ("preserve", "transcode", "remove")
        if self.action not in valid_actions:
            raise ValueError(
                f"Invalid action: {self.action}. "
                f"Must be one of: {', '.join(valid_actions)}"
            )
        if self.action == "transcode" and not self.transcode_to:
            raise ValueError("transcode_to is required when action is 'transcode'")


@dataclass(frozen=True)
class TranscriptionPolicyOptions:
    """Policy options for transcription-based operations.

    Controls automatic language detection and updates via transcription analysis.
    """

    enabled: bool = False  # Enable transcription analysis during policy application
    update_language_from_transcription: bool = False  # Update track language tags
    confidence_threshold: float = 0.8  # Min confidence for updates (0.0-1.0)
    detect_commentary: bool = False  # Enable commentary detection
    reorder_commentary: bool = False  # Move commentary tracks to end

    def __post_init__(self) -> None:
        """Validate transcription policy options."""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be between 0.0 and 1.0, "
                f"got {self.confidence_threshold}"
            )
        if self.reorder_commentary and not self.detect_commentary:
            raise ValueError("reorder_commentary requires detect_commentary to be true")


@dataclass(frozen=True)
class DefaultFlagsConfig:
    """Configuration for default flag behavior in a policy."""

    set_first_video_default: bool = True
    set_preferred_audio_default: bool = True
    set_preferred_subtitle_default: bool = False
    clear_other_defaults: bool = True


@dataclass(frozen=True)
class TranscodePolicyConfig:
    """Transcoding-specific policy configuration."""

    # Video settings
    target_video_codec: str | None = None  # hevc, h264, vp9, av1
    target_crf: int | None = None  # 0-51 for x264/x265
    target_bitrate: str | None = None  # e.g., "5M", "2500k"
    max_resolution: str | None = None  # 1080p, 720p, 4k, etc.
    max_width: int | None = None  # Max width in pixels
    max_height: int | None = None  # Max height in pixels

    # Audio preservation
    audio_preserve_codecs: tuple[str, ...] = ()  # Codecs to stream copy
    audio_transcode_to: str = "aac"  # Target codec for non-preserved
    audio_transcode_bitrate: str = "192k"  # Bitrate for transcoded audio
    audio_downmix: str | None = None  # None, "stereo", "5.1"

    # Destination
    destination: str | None = None  # Template string for output location
    destination_fallback: str = "Unknown"  # Fallback for missing metadata

    def __post_init__(self) -> None:
        """Validate transcode policy configuration."""
        if self.target_video_codec is not None:
            codec = self.target_video_codec.lower()
            if codec not in VALID_VIDEO_CODECS:
                raise ValueError(
                    f"Invalid target_video_codec: {self.target_video_codec}. "
                    f"Must be one of: {', '.join(sorted(VALID_VIDEO_CODECS))}"
                )

        if self.target_crf is not None:
            if not 0 <= self.target_crf <= 51:
                raise ValueError(
                    f"Invalid target_crf: {self.target_crf}. Must be 0-51."
                )

        if self.max_resolution is not None:
            if self.max_resolution.lower() not in VALID_RESOLUTIONS:
                raise ValueError(
                    f"Invalid max_resolution: {self.max_resolution}. "
                    f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
                )

        if self.audio_transcode_to.lower() not in VALID_AUDIO_CODECS:
            raise ValueError(
                f"Invalid audio_transcode_to: {self.audio_transcode_to}. "
                f"Must be one of: {', '.join(sorted(VALID_AUDIO_CODECS))}"
            )

        if self.audio_downmix is not None:
            if self.audio_downmix not in ("stereo", "5.1"):
                raise ValueError(
                    f"Invalid audio_downmix: {self.audio_downmix}. "
                    "Must be 'stereo' or '5.1'."
                )

    @property
    def has_video_settings(self) -> bool:
        """True if any video transcoding settings are specified."""
        return any(
            [
                self.target_video_codec,
                self.target_crf,
                self.target_bitrate,
                self.max_resolution,
                self.max_width,
                self.max_height,
            ]
        )

    @property
    def has_audio_settings(self) -> bool:
        """True if audio processing settings are specified."""
        return bool(self.audio_preserve_codecs) or self.audio_downmix is not None

    def get_max_dimensions(self) -> tuple[int, int] | None:
        """Get max dimensions from resolution preset or explicit values.

        Returns:
            (max_width, max_height) tuple or None if no limit.
        """
        if self.max_resolution:
            return RESOLUTION_MAP.get(self.max_resolution.lower())
        if self.max_width or self.max_height:
            return (self.max_width or 99999, self.max_height or 99999)
        return None


# Default track order matching the policy schema
DEFAULT_TRACK_ORDER: tuple[TrackType, ...] = (
    TrackType.VIDEO,
    TrackType.AUDIO_MAIN,
    TrackType.AUDIO_ALTERNATE,
    TrackType.SUBTITLE_MAIN,
    TrackType.SUBTITLE_FORCED,
    TrackType.AUDIO_COMMENTARY,
    TrackType.SUBTITLE_COMMENTARY,
    TrackType.ATTACHMENT,
)


@dataclass(frozen=True)
class PolicySchema:
    """Validated policy configuration loaded from YAML.

    This is an immutable representation of a policy file.
    """

    schema_version: int
    track_order: tuple[TrackType, ...] = DEFAULT_TRACK_ORDER
    audio_language_preference: tuple[str, ...] = ("eng", "und")
    subtitle_language_preference: tuple[str, ...] = ("eng", "und")
    commentary_patterns: tuple[str, ...] = ("commentary", "director")
    default_flags: DefaultFlagsConfig = field(default_factory=DefaultFlagsConfig)
    transcode: TranscodePolicyConfig | None = None
    transcription: TranscriptionPolicyOptions | None = None

    def __post_init__(self) -> None:
        """Validate policy schema after initialization."""
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1")
        if not self.track_order:
            raise ValueError("track_order cannot be empty")
        if not self.audio_language_preference:
            raise ValueError("audio_language_preference cannot be empty")
        if not self.subtitle_language_preference:
            raise ValueError("subtitle_language_preference cannot be empty")

    @property
    def has_transcode_settings(self) -> bool:
        """True if transcode settings are specified."""
        return self.transcode is not None

    @property
    def has_transcription_settings(self) -> bool:
        """True if transcription settings are specified and enabled."""
        return self.transcription is not None and self.transcription.enabled


@dataclass(frozen=True)
class PlannedAction:
    """A single planned change. Immutable."""

    action_type: ActionType
    track_index: int | None  # None for REORDER (file-level action)
    current_value: Any
    desired_value: Any
    track_id: str | None = None  # Track UID if available

    @property
    def description(self) -> str:
        """Human-readable description of this action."""
        if self.action_type == ActionType.REORDER:
            return f"Reorder: {self.current_value} → {self.desired_value}"
        elif self.action_type == ActionType.SET_DEFAULT:
            return f"Track {self.track_index}: Set as default"
        elif self.action_type == ActionType.CLEAR_DEFAULT:
            return f"Track {self.track_index}: Clear default flag"
        elif self.action_type == ActionType.SET_FORCED:
            return f"Track {self.track_index}: Set as forced"
        elif self.action_type == ActionType.CLEAR_FORCED:
            return f"Track {self.track_index}: Clear forced flag"
        elif self.action_type == ActionType.SET_TITLE:
            return f"Track {self.track_index}: Set title '{self.desired_value}'"
        elif self.action_type == ActionType.SET_LANGUAGE:
            return f"Track {self.track_index}: Set language '{self.desired_value}'"
        else:
            return f"Track {self.track_index}: {self.action_type.value}"


@dataclass(frozen=True)
class Plan:
    """Immutable execution plan produced by policy evaluation."""

    file_id: str
    file_path: Path
    policy_version: int
    actions: tuple[PlannedAction, ...]
    requires_remux: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_empty(self) -> bool:
        """True if no actions needed."""
        return len(self.actions) == 0

    @property
    def summary(self) -> str:
        """Human-readable summary of changes."""
        if self.is_empty:
            return "No changes required"

        action_count = len(self.actions)
        remux_note = " (requires remux)" if self.requires_remux else ""
        return f"{action_count} change{'s' if action_count != 1 else ''}{remux_note}"
