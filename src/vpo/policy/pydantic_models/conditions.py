"""Condition Pydantic models for policy parsing.

This module contains models for conditional rule evaluation:
- ComparisonModel: Numeric comparison operators
- TitleMatchModel: Title matching criteria
- TrackFiltersModel: Track filter criteria
- ExistsConditionModel: Track existence conditions
- CountConditionModel: Track count conditions
- AudioIsMultiLanguageModel: Multi-language audio detection
- PluginMetadataConditionModel: Plugin metadata conditions
- IsOriginalConditionModel: Original audio detection
- IsDubbedConditionModel: Dubbed audio detection
- ConditionModel: Union of all condition types
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ComparisonModel(BaseModel):
    """Pydantic model for numeric comparison (e.g., height: {gte: 2160})."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    eq: int | None = None
    lt: int | None = None
    lte: int | None = None
    gt: int | None = None
    gte: int | None = None

    @model_validator(mode="after")
    def validate_single_operator(self) -> ComparisonModel:
        """Validate that exactly one comparison operator is set."""
        operators = [
            ("eq", self.eq),
            ("lt", self.lt),
            ("lte", self.lte),
            ("gt", self.gt),
            ("gte", self.gte),
        ]
        set_operators = [(name, val) for name, val in operators if val is not None]

        if len(set_operators) != 1:
            if len(set_operators) == 0:
                raise ValueError(
                    "Comparison must specify exactly one operator (eq/lt/lte/gt/gte)"
                )
            names = [name for name, _ in set_operators]
            raise ValueError(
                f"Comparison must specify exactly one operator, got: {', '.join(names)}"
            )
        return self


class TitleMatchModel(BaseModel):
    """Pydantic model for title matching criteria."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contains: str | None = None
    regex: str | None = None

    @model_validator(mode="after")
    def validate_single_matcher(self) -> TitleMatchModel:
        """Validate that at most one matcher is set."""
        matchers = [self.contains, self.regex]
        set_count = sum(1 for m in matchers if m is not None)

        if set_count == 0:
            raise ValueError("Title match must specify either 'contains' or 'regex'")
        if set_count > 1:
            raise ValueError(
                "Title match must specify only one of 'contains' or 'regex'"
            )
        return self

    @field_validator("regex")
    @classmethod
    def validate_regex(cls, v: str | None) -> str | None:
        """Validate regex pattern is valid."""
        if v is not None:
            import re

            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}") from e
        return v


class TrackFiltersModel(BaseModel):
    """Pydantic model for track filter criteria."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    language: str | list[str] | None = None
    codec: str | list[str] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | ComparisonModel | None = None
    width: int | ComparisonModel | None = None
    height: int | ComparisonModel | None = None
    title: str | TitleMatchModel | None = None
    not_commentary: bool | None = None  # V8: exclude commentary tracks


class ExistsConditionModel(BaseModel):
    """Pydantic model for existence condition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_type: Literal["video", "audio", "subtitle", "attachment"]
    language: str | list[str] | None = None
    codec: str | list[str] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | ComparisonModel | None = None
    width: int | ComparisonModel | None = None
    height: int | ComparisonModel | None = None
    title: str | TitleMatchModel | None = None
    not_commentary: bool | None = None  # V8: exclude commentary tracks


class CountConditionModel(BaseModel):
    """Pydantic model for count condition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_type: Literal["video", "audio", "subtitle", "attachment"]
    language: str | list[str] | None = None
    codec: str | list[str] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    not_commentary: bool | None = None  # V8: exclude commentary tracks
    channels: int | ComparisonModel | None = None
    width: int | ComparisonModel | None = None
    height: int | ComparisonModel | None = None
    title: str | TitleMatchModel | None = None
    # Count comparison (required)
    eq: int | None = None
    lt: int | None = None
    lte: int | None = None
    gt: int | None = None
    gte: int | None = None

    @model_validator(mode="after")
    def validate_count_operator(self) -> CountConditionModel:
        """Validate that exactly one count comparison operator is set."""
        operators = [
            ("eq", self.eq),
            ("lt", self.lt),
            ("lte", self.lte),
            ("gt", self.gt),
            ("gte", self.gte),
        ]
        set_operators = [(name, val) for name, val in operators if val is not None]

        if len(set_operators) != 1:
            if len(set_operators) == 0:
                raise ValueError(
                    "Count condition must specify exactly one count operator "
                    "(eq/lt/lte/gt/gte)"
                )
            names = [name for name, _ in set_operators]
            raise ValueError(
                f"Count condition must specify exactly one count operator, "
                f"got: {', '.join(names)}"
            )
        return self


class AudioIsMultiLanguageModel(BaseModel):
    """Pydantic model for audio multi-language condition.

    Checks if an audio track contains multiple detected languages.
    Requires language analysis to have been performed on the track.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_index: int | None = None
    threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    primary_language: str | None = None

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate threshold is a reasonable percentage."""
        if v < 0.0 or v > 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        return v


class PluginMetadataConditionModel(BaseModel):
    """Pydantic model for plugin metadata condition (V12+).

    Checks plugin-provided metadata for a file against expected values.
    Enables policy rules based on external metadata from plugins like
    Radarr/Sonarr.

    Example YAML:
        when:
          plugin_metadata:
            plugin: radarr
            field: original_language
            value: jpn
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin: str
    """Name of the plugin that provided the metadata (e.g., 'radarr')."""

    field: str
    """Field name within the plugin's metadata (e.g., 'original_language')."""

    value: str | int | float | bool | None = None
    """Value to compare against. Required for all operators except 'exists'."""

    operator: Literal["eq", "neq", "contains", "lt", "lte", "gt", "gte", "exists"] = (
        "eq"
    )
    """Comparison operator. Use 'exists' to check if field is present."""

    @field_validator("plugin")
    @classmethod
    def validate_plugin_name(cls, v: str) -> str:
        """Validate plugin name is non-empty and valid."""
        if not v or not v.strip():
            raise ValueError("plugin name cannot be empty")
        v = v.strip().casefold()
        # Plugin names should be kebab-case identifiers
        import re

        if not re.match(r"^[a-z][a-z0-9-]*$", v):
            raise ValueError(
                f"Invalid plugin name '{v}'. "
                "Plugin names must be lowercase, start with a letter, "
                "and contain only letters, numbers, and hyphens."
            )
        return v

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Validate field name is non-empty and normalize to lowercase."""
        import re

        v = v.strip()
        if not v:
            raise ValueError("field name cannot be empty")
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$", v):
            raise ValueError(
                f"Invalid field name '{v}': must start with a letter, "
                "contain only letters/digits/underscores, and be 1-64 characters"
            )
        return v.casefold()

    @model_validator(mode="after")
    def validate_operator_value_compatibility(self) -> PluginMetadataConditionModel:
        """Validate that operator is compatible with value type."""
        # 'exists' operator doesn't need a value
        if self.operator == "exists":
            return self

        # All other operators require a value
        if self.value is None:
            raise ValueError(
                f"Operator '{self.operator}' requires a value. "
                "Use operator: exists to check if a field is present."
            )

        # Numeric operators require numeric values
        numeric_ops = ("lt", "lte", "gt", "gte")
        if self.operator in numeric_ops:
            if not isinstance(self.value, (int, float)):
                raise ValueError(
                    f"Operator '{self.operator}' requires a numeric value, "
                    f"got {type(self.value).__name__}"
                )
        return self


class ContainerMetadataConditionModel(BaseModel):
    """Pydantic model for container metadata condition.

    Checks container-level metadata tags (e.g., title, encoder) against
    expected values. Uses the same operator set as PluginMetadataConditionModel.

    Example YAML:
        when:
          container_metadata:
            field: title
            value: "My Movie"

        when:
          container_metadata:
            field: encoder
            operator: exists
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    """Tag name to check (e.g., 'title', 'encoder'). Normalized to lowercase."""

    value: str | int | float | bool | None = None
    """Value to compare against. Required for all operators except 'exists'."""

    operator: Literal["eq", "neq", "contains", "lt", "lte", "gt", "gte", "exists"] = (
        "eq"
    )
    """Comparison operator. Use 'exists' to check if tag is present."""

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Validate field name is non-empty and normalize to lowercase."""
        import re

        v = v.strip()
        if not v:
            raise ValueError("field name cannot be empty")
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$", v):
            raise ValueError(
                f"Invalid field name '{v}': must start with a letter, "
                "contain only letters/digits/underscores, and be 1-64 characters"
            )
        return v.casefold()

    @model_validator(mode="after")
    def validate_operator_value_compatibility(
        self,
    ) -> ContainerMetadataConditionModel:
        """Validate that operator is compatible with value type."""
        if self.operator == "exists":
            return self

        if self.value is None:
            raise ValueError(
                f"Operator '{self.operator}' requires a value. "
                "Use operator: exists to check if a tag is present."
            )

        numeric_ops = ("lt", "lte", "gt", "gte")
        if self.operator in numeric_ops:
            if not isinstance(self.value, (int, float)):
                raise ValueError(
                    f"Operator '{self.operator}' requires a numeric value, "
                    f"got {type(self.value).__name__}"
                )
        return self


class IsOriginalConditionModel(BaseModel):
    """Pydantic model for is_original condition.

    Checks if audio track is classified as original theatrical audio.
    Requires track classification to have been performed on the file.

    Supports two forms:
    1. Simple boolean: is_original: true
    2. Full object: is_original: { value: true, min_confidence: 0.8, language: jpn }

    Example YAML:
        when:
          is_original: true

        when:
          is_original:
            value: true
            min_confidence: 0.8
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: bool = True
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    language: str | None = None


class IsDubbedConditionModel(BaseModel):
    """Pydantic model for is_dubbed condition.

    Checks if audio track is classified as a dubbed version.
    Requires track classification to have been performed on the file.

    Supports two forms:
    1. Simple boolean: is_dubbed: true
    2. Full object: is_dubbed: { value: true, min_confidence: 0.8, language: eng }

    Example YAML:
        when:
          is_dubbed: true

        when:
          is_dubbed:
            value: true
            language: eng
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: bool = True
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    language: str | None = None


class ConditionModel(BaseModel):
    """Pydantic model for condition (union of condition types)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Leaf conditions
    exists: ExistsConditionModel | None = None
    count: CountConditionModel | None = None
    audio_is_multi_language: AudioIsMultiLanguageModel | None = None
    plugin_metadata: PluginMetadataConditionModel | None = None  # V12+
    container_metadata: ContainerMetadataConditionModel | None = None  # V12+
    is_original: IsOriginalConditionModel | bool | None = None  # V12+, 044 feature
    is_dubbed: IsDubbedConditionModel | bool | None = None  # V12+, 044 feature

    # Boolean operators
    all_of: list[ConditionModel] | None = Field(None, alias="and")
    any_of: list[ConditionModel] | None = Field(None, alias="or")
    not_: ConditionModel | None = Field(None, alias="not")

    @model_validator(mode="after")
    def validate_single_condition_type(self) -> ConditionModel:
        """Validate that exactly one condition type is specified."""
        conditions = [
            ("exists", self.exists),
            ("count", self.count),
            ("audio_is_multi_language", self.audio_is_multi_language),
            ("plugin_metadata", self.plugin_metadata),
            ("container_metadata", self.container_metadata),
            ("is_original", self.is_original),
            ("is_dubbed", self.is_dubbed),
            ("and", self.all_of),
            ("or", self.any_of),
            ("not", self.not_),
        ]
        set_conditions = [(name, val) for name, val in conditions if val is not None]

        if len(set_conditions) != 1:
            if len(set_conditions) == 0:
                raise ValueError(
                    "Condition must specify exactly one type "
                    "(exists/count/audio_is_multi_language/plugin_metadata/"
                    "container_metadata/is_original/is_dubbed/and/or/not)"
                )
            names = [name for name, _ in set_conditions]
            raise ValueError(
                f"Condition must specify exactly one type, got: {', '.join(names)}"
            )
        return self

    @model_validator(mode="after")
    def validate_boolean_conditions_not_empty(self) -> ConditionModel:
        """Validate that boolean conditions have at least 2 sub-conditions."""
        if self.all_of is not None and len(self.all_of) < 2:
            raise ValueError("'and' condition must have at least 2 sub-conditions")
        if self.any_of is not None and len(self.any_of) < 2:
            raise ValueError("'or' condition must have at least 2 sub-conditions")
        return self
