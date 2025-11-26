"""Policy file loading and validation.

This module provides functions to load YAML policy files and validate
them using Pydantic models.
"""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from video_policy_orchestrator.policy.matchers import validate_regex_patterns
from video_policy_orchestrator.policy.models import (
    DEFAULT_TRACK_ORDER,
    VALID_AUDIO_CODECS,
    VALID_RESOLUTIONS,
    VALID_VIDEO_CODECS,
    AndCondition,
    AttachmentFilterConfig,
    AudioFilterConfig,
    AudioSynthesisConfig,
    Comparison,
    ComparisonOperator,
    Condition,
    ConditionalAction,
    ConditionalRule,
    ContainerConfig,
    CountCondition,
    DefaultFlagsConfig,
    ExistsCondition,
    FailAction,
    LanguageFallbackConfig,
    NotCondition,
    OrCondition,
    PolicySchema,
    SkipAction,
    SkipType,
    SubtitleFilterConfig,
    SynthesisTrackDefinitionRef,
    TitleMatch,
    TrackFilters,
    TrackType,
    TranscodePolicyConfig,
    TranscriptionPolicyOptions,
    WarnAction,
)

# Current maximum supported schema version
MAX_SCHEMA_VERSION = 5


class PolicyValidationError(Exception):
    """Error during policy validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.message = message
        self.field = field
        super().__init__(message)


class DefaultFlagsModel(BaseModel):
    """Pydantic model for default flags configuration."""

    model_config = ConfigDict(extra="forbid")

    set_first_video_default: bool = True
    set_preferred_audio_default: bool = True
    set_preferred_subtitle_default: bool = False
    clear_other_defaults: bool = True


class TranscriptionPolicyModel(BaseModel):
    """Pydantic model for transcription policy options."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    update_language_from_transcription: bool = False
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    detect_commentary: bool = False
    reorder_commentary: bool = False

    @field_validator("reorder_commentary")
    @classmethod
    def validate_reorder_requires_detect(
        cls,
        v: bool,
        info,  # noqa: ANN001
    ) -> bool:
        """Validate that reorder_commentary requires detect_commentary."""
        # Note: This validation is also done in the dataclass,
        # but we check here for early failure with better error messages
        return v


class TranscodePolicyModel(BaseModel):
    """Pydantic model for transcode policy configuration."""

    model_config = ConfigDict(extra="forbid")

    # Video settings
    target_video_codec: str | None = None
    target_crf: int | None = Field(default=None, ge=0, le=51)
    target_bitrate: str | None = None
    max_resolution: str | None = None
    max_width: int | None = Field(default=None, ge=1)
    max_height: int | None = Field(default=None, ge=1)

    # Audio preservation
    audio_preserve_codecs: list[str] = Field(default_factory=list)
    audio_transcode_to: str = "aac"
    audio_transcode_bitrate: str = "192k"
    audio_downmix: str | None = None

    # Destination
    destination: str | None = None
    destination_fallback: str = "Unknown"

    @field_validator("target_video_codec")
    @classmethod
    def validate_video_codec(cls, v: str | None) -> str | None:
        """Validate video codec."""
        if v is not None and v.lower() not in VALID_VIDEO_CODECS:
            raise ValueError(
                f"Invalid video codec '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_VIDEO_CODECS))}"
            )
        return v

    @field_validator("max_resolution")
    @classmethod
    def validate_resolution(cls, v: str | None) -> str | None:
        """Validate resolution preset."""
        if v is not None and v.lower() not in VALID_RESOLUTIONS:
            raise ValueError(
                f"Invalid resolution '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
            )
        return v

    @field_validator("audio_transcode_to")
    @classmethod
    def validate_audio_codec(cls, v: str) -> str:
        """Validate audio codec."""
        if v.lower() not in VALID_AUDIO_CODECS:
            raise ValueError(
                f"Invalid audio codec '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_AUDIO_CODECS))}"
            )
        return v

    @field_validator("audio_downmix")
    @classmethod
    def validate_audio_downmix(cls, v: str | None) -> str | None:
        """Validate audio downmix option."""
        if v is not None and v not in ("stereo", "5.1"):
            raise ValueError(f"Invalid audio_downmix '{v}'. Must be 'stereo' or '5.1'.")
        return v


# =============================================================================
# V3 Pydantic Models for Track Filtering
# =============================================================================


def _validate_language_codes(languages: list[str], field_name: str) -> list[str]:
    """Validate a list of language codes."""
    import re

    pattern = re.compile(r"^[a-z]{2,3}$")
    for idx, lang in enumerate(languages):
        if not pattern.match(lang):
            raise ValueError(
                f"Invalid language code '{lang}' at {field_name}[{idx}]. "
                "Use ISO 639-2 codes (e.g., 'eng', 'jpn')."
            )
    return languages


class LanguageFallbackModel(BaseModel):
    """Pydantic model for language fallback configuration."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["content_language", "keep_all", "keep_first", "error"]


class AudioFilterModel(BaseModel):
    """Pydantic model for audio filter configuration."""

    model_config = ConfigDict(extra="forbid")

    languages: list[str]
    fallback: LanguageFallbackModel | None = None
    minimum: int = Field(default=1, ge=1)

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, v: list[str]) -> list[str]:
        """Validate language codes in audio filter."""
        if not v:
            raise ValueError("languages cannot be empty")
        return _validate_language_codes(v, "languages")


class SubtitleFilterModel(BaseModel):
    """Pydantic model for subtitle filter configuration."""

    model_config = ConfigDict(extra="forbid")

    languages: list[str] | None = None
    preserve_forced: bool = False
    remove_all: bool = False

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, v: list[str] | None) -> list[str] | None:
        """Validate language codes in subtitle filter."""
        if v is not None:
            return _validate_language_codes(v, "languages")
        return v


class AttachmentFilterModel(BaseModel):
    """Pydantic model for attachment filter configuration."""

    model_config = ConfigDict(extra="forbid")

    remove_all: bool = False


class ContainerModel(BaseModel):
    """Pydantic model for container configuration."""

    model_config = ConfigDict(extra="forbid")

    target: Literal["mkv", "mp4"]
    on_incompatible_codec: Literal["error", "skip", "transcode"] = "error"


# =============================================================================
# V4 Pydantic Models for Conditional Rules
# =============================================================================


# =============================================================================
# V5 Pydantic Models for Audio Synthesis
# =============================================================================

# Valid audio codecs for synthesis
VALID_SYNTHESIS_CODECS = frozenset({"eac3", "aac", "ac3", "opus", "flac"})

# Valid channel configurations
VALID_CHANNEL_CONFIGS = frozenset({"mono", "stereo", "5.1", "7.1"})


class ChannelPreferenceModel(BaseModel):
    """Pydantic model for channel preference in source selection."""

    model_config = ConfigDict(extra="forbid")

    max: bool | None = None
    min: bool | None = None

    @model_validator(mode="after")
    def validate_single_preference(self) -> "ChannelPreferenceModel":
        """Validate that exactly one preference is set."""
        prefs = [self.max, self.min]
        set_count = sum(1 for p in prefs if p is True)
        if set_count != 1:
            raise ValueError(
                "Channel preference must specify exactly one of max or min"
            )
        return self


class PreferenceCriterionModel(BaseModel):
    """Pydantic model for source selection preference criterion."""

    model_config = ConfigDict(extra="forbid")

    language: str | list[str] | None = None
    not_commentary: bool | None = None
    channels: Literal["max", "min"] | int | ChannelPreferenceModel | None = None
    codec: str | list[str] | None = None

    @model_validator(mode="after")
    def validate_at_least_one_criterion(self) -> "PreferenceCriterionModel":
        """Validate that at least one criterion is specified."""
        criteria = [self.language, self.not_commentary, self.channels, self.codec]
        if all(c is None for c in criteria):
            raise ValueError(
                "Preference criterion must specify at least one of: "
                "language, not_commentary, channels, codec"
            )
        return self

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, v: str | list[str] | None) -> str | list[str] | None:
        """Normalize language to lowercase."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.lower()
        return [lang.lower() for lang in v]

    @field_validator("codec", mode="before")
    @classmethod
    def normalize_codec(cls, v: str | list[str] | None) -> str | list[str] | None:
        """Normalize codec to lowercase."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.lower()
        return [codec.lower() for codec in v]


class SourcePreferencesModel(BaseModel):
    """Pydantic model for source track preferences."""

    model_config = ConfigDict(extra="forbid")

    prefer: list[PreferenceCriterionModel]

    @field_validator("prefer")
    @classmethod
    def validate_prefer_not_empty(
        cls, v: list[PreferenceCriterionModel]
    ) -> list[PreferenceCriterionModel]:
        """Validate that prefer list is not empty."""
        if not v:
            raise ValueError("source.prefer must have at least one criterion")
        return v


class SynthesisTrackDefinitionModel(BaseModel):
    """Pydantic model for a synthesis track definition."""

    model_config = ConfigDict(extra="forbid")

    name: str
    codec: str
    channels: str | int
    source: SourcePreferencesModel
    bitrate: str | None = None
    create_if: "ConditionModel | None" = None
    title: str | Literal["inherit"] = "inherit"
    language: str | Literal["inherit"] = "inherit"
    position: Literal["after_source", "end"] | int = "end"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is non-empty."""
        if not v or not v.strip():
            raise ValueError("Synthesis track name cannot be empty")
        return v.strip()

    @field_validator("codec")
    @classmethod
    def validate_codec(cls, v: str) -> str:
        """Validate that codec is supported."""
        v_lower = v.lower()
        if v_lower not in VALID_SYNTHESIS_CODECS:
            raise ValueError(
                f"Invalid synthesis codec '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_SYNTHESIS_CODECS))}"
            )
        return v_lower

    @field_validator("channels", mode="before")
    @classmethod
    def validate_channels(cls, v: str | int) -> str | int:
        """Validate channel configuration."""
        if isinstance(v, int):
            if v < 1 or v > 8:
                raise ValueError(f"Channel count must be 1-8, got {v}")
            return v
        v_lower = v.lower()
        if v_lower not in VALID_CHANNEL_CONFIGS:
            raise ValueError(
                f"Invalid channel config '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_CHANNEL_CONFIGS))} or 1-8"
            )
        return v_lower

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str | None) -> str | None:
        """Validate bitrate format."""
        if v is None:
            return None
        import re

        if not re.match(r"^\d+(\.\d+)?[kKmM]?$", v):
            raise ValueError(
                f"Invalid bitrate format '{v}'. Use format like '640k' or '1.5M'"
            )
        return v.lower()

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: str | int) -> str | int:
        """Validate position value."""
        if isinstance(v, int) and v < 1:
            raise ValueError("Position must be >= 1 when specified as integer")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate language code format."""
        if v == "inherit":
            return v
        import re

        if not re.match(r"^[a-z]{2,3}$", v.lower()):
            raise ValueError(
                f"Invalid language code '{v}'. "
                "Use ISO 639-2 codes (e.g., 'eng', 'jpn') or 'inherit'"
            )
        return v.lower()


class AudioSynthesisModel(BaseModel):
    """Pydantic model for audio_synthesis configuration."""

    model_config = ConfigDict(extra="forbid")

    tracks: list[SynthesisTrackDefinitionModel]

    @field_validator("tracks")
    @classmethod
    def validate_tracks_not_empty(
        cls, v: list[SynthesisTrackDefinitionModel]
    ) -> list[SynthesisTrackDefinitionModel]:
        """Validate that tracks list is not empty."""
        if not v:
            raise ValueError("audio_synthesis.tracks must have at least one track")
        return v

    @model_validator(mode="after")
    def validate_unique_names(self) -> "AudioSynthesisModel":
        """Validate that track names are unique."""
        names: set[str] = set()
        for track in self.tracks:
            if track.name in names:
                raise ValueError(f"Duplicate synthesis track name: '{track.name}'")
            names.add(track.name)
        return self


class ComparisonModel(BaseModel):
    """Pydantic model for numeric comparison (e.g., height: {gte: 2160})."""

    model_config = ConfigDict(extra="forbid")

    eq: int | None = None
    lt: int | None = None
    lte: int | None = None
    gt: int | None = None
    gte: int | None = None

    @model_validator(mode="after")
    def validate_single_operator(self) -> "ComparisonModel":
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

    model_config = ConfigDict(extra="forbid")

    contains: str | None = None
    regex: str | None = None

    @model_validator(mode="after")
    def validate_single_matcher(self) -> "TitleMatchModel":
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

    model_config = ConfigDict(extra="forbid")

    language: str | list[str] | None = None
    codec: str | list[str] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | ComparisonModel | None = None
    width: int | ComparisonModel | None = None
    height: int | ComparisonModel | None = None
    title: str | TitleMatchModel | None = None


class ExistsConditionModel(BaseModel):
    """Pydantic model for existence condition."""

    model_config = ConfigDict(extra="forbid")

    track_type: Literal["video", "audio", "subtitle", "attachment"]
    language: str | list[str] | None = None
    codec: str | list[str] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | ComparisonModel | None = None
    width: int | ComparisonModel | None = None
    height: int | ComparisonModel | None = None
    title: str | TitleMatchModel | None = None


class CountConditionModel(BaseModel):
    """Pydantic model for count condition."""

    model_config = ConfigDict(extra="forbid")

    track_type: Literal["video", "audio", "subtitle", "attachment"]
    language: str | list[str] | None = None
    codec: str | list[str] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
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
    def validate_count_operator(self) -> "CountConditionModel":
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


class ConditionModel(BaseModel):
    """Pydantic model for condition (union of condition types)."""

    model_config = ConfigDict(extra="forbid")

    # Leaf conditions
    exists: ExistsConditionModel | None = None
    count: CountConditionModel | None = None

    # Boolean operators
    all_of: list["ConditionModel"] | None = Field(None, alias="and")
    any_of: list["ConditionModel"] | None = Field(None, alias="or")
    not_: "ConditionModel | None" = Field(None, alias="not")

    @model_validator(mode="after")
    def validate_single_condition_type(self) -> "ConditionModel":
        """Validate that exactly one condition type is specified."""
        conditions = [
            ("exists", self.exists),
            ("count", self.count),
            ("and", self.all_of),
            ("or", self.any_of),
            ("not", self.not_),
        ]
        set_conditions = [(name, val) for name, val in conditions if val is not None]

        if len(set_conditions) != 1:
            if len(set_conditions) == 0:
                raise ValueError(
                    "Condition must specify exactly one type (exists/count/and/or/not)"
                )
            names = [name for name, _ in set_conditions]
            raise ValueError(
                f"Condition must specify exactly one type, got: {', '.join(names)}"
            )
        return self

    @model_validator(mode="after")
    def validate_boolean_conditions_not_empty(self) -> "ConditionModel":
        """Validate that boolean conditions have at least 2 sub-conditions."""
        if self.all_of is not None and len(self.all_of) < 2:
            raise ValueError("'and' condition must have at least 2 sub-conditions")
        if self.any_of is not None and len(self.any_of) < 2:
            raise ValueError("'or' condition must have at least 2 sub-conditions")
        return self


class ActionModel(BaseModel):
    """Pydantic model for conditional action."""

    model_config = ConfigDict(extra="forbid")

    # Skip actions
    skip_video_transcode: bool | None = None
    skip_audio_transcode: bool | None = None
    skip_track_filter: bool | None = None

    # Message actions
    warn: str | None = None
    fail: str | None = None

    @model_validator(mode="after")
    def validate_at_least_one_action(self) -> "ActionModel":
        """Validate that at least one action is specified."""
        actions = [
            self.skip_video_transcode,
            self.skip_audio_transcode,
            self.skip_track_filter,
            self.warn,
            self.fail,
        ]
        if not any(a is not None for a in actions):
            raise ValueError(
                "Action must specify at least one action "
                "(skip_video_transcode/skip_audio_transcode/skip_track_filter/"
                "warn/fail)"
            )
        return self


class ConditionalRuleModel(BaseModel):
    """Pydantic model for a conditional rule."""

    model_config = ConfigDict(extra="forbid")

    name: str
    when: ConditionModel
    then: ActionModel | list[ActionModel]
    else_: ActionModel | list[ActionModel] | None = Field(None, alias="else")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate rule name is non-empty."""
        if not v or not v.strip():
            raise ValueError("Rule name cannot be empty")
        return v.strip()


class PolicyModel(BaseModel):
    """Pydantic model for policy YAML validation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=MAX_SCHEMA_VERSION)
    track_order: list[str] = Field(
        default_factory=lambda: [t.value for t in DEFAULT_TRACK_ORDER]
    )
    audio_language_preference: list[str] = Field(default_factory=lambda: ["eng", "und"])
    subtitle_language_preference: list[str] = Field(
        default_factory=lambda: ["eng", "und"]
    )
    commentary_patterns: list[str] = Field(
        default_factory=lambda: ["commentary", "director"]
    )
    default_flags: DefaultFlagsModel = Field(default_factory=DefaultFlagsModel)
    transcode: TranscodePolicyModel | None = None
    transcription: TranscriptionPolicyModel | None = None

    # V3 fields (optional, require schema_version >= 3)
    audio_filter: AudioFilterModel | None = None
    subtitle_filter: SubtitleFilterModel | None = None
    attachment_filter: AttachmentFilterModel | None = None
    container: ContainerModel | None = None

    # V4 fields (optional, require schema_version >= 4)
    conditional: list[ConditionalRuleModel] | None = None

    # V5 fields (optional, require schema_version >= 5)
    audio_synthesis: AudioSynthesisModel | None = None

    @model_validator(mode="after")
    def validate_versioned_fields(self) -> "PolicyModel":
        """Validate that versioned fields are used with correct schema_version."""
        # V3 field validation
        v3_fields = {
            "audio_filter": self.audio_filter,
            "subtitle_filter": self.subtitle_filter,
            "attachment_filter": self.attachment_filter,
            "container": self.container,
        }
        used_v3_fields = [
            name for name, value in v3_fields.items() if value is not None
        ]

        if used_v3_fields and self.schema_version < 3:
            fields_str = ", ".join(used_v3_fields)
            raise ValueError(
                f"V3 fields ({fields_str}) require schema_version >= 3, "
                f"but schema_version is {self.schema_version}"
            )

        # V4 field validation
        if self.conditional is not None and self.schema_version < 4:
            raise ValueError(
                f"V4 fields (conditional) require schema_version >= 4, "
                f"but schema_version is {self.schema_version}"
            )

        # V5 field validation
        if self.audio_synthesis is not None and self.schema_version < 5:
            raise ValueError(
                f"V5 fields (audio_synthesis) require schema_version >= 5, "
                f"but schema_version is {self.schema_version}"
            )

        return self

    @field_validator("track_order")
    @classmethod
    def validate_track_order(cls, v: list[str]) -> list[str]:
        """Validate track order contains valid track types."""
        if not v:
            raise ValueError("track_order cannot be empty")

        valid_types = {t.value for t in TrackType}
        for idx, track_type in enumerate(v):
            if track_type not in valid_types:
                raise ValueError(
                    f"Unknown track type '{track_type}' at track_order[{idx}]. "
                    f"Valid types: {', '.join(sorted(valid_types))}"
                )
        return v

    @field_validator("audio_language_preference", "subtitle_language_preference")
    @classmethod
    def validate_language_preference(cls, v: list[str]) -> list[str]:
        """Validate language preference contains valid ISO 639-2 codes."""
        if not v:
            raise ValueError("Language preference cannot be empty")

        import re

        pattern = re.compile(r"^[a-z]{2,3}$")
        for idx, lang in enumerate(v):
            if not pattern.match(lang):
                raise ValueError(
                    f"Invalid language code '{lang}' at index {idx}. "
                    "Use ISO 639-2 codes (e.g., 'eng', 'jpn')."
                )
        return v

    @field_validator("commentary_patterns")
    @classmethod
    def validate_commentary_patterns(cls, v: list[str]) -> list[str]:
        """Validate commentary patterns are valid regex."""
        errors = validate_regex_patterns(v)
        if errors:
            raise ValueError(errors[0])
        return v


# =============================================================================
# V4 Conversion Functions for Conditional Rules
# =============================================================================


def _convert_comparison(model: ComparisonModel) -> Comparison:
    """Convert ComparisonModel to Comparison dataclass."""
    for op_name, op_enum in [
        ("eq", ComparisonOperator.EQ),
        ("lt", ComparisonOperator.LT),
        ("lte", ComparisonOperator.LTE),
        ("gt", ComparisonOperator.GT),
        ("gte", ComparisonOperator.GTE),
    ]:
        val = getattr(model, op_name)
        if val is not None:
            return Comparison(operator=op_enum, value=val)
    # Should never happen due to validation
    raise ValueError("No comparison operator found")


def _convert_title_match(model: TitleMatchModel) -> TitleMatch:
    """Convert TitleMatchModel to TitleMatch dataclass."""
    return TitleMatch(contains=model.contains, regex=model.regex)


def _convert_track_filters(
    *,
    language: str | list[str] | None = None,
    codec: str | list[str] | None = None,
    is_default: bool | None = None,
    is_forced: bool | None = None,
    channels: int | ComparisonModel | None = None,
    width: int | ComparisonModel | None = None,
    height: int | ComparisonModel | None = None,
    title: str | TitleMatchModel | None = None,
) -> TrackFilters:
    """Convert filter fields to TrackFilters dataclass."""
    # Normalize language to tuple
    lang_tuple: str | tuple[str, ...] | None = None
    if language is not None:
        if isinstance(language, list):
            lang_tuple = tuple(language)
        else:
            lang_tuple = language

    # Normalize codec to tuple
    codec_tuple: str | tuple[str, ...] | None = None
    if codec is not None:
        if isinstance(codec, list):
            codec_tuple = tuple(codec)
        else:
            codec_tuple = codec

    # Convert channels comparison
    channels_val: int | Comparison | None = None
    if channels is not None:
        if isinstance(channels, ComparisonModel):
            channels_val = _convert_comparison(channels)
        else:
            channels_val = channels

    # Convert width comparison
    width_val: int | Comparison | None = None
    if width is not None:
        if isinstance(width, ComparisonModel):
            width_val = _convert_comparison(width)
        else:
            width_val = width

    # Convert height comparison
    height_val: int | Comparison | None = None
    if height is not None:
        if isinstance(height, ComparisonModel):
            height_val = _convert_comparison(height)
        else:
            height_val = height

    # Convert title match
    title_val: str | TitleMatch | None = None
    if title is not None:
        if isinstance(title, TitleMatchModel):
            title_val = _convert_title_match(title)
        else:
            title_val = title

    return TrackFilters(
        language=lang_tuple,
        codec=codec_tuple,
        is_default=is_default,
        is_forced=is_forced,
        channels=channels_val,
        width=width_val,
        height=height_val,
        title=title_val,
    )


def _convert_exists_condition(model: ExistsConditionModel) -> ExistsCondition:
    """Convert ExistsConditionModel to ExistsCondition dataclass."""
    filters = _convert_track_filters(
        language=model.language,
        codec=model.codec,
        is_default=model.is_default,
        is_forced=model.is_forced,
        channels=model.channels,
        width=model.width,
        height=model.height,
        title=model.title,
    )
    return ExistsCondition(track_type=model.track_type, filters=filters)


def _convert_count_condition(model: CountConditionModel) -> CountCondition:
    """Convert CountConditionModel to CountCondition dataclass."""
    filters = _convert_track_filters(
        language=model.language,
        codec=model.codec,
        is_default=model.is_default,
        is_forced=model.is_forced,
        channels=model.channels,
        width=model.width,
        height=model.height,
        title=model.title,
    )

    # Get count comparison operator
    for op_name, op_enum in [
        ("eq", ComparisonOperator.EQ),
        ("lt", ComparisonOperator.LT),
        ("lte", ComparisonOperator.LTE),
        ("gt", ComparisonOperator.GT),
        ("gte", ComparisonOperator.GTE),
    ]:
        val = getattr(model, op_name)
        if val is not None:
            return CountCondition(
                track_type=model.track_type,
                filters=filters,
                operator=op_enum,
                value=val,
            )

    # Should never happen due to validation
    raise ValueError("No count comparison operator found")


def _convert_condition(model: ConditionModel) -> Condition:
    """Convert ConditionModel to Condition type."""
    if model.exists is not None:
        return _convert_exists_condition(model.exists)

    if model.count is not None:
        return _convert_count_condition(model.count)

    if model.all_of is not None:
        return AndCondition(
            conditions=tuple(_convert_condition(c) for c in model.all_of)
        )

    if model.any_of is not None:
        return OrCondition(
            conditions=tuple(_convert_condition(c) for c in model.any_of)
        )

    if model.not_ is not None:
        return NotCondition(inner=_convert_condition(model.not_))

    # Should never happen due to validation
    raise ValueError("No condition type found")


def _convert_action(model: ActionModel) -> tuple[ConditionalAction, ...]:
    """Convert ActionModel to tuple of ConditionalAction.

    A single ActionModel can contain multiple actions (e.g., both skip and warn).
    """
    actions: list[ConditionalAction] = []

    if model.skip_video_transcode is True:
        actions.append(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE))

    if model.skip_audio_transcode is True:
        actions.append(SkipAction(skip_type=SkipType.AUDIO_TRANSCODE))

    if model.skip_track_filter is True:
        actions.append(SkipAction(skip_type=SkipType.TRACK_FILTER))

    if model.warn is not None:
        actions.append(WarnAction(message=model.warn))

    if model.fail is not None:
        actions.append(FailAction(message=model.fail))

    return tuple(actions)


def _convert_actions(
    models: ActionModel | list[ActionModel] | None,
) -> tuple[ConditionalAction, ...] | None:
    """Convert action model(s) to tuple of ConditionalAction."""
    if models is None:
        return None

    if isinstance(models, list):
        actions: list[ConditionalAction] = []
        for m in models:
            actions.extend(_convert_action(m))
        return tuple(actions)

    return _convert_action(models)


def _convert_conditional_rule(model: ConditionalRuleModel) -> ConditionalRule:
    """Convert ConditionalRuleModel to ConditionalRule dataclass."""
    then_actions = _convert_actions(model.then)
    if then_actions is None:
        then_actions = ()

    else_actions = _convert_actions(model.else_)

    return ConditionalRule(
        name=model.name,
        when=_convert_condition(model.when),
        then_actions=then_actions,
        else_actions=else_actions,
    )


def _convert_conditional_rules(
    models: list[ConditionalRuleModel] | None,
) -> tuple[ConditionalRule, ...]:
    """Convert list of ConditionalRuleModel to tuple of ConditionalRule."""
    if models is None:
        return ()
    return tuple(_convert_conditional_rule(m) for m in models)


# =============================================================================
# V5 Conversion Functions for Audio Synthesis
# =============================================================================


def _convert_preference_criterion(
    model: PreferenceCriterionModel,
) -> dict:
    """Convert PreferenceCriterionModel to dict for storage."""
    result: dict = {}

    if model.language is not None:
        if isinstance(model.language, list):
            result["language"] = tuple(model.language)
        else:
            result["language"] = model.language

    if model.not_commentary is not None:
        result["not_commentary"] = model.not_commentary

    if model.channels is not None:
        if isinstance(model.channels, ChannelPreferenceModel):
            if model.channels.max:
                result["channels"] = "max"
            elif model.channels.min:
                result["channels"] = "min"
        else:
            result["channels"] = model.channels

    if model.codec is not None:
        if isinstance(model.codec, list):
            result["codec"] = tuple(model.codec)
        else:
            result["codec"] = model.codec

    return result


def _convert_synthesis_track_definition(
    model: SynthesisTrackDefinitionModel,
) -> SynthesisTrackDefinitionRef:
    """Convert SynthesisTrackDefinitionModel to SynthesisTrackDefinitionRef."""
    # Convert source preferences to tuple of dicts
    source_prefer = tuple(_convert_preference_criterion(p) for p in model.source.prefer)

    # Convert create_if condition if present
    create_if: Condition | None = None
    if model.create_if is not None:
        create_if = _convert_condition(model.create_if)

    return SynthesisTrackDefinitionRef(
        name=model.name,
        codec=model.codec,
        channels=model.channels,
        source_prefer=source_prefer,
        bitrate=model.bitrate,
        create_if=create_if,
        title=model.title,
        language=model.language,
        position=model.position,
    )


def _convert_audio_synthesis(
    model: AudioSynthesisModel | None,
) -> AudioSynthesisConfig | None:
    """Convert AudioSynthesisModel to AudioSynthesisConfig."""
    if model is None:
        return None

    tracks = tuple(_convert_synthesis_track_definition(t) for t in model.tracks)

    return AudioSynthesisConfig(tracks=tracks)


def _convert_to_policy_schema(model: PolicyModel) -> PolicySchema:
    """Convert validated Pydantic model to PolicySchema dataclass."""
    # Convert track order strings to TrackType enum
    track_order = tuple(TrackType(t) for t in model.track_order)

    # Convert default flags
    default_flags = DefaultFlagsConfig(
        set_first_video_default=model.default_flags.set_first_video_default,
        set_preferred_audio_default=model.default_flags.set_preferred_audio_default,
        set_preferred_subtitle_default=model.default_flags.set_preferred_subtitle_default,
        clear_other_defaults=model.default_flags.clear_other_defaults,
    )

    # Convert transcode config if present
    transcode: TranscodePolicyConfig | None = None
    if model.transcode is not None:
        transcode = TranscodePolicyConfig(
            target_video_codec=model.transcode.target_video_codec,
            target_crf=model.transcode.target_crf,
            target_bitrate=model.transcode.target_bitrate,
            max_resolution=model.transcode.max_resolution,
            max_width=model.transcode.max_width,
            max_height=model.transcode.max_height,
            audio_preserve_codecs=tuple(model.transcode.audio_preserve_codecs),
            audio_transcode_to=model.transcode.audio_transcode_to,
            audio_transcode_bitrate=model.transcode.audio_transcode_bitrate,
            audio_downmix=model.transcode.audio_downmix,
            destination=model.transcode.destination,
            destination_fallback=model.transcode.destination_fallback,
        )

    # Convert transcription config if present
    transcription: TranscriptionPolicyOptions | None = None
    if model.transcription is not None:
        transcription = TranscriptionPolicyOptions(
            enabled=model.transcription.enabled,
            update_language_from_transcription=model.transcription.update_language_from_transcription,
            confidence_threshold=model.transcription.confidence_threshold,
            detect_commentary=model.transcription.detect_commentary,
            reorder_commentary=model.transcription.reorder_commentary,
        )

    # Convert V3 audio_filter config if present
    audio_filter: AudioFilterConfig | None = None
    if model.audio_filter is not None:
        fallback: LanguageFallbackConfig | None = None
        if model.audio_filter.fallback is not None:
            fallback = LanguageFallbackConfig(mode=model.audio_filter.fallback.mode)
        audio_filter = AudioFilterConfig(
            languages=tuple(model.audio_filter.languages),
            fallback=fallback,
            minimum=model.audio_filter.minimum,
        )

    # Convert V3 subtitle_filter config if present
    subtitle_filter: SubtitleFilterConfig | None = None
    if model.subtitle_filter is not None:
        languages = None
        if model.subtitle_filter.languages is not None:
            languages = tuple(model.subtitle_filter.languages)
        subtitle_filter = SubtitleFilterConfig(
            languages=languages,
            preserve_forced=model.subtitle_filter.preserve_forced,
            remove_all=model.subtitle_filter.remove_all,
        )

    # Convert V3 attachment_filter config if present
    attachment_filter: AttachmentFilterConfig | None = None
    if model.attachment_filter is not None:
        attachment_filter = AttachmentFilterConfig(
            remove_all=model.attachment_filter.remove_all,
        )

    # Convert V3 container config if present
    container: ContainerConfig | None = None
    if model.container is not None:
        container = ContainerConfig(
            target=model.container.target,
            on_incompatible_codec=model.container.on_incompatible_codec,
        )

    # Convert V4 conditional rules if present
    conditional_rules = _convert_conditional_rules(model.conditional)

    # Convert V5 audio synthesis if present
    audio_synthesis = _convert_audio_synthesis(model.audio_synthesis)

    return PolicySchema(
        schema_version=model.schema_version,
        track_order=track_order,
        audio_language_preference=tuple(model.audio_language_preference),
        subtitle_language_preference=tuple(model.subtitle_language_preference),
        commentary_patterns=tuple(model.commentary_patterns),
        default_flags=default_flags,
        transcode=transcode,
        transcription=transcription,
        audio_filter=audio_filter,
        subtitle_filter=subtitle_filter,
        attachment_filter=attachment_filter,
        container=container,
        conditional_rules=conditional_rules,
        audio_synthesis=audio_synthesis,
    )


def load_policy(policy_path: Path) -> PolicySchema:
    """Load and validate a policy from a YAML file.

    Args:
        policy_path: Path to the YAML policy file.

    Returns:
        Validated PolicySchema object.

    Raises:
        PolicyValidationError: If the policy file is invalid.
        FileNotFoundError: If the policy file does not exist.
    """
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    try:
        with open(policy_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise PolicyValidationError(f"Invalid YAML syntax: {e}") from e

    if data is None:
        raise PolicyValidationError("Policy file is empty")

    if not isinstance(data, dict):
        raise PolicyValidationError("Policy file must be a YAML mapping")

    return load_policy_from_dict(data)


def load_policy_from_dict(data: dict[str, Any]) -> PolicySchema:
    """Load and validate a policy from a dictionary.

    Args:
        data: Dictionary containing policy configuration.

    Returns:
        Validated PolicySchema object.

    Raises:
        PolicyValidationError: If the policy data is invalid.
    """
    try:
        model = PolicyModel.model_validate(data)
    except Exception as e:
        # Transform Pydantic errors to user-friendly messages
        error_msg = _format_validation_error(e)
        raise PolicyValidationError(error_msg) from e

    return _convert_to_policy_schema(model)


def _format_validation_error(error: Exception) -> str:
    """Format a Pydantic validation error into a user-friendly message."""
    from pydantic import ValidationError

    if isinstance(error, ValidationError):
        # Get the first error
        errors = error.errors()
        if errors:
            first_error = errors[0]
            loc = ".".join(str(x) for x in first_error.get("loc", []))
            msg = first_error.get("msg", str(error))
            if loc:
                return f"Policy validation failed: {loc}: {msg}"
            return f"Policy validation failed: {msg}"

    return f"Policy validation failed: {error}"
