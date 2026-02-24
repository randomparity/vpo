"""Policy schema types for defining multi-phase policies.

This module contains the top-level policy schema types including
GlobalConfig, PhaseDefinition, EvaluationPolicy, and PolicySchema.
"""

from dataclasses import dataclass, field
from typing import Literal

from vpo.policy.types.actions import ConditionalRule
from vpo.policy.types.conditions import Comparison
from vpo.policy.types.enums import (
    CANONICAL_OPERATION_ORDER,
    DEFAULT_TRACK_ORDER,
    MatchMode,
    OnErrorMode,
    OperationType,
    TrackType,
)
from vpo.policy.types.filters import (
    AttachmentFilterConfig,
    AudioActionsConfig,
    AudioFilterConfig,
    ContainerConfig,
    DefaultFlagsConfig,
    FileTimestampConfig,
    SubtitleActionsConfig,
    SubtitleFilterConfig,
    TranscriptionPolicyOptions,
    VideoActionsConfig,
)
from vpo.policy.types.plan import PhaseSkipCondition, RunIfCondition
from vpo.policy.types.transcode import AudioTranscodeConfig, VideoTranscodeConfig

# =============================================================================
# Audio Synthesis Configuration
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

    channels: int | Comparison | None = None
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


# Import Condition type for forward reference
from vpo.policy.types.conditions import Condition  # noqa: E402

# =============================================================================
# Phased Policy Data Models
# =============================================================================


@dataclass(frozen=True)
class GlobalConfig:
    """Global configuration shared across all phases.

    Settings defined here are available to all phases unless overridden
    by per-phase configuration.
    """

    audio_languages: tuple[str, ...] = ("eng", "und")
    """Ordered list of preferred audio languages (ISO 639-2/B codes)."""

    subtitle_languages: tuple[str, ...] = ("eng", "und")
    """Ordered list of preferred subtitle languages (ISO 639-2/B codes)."""

    commentary_patterns: tuple[str, ...] = (
        "commentary",
        "director",
        "audio description",
    )
    """Patterns to match commentary track titles."""

    on_error: OnErrorMode = OnErrorMode.CONTINUE
    """How to handle errors during phase execution."""


@dataclass(frozen=True)
class RulesConfig:
    """Configuration for conditional rules within a phase.

    Wraps the list of rules with a match mode that controls
    evaluation semantics.
    """

    match: MatchMode
    """How rules are matched: FIRST (stop on first match) or ALL (evaluate all)."""

    items: tuple[ConditionalRule, ...]
    """Ordered list of conditional rules to evaluate."""


@dataclass(frozen=True)
class PhaseDefinition:
    """A named phase containing zero or more operations.

    Each phase groups related operations that execute together.
    Operations within a phase execute in canonical order regardless
    of their definition order in the YAML.
    """

    name: str
    """User-defined phase name (validated: alphanumeric + hyphen + underscore)."""

    # Operations (all optional, at most one of each type)
    container: ContainerConfig | None = None
    """Container format conversion configuration."""

    keep_audio: AudioFilterConfig | None = None
    """Audio track filtering configuration."""

    keep_subtitles: SubtitleFilterConfig | None = None
    """Subtitle track filtering configuration."""

    filter_attachments: AttachmentFilterConfig | None = None
    """Attachment track filtering configuration."""

    track_order: tuple[TrackType, ...] | None = None
    """Track ordering configuration."""

    default_flags: DefaultFlagsConfig | None = None
    """Default flag configuration."""

    rules: RulesConfig | None = None
    """Conditional rules for this phase (match mode + items)."""

    audio_synthesis: AudioSynthesisConfig | None = None
    """Audio synthesis configuration."""

    transcode: VideoTranscodeConfig | None = None
    """Video transcode configuration."""

    audio_transcode: AudioTranscodeConfig | None = None
    """Audio transcode configuration."""

    transcription: TranscriptionPolicyOptions | None = None
    """Transcription analysis configuration."""

    file_timestamp: FileTimestampConfig | None = None
    """File timestamp handling configuration."""

    audio_actions: AudioActionsConfig | None = None
    """Pre-processing actions for audio tracks."""

    subtitle_actions: SubtitleActionsConfig | None = None
    """Pre-processing actions for subtitle tracks."""

    video_actions: VideoActionsConfig | None = None
    """Pre-processing actions for video tracks."""

    # Conditional phase execution fields
    skip_when: PhaseSkipCondition | None = None
    """Conditions that cause this phase to be skipped."""

    depends_on: tuple[str, ...] | None = None
    """Phase names this phase depends on (must complete successfully)."""

    run_if: RunIfCondition | None = None
    """Positive run condition (e.g., run only if previous phase modified file)."""

    on_error: OnErrorMode | None = None
    """Override global on_error setting for this phase."""

    def get_operations(self) -> list[OperationType]:
        """Return list of operations defined in this phase.

        Returns operations in canonical execution order, not definition order.
        """
        ops: list[OperationType] = []
        for op_type in CANONICAL_OPERATION_ORDER:
            if op_type == OperationType.CONTAINER and self.container is not None:
                ops.append(op_type)
            elif op_type == OperationType.AUDIO_FILTER and self.keep_audio is not None:
                ops.append(op_type)
            elif (
                op_type == OperationType.SUBTITLE_FILTER
                and self.keep_subtitles is not None
            ):
                ops.append(op_type)
            elif (
                op_type == OperationType.ATTACHMENT_FILTER
                and self.filter_attachments is not None
            ):
                ops.append(op_type)
            elif op_type == OperationType.TRACK_ORDER and self.track_order is not None:
                ops.append(op_type)
            elif (
                op_type == OperationType.DEFAULT_FLAGS
                and self.default_flags is not None
            ):
                ops.append(op_type)
            elif op_type == OperationType.CONDITIONAL and self.rules is not None:
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
                op_type == OperationType.FILE_TIMESTAMP
                and self.file_timestamp is not None
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
class EvaluationPolicy:
    """Flat policy structure for the evaluator.

    This combines a PhaseDefinition with GlobalConfig to provide all the
    attributes the evaluator needs in a flat structure. Created by
    PhaseExecutor for each phase execution.
    """

    schema_version: Literal[13] = 13
    """Schema version."""

    # From GlobalConfig
    audio_languages: tuple[str, ...] = ("eng", "und")
    """Ordered list of preferred audio languages."""

    subtitle_languages: tuple[str, ...] = ("eng", "und")
    """Ordered list of preferred subtitle languages."""

    commentary_patterns: tuple[str, ...] = ("commentary", "director")
    """Patterns to match commentary tracks."""

    # From PhaseDefinition (all optional)
    track_order: tuple[TrackType, ...] = DEFAULT_TRACK_ORDER
    """Track ordering."""

    default_flags: DefaultFlagsConfig = field(
        default_factory=lambda: DefaultFlagsConfig()
    )
    """Default flag settings."""

    keep_audio: AudioFilterConfig | None = None
    """Audio filter configuration."""

    keep_subtitles: SubtitleFilterConfig | None = None
    """Subtitle filter configuration."""

    filter_attachments: AttachmentFilterConfig | None = None
    """Attachment filter configuration."""

    container: ContainerConfig | None = None
    """Container configuration."""

    rules: RulesConfig | None = None
    """Conditional rules with match mode."""

    transcription: TranscriptionPolicyOptions | None = None
    """Transcription settings."""

    audio_actions: AudioActionsConfig | None = None
    """Audio preprocessing actions."""

    subtitle_actions: SubtitleActionsConfig | None = None
    """Subtitle preprocessing actions."""

    video_actions: VideoActionsConfig | None = None
    """Video preprocessing actions."""

    @property
    def has_track_filtering(self) -> bool:
        """True if any track filtering is configured."""
        return (
            self.keep_audio is not None
            or self.keep_subtitles is not None
            or self.filter_attachments is not None
        )

    @property
    def has_container_config(self) -> bool:
        """True if container conversion is configured."""
        return self.container is not None

    @property
    def has_rules(self) -> bool:
        """True if conditional rules are defined."""
        return self.rules is not None and len(self.rules.items) > 0

    @property
    def has_transcription_settings(self) -> bool:
        """True if transcription is configured."""
        return self.transcription is not None

    @classmethod
    def from_phase(
        cls, phase: PhaseDefinition, config: GlobalConfig
    ) -> "EvaluationPolicy":
        """Create an EvaluationPolicy from a phase definition and global config.

        Args:
            phase: The phase definition with operation configs.
            config: Global configuration (language prefs, etc.).

        Returns:
            EvaluationPolicy suitable for evaluate_policy().
        """
        return cls(
            schema_version=13,
            audio_languages=config.audio_languages,
            subtitle_languages=config.subtitle_languages,
            commentary_patterns=config.commentary_patterns,
            track_order=phase.track_order or DEFAULT_TRACK_ORDER,
            default_flags=phase.default_flags or DefaultFlagsConfig(),
            keep_audio=phase.keep_audio,
            keep_subtitles=phase.keep_subtitles,
            filter_attachments=phase.filter_attachments,
            container=phase.container,
            rules=phase.rules,
            transcription=phase.transcription,
            audio_actions=phase.audio_actions,
            subtitle_actions=phase.subtitle_actions,
            video_actions=phase.video_actions,
        )


@dataclass(frozen=True)
class PolicySchema:
    """Policy schema with user-defined phases.

    This is the top-level structure for policies. It uses a phase-based approach
    where each phase groups related operations.
    """

    schema_version: Literal[13]
    """Schema version, must be exactly 13."""

    config: GlobalConfig
    """Global configuration shared across all phases."""

    phases: tuple[PhaseDefinition, ...]
    """Ordered list of named phases."""

    name: str | None = None
    """Optional display name for UI presentation."""

    description: str | None = None
    """Optional policy description for documentation purposes."""

    category: str | None = None
    """Optional category for filtering/grouping policies (e.g., organize, transcode)."""

    def __post_init__(self) -> None:
        """Validate policy schema."""
        if self.schema_version != 13:
            raise ValueError(
                f"PolicySchema requires schema_version=13, got {self.schema_version}"
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
            lower = name.casefold()
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
