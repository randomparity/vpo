"""Condition types for conditional rules in policies.

This module contains all condition types used in conditional rules,
including exists, count, boolean logic, and specialized conditions.
"""

from dataclasses import dataclass, field
from enum import Enum


class ComparisonOperator(Enum):
    """Operators for numeric comparisons in conditions."""

    EQ = "eq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"


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
    EXISTS = "exists"  # Check if field exists (no value needed)


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


@dataclass(frozen=True)
class PluginMetadataCondition:
    """Check plugin-provided metadata for a file.

    Evaluates metadata stored by plugins (e.g., Radarr, Sonarr) against
    specified criteria. This enables policy rules based on external metadata.

    Attributes:
        plugin: Name of the plugin that provided the metadata (e.g., "radarr").
        field: Field name within the plugin's metadata (e.g., "original_language").
        operator: Comparison operator (default: eq for equality).
        value: Value to compare against. Required for all operators except EXISTS.

    Example YAML:
        when:
          plugin_metadata:
            plugin: radarr
            field: original_language
            value: jpn

        # Check if field exists:
        when:
          plugin_metadata:
            plugin: radarr
            field: original_language
            operator: exists
    """

    plugin: str
    field: str
    value: str | int | float | bool | None = None
    operator: PluginMetadataOperator = PluginMetadataOperator.EQ


@dataclass(frozen=True)
class ContainerMetadataCondition:
    """Check container-level metadata tags for a file.

    Evaluates container metadata (e.g., title, encoder from format.tags)
    against specified criteria. Uses the same operator set as
    PluginMetadataCondition.

    Attributes:
        field: Tag name to check (e.g., "title", "encoder"). Case-insensitive.
        operator: Comparison operator (default: eq for equality).
        value: Value to compare against. Required for all operators except EXISTS.

    Example YAML:
        when:
          container_metadata:
            field: title
            value: ".*720p.*"
            operator: contains

        when:
          container_metadata:
            field: encoder
            operator: exists
    """

    field: str
    value: str | int | float | bool | None = None
    operator: PluginMetadataOperator = PluginMetadataOperator.EQ


@dataclass(frozen=True)
class IsOriginalCondition:
    """Check if audio track is classified as original theatrical audio.

    Evaluates track classification results to determine if a track is the
    original language/theatrical audio track. Requires track classification
    to have been run on the file.

    Attributes:
        value: Expected classification (True for original, False for dubbed).
        min_confidence: Minimum confidence threshold for classification (0.0-1.0).
            Default is 0.7 (70%) per specification.
        language: Optional language filter (ISO 639-2/B code). If set, only
            matches tracks with this detected language.

    Example YAML:
        when:
          is_original: true

        # With confidence threshold:
        when:
          is_original:
            value: true
            min_confidence: 0.8

        # With language filter:
        when:
          is_original:
            value: true
            language: jpn
    """

    value: bool = True
    min_confidence: float = 0.7
    language: str | None = None


@dataclass(frozen=True)
class IsDubbedCondition:
    """Check if audio track is classified as a dubbed version.

    Evaluates track classification results to determine if a track is a
    dubbed version of the original audio. Requires track classification
    to have been run on the file.

    Attributes:
        value: Expected classification (True for dubbed, False for original).
        min_confidence: Minimum confidence threshold for classification (0.0-1.0).
            Default is 0.7 (70%) per specification.
        language: Optional language filter (ISO 639-2/B code). If set, only
            matches tracks with this detected language.

    Example YAML:
        when:
          is_dubbed: true

        # With confidence threshold and language:
        when:
          is_dubbed:
            value: true
            min_confidence: 0.8
            language: eng
    """

    value: bool = True
    min_confidence: float = 0.7
    language: str | None = None


# Type alias for union of all condition types
Condition = (
    ExistsCondition
    | CountCondition
    | AndCondition
    | OrCondition
    | NotCondition
    | AudioIsMultiLanguageCondition
    | PluginMetadataCondition
    | ContainerMetadataCondition
    | IsOriginalCondition
    | IsDubbedCondition
)
