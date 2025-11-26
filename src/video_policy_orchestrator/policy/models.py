"""Policy engine data models.

This module defines dataclasses for policy configuration and execution plans.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal


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


# =============================================================================
# V3 Track Filtering Configuration Models
# =============================================================================


@dataclass(frozen=True)
class LanguageFallbackConfig:
    """Configuration for fallback when preferred languages aren't found.

    This controls what happens when track filtering would remove all tracks
    because none match the preferred languages.
    """

    mode: Literal["content_language", "keep_all", "keep_first", "error"]
    """Fallback mode:
    - content_language: Keep tracks matching the content's original language
    - keep_all: Keep all tracks (disable filtering)
    - keep_first: Keep first N tracks to meet minimum
    - error: Fail with InsufficientTracksError
    """


@dataclass(frozen=True)
class AudioFilterConfig:
    """Configuration for filtering audio tracks.

    Audio filtering removes tracks whose language doesn't match the preferred
    languages list. A minimum of 1 audio track is always enforced to prevent
    creating audio-less files.
    """

    languages: tuple[str, ...]
    """ISO 639-2/B language codes to keep (e.g., ('eng', 'und', 'jpn')).
    Tracks with languages not in this list will be removed."""

    fallback: LanguageFallbackConfig | None = None
    """Fallback behavior when no tracks match preferred languages."""

    minimum: int = 1
    """Minimum number of audio tracks that must remain.
    If filtering would leave fewer tracks, fallback is triggered."""

    def __post_init__(self) -> None:
        """Validate audio filter configuration."""
        if not self.languages:
            raise ValueError("languages cannot be empty")
        if self.minimum < 1:
            raise ValueError("minimum must be at least 1 for audio tracks")


@dataclass(frozen=True)
class SubtitleFilterConfig:
    """Configuration for filtering subtitle tracks.

    Subtitle filtering can remove tracks by language, remove all subtitles,
    or preserve forced subtitles regardless of language.
    """

    languages: tuple[str, ...] | None = None
    """ISO 639-2/B language codes to keep. If None, no language filtering."""

    preserve_forced: bool = False
    """If True, forced subtitle tracks are preserved regardless of language."""

    remove_all: bool = False
    """If True, remove all subtitle tracks. Overrides other settings."""


@dataclass(frozen=True)
class AttachmentFilterConfig:
    """Configuration for filtering attachment tracks.

    Attachments typically include fonts (for styled subtitles) and cover art.
    Removing fonts may affect rendering of ASS/SSA subtitles.
    """

    remove_all: bool = False
    """If True, remove all attachment tracks (fonts, cover art, etc.)."""


@dataclass(frozen=True)
class ContainerConfig:
    """Configuration for container format conversion.

    Container conversion performs lossless remuxing to the target format.
    Some codecs may be incompatible with certain containers.
    """

    target: Literal["mkv", "mp4"]
    """Target container format."""

    on_incompatible_codec: Literal["error", "skip", "transcode"] = "error"
    """Behavior when source contains codecs incompatible with target:
    - error: Fail with IncompatibleCodecError listing problematic tracks
    - skip: Skip the entire file with a warning
    - transcode: Transcode incompatible tracks (requires transcode config)
    """


# =============================================================================
# V3 Plan Extension Models
# =============================================================================


@dataclass(frozen=True)
class TrackDisposition:
    """Disposition of a track in the filtering plan.

    Represents the planned action for a single track, including whether it
    will be kept or removed and the reason for that decision.
    """

    track_index: int
    """0-based global track index in source file."""

    track_type: str
    """Track type: 'video', 'audio', 'subtitle', 'attachment'."""

    codec: str | None
    """Codec name (e.g., 'hevc', 'aac', 'subrip')."""

    language: str | None
    """ISO 639-2/B language code or None if untagged."""

    title: str | None
    """Track title if present."""

    channels: int | None
    """Audio channels (audio tracks only)."""

    resolution: str | None
    """Resolution string like '1920x1080' (video tracks only)."""

    action: Literal["KEEP", "REMOVE"]
    """Whether the track will be kept or removed."""

    reason: str
    """Human-readable reason for the action."""


@dataclass(frozen=True)
class ContainerChange:
    """Planned container format conversion.

    Represents a container format change from the source format to the
    target format, including any warnings about the conversion.
    """

    source_format: str
    """Source container format (e.g., 'mkv', 'avi', 'mp4')."""

    target_format: str
    """Target container format (e.g., 'mkv', 'mp4')."""

    warnings: tuple[str, ...]
    """Warnings about the conversion (e.g., subtitle format limitations)."""

    incompatible_tracks: tuple[int, ...]
    """Track indices that are incompatible with target format."""


# =============================================================================
# Core Policy Schema and Plan Models
# =============================================================================


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

    # V3 fields (all optional for backward compatibility)
    audio_filter: AudioFilterConfig | None = None
    """Audio track filtering configuration. Requires schema_version >= 3."""

    subtitle_filter: SubtitleFilterConfig | None = None
    """Subtitle track filtering configuration. Requires schema_version >= 3."""

    attachment_filter: AttachmentFilterConfig | None = None
    """Attachment track filtering configuration. Requires schema_version >= 3."""

    container: ContainerConfig | None = None
    """Container format conversion configuration. Requires schema_version >= 3."""

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

    @property
    def has_track_filtering(self) -> bool:
        """True if any track filtering is configured."""
        return any(
            [
                self.audio_filter is not None,
                self.subtitle_filter is not None,
                self.attachment_filter is not None,
            ]
        )

    @property
    def has_container_config(self) -> bool:
        """True if container conversion is configured."""
        return self.container is not None


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

    # V3 fields for track filtering
    track_dispositions: tuple[TrackDisposition, ...] = ()
    """Detailed disposition for each track in the source file."""

    container_change: ContainerChange | None = None
    """Container conversion details if applicable."""

    tracks_removed: int = 0
    """Count of tracks being removed."""

    tracks_kept: int = 0
    """Count of tracks being kept."""

    @property
    def is_empty(self) -> bool:
        """True if no actions needed."""
        # Check both traditional actions and v3 track dispositions
        has_removals = self.tracks_removed > 0
        has_container_change = self.container_change is not None
        return len(self.actions) == 0 and not has_removals and not has_container_change

    @property
    def summary(self) -> str:
        """Human-readable summary of changes."""
        if self.is_empty:
            return "No changes required"

        parts = []

        # Traditional actions
        action_count = len(self.actions)
        if action_count > 0:
            parts.append(f"{action_count} change{'s' if action_count != 1 else ''}")

        # Track filtering summary
        if self.tracks_removed > 0:
            plural = "s" if self.tracks_removed != 1 else ""
            parts.append(f"{self.tracks_removed} track{plural} removed")

        # Container change
        if self.container_change:
            src = self.container_change.source_format
            tgt = self.container_change.target_format
            parts.append(f"convert {src} → {tgt}")

        summary = ", ".join(parts)
        remux_note = " (requires remux)" if self.requires_remux else ""
        return f"{summary}{remux_note}"
