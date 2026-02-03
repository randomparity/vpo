"""Action types for conditional rules in policies.

This module contains all action types that can be executed by conditional rules,
including skip, warn, fail, set_forced, set_default, and set_language actions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from vpo.policy.types.conditions import Condition


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


@dataclass(frozen=True)
class SetContainerMetadataAction:
    """Set a container-level metadata tag.

    Used to set or clear container-level metadata such as title, encoder,
    date, comment, etc.

    Either value OR from_plugin_metadata must be specified, but not both.
    An empty string value clears the tag.

    Attributes:
        field: Metadata field name (e.g., "title", "encoder").
        value: Static value to set (empty string clears the tag).
        from_plugin_metadata: Reference to plugin metadata for dynamic value.
    """

    field: str
    value: str | None = None
    from_plugin_metadata: PluginMetadataReference | None = None


# Type alias for union of all action types
ConditionalAction = (
    SkipAction
    | WarnAction
    | FailAction
    | SetForcedAction
    | SetDefaultAction
    | SetLanguageAction
    | SetContainerMetadataAction
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
class ContainerMetadataChange:
    """A pending change to a container-level metadata tag.

    Represents a set_container_metadata action that should be
    applied at the container level (not track-level).
    """

    field: str
    new_value: str  # Empty string means clear/delete the tag


@dataclass(frozen=True)
class ConditionalResult:
    """Result of conditional rule evaluation.

    Captures which rule matched, which branch was executed,
    any warnings generated, track flag/language changes, and a trace for debugging.
    """

    matched_rule: str | None  # Name of first matching rule, None if no match
    matched_branch: Literal["then", "else"] | None
    warnings: tuple[str, ...]  # Formatted warning messages
    evaluation_trace: tuple[RuleEvaluation, ...]  # For dry-run output
    skip_flags: SkipFlags = field(default_factory=SkipFlags)
    track_flag_changes: tuple[TrackFlagChange, ...] = ()  # From set_forced/set_default
    track_language_changes: tuple[TrackLanguageChange, ...] = ()  # From set_language
    container_metadata_changes: tuple[
        ContainerMetadataChange, ...
    ] = ()  # From set_container_metadata
