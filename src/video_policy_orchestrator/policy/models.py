"""Policy engine data models.

This module defines dataclasses for policy configuration and execution plans.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Union


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


class ProcessingPhase(Enum):
    """Workflow processing phases for video file operations.

    NOTE: This enum is used for V9/V10 policies with fixed phase names.
    For V11+ policies, phases are user-defined strings. See PhaseDefinition.
    """

    ANALYZE = "analyze"  # Language detection via transcription
    APPLY = "apply"  # Track ordering, filtering, metadata, container
    TRANSCODE = "transcode"  # Video/audio codec conversion


# =============================================================================
# V11 User-Defined Phases
# =============================================================================


class OperationType(Enum):
    """Types of operations that can appear in a V11 phase.

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
    OperationType.TRANSCRIPTION,
)


class OnErrorMode(Enum):
    """How to handle errors during phase execution (V11+).

    Controls behavior when an operation or phase fails.
    """

    SKIP = "skip"  # Stop processing this file, continue batch
    CONTINUE = "continue"  # Log error, continue to next phase
    FAIL = "fail"  # Stop entire batch processing


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
    set_subtitle_default_when_audio_differs: bool = False


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscodePolicyConfig":
        """Create TranscodePolicyConfig from a dictionary.

        Args:
            data: Dictionary with policy configuration. Keys match dataclass fields.
                  Supports both 'audio_transcode_bitrate' and legacy 'audio_bitrate'.

        Returns:
            TranscodePolicyConfig instance.

        Raises:
            ValueError: If validation fails on any field.
        """
        return cls(
            target_video_codec=data.get("target_video_codec"),
            target_crf=data.get("target_crf"),
            target_bitrate=data.get("target_bitrate"),
            max_resolution=data.get("max_resolution"),
            max_width=data.get("max_width"),
            max_height=data.get("max_height"),
            audio_preserve_codecs=tuple(data.get("audio_preserve_codecs", [])),
            audio_transcode_to=data.get("audio_transcode_to", "aac"),
            audio_transcode_bitrate=data.get(
                "audio_transcode_bitrate",
                data.get("audio_bitrate", "192k"),  # Legacy key support
            ),
            audio_downmix=data.get("audio_downmix"),
            destination=data.get("destination"),
            destination_fallback=data.get("destination_fallback", "Unknown"),
        )


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

    V10: Added support for music, sfx, and non-speech track handling.
    """

    languages: tuple[str, ...]
    """ISO 639-2/B language codes to keep (e.g., ('eng', 'und', 'jpn')).
    Tracks with languages not in this list will be removed."""

    fallback: LanguageFallbackConfig | None = None
    """Fallback behavior when no tracks match preferred languages."""

    minimum: int = 1
    """Minimum number of audio tracks that must remain.
    If filtering would leave fewer tracks, fallback is triggered."""

    # V10: Music track handling
    keep_music_tracks: bool = True
    """If True, keep music tracks (score, soundtrack) even if not in languages list."""

    exclude_music_from_language_filter: bool = True
    """If True, music tracks bypass language filtering entirely."""

    # V10: SFX track handling
    keep_sfx_tracks: bool = True
    """If True, keep SFX tracks (sound effects) even if not in languages list."""

    exclude_sfx_from_language_filter: bool = True
    """If True, SFX tracks bypass language filtering entirely."""

    # V10: Non-speech track handling (unlabeled tracks detected as no speech)
    keep_non_speech_tracks: bool = True
    """If True, keep non-speech tracks (unlabeled tracks with no dialog)."""

    exclude_non_speech_from_language_filter: bool = True
    """If True, non-speech tracks bypass language filtering entirely."""

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

    transcription_status: str | None = None
    """Transcription analysis status for audio tracks.

    Format: 'main 95%', 'commentary 88%', 'alternate 72%', or 'TBD'.
    None for non-audio tracks.
    """


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
    TrackType.AUDIO_MUSIC,
    TrackType.AUDIO_SFX,
    TrackType.AUDIO_NON_SPEECH,
    TrackType.SUBTITLE_MAIN,
    TrackType.SUBTITLE_FORCED,
    TrackType.AUDIO_COMMENTARY,
    TrackType.SUBTITLE_COMMENTARY,
    TrackType.ATTACHMENT,
)


# =============================================================================
# V9 Workflow Configuration
# =============================================================================


@dataclass(frozen=True)
class WorkflowConfig:
    """Workflow configuration from policy YAML (V9+).

    Defines the processing phases to run and their execution behavior.
    Phases execute in order: ANALYZE → APPLY → TRANSCODE.
    """

    phases: tuple[ProcessingPhase, ...]
    """Phases to execute in order."""

    auto_process: bool = False
    """If True, daemon auto-queues PROCESS jobs when files are scanned."""

    on_error: Literal["skip", "continue", "fail"] = "continue"
    """Error handling:
    - skip: Stop processing file, mark as failed
    - continue: Log error and proceed to next phase
    - fail: Stop entire batch with error
    """

    def __post_init__(self) -> None:
        """Validate workflow configuration."""
        if not self.phases:
            raise ValueError("workflow.phases cannot be empty")

        valid_phases = set(ProcessingPhase)
        for phase in self.phases:
            if phase not in valid_phases:
                raise ValueError(f"Invalid phase: {phase}")

        # Check for duplicate phases
        if len(self.phases) != len(set(self.phases)):
            raise ValueError("Duplicate phases not allowed")

        valid_on_error = ("skip", "continue", "fail")
        if self.on_error not in valid_on_error:
            raise ValueError(
                f"Invalid on_error: {self.on_error}. "
                f"Must be one of: {', '.join(valid_on_error)}"
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

    # V4 fields (all optional for backward compatibility)
    conditional_rules: tuple["ConditionalRule", ...] = ()
    """Conditional rules evaluated before other policy sections. Schema v4+."""

    # V5 fields (all optional for backward compatibility)
    audio_synthesis: "AudioSynthesisConfig | None" = None
    """Audio synthesis configuration. Requires schema_version >= 5."""

    # V6 fields (all optional for backward compatibility)
    video_transcode: "VideoTranscodeConfig | None" = None
    """Video transcode configuration. Requires schema_version >= 6."""

    audio_transcode: "AudioTranscodeConfig | None" = None
    """Audio transcode configuration. Requires schema_version >= 6."""

    # V9 fields (all optional for backward compatibility)
    workflow: WorkflowConfig | None = None
    """Workflow configuration. Requires schema_version >= 9."""

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

    @property
    def has_conditional_rules(self) -> bool:
        """True if any conditional rules are configured."""
        return len(self.conditional_rules) > 0

    @property
    def has_audio_synthesis(self) -> bool:
        """True if audio synthesis is configured."""
        return self.audio_synthesis is not None

    @property
    def has_workflow(self) -> bool:
        """True if workflow configuration is present."""
        return self.workflow is not None


# =============================================================================
# V5 Audio Synthesis Configuration
# =============================================================================


@dataclass(frozen=True)
class AudioSynthesisConfig:
    """Audio synthesis configuration from policy.

    Contains the list of synthesis track definitions to be processed
    when applying the policy.
    """

    tracks: tuple["SynthesisTrackDefinitionRef", ...]
    """Synthesis track definitions to process."""


@dataclass(frozen=True)
class SkipIfExistsCriteria:
    """Criteria for skipping synthesis if a matching track exists.

    Used in audio_synthesis.tracks[].skip_if_exists to implement
    "use existing OR create new" behavior. If any track matches ALL
    specified criteria, synthesis is skipped.

    All specified criteria must match (AND logic). Unspecified criteria
    (None values) match any track.
    """

    codec: str | tuple[str, ...] | None = None
    """Codec(s) that satisfy the requirement (case-insensitive)."""

    channels: Union[int, "Comparison", None] = None
    """Channel count or comparison (e.g., {gte: 6} for 5.1+)."""

    language: str | tuple[str, ...] | None = None
    """Language code(s) that satisfy the requirement."""

    not_commentary: bool | None = None
    """If True, track must not be commentary."""


@dataclass(frozen=True)
class SynthesisTrackDefinitionRef:
    """Reference to a synthesis track definition in policy.

    This is a lightweight reference stored in PolicySchema that points
    to the full SynthesisTrackDefinition in the synthesis module.
    """

    name: str
    """Human-readable identifier for this synthesis definition."""

    codec: str
    """Target codec (eac3, aac, ac3, opus, flac)."""

    channels: str | int
    """Target channel configuration or count."""

    source_prefer: tuple[dict, ...]
    """Source preference criteria as raw dicts."""

    bitrate: str | None = None
    """Target bitrate (e.g., '640k')."""

    create_if: "Condition | None" = None
    """Condition that must be true for synthesis."""

    skip_if_exists: SkipIfExistsCriteria | None = None
    """Skip synthesis if a matching track already exists (V8+)."""

    title: str = "inherit"
    """Track title or 'inherit'."""

    language: str = "inherit"
    """Language code or 'inherit'."""

    position: str | int = "end"
    """Position: 'after_source', 'end', or integer."""


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

    # V4 fields for conditional rules
    conditional_result: "ConditionalResult | None" = None
    """Result of conditional rule evaluation, if any rules were defined."""

    skip_flags: "SkipFlags" = field(default_factory=lambda: SkipFlags())
    """Flags set by conditional rules to suppress operations."""

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


# =============================================================================
# V4 Conditional Policy Models
# =============================================================================


class ComparisonOperator(Enum):
    """Operators for numeric comparisons in conditions."""

    EQ = "eq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"


@dataclass(frozen=True)
class Comparison:
    """Numeric comparison with operator and value.

    Used for comparing track properties like height, width, or channels
    against threshold values.
    """

    operator: ComparisonOperator
    value: int


@dataclass(frozen=True)
class TitleMatch:
    """String matching criteria for title field.

    Supports substring contains matching or regex pattern matching.
    At most one of contains or regex should be set.
    """

    contains: str | None = None
    regex: str | None = None


@dataclass(frozen=True)
class TrackFilters:
    """Criteria for matching track properties in conditions.

    All specified criteria must match (AND logic). Unspecified criteria
    (None values) match any track.
    """

    language: str | tuple[str, ...] | None = None
    codec: str | tuple[str, ...] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | Comparison | None = None
    width: int | Comparison | None = None
    height: int | Comparison | None = None
    title: str | TitleMatch | None = None
    not_commentary: bool | None = None  # V8: exclude commentary tracks


@dataclass(frozen=True)
class ExistsCondition:
    """Check if at least one track matches criteria.

    Evaluates to True if any track of the specified type matches
    all filter criteria.
    """

    track_type: str  # "video", "audio", "subtitle", "attachment"
    filters: TrackFilters = field(default_factory=TrackFilters)


@dataclass(frozen=True)
class CountCondition:
    """Check count of matching tracks against threshold.

    Evaluates to True if the count of matching tracks satisfies
    the comparison operator and value.
    """

    track_type: str
    filters: TrackFilters
    operator: ComparisonOperator
    value: int


@dataclass(frozen=True)
class AndCondition:
    """All sub-conditions must be true (logical AND)."""

    conditions: tuple["Condition", ...]


@dataclass(frozen=True)
class OrCondition:
    """At least one sub-condition must be true (logical OR)."""

    conditions: tuple["Condition", ...]


@dataclass(frozen=True)
class NotCondition:
    """Negate a condition (logical NOT)."""

    inner: "Condition"


@dataclass(frozen=True)
class AudioIsMultiLanguageCondition:
    """Check if audio track(s) have multiple detected languages.

    Evaluates language analysis results to determine if audio contains
    multiple spoken languages. Supports threshold and primary language filters.

    Attributes:
        track_index: Specific audio track to check (None = check all audio tracks).
        threshold: Minimum secondary language percentage to trigger (default 5%).
        primary_language: If set, only match if this is the primary language.
    """

    track_index: int | None = None
    threshold: float = 0.05  # 5% secondary language triggers multi-language
    primary_language: str | None = None


class PluginMetadataOperator(Enum):
    """Operators for plugin metadata comparisons.

    Used in PluginMetadataCondition to compare field values.
    """

    EQ = "eq"  # Equality (string, integer, float, boolean)
    NEQ = "neq"  # Not equal (string, integer, float, boolean)
    CONTAINS = "contains"  # Substring match (strings only)
    LT = "lt"  # Less than (numeric types: int/float)
    LTE = "lte"  # Less than or equal (numeric types: int/float)
    GT = "gt"  # Greater than (numeric types: int/float)
    GTE = "gte"  # Greater than or equal (numeric types: int/float)


@dataclass(frozen=True)
class PluginMetadataCondition:
    """Check plugin-provided metadata for a file.

    Evaluates metadata stored by plugins (e.g., Radarr, Sonarr) against
    specified criteria. This enables policy rules based on external metadata.

    Attributes:
        plugin: Name of the plugin that provided the metadata (e.g., "radarr").
        field: Field name within the plugin's metadata (e.g., "original_language").
        operator: Comparison operator (default: eq for equality).
        value: Value to compare against (string, int, float, or bool).

    Example YAML:
        when:
          plugin_metadata:
            plugin: radarr
            field: original_language
            value: jpn
    """

    plugin: str
    field: str
    value: str | int | float | bool
    operator: PluginMetadataOperator = PluginMetadataOperator.EQ


# Type alias for union of all condition types
Condition = (
    ExistsCondition
    | CountCondition
    | AndCondition
    | OrCondition
    | NotCondition
    | AudioIsMultiLanguageCondition
    | PluginMetadataCondition
)


class SkipType(Enum):
    """Types of processing that can be skipped."""

    VIDEO_TRANSCODE = "skip_video_transcode"
    AUDIO_TRANSCODE = "skip_audio_transcode"
    TRACK_FILTER = "skip_track_filter"


@dataclass(frozen=True)
class SkipAction:
    """Set a skip flag to suppress later processing."""

    skip_type: SkipType


@dataclass(frozen=True)
class WarnAction:
    """Log a warning message and continue processing.

    The message supports placeholders: {filename}, {path}, {rule_name}
    """

    message: str


@dataclass(frozen=True)
class FailAction:
    """Stop processing with an error.

    The message supports placeholders: {filename}, {path}, {rule_name}
    """

    message: str


@dataclass(frozen=True)
class SetForcedAction:
    """Set the forced flag on matching tracks.

    Typically used to enable forced subtitles for multi-language content.

    Attributes:
        track_type: Type of track to modify (usually "subtitle").
        language: Language filter for matching tracks (optional).
        value: Value to set for the forced flag (default True).
    """

    track_type: str = "subtitle"
    language: str | None = None
    value: bool = True


@dataclass(frozen=True)
class SetDefaultAction:
    """Set the default flag on matching tracks.

    Used to mark a track as default playback track.

    Attributes:
        track_type: Type of track to modify.
        language: Language filter for matching tracks (optional).
        value: Value to set for the default flag (default True).
    """

    track_type: str
    language: str | None = None
    value: bool = True


@dataclass(frozen=True)
class PluginMetadataReference:
    """Reference to a plugin metadata field for dynamic value resolution.

    Used to pull values from plugin metadata at runtime, e.g., getting the
    original_language from Radarr/Sonarr to set as the video track language.

    Attributes:
        plugin: Name of the plugin (e.g., "radarr", "sonarr").
        field: Field name within the plugin's metadata (e.g., "original_language").
    """

    plugin: str
    field: str


@dataclass(frozen=True)
class SetLanguageAction:
    """Set the language tag on matching tracks.

    Used to correct or set track language metadata based on external sources
    like Radarr/Sonarr plugin metadata.

    Either new_language OR from_plugin_metadata must be specified, but not both.
    If from_plugin_metadata is used and the plugin/field is not available,
    the action is skipped (no change made).

    Attributes:
        track_type: Type of track to modify ("video", "audio", "subtitle").
        new_language: The ISO 639-2/B language code to set (static value).
        from_plugin_metadata: Reference to plugin metadata for dynamic language.
        match_language: Only modify tracks with this language (optional).
            If None, modifies all tracks of the specified type.
    """

    track_type: str
    new_language: str | None = None
    from_plugin_metadata: PluginMetadataReference | None = None
    match_language: str | None = None


# Type alias for union of all action types
ConditionalAction = (
    SkipAction
    | WarnAction
    | FailAction
    | SetForcedAction
    | SetDefaultAction
    | SetLanguageAction
)


@dataclass(frozen=True)
class ConditionalRule:
    """A named rule with condition and actions.

    Rules are evaluated in order. The first rule whose condition matches
    executes its then_actions. If no rule matches and the last rule has
    else_actions, those are executed (first-match-wins semantics).
    """

    name: str
    when: Condition
    then_actions: tuple[ConditionalAction, ...]
    else_actions: tuple[ConditionalAction, ...] | None = None


@dataclass(frozen=True)
class SkipFlags:
    """Flags set by conditional rules to suppress operations.

    These flags are checked by the policy evaluator to determine
    whether to skip certain processing steps.
    """

    skip_video_transcode: bool = False
    skip_audio_transcode: bool = False
    skip_track_filter: bool = False


@dataclass(frozen=True)
class RuleEvaluation:
    """Trace of a single rule's evaluation for dry-run output.

    Provides human-readable information about why a rule matched
    or didn't match.
    """

    rule_name: str
    matched: bool
    reason: str  # Human-readable explanation


@dataclass(frozen=True)
class TrackFlagChange:
    """A pending change to a track's flags.

    Represents a set_forced or set_default action that should
    be applied to a specific track.
    """

    track_index: int
    flag_type: str  # "forced" or "default"
    value: bool


@dataclass(frozen=True)
class TrackLanguageChange:
    """A pending change to a track's language tag.

    Represents a set_language action that should be applied
    to a specific track.
    """

    track_index: int
    new_language: str


@dataclass(frozen=True)
class ConditionalResult:
    """Result of conditional rule evaluation.

    Captures which rule matched, which branch was executed,
    any warnings generated, track flag changes, and a trace for debugging.
    """

    matched_rule: str | None  # Name of first matching rule, None if no match
    matched_branch: Literal["then", "else"] | None
    warnings: tuple[str, ...]  # Formatted warning messages
    evaluation_trace: tuple[RuleEvaluation, ...]  # For dry-run output
    skip_flags: SkipFlags = field(default_factory=SkipFlags)
    track_flag_changes: tuple[TrackFlagChange, ...] = ()  # From set_forced/set_default


# =============================================================================
# V6 Conditional Video Transcoding Models
# =============================================================================


class QualityMode(Enum):
    """Video encoding quality mode."""

    CRF = "crf"  # Constant Rate Factor (variable bitrate, quality-based)
    BITRATE = "bitrate"  # Target bitrate mode (constant bitrate)
    CONSTRAINED_QUALITY = "constrained_quality"  # CRF with max bitrate cap


class ScaleAlgorithm(Enum):
    """Video scaling algorithm."""

    LANCZOS = "lanczos"  # Best quality for downscaling
    BICUBIC = "bicubic"  # Good quality, faster
    BILINEAR = "bilinear"  # Fast, acceptable quality


class HardwareAccelMode(Enum):
    """Hardware acceleration mode for video encoding."""

    AUTO = "auto"  # Auto-detect best available encoder
    NVENC = "nvenc"  # Force NVIDIA NVENC
    QSV = "qsv"  # Force Intel Quick Sync Video
    VAAPI = "vaapi"  # Force VAAPI (Linux AMD/Intel)
    NONE = "none"  # Force CPU encoding


# Valid encoding presets (slowest to fastest)
VALID_PRESETS = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
)

# Valid tune options per encoder type
# x264/x265 support these tunes
X264_X265_TUNES = (
    "film",
    "animation",
    "grain",
    "stillimage",
    "fastdecode",
    "zerolatency",
)

# Codec-specific default CRF values (balanced quality)
DEFAULT_CRF_VALUES: dict[str, int] = {
    "h264": 23,
    "x264": 23,
    "hevc": 28,
    "h265": 28,
    "x265": 28,
    "vp9": 31,
    "av1": 30,
}


def parse_bitrate(bitrate_str: str) -> int | None:
    """Parse a bitrate string like '10M' or '5000k' to bits per second.

    Args:
        bitrate_str: Bitrate string with M/m (megabits) or K/k (kilobits) suffix.

    Returns:
        Bitrate in bits per second, or None if parsing fails.

    Examples:
        parse_bitrate("10M") -> 10_000_000
        parse_bitrate("5000k") -> 5_000_000
        parse_bitrate("2500K") -> 2_500_000
    """
    if not bitrate_str:
        return None

    bitrate_str = bitrate_str.strip()
    try:
        if bitrate_str[-1].lower() == "m":
            return int(float(bitrate_str[:-1]) * 1_000_000)
        elif bitrate_str[-1].lower() == "k":
            return int(float(bitrate_str[:-1]) * 1_000)
        else:
            # Assume bits per second
            return int(bitrate_str)
    except (ValueError, IndexError):
        return None


def get_default_crf(codec: str) -> int:
    """Get codec-specific default CRF value.

    Args:
        codec: Video codec name (h264, hevc, vp9, av1).

    Returns:
        Default CRF value for the codec.
    """
    return DEFAULT_CRF_VALUES.get(codec.lower(), 23)


@dataclass(frozen=True)
class SkipCondition:
    """Conditions for skipping video transcoding (AND logic).

    All specified conditions must be true for the skip to occur.
    Unspecified conditions (None) are not evaluated.
    """

    codec_matches: tuple[str, ...] | None = None
    """Skip if video codec matches any in this list (case-insensitive)."""

    resolution_within: str | None = None
    """Skip if video resolution <= this preset (e.g., '1080p')."""

    bitrate_under: str | None = None
    """Skip if video bitrate < this value (e.g., '10M')."""

    def __post_init__(self) -> None:
        """Validate skip condition configuration."""
        # Require at least one condition to be specified
        if (
            self.codec_matches is None
            and self.resolution_within is None
            and self.bitrate_under is None
        ):
            raise ValueError(
                "SkipCondition requires at least one condition to be specified. "
                "Empty skip_if would skip all files. "
                "Specify codec_matches, resolution_within, or bitrate_under."
            )
        if self.resolution_within is not None:
            if self.resolution_within.lower() not in VALID_RESOLUTIONS:
                raise ValueError(
                    f"Invalid resolution_within: {self.resolution_within}. "
                    f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
                )
        if self.bitrate_under is not None:
            if parse_bitrate(self.bitrate_under) is None:
                raise ValueError(
                    f"Invalid bitrate_under: {self.bitrate_under}. "
                    "Must be a number followed by M or k (e.g., '10M', '5000k')."
                )


@dataclass(frozen=True)
class QualitySettings:
    """Video encoding quality settings."""

    mode: QualityMode = QualityMode.CRF
    """Quality control mode (crf, bitrate, constrained_quality)."""

    crf: int | None = None
    """CRF value (0-51). Lower = better quality. Defaults applied per codec."""

    bitrate: str | None = None
    """Target bitrate for bitrate mode (e.g., '5M', '2500k')."""

    min_bitrate: str | None = None
    """Minimum bitrate for constrained quality."""

    max_bitrate: str | None = None
    """Maximum bitrate for constrained quality."""

    preset: str = "medium"
    """Encoding preset (ultrafast to veryslow)."""

    tune: str | None = None
    """Content-specific tune option (film, animation, grain, etc.)."""

    two_pass: bool = False
    """Enable two-pass encoding for accurate bitrate targeting."""

    def __post_init__(self) -> None:
        """Validate quality settings."""
        if self.crf is not None:
            if not 0 <= self.crf <= 51:
                raise ValueError(f"Invalid crf: {self.crf}. Must be 0-51.")

        if self.preset not in VALID_PRESETS:
            raise ValueError(
                f"Invalid preset: {self.preset}. "
                f"Must be one of: {', '.join(VALID_PRESETS)}"
            )

        if self.tune is not None:
            if self.tune not in X264_X265_TUNES:
                raise ValueError(
                    f"Invalid tune: {self.tune}. "
                    f"Must be one of: {', '.join(X264_X265_TUNES)}"
                )

        # Validate bitrate strings
        for bitrate_name, bitrate_val in [
            ("bitrate", self.bitrate),
            ("min_bitrate", self.min_bitrate),
            ("max_bitrate", self.max_bitrate),
        ]:
            if bitrate_val is not None:
                if parse_bitrate(bitrate_val) is None:
                    raise ValueError(
                        f"Invalid {bitrate_name}: {bitrate_val}. "
                        "Must be a number followed by M or k."
                    )

        # Validate mode-specific requirements
        if self.mode == QualityMode.BITRATE and self.bitrate is None:
            raise ValueError("bitrate is required when mode is 'bitrate'")


@dataclass(frozen=True)
class ScalingSettings:
    """Video resolution scaling settings."""

    max_resolution: str | None = None
    """Maximum resolution preset (e.g., '1080p', '720p', '4k')."""

    max_width: int | None = None
    """Maximum width in pixels (alternative to max_resolution)."""

    max_height: int | None = None
    """Maximum height in pixels (alternative to max_resolution)."""

    algorithm: ScaleAlgorithm = ScaleAlgorithm.LANCZOS
    """Scaling algorithm to use."""

    upscale: bool = False
    """Allow upscaling smaller content (false = preserve original if smaller)."""

    def __post_init__(self) -> None:
        """Validate scaling settings."""
        if self.max_resolution is not None:
            if self.max_resolution.lower() not in VALID_RESOLUTIONS:
                raise ValueError(
                    f"Invalid max_resolution: {self.max_resolution}. "
                    f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
                )

        if self.max_width is not None and self.max_width <= 0:
            raise ValueError(f"max_width must be positive, got {self.max_width}")

        if self.max_height is not None and self.max_height <= 0:
            raise ValueError(f"max_height must be positive, got {self.max_height}")

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


@dataclass(frozen=True)
class HardwareAccelConfig:
    """Hardware acceleration settings."""

    enabled: HardwareAccelMode = HardwareAccelMode.AUTO
    """Hardware acceleration mode."""

    fallback_to_cpu: bool = True
    """Fall back to CPU encoding if hardware encoder fails or unavailable."""


@dataclass(frozen=True)
class AudioTranscodeConfig:
    """Audio handling configuration for video transcoding.

    Controls which audio codecs are preserved (stream-copied) and
    which are transcoded during video transcoding operations.
    """

    preserve_codecs: tuple[str, ...] = ("truehd", "dts-hd", "flac", "pcm_s24le")
    """Audio codecs to preserve (stream-copy without re-encoding)."""

    transcode_to: str = "aac"
    """Target codec for non-preserved audio tracks."""

    transcode_bitrate: str = "192k"
    """Bitrate for transcoded audio tracks."""

    def __post_init__(self) -> None:
        """Validate audio transcode configuration."""
        if self.transcode_to.lower() not in VALID_AUDIO_CODECS:
            raise ValueError(
                f"Invalid transcode_to: {self.transcode_to}. "
                f"Must be one of: {', '.join(sorted(VALID_AUDIO_CODECS))}"
            )
        if parse_bitrate(self.transcode_bitrate) is None:
            raise ValueError(
                f"Invalid transcode_bitrate: {self.transcode_bitrate}. "
                "Must be a number followed by k (e.g., '192k', '256k')."
            )


@dataclass(frozen=True)
class VideoTranscodeConfig:
    """Video transcoding configuration within a transcode policy.

    This is the new V6 configuration that extends the existing
    TranscodePolicyConfig with conditional skip logic and enhanced settings.
    """

    target_codec: str
    """Target video codec (hevc, h264, vp9, av1)."""

    skip_if: SkipCondition | None = None
    """Conditions for skipping transcoding."""

    quality: QualitySettings | None = None
    """Quality settings (CRF, bitrate, preset, tune)."""

    scaling: ScalingSettings | None = None
    """Resolution scaling settings."""

    hardware_acceleration: HardwareAccelConfig | None = None
    """Hardware acceleration settings."""

    def __post_init__(self) -> None:
        """Validate video transcode configuration."""
        if self.target_codec.lower() not in VALID_VIDEO_CODECS:
            raise ValueError(
                f"Invalid target_codec: {self.target_codec}. "
                f"Must be one of: {', '.join(sorted(VALID_VIDEO_CODECS))}"
            )


@dataclass(frozen=True)
class VideoTranscodeAction:
    """Planned video transcode action."""

    source_codec: str
    """Source video codec."""

    target_codec: str
    """Target video codec."""

    encoder: str
    """FFmpeg encoder name (e.g., 'libx265', 'hevc_nvenc')."""

    crf: int | None = None
    """CRF value if using CRF mode."""

    bitrate: str | None = None
    """Target bitrate if using bitrate mode."""

    max_bitrate: str | None = None
    """Max bitrate if using constrained quality mode."""

    preset: str = "medium"
    """Encoding preset."""

    tune: str | None = None
    """Tune option."""

    scale_width: int | None = None
    """Target width if scaling."""

    scale_height: int | None = None
    """Target height if scaling."""

    scale_algorithm: str | None = None
    """Scaling algorithm name."""


@dataclass(frozen=True)
class VideoTranscodeResult:
    """Result of video transcode evaluation.

    This captures whether transcoding was skipped and the planned
    operations if not skipped.
    """

    skipped: bool
    """True if transcoding was skipped due to skip conditions."""

    skip_reason: str | None = None
    """Human-readable reason for skipping (e.g., 'Already HEVC at 1080p')."""

    video_action: VideoTranscodeAction | None = None
    """Planned video transcode action if not skipped."""

    audio_actions: tuple["AudioTrackAction", ...] = ()
    """Planned audio track actions."""

    encoder: str | None = None
    """Selected encoder name (e.g., 'hevc_nvenc', 'libx265')."""

    encoder_type: str | None = None
    """Encoder type: 'hardware' or 'software'."""


@dataclass(frozen=True)
class AudioTrackAction:
    """Planned action for a single audio track."""

    track_index: int
    """Track index in source file."""

    action: str
    """Action: 'copy', 'transcode', or 'remove'."""

    source_codec: str | None = None
    """Source audio codec."""

    target_codec: str | None = None
    """Target codec if transcoding."""

    target_bitrate: str | None = None
    """Target bitrate if transcoding."""

    reason: str = ""
    """Human-readable reason for the action."""


# =============================================================================
# V11 User-Defined Phases Data Models
# =============================================================================


@dataclass(frozen=True)
class GlobalConfig:
    """Global configuration shared across all phases (V11+).

    Settings defined here are available to all phases unless overridden
    by per-phase configuration.
    """

    # Language preferences (existing)
    audio_language_preference: tuple[str, ...] = ("eng", "und")
    """Ordered list of preferred audio languages (ISO 639-2/B codes)."""

    subtitle_language_preference: tuple[str, ...] = ("eng", "und")
    """Ordered list of preferred subtitle languages (ISO 639-2/B codes)."""

    # Track classification (existing)
    commentary_patterns: tuple[str, ...] = (
        "commentary",
        "director",
        "audio description",
    )
    """Patterns to match commentary track titles."""

    # Error handling (moved from WorkflowConfig)
    on_error: OnErrorMode = OnErrorMode.CONTINUE
    """How to handle errors during phase execution."""


@dataclass(frozen=True)
class PhaseDefinition:
    """A named phase containing zero or more operations (V11+).

    Each phase groups related operations that execute together.
    Operations within a phase execute in canonical order regardless
    of their definition order in the YAML.
    """

    name: str
    """User-defined phase name (validated: alphanumeric + hyphen + underscore)."""

    # Operations (all optional, at most one of each type)
    container: ContainerConfig | None = None
    """Container format conversion configuration."""

    audio_filter: AudioFilterConfig | None = None
    """Audio track filtering configuration."""

    subtitle_filter: SubtitleFilterConfig | None = None
    """Subtitle track filtering configuration."""

    attachment_filter: AttachmentFilterConfig | None = None
    """Attachment track filtering configuration."""

    track_order: tuple[TrackType, ...] | None = None
    """Track ordering configuration."""

    default_flags: DefaultFlagsConfig | None = None
    """Default flag configuration."""

    conditional: tuple["ConditionalRule", ...] | None = None
    """Conditional rules for this phase."""

    audio_synthesis: "AudioSynthesisConfig | None" = None
    """Audio synthesis configuration."""

    transcode: "VideoTranscodeConfig | None" = None
    """Video transcode configuration (V6-style nested format)."""

    audio_transcode: "AudioTranscodeConfig | None" = None
    """Audio transcode configuration (V6-style)."""

    transcription: TranscriptionPolicyOptions | None = None
    """Transcription analysis configuration."""

    def get_operations(self) -> list[OperationType]:
        """Return list of operations defined in this phase.

        Returns operations in canonical execution order, not definition order.
        """
        ops: list[OperationType] = []
        for op_type in CANONICAL_OPERATION_ORDER:
            if op_type == OperationType.CONTAINER and self.container is not None:
                ops.append(op_type)
            elif (
                op_type == OperationType.AUDIO_FILTER and self.audio_filter is not None
            ):
                ops.append(op_type)
            elif (
                op_type == OperationType.SUBTITLE_FILTER
                and self.subtitle_filter is not None
            ):
                ops.append(op_type)
            elif (
                op_type == OperationType.ATTACHMENT_FILTER
                and self.attachment_filter is not None
            ):
                ops.append(op_type)
            elif op_type == OperationType.TRACK_ORDER and self.track_order is not None:
                ops.append(op_type)
            elif (
                op_type == OperationType.DEFAULT_FLAGS
                and self.default_flags is not None
            ):
                ops.append(op_type)
            elif op_type == OperationType.CONDITIONAL and self.conditional is not None:
                ops.append(op_type)
            elif (
                op_type == OperationType.AUDIO_SYNTHESIS
                and self.audio_synthesis is not None
            ):
                ops.append(op_type)
            elif op_type == OperationType.TRANSCODE and (
                self.transcode is not None or self.audio_transcode is not None
            ):
                ops.append(op_type)
            elif (
                op_type == OperationType.TRANSCRIPTION
                and self.transcription is not None
            ):
                ops.append(op_type)
        return ops

    def is_empty(self) -> bool:
        """Return True if no operations are defined in this phase."""
        return len(self.get_operations()) == 0


@dataclass(frozen=True)
class V11PolicySchema:
    """V11 policy schema with user-defined phases.

    This is the new top-level policy structure for V11 policies.
    It replaces the flat PolicySchema structure with a phase-based approach.
    """

    schema_version: Literal[11]
    """Schema version, must be exactly 11."""

    config: GlobalConfig
    """Global configuration shared across all phases."""

    phases: tuple[PhaseDefinition, ...]
    """Ordered list of named phases."""

    def __post_init__(self) -> None:
        """Validate V11 policy schema."""
        if self.schema_version != 11:
            raise ValueError(
                f"V11PolicySchema requires schema_version=11, got {self.schema_version}"
            )
        if not self.phases:
            raise ValueError("phases cannot be empty, at least one phase required")

        # Check for duplicate phase names (exact match)
        names = [p.name for p in self.phases]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate phase names: {set(duplicates)}")

        # Check for case-insensitive collisions
        seen: dict[str, str] = {}
        for name in names:
            lower = name.lower()
            if lower in seen:
                raise ValueError(
                    f"Phase names must be unique (case-insensitive): "
                    f"'{seen[lower]}' and '{name}' collide"
                )
            seen[lower] = name

    @property
    def phase_names(self) -> tuple[str, ...]:
        """Return ordered list of phase names."""
        return tuple(p.name for p in self.phases)

    def get_phase(self, name: str) -> PhaseDefinition | None:
        """Look up phase by name.

        Args:
            name: Phase name to look up.

        Returns:
            PhaseDefinition if found, None otherwise.
        """
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None


@dataclass
class PhaseExecutionContext:
    """Mutable context passed through phase execution (V11+).

    This context is created at the start of file processing and
    updated as each phase executes.
    """

    file_path: Path
    """Path to the media file being processed."""

    file_info: Any  # FileInfo from db module - avoiding circular import
    """Current introspection data for the file."""

    policy: V11PolicySchema
    """The policy being applied."""

    current_phase: str
    """Name of the currently executing phase."""

    phase_index: int
    """1-based index of the current phase."""

    total_phases: int
    """Total number of phases to execute."""

    global_config: GlobalConfig
    """Global configuration from policy."""

    # Execution state
    backup_path: Path | None = None
    """Path to backup file created at phase start."""

    file_modified: bool = False
    """True if any operation in this phase modified the file."""

    operations_completed: list[str] = field(default_factory=list)
    """List of operation names completed in this phase."""

    # Dry-run output
    dry_run: bool = False
    """True if running in dry-run mode (no file modifications)."""

    planned_actions: list[PlannedAction] = field(default_factory=list)
    """Actions planned during dry-run."""


@dataclass(frozen=True)
class PhaseResult:
    """Result from executing a single phase (V11+)."""

    phase_name: str
    """Name of the phase that was executed."""

    success: bool
    """True if phase completed successfully."""

    duration_seconds: float
    """Time taken to execute the phase."""

    operations_executed: tuple[str, ...]
    """Names of operations that were executed."""

    changes_made: int
    """Number of changes made to the file."""

    message: str | None = None
    """Human-readable status message."""

    error: str | None = None
    """Error message if success is False."""

    # For dry-run output
    planned_actions: tuple[PlannedAction, ...] = ()
    """Actions that would be taken (dry-run mode)."""


@dataclass(frozen=True)
class FileProcessingResult:
    """Result from processing a file through all phases (V11+)."""

    file_path: Path
    """Path to the processed file."""

    success: bool
    """True if all phases completed successfully."""

    phase_results: tuple[PhaseResult, ...]
    """Results from each executed phase."""

    total_duration_seconds: float
    """Total time taken to process the file."""

    total_changes: int
    """Total number of changes made across all phases."""

    # Summary counts
    phases_completed: int
    """Number of phases that completed successfully."""

    phases_failed: int
    """Number of phases that failed."""

    phases_skipped: int
    """Number of phases that were skipped."""

    # Error info
    failed_phase: str | None = None
    """Name of the phase that failed, if any."""

    error_message: str | None = None
    """Error message from failed phase, if any."""


class PhaseExecutionError(Exception):
    """Raised when phase execution fails (V11+).

    This exception wraps operation-level errors and provides context
    about which phase and operation failed.
    """

    def __init__(
        self,
        phase_name: str,
        operation: str | None,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        """Initialize PhaseExecutionError.

        Args:
            phase_name: Name of the phase that failed.
            operation: Name of the operation that failed, if known.
            message: Human-readable error message.
            cause: The underlying exception, if any.
        """
        self.phase_name = phase_name
        self.operation = operation
        self.message = message
        self.cause = cause
        super().__init__(f"Phase '{phase_name}' failed: {message}")
