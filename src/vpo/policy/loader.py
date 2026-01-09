"""Policy file loading and validation.

This module provides functions to load YAML policy files and validate
them using Pydantic models.
"""

from pathlib import Path
from typing import Any, Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vpo.policy.matchers import validate_regex_patterns
from vpo.policy.models import (
    DEFAULT_TRACK_ORDER,
    VALID_AUDIO_CODECS,
    VALID_PRESETS,
    VALID_RESOLUTIONS,
    VALID_VIDEO_CODECS,
    X264_X265_TUNES,
    AndCondition,
    AttachmentFilterConfig,
    AudioActionsConfig,
    AudioFilterConfig,
    AudioIsMultiLanguageCondition,
    AudioSynthesisConfig,
    AudioTranscodeConfig,
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
    GlobalConfig,
    HardwareAccelConfig,
    HardwareAccelMode,
    IsDubbedCondition,
    IsOriginalCondition,
    LanguageFallbackConfig,
    NotCondition,
    OnErrorMode,
    OrCondition,
    PhaseDefinition,
    PhasedPolicySchema,
    PhaseSkipCondition,
    PluginMetadataCondition,
    PluginMetadataOperator,
    PluginMetadataReference,
    PolicySchema,
    ProcessingPhase,
    QualityMode,
    QualitySettings,
    RunIfCondition,
    ScaleAlgorithm,
    ScalingSettings,
    SetDefaultAction,
    SetForcedAction,
    SetLanguageAction,
    SkipAction,
    SkipCondition,
    SkipIfExistsCriteria,
    SkipType,
    SubtitleActionsConfig,
    SubtitleFilterConfig,
    SynthesisTrackDefinitionRef,
    TitleMatch,
    TrackFilters,
    TrackType,
    TranscodePolicyConfig,
    TranscriptionPolicyOptions,
    VideoTranscodeConfig,
    WarnAction,
    WorkflowConfig,
    parse_bitrate,
)
from vpo.policy.parsing import (
    parse_duration as _parse_duration,
)
from vpo.policy.parsing import (
    parse_file_size as _parse_file_size,
)

# Current supported schema version (only V12 is supported)
SCHEMA_VERSION = 12

# Backward compatibility alias (deprecated)
MAX_SCHEMA_VERSION = SCHEMA_VERSION

# Reserved phase names that cannot be used as user-defined phase names
RESERVED_PHASE_NAMES = frozenset({"config", "schema_version", "phases"})


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
    set_subtitle_default_when_audio_differs: bool = False
    set_subtitle_forced_when_audio_differs: bool = False


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
        if v is not None and v.casefold() not in VALID_VIDEO_CODECS:
            raise ValueError(
                f"Invalid video codec '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_VIDEO_CODECS))}"
            )
        return v

    @field_validator("max_resolution")
    @classmethod
    def validate_resolution(cls, v: str | None) -> str | None:
        """Validate resolution preset."""
        if v is not None and v.casefold() not in VALID_RESOLUTIONS:
            raise ValueError(
                f"Invalid resolution '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
            )
        return v

    @field_validator("audio_transcode_to")
    @classmethod
    def validate_audio_codec(cls, v: str) -> str:
        """Validate audio codec."""
        if v.casefold() not in VALID_AUDIO_CODECS:
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
# V6 Pydantic Models for Conditional Video Transcoding
# =============================================================================


class SkipConditionModel(BaseModel):
    """Pydantic model for skip condition configuration."""

    model_config = ConfigDict(extra="forbid")

    codec_matches: list[str] | None = None
    resolution_within: str | None = None
    bitrate_under: str | None = None

    @field_validator("resolution_within")
    @classmethod
    def validate_resolution(cls, v: str | None) -> str | None:
        """Validate resolution preset."""
        if v is not None and v.casefold() not in VALID_RESOLUTIONS:
            raise ValueError(
                f"Invalid resolution_within '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
            )
        return v

    @field_validator("bitrate_under")
    @classmethod
    def validate_bitrate(cls, v: str | None) -> str | None:
        """Validate bitrate format."""
        if v is not None:
            if parse_bitrate(v) is None:
                raise ValueError(
                    f"Invalid bitrate_under '{v}'. "
                    "Must be a number followed by M or k (e.g., '10M', '5000k')."
                )
        return v


class QualitySettingsModel(BaseModel):
    """Pydantic model for video quality settings."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["crf", "bitrate", "constrained_quality"] = "crf"
    crf: int | None = Field(default=None, ge=0, le=51)
    bitrate: str | None = None
    min_bitrate: str | None = None
    max_bitrate: str | None = None
    preset: str = "medium"
    tune: str | None = None
    two_pass: bool = False

    @field_validator("preset")
    @classmethod
    def validate_preset(cls, v: str) -> str:
        """Validate encoding preset."""
        if v not in VALID_PRESETS:
            raise ValueError(
                f"Invalid preset '{v}'. Must be one of: {', '.join(VALID_PRESETS)}"
            )
        return v

    @field_validator("tune")
    @classmethod
    def validate_tune(cls, v: str | None) -> str | None:
        """Validate tune option."""
        if v is not None and v not in X264_X265_TUNES:
            raise ValueError(
                f"Invalid tune '{v}'. Must be one of: {', '.join(X264_X265_TUNES)}"
            )
        return v

    @field_validator("bitrate", "min_bitrate", "max_bitrate")
    @classmethod
    def validate_bitrate(cls, v: str | None) -> str | None:
        """Validate bitrate format."""
        if v is not None:
            if parse_bitrate(v) is None:
                raise ValueError(
                    f"Invalid bitrate '{v}'. "
                    "Must be a number followed by M or k (e.g., '5M', '2500k')."
                )
        return v

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> "QualitySettingsModel":
        """Validate mode-specific requirements and detect conflicting options."""
        if self.mode == "bitrate" and self.bitrate is None:
            raise ValueError("bitrate is required when mode is 'bitrate'")

        # Warn about conflicting options that may indicate user error
        if self.mode == "crf" and self.bitrate is not None:
            raise ValueError(
                "Conflicting options: mode is 'crf' but bitrate is specified. "
                "Use mode='bitrate' for bitrate targeting, or "
                "mode='constrained_quality' for CRF with max bitrate cap."
            )

        if self.mode == "bitrate" and self.crf is not None:
            raise ValueError(
                "Conflicting options: mode is 'bitrate' but crf is specified. "
                "Use mode='crf' for quality-based encoding, or "
                "mode='constrained_quality' for CRF with max bitrate cap."
            )

        return self


class ScalingSettingsModel(BaseModel):
    """Pydantic model for video scaling settings."""

    model_config = ConfigDict(extra="forbid")

    max_resolution: str | None = None
    max_width: int | None = Field(default=None, ge=1)
    max_height: int | None = Field(default=None, ge=1)
    algorithm: Literal["lanczos", "bicubic", "bilinear"] = "lanczos"
    upscale: bool = False

    @field_validator("max_resolution")
    @classmethod
    def validate_resolution(cls, v: str | None) -> str | None:
        """Validate resolution preset."""
        if v is not None and v.casefold() not in VALID_RESOLUTIONS:
            raise ValueError(
                f"Invalid max_resolution '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
            )
        return v


class HardwareAccelConfigModel(BaseModel):
    """Pydantic model for hardware acceleration settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: Literal["auto", "nvenc", "qsv", "vaapi", "none"] = "auto"
    fallback_to_cpu: bool = True


class VideoTranscodeConfigModel(BaseModel):
    """Pydantic model for V6 video transcode configuration."""

    model_config = ConfigDict(extra="forbid")

    target_codec: str

    skip_if: SkipConditionModel | None = None
    quality: QualitySettingsModel | None = None
    scaling: ScalingSettingsModel | None = None
    hardware_acceleration: HardwareAccelConfigModel | None = None

    @field_validator("target_codec")
    @classmethod
    def validate_video_codec(cls, v: str) -> str:
        """Validate video codec."""
        if v.casefold() not in VALID_VIDEO_CODECS:
            raise ValueError(
                f"Invalid target_codec '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_VIDEO_CODECS))}"
            )
        return v


class AudioTranscodeConfigModel(BaseModel):
    """Pydantic model for V6 audio transcode configuration."""

    model_config = ConfigDict(extra="forbid")

    preserve_codecs: list[str] = Field(
        default_factory=lambda: ["truehd", "dts-hd", "flac", "pcm_s24le"]
    )
    transcode_to: str = "aac"
    transcode_bitrate: str = "192k"

    @field_validator("transcode_to")
    @classmethod
    def validate_audio_codec(cls, v: str) -> str:
        """Validate audio codec."""
        if v.casefold() not in VALID_AUDIO_CODECS:
            raise ValueError(
                f"Invalid transcode_to '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_AUDIO_CODECS))}"
            )
        return v

    @field_validator("transcode_bitrate")
    @classmethod
    def validate_bitrate(cls, v: str) -> str:
        """Validate bitrate format."""
        if parse_bitrate(v) is None:
            raise ValueError(
                f"Invalid transcode_bitrate '{v}'. "
                "Must be a number followed by k (e.g., '192k', '256k')."
            )
        return v


class TranscodeV6Model(BaseModel):
    """Pydantic model for V6 transcode configuration with video/audio sections."""

    model_config = ConfigDict(extra="forbid")

    video: VideoTranscodeConfigModel | None = None
    audio: AudioTranscodeConfigModel | None = None


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
    """Pydantic model for audio filter configuration.

    V10: Added support for music, sfx, and non-speech track handling.
    """

    model_config = ConfigDict(extra="forbid")

    languages: list[str]
    fallback: LanguageFallbackModel | None = None
    minimum: int = Field(default=1, ge=1)

    # V10: Music track handling
    keep_music_tracks: bool = True
    exclude_music_from_language_filter: bool = True

    # V10: SFX track handling
    keep_sfx_tracks: bool = True
    exclude_sfx_from_language_filter: bool = True

    # V10: Non-speech track handling
    keep_non_speech_tracks: bool = True
    exclude_non_speech_from_language_filter: bool = True

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


class AudioActionsModel(BaseModel):
    """Pydantic model for audio track pre-processing actions.

    Actions are applied BEFORE filtering to clean up misconfigured metadata.
    """

    model_config = ConfigDict(extra="forbid")

    clear_all_forced: bool = False
    clear_all_default: bool = False
    clear_all_titles: bool = False


class SubtitleActionsModel(BaseModel):
    """Pydantic model for subtitle track pre-processing actions.

    Actions are applied BEFORE filtering to clean up misconfigured metadata.
    """

    model_config = ConfigDict(extra="forbid")

    clear_all_forced: bool = False
    clear_all_default: bool = False
    clear_all_titles: bool = False


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
            return v.casefold()
        return [lang.casefold() for lang in v]

    @field_validator("codec", mode="before")
    @classmethod
    def normalize_codec(cls, v: str | list[str] | None) -> str | list[str] | None:
        """Normalize codec to lowercase."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.casefold()
        return [codec.casefold() for codec in v]


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


class SkipIfExistsModel(BaseModel):
    """Pydantic model for skip_if_exists criteria in audio synthesis.

    Allows synthesis to be skipped if a matching track already exists.
    All specified criteria must match (AND logic).
    """

    model_config = ConfigDict(extra="forbid")

    codec: str | list[str] | None = None
    channels: Union[int, "ComparisonModel", None] = None
    language: str | list[str] | None = None
    not_commentary: bool | None = None

    @field_validator("codec", mode="before")
    @classmethod
    def normalize_codec(cls, v: str | list[str] | None) -> str | list[str] | None:
        """Normalize codec to lowercase."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.casefold()
        return [codec.casefold() for codec in v]

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, v: str | list[str] | None) -> str | list[str] | None:
        """Normalize language to lowercase."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.casefold()
        return [lang.casefold() for lang in v]


class SynthesisTrackDefinitionModel(BaseModel):
    """Pydantic model for a synthesis track definition."""

    model_config = ConfigDict(extra="forbid")

    name: str
    codec: str
    channels: str | int
    source: SourcePreferencesModel
    bitrate: str | None = None
    create_if: "ConditionModel | None" = None
    skip_if_exists: SkipIfExistsModel | None = None
    title: str | Literal["inherit"] = "inherit"
    language: str | Literal["inherit"] = "inherit"
    position: Literal["after_source", "end"] | int = "end"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is non-empty and path-safe.

        Security: The name is used in file path construction (synth_{name}.ext)
        in executor.py. Path traversal sequences and separators must be rejected
        to prevent directory escape attacks.

        Note: The '..' check is intentionally conservative - it rejects any name
        containing '..' even if not a true path traversal (e.g., "Track..v2").
        """
        if not v or not v.strip():
            raise ValueError("Synthesis track name cannot be empty")
        v = v.strip()
        # Reject path traversal sequences and separators
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError(
                f"Synthesis track name cannot contain path separators or '..': {v!r}"
            )
        return v

    @field_validator("codec")
    @classmethod
    def validate_codec(cls, v: str) -> str:
        """Validate that codec is supported."""
        v_lower = v.casefold()
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
        v_lower = v.casefold()
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
        return v.casefold()

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

        if not re.match(r"^[a-z]{2,3}$", v.casefold()):
            raise ValueError(
                f"Invalid language code '{v}'. "
                "Use ISO 639-2 codes (e.g., 'eng', 'jpn') or 'inherit'"
            )
        return v.casefold()


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


class WorkflowConfigModel(BaseModel):
    """Pydantic model for workflow configuration (V9+)."""

    model_config = ConfigDict(extra="forbid")

    phases: list[str]
    """Processing phases to run in order."""

    auto_process: bool = False
    """If True, daemon auto-queues PROCESS jobs when files are scanned."""

    on_error: Literal["skip", "continue", "fail"] = "continue"
    """Error handling mode."""

    @field_validator("phases")
    @classmethod
    def validate_phases(cls, v: list[str]) -> list[str]:
        """Validate phases list."""
        if not v:
            raise ValueError("workflow.phases cannot be empty")

        valid_phases = {p.value for p in ProcessingPhase}
        for phase in v:
            if phase not in valid_phases:
                raise ValueError(
                    f"Invalid phase '{phase}'. "
                    f"Valid phases: {', '.join(sorted(valid_phases))}"
                )

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate phases not allowed")

        return v


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
    not_commentary: bool | None = None  # V8: exclude commentary tracks


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
    not_commentary: bool | None = None  # V8: exclude commentary tracks


class CountConditionModel(BaseModel):
    """Pydantic model for count condition."""

    model_config = ConfigDict(extra="forbid")

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


class AudioIsMultiLanguageModel(BaseModel):
    """Pydantic model for audio multi-language condition.

    Checks if an audio track contains multiple detected languages.
    Requires language analysis to have been performed on the track.
    """

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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
        if not v or not v.strip():
            raise ValueError("field name cannot be empty")
        return v.strip().casefold()

    @model_validator(mode="after")
    def validate_operator_value_compatibility(self) -> "PluginMetadataConditionModel":
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

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

    value: bool = True
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    language: str | None = None


class ConditionModel(BaseModel):
    """Pydantic model for condition (union of condition types)."""

    model_config = ConfigDict(extra="forbid")

    # Leaf conditions
    exists: ExistsConditionModel | None = None
    count: CountConditionModel | None = None
    audio_is_multi_language: AudioIsMultiLanguageModel | None = None
    plugin_metadata: PluginMetadataConditionModel | None = None  # V12+
    is_original: IsOriginalConditionModel | bool | None = None  # V12+, 044 feature
    is_dubbed: IsDubbedConditionModel | bool | None = None  # V12+, 044 feature

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
            ("audio_is_multi_language", self.audio_is_multi_language),
            ("plugin_metadata", self.plugin_metadata),
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
                    "is_original/is_dubbed/and/or/not)"
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


class SetForcedActionModel(BaseModel):
    """Pydantic model for set_forced action.

    Sets the forced flag on matching subtitle tracks.
    """

    model_config = ConfigDict(extra="forbid")

    track_type: Literal["subtitle"] = "subtitle"
    language: str | None = None
    value: bool = True


class SetDefaultActionModel(BaseModel):
    """Pydantic model for set_default action.

    Sets the default flag on matching tracks.
    """

    model_config = ConfigDict(extra="forbid")

    track_type: Literal["video", "audio", "subtitle"]
    language: str | None = None
    value: bool = True


class PluginMetadataReferenceModel(BaseModel):
    """Pydantic model for referencing plugin metadata values.

    Used to dynamically pull values from plugin metadata at runtime.
    """

    model_config = ConfigDict(extra="forbid")

    plugin: str
    field: str

    @field_validator("plugin")
    @classmethod
    def validate_plugin_name(cls, v: str) -> str:
        """Validate and normalize plugin name to lowercase."""
        if not v or not v.strip():
            raise ValueError("plugin name cannot be empty")
        return v.strip().casefold()

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Validate and normalize field name to lowercase."""
        if not v or not v.strip():
            raise ValueError("field name cannot be empty")
        return v.strip().casefold()


class SetLanguageActionModel(BaseModel):
    """Pydantic model for set_language action.

    Sets the language tag on matching tracks. Either new_language or
    from_plugin_metadata must be specified, but not both.
    """

    model_config = ConfigDict(extra="forbid")

    track_type: Literal["video", "audio", "subtitle"]
    new_language: str | None = None
    from_plugin_metadata: PluginMetadataReferenceModel | None = None
    match_language: str | None = None

    @model_validator(mode="after")
    def validate_language_source(self) -> "SetLanguageActionModel":
        """Validate that exactly one language source is specified."""
        has_static = self.new_language is not None
        has_dynamic = self.from_plugin_metadata is not None

        if not has_static and not has_dynamic:
            raise ValueError(
                "set_language must specify either 'new_language' or "
                "'from_plugin_metadata'"
            )
        if has_static and has_dynamic:
            raise ValueError(
                "set_language cannot specify both 'new_language' and "
                "'from_plugin_metadata'"
            )
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

    # Track flag actions
    set_forced: SetForcedActionModel | None = None
    set_default: SetDefaultActionModel | None = None

    # Track metadata actions
    set_language: SetLanguageActionModel | None = None

    @model_validator(mode="after")
    def validate_at_least_one_action(self) -> "ActionModel":
        """Validate that at least one action is specified."""
        actions = [
            self.skip_video_transcode,
            self.skip_audio_transcode,
            self.skip_track_filter,
            self.warn,
            self.fail,
            self.set_forced,
            self.set_default,
            self.set_language,
        ]
        if not any(a is not None for a in actions):
            raise ValueError(
                "Action must specify at least one action "
                "(skip_video_transcode/skip_audio_transcode/skip_track_filter/"
                "warn/fail/set_forced/set_default/set_language)"
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

    schema_version: Literal[12] = 12
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
    transcode: TranscodePolicyModel | TranscodeV6Model | None = None
    transcription: TranscriptionPolicyModel | None = None

    # Track actions (pre-processing, applied before filters)
    audio_actions: AudioActionsModel | None = None
    subtitle_actions: SubtitleActionsModel | None = None

    # Track filtering configuration
    audio_filter: AudioFilterModel | None = None
    subtitle_filter: SubtitleFilterModel | None = None
    attachment_filter: AttachmentFilterModel | None = None
    container: ContainerModel | None = None

    # Conditional rules
    conditional: list[ConditionalRuleModel] | None = None

    # Audio synthesis
    audio_synthesis: AudioSynthesisModel | None = None

    # Workflow configuration
    workflow: WorkflowConfigModel | None = None

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
# V11 Pydantic Models for User-Defined Phases
# =============================================================================


# Phase name validation pattern: starts with letter, alphanumeric + hyphen + underscore
PHASE_NAME_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$"


class GlobalConfigModel(BaseModel):
    """Pydantic model for V11 global configuration."""

    model_config = ConfigDict(extra="forbid")

    audio_language_preference: list[str] = Field(default_factory=lambda: ["eng", "und"])
    """Ordered list of preferred audio languages (ISO 639-2/B codes)."""

    subtitle_language_preference: list[str] = Field(
        default_factory=lambda: ["eng", "und"]
    )
    """Ordered list of preferred subtitle languages (ISO 639-2/B codes)."""

    commentary_patterns: list[str] = Field(
        default_factory=lambda: ["commentary", "director", "audio description"]
    )
    """Patterns to match commentary track titles."""

    on_error: Literal["skip", "continue", "fail"] = "continue"
    """How to handle errors during phase execution."""

    @field_validator("audio_language_preference", "subtitle_language_preference")
    @classmethod
    def validate_language_codes(cls, v: list[str]) -> list[str]:
        """Validate language codes are valid ISO 639-2/B format."""
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
    def validate_patterns(cls, v: list[str]) -> list[str]:
        """Validate commentary patterns are valid regex."""
        errors = validate_regex_patterns(v)
        if errors:
            raise ValueError(errors[0])
        return v


# =============================================================================
# Conditional Phase Pydantic Models
# =============================================================================


class PhaseSkipConditionModel(BaseModel):
    """Pydantic model for phase skip conditions.

    Multiple conditions use OR logic - phase is skipped if ANY matches.
    """

    model_config = ConfigDict(extra="forbid")

    video_codec: list[str] | None = None
    """Skip if video codec matches any in this list."""

    audio_codec_exists: str | None = None
    """Skip if an audio track with this codec exists."""

    subtitle_language_exists: str | None = None
    """Skip if a subtitle track with this language exists."""

    container: list[str] | None = None
    """Skip if container format matches any in this list."""

    resolution: str | None = None
    """Skip if video resolution matches exactly."""

    resolution_under: str | None = None
    """Skip if video resolution is under this threshold."""

    file_size_under: str | None = None
    """Skip if file size is under this value."""

    file_size_over: str | None = None
    """Skip if file size is over this value."""

    duration_under: str | None = None
    """Skip if duration is under this value."""

    duration_over: str | None = None
    """Skip if duration is over this value."""

    @field_validator("video_codec")
    @classmethod
    def normalize_video_codecs(cls, v: list[str] | None) -> list[str] | None:
        """Normalize video codec names to lowercase."""
        if v is None:
            return None
        return [c.casefold() for c in v]

    @field_validator("audio_codec_exists")
    @classmethod
    def normalize_audio_codec(cls, v: str | None) -> str | None:
        """Normalize audio codec to lowercase."""
        return v.casefold() if v else None

    @field_validator("subtitle_language_exists")
    @classmethod
    def normalize_subtitle_language(cls, v: str | None) -> str | None:
        """Normalize language code to lowercase."""
        return v.casefold() if v else None

    @field_validator("container")
    @classmethod
    def normalize_containers(cls, v: list[str] | None) -> list[str] | None:
        """Normalize container formats to lowercase."""
        if v is None:
            return None
        return [c.casefold() for c in v]

    @field_validator("resolution", "resolution_under")
    @classmethod
    def validate_resolution(cls, v: str | None) -> str | None:
        """Validate resolution format."""
        if v is None:
            return None
        valid_resolutions = {"480p", "720p", "1080p", "1440p", "2160p", "4k"}
        if v.casefold() not in valid_resolutions:
            raise ValueError(
                f"Invalid resolution '{v}'. "
                f"Valid values: {', '.join(sorted(valid_resolutions))}"
            )
        return v.casefold()

    @field_validator("file_size_under", "file_size_over")
    @classmethod
    def validate_file_size(cls, v: str | None) -> str | None:
        """Validate file size format."""
        if v is None:
            return None
        if _parse_file_size(v) is None:
            raise ValueError(
                f"Invalid file size '{v}'. Use format like '500MB', '5GB', '1TB'."
            )
        return v

    @field_validator("duration_under", "duration_over")
    @classmethod
    def validate_duration(cls, v: str | None) -> str | None:
        """Validate duration format."""
        if v is None:
            return None
        if _parse_duration(v) is None:
            raise ValueError(
                f"Invalid duration '{v}'. Use format like '30m', '2h', '1h30m'."
            )
        return v

    @model_validator(mode="after")
    def validate_at_least_one_condition(self) -> "PhaseSkipConditionModel":
        """Validate that at least one condition is specified."""
        conditions = [
            self.video_codec,
            self.audio_codec_exists,
            self.subtitle_language_exists,
            self.container,
            self.resolution,
            self.resolution_under,
            self.file_size_under,
            self.file_size_over,
            self.duration_under,
            self.duration_over,
        ]
        if not any(c is not None for c in conditions):
            raise ValueError(
                "skip_when must specify at least one condition "
                "(video_codec, audio_codec_exists, file_size_under, etc.)"
            )
        return self


class RunIfConditionModel(BaseModel):
    """Pydantic model for run_if conditions.

    Exactly one condition must be specified.
    """

    model_config = ConfigDict(extra="forbid")

    phase_modified: str | None = None
    """Run only if the named phase modified the file."""

    phase_completed: str | None = None
    """Run only if the named phase completed (future extension)."""

    @model_validator(mode="after")
    def validate_exactly_one_condition(self) -> "RunIfConditionModel":
        """Validate that exactly one condition is specified."""
        conditions = [self.phase_modified, self.phase_completed]
        set_count = sum(1 for c in conditions if c is not None)
        if set_count != 1:
            raise ValueError(
                "run_if must specify exactly one condition (phase_modified)"
            )
        return self


class PhaseModel(BaseModel):
    """Pydantic model for a V11 phase definition."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=PHASE_NAME_PATTERN)
    """User-defined phase name."""

    # Operations (all optional)
    container: ContainerModel | None = None
    audio_filter: AudioFilterModel | None = None
    subtitle_filter: SubtitleFilterModel | None = None
    attachment_filter: AttachmentFilterModel | None = None
    track_order: list[str] | None = None
    default_flags: DefaultFlagsModel | None = None
    conditional: list[ConditionalRuleModel] | None = None
    audio_synthesis: AudioSynthesisModel | None = None
    transcode: TranscodeV6Model | None = None
    transcription: TranscriptionPolicyModel | None = None
    audio_actions: AudioActionsModel | None = None
    subtitle_actions: SubtitleActionsModel | None = None

    # Conditional phase execution
    skip_when: PhaseSkipConditionModel | None = None
    """Conditions that cause this phase to be skipped."""

    depends_on: list[str] | None = None
    """Phase names this phase depends on."""

    run_if: RunIfConditionModel | None = None
    """Positive run condition."""

    on_error: Literal["skip", "continue", "fail"] | None = Field(None, alias="on_error")
    """Per-phase error handling override."""

    @field_validator("name")
    @classmethod
    def validate_not_reserved(cls, v: str) -> str:
        """Validate that phase name is not a reserved word."""
        if v.casefold() in RESERVED_PHASE_NAMES:
            raise ValueError(
                f"Phase name '{v}' is reserved. "
                f"Reserved names: {', '.join(sorted(RESERVED_PHASE_NAMES))}"
            )
        return v

    @field_validator("track_order")
    @classmethod
    def validate_track_order(cls, v: list[str] | None) -> list[str] | None:
        """Validate track order contains valid track types."""
        if v is None:
            return None
        if not v:
            raise ValueError("track_order cannot be empty if specified")

        valid_types = {t.value for t in TrackType}
        for idx, track_type in enumerate(v):
            if track_type not in valid_types:
                raise ValueError(
                    f"Unknown track type '{track_type}' at track_order[{idx}]. "
                    f"Valid types: {', '.join(sorted(valid_types))}"
                )
        return v


class PhasedPolicyModel(BaseModel):
    """Pydantic model for phased policy with user-defined phases."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[12] = 12
    """Schema version, must be exactly 12."""

    config: GlobalConfigModel = Field(default_factory=GlobalConfigModel)
    """Global configuration."""

    phases: list[PhaseModel] = Field(..., min_length=1)
    """List of phase definitions (at least one required)."""

    @field_validator("phases")
    @classmethod
    def validate_unique_names(cls, v: list[PhaseModel]) -> list[PhaseModel]:
        """Validate that all phase names are unique (case-insensitive)."""
        names = [p.name for p in v]
        # Check for exact duplicates
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
        return v

    @model_validator(mode="after")
    def validate_phase_references(self) -> "PhasedPolicyModel":
        """Validate that depends_on and run_if reference valid, earlier phases."""
        phase_names = [p.name for p in self.phases]
        phase_index_map = {name: idx for idx, name in enumerate(phase_names)}

        for idx, phase in enumerate(self.phases):
            # Validate depends_on references
            if phase.depends_on:
                for dep_name in phase.depends_on:
                    if dep_name not in phase_index_map:
                        raise ValueError(
                            f"Phase '{phase.name}' depends on unknown phase "
                            f"'{dep_name}'. Valid phases: {', '.join(phase_names)}"
                        )
                    dep_idx = phase_index_map[dep_name]
                    if dep_idx >= idx:
                        raise ValueError(
                            f"Phase '{phase.name}' depends on '{dep_name}', but "
                            f"'{dep_name}' appears later or is the same phase. "
                            f"Dependencies must reference earlier phases."
                        )

            # Validate run_if references
            if phase.run_if:
                ref_name = phase.run_if.phase_modified or phase.run_if.phase_completed
                if ref_name and ref_name not in phase_index_map:
                    raise ValueError(
                        f"Phase '{phase.name}' run_if references unknown phase "
                        f"'{ref_name}'. Valid phases: {', '.join(phase_names)}"
                    )
                if ref_name:
                    ref_idx = phase_index_map[ref_name]
                    if ref_idx >= idx:
                        raise ValueError(
                            f"Phase '{phase.name}' run_if references '{ref_name}', "
                            f"but '{ref_name}' appears later or is the same phase. "
                            f"run_if must reference earlier phases."
                        )

        return self


# Backward compatibility alias (deprecated)
V11PolicyModel = PhasedPolicyModel


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
    not_commentary: bool | None = None,
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
        not_commentary=not_commentary,
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
        not_commentary=model.not_commentary,
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
        not_commentary=model.not_commentary,
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


def _convert_audio_is_multi_language_condition(
    model: AudioIsMultiLanguageModel,
) -> AudioIsMultiLanguageCondition:
    """Convert AudioIsMultiLanguageModel to AudioIsMultiLanguageCondition."""
    return AudioIsMultiLanguageCondition(
        track_index=model.track_index,
        threshold=model.threshold,
        primary_language=model.primary_language,
    )


def _convert_plugin_metadata_condition(
    model: PluginMetadataConditionModel,
) -> PluginMetadataCondition:
    """Convert PluginMetadataConditionModel to PluginMetadataCondition."""
    # Convert operator string to enum
    op_map = {
        "eq": PluginMetadataOperator.EQ,
        "neq": PluginMetadataOperator.NEQ,
        "contains": PluginMetadataOperator.CONTAINS,
        "lt": PluginMetadataOperator.LT,
        "lte": PluginMetadataOperator.LTE,
        "gt": PluginMetadataOperator.GT,
        "gte": PluginMetadataOperator.GTE,
        "exists": PluginMetadataOperator.EXISTS,
    }
    return PluginMetadataCondition(
        plugin=model.plugin,
        field=model.field,
        value=model.value,
        operator=op_map[model.operator],
    )


def _convert_is_original_condition(
    model: IsOriginalConditionModel | bool,
) -> IsOriginalCondition:
    """Convert is_original Pydantic model to domain condition.

    Handles two forms:
    1. Simple boolean: is_original: true
    2. Full object: is_original: { value: true, min_confidence: 0.8 }
    """
    if isinstance(model, bool):
        return IsOriginalCondition(value=model)

    return IsOriginalCondition(
        value=model.value,
        min_confidence=model.min_confidence,
        language=model.language,
    )


def _convert_is_dubbed_condition(
    model: IsDubbedConditionModel | bool,
) -> IsDubbedCondition:
    """Convert is_dubbed Pydantic model to domain condition.

    Handles two forms:
    1. Simple boolean: is_dubbed: true
    2. Full object: is_dubbed: { value: true, min_confidence: 0.8, language: eng }
    """
    if isinstance(model, bool):
        return IsDubbedCondition(value=model)

    return IsDubbedCondition(
        value=model.value,
        min_confidence=model.min_confidence,
        language=model.language,
    )


def _convert_condition(model: ConditionModel) -> Condition:
    """Convert ConditionModel to Condition type."""
    if model.exists is not None:
        return _convert_exists_condition(model.exists)

    if model.count is not None:
        return _convert_count_condition(model.count)

    if model.audio_is_multi_language is not None:
        return _convert_audio_is_multi_language_condition(model.audio_is_multi_language)

    if model.plugin_metadata is not None:
        return _convert_plugin_metadata_condition(model.plugin_metadata)

    if model.is_original is not None:
        return _convert_is_original_condition(model.is_original)

    if model.is_dubbed is not None:
        return _convert_is_dubbed_condition(model.is_dubbed)

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

    if model.set_forced is not None:
        actions.append(
            SetForcedAction(
                track_type=model.set_forced.track_type,
                language=model.set_forced.language,
                value=model.set_forced.value,
            )
        )

    if model.set_default is not None:
        actions.append(
            SetDefaultAction(
                track_type=model.set_default.track_type,
                language=model.set_default.language,
                value=model.set_default.value,
            )
        )

    if model.set_language is not None:
        from_plugin_ref = None
        if model.set_language.from_plugin_metadata is not None:
            from_plugin_ref = PluginMetadataReference(
                plugin=model.set_language.from_plugin_metadata.plugin,
                field=model.set_language.from_plugin_metadata.field,
            )
        actions.append(
            SetLanguageAction(
                track_type=model.set_language.track_type,
                new_language=model.set_language.new_language,
                from_plugin_metadata=from_plugin_ref,
                match_language=model.set_language.match_language,
            )
        )

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


def _convert_skip_if_exists(
    model: SkipIfExistsModel | None,
) -> SkipIfExistsCriteria | None:
    """Convert SkipIfExistsModel to SkipIfExistsCriteria dataclass."""
    if model is None:
        return None

    # Normalize codec to tuple
    codec: str | tuple[str, ...] | None = None
    if model.codec is not None:
        if isinstance(model.codec, list):
            codec = tuple(model.codec)
        else:
            codec = model.codec

    # Convert channels comparison
    channels: int | Comparison | None = None
    if model.channels is not None:
        if isinstance(model.channels, ComparisonModel):
            channels = _convert_comparison(model.channels)
        else:
            channels = model.channels

    # Normalize language to tuple
    language: str | tuple[str, ...] | None = None
    if model.language is not None:
        if isinstance(model.language, list):
            language = tuple(model.language)
        else:
            language = model.language

    return SkipIfExistsCriteria(
        codec=codec,
        channels=channels,
        language=language,
        not_commentary=model.not_commentary,
    )


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

    # Convert skip_if_exists criteria if present (V8+)
    skip_if_exists = _convert_skip_if_exists(model.skip_if_exists)

    return SynthesisTrackDefinitionRef(
        name=model.name,
        codec=model.codec,
        channels=model.channels,
        source_prefer=source_prefer,
        bitrate=model.bitrate,
        create_if=create_if,
        skip_if_exists=skip_if_exists,
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


# =============================================================================
# V6 Conversion Functions for Conditional Video Transcoding
# =============================================================================


def _convert_skip_condition(model: SkipConditionModel | None) -> SkipCondition | None:
    """Convert SkipConditionModel to SkipCondition dataclass."""
    if model is None:
        return None

    return SkipCondition(
        codec_matches=tuple(model.codec_matches) if model.codec_matches else None,
        resolution_within=model.resolution_within,
        bitrate_under=model.bitrate_under,
    )


def _convert_quality_settings(
    model: QualitySettingsModel | None,
) -> QualitySettings | None:
    """Convert QualitySettingsModel to QualitySettings dataclass."""
    if model is None:
        return None

    # Convert mode string to enum
    mode_map = {
        "crf": QualityMode.CRF,
        "bitrate": QualityMode.BITRATE,
        "constrained_quality": QualityMode.CONSTRAINED_QUALITY,
    }

    return QualitySettings(
        mode=mode_map[model.mode],
        crf=model.crf,
        bitrate=model.bitrate,
        min_bitrate=model.min_bitrate,
        max_bitrate=model.max_bitrate,
        preset=model.preset,
        tune=model.tune,
        two_pass=model.two_pass,
    )


def _convert_scaling_settings(
    model: ScalingSettingsModel | None,
) -> ScalingSettings | None:
    """Convert ScalingSettingsModel to ScalingSettings dataclass."""
    if model is None:
        return None

    # Convert algorithm string to enum
    algo_map = {
        "lanczos": ScaleAlgorithm.LANCZOS,
        "bicubic": ScaleAlgorithm.BICUBIC,
        "bilinear": ScaleAlgorithm.BILINEAR,
    }

    return ScalingSettings(
        max_resolution=model.max_resolution,
        max_width=model.max_width,
        max_height=model.max_height,
        algorithm=algo_map[model.algorithm],
        upscale=model.upscale,
    )


def _convert_hardware_accel_config(
    model: HardwareAccelConfigModel | None,
) -> HardwareAccelConfig | None:
    """Convert HardwareAccelConfigModel to HardwareAccelConfig dataclass."""
    if model is None:
        return None

    # Convert enabled string to enum
    mode_map = {
        "auto": HardwareAccelMode.AUTO,
        "nvenc": HardwareAccelMode.NVENC,
        "qsv": HardwareAccelMode.QSV,
        "vaapi": HardwareAccelMode.VAAPI,
        "none": HardwareAccelMode.NONE,
    }

    return HardwareAccelConfig(
        enabled=mode_map[model.enabled],
        fallback_to_cpu=model.fallback_to_cpu,
    )


def _convert_video_transcode_config(
    model: VideoTranscodeConfigModel | None,
) -> VideoTranscodeConfig | None:
    """Convert VideoTranscodeConfigModel to VideoTranscodeConfig dataclass."""
    if model is None:
        return None

    return VideoTranscodeConfig(
        target_codec=model.target_codec,
        skip_if=_convert_skip_condition(model.skip_if),
        quality=_convert_quality_settings(model.quality),
        scaling=_convert_scaling_settings(model.scaling),
        hardware_acceleration=_convert_hardware_accel_config(
            model.hardware_acceleration
        ),
    )


def _convert_audio_transcode_config(
    model: AudioTranscodeConfigModel | None,
) -> AudioTranscodeConfig | None:
    """Convert AudioTranscodeConfigModel to AudioTranscodeConfig dataclass."""
    if model is None:
        return None

    return AudioTranscodeConfig(
        preserve_codecs=tuple(model.preserve_codecs),
        transcode_to=model.transcode_to,
        transcode_bitrate=model.transcode_bitrate,
    )


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
        set_subtitle_default_when_audio_differs=model.default_flags.set_subtitle_default_when_audio_differs,
        set_subtitle_forced_when_audio_differs=model.default_flags.set_subtitle_forced_when_audio_differs,
    )

    # Convert transcode config (supports both V1-5 flat and V6 nested formats)
    transcode: TranscodePolicyConfig | None = None
    video_transcode: VideoTranscodeConfig | None = None
    audio_transcode: AudioTranscodeConfig | None = None

    if model.transcode is not None:
        if isinstance(model.transcode, TranscodeV6Model):
            # V6 nested format with video/audio sections
            video_transcode = _convert_video_transcode_config(model.transcode.video)
            audio_transcode = _convert_audio_transcode_config(model.transcode.audio)
        else:
            # V1-5 flat format (TranscodePolicyModel)
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

    # Convert track actions if present (applied before filters)
    audio_actions: AudioActionsConfig | None = None
    if model.audio_actions is not None:
        audio_actions = AudioActionsConfig(
            clear_all_forced=model.audio_actions.clear_all_forced,
            clear_all_default=model.audio_actions.clear_all_default,
            clear_all_titles=model.audio_actions.clear_all_titles,
        )

    subtitle_actions: SubtitleActionsConfig | None = None
    if model.subtitle_actions is not None:
        subtitle_actions = SubtitleActionsConfig(
            clear_all_forced=model.subtitle_actions.clear_all_forced,
            clear_all_default=model.subtitle_actions.clear_all_default,
            clear_all_titles=model.subtitle_actions.clear_all_titles,
        )

    # Convert V3 audio_filter config if present (V10 adds music/sfx/non_speech options)
    audio_filter: AudioFilterConfig | None = None
    if model.audio_filter is not None:
        fallback: LanguageFallbackConfig | None = None
        if model.audio_filter.fallback is not None:
            fallback = LanguageFallbackConfig(mode=model.audio_filter.fallback.mode)
        audio_filter = AudioFilterConfig(
            languages=tuple(model.audio_filter.languages),
            fallback=fallback,
            minimum=model.audio_filter.minimum,
            # V10: Music/SFX/Non-speech track handling
            keep_music_tracks=model.audio_filter.keep_music_tracks,
            exclude_music_from_language_filter=model.audio_filter.exclude_music_from_language_filter,
            keep_sfx_tracks=model.audio_filter.keep_sfx_tracks,
            exclude_sfx_from_language_filter=model.audio_filter.exclude_sfx_from_language_filter,
            keep_non_speech_tracks=model.audio_filter.keep_non_speech_tracks,
            exclude_non_speech_from_language_filter=model.audio_filter.exclude_non_speech_from_language_filter,
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

    # Convert V9 workflow config if present
    workflow: WorkflowConfig | None = None
    if model.workflow is not None:
        workflow = WorkflowConfig(
            phases=tuple(ProcessingPhase(p) for p in model.workflow.phases),
            auto_process=model.workflow.auto_process,
            on_error=model.workflow.on_error,
        )

    return PolicySchema(
        schema_version=model.schema_version,
        track_order=track_order,
        audio_language_preference=tuple(model.audio_language_preference),
        subtitle_language_preference=tuple(model.subtitle_language_preference),
        commentary_patterns=tuple(model.commentary_patterns),
        default_flags=default_flags,
        transcode=transcode,
        transcription=transcription,
        audio_actions=audio_actions,
        subtitle_actions=subtitle_actions,
        audio_filter=audio_filter,
        subtitle_filter=subtitle_filter,
        attachment_filter=attachment_filter,
        container=container,
        conditional_rules=conditional_rules,
        audio_synthesis=audio_synthesis,
        video_transcode=video_transcode,
        audio_transcode=audio_transcode,
        workflow=workflow,
    )


# =============================================================================
# V11 Conversion Functions
# =============================================================================


def _convert_phase_model(phase: PhaseModel) -> PhaseDefinition:
    """Convert PhaseModel to PhaseDefinition dataclass."""
    # Convert container
    container: ContainerConfig | None = None
    if phase.container is not None:
        container = ContainerConfig(
            target=phase.container.target,
            on_incompatible_codec=phase.container.on_incompatible_codec,
        )

    # Convert audio_filter
    audio_filter: AudioFilterConfig | None = None
    if phase.audio_filter is not None:
        fallback: LanguageFallbackConfig | None = None
        if phase.audio_filter.fallback is not None:
            fallback = LanguageFallbackConfig(mode=phase.audio_filter.fallback.mode)
        audio_filter = AudioFilterConfig(
            languages=tuple(phase.audio_filter.languages),
            fallback=fallback,
            minimum=phase.audio_filter.minimum,
            keep_music_tracks=phase.audio_filter.keep_music_tracks,
            exclude_music_from_language_filter=phase.audio_filter.exclude_music_from_language_filter,
            keep_sfx_tracks=phase.audio_filter.keep_sfx_tracks,
            exclude_sfx_from_language_filter=phase.audio_filter.exclude_sfx_from_language_filter,
            keep_non_speech_tracks=phase.audio_filter.keep_non_speech_tracks,
            exclude_non_speech_from_language_filter=phase.audio_filter.exclude_non_speech_from_language_filter,
        )

    # Convert subtitle_filter
    subtitle_filter: SubtitleFilterConfig | None = None
    if phase.subtitle_filter is not None:
        languages = None
        if phase.subtitle_filter.languages is not None:
            languages = tuple(phase.subtitle_filter.languages)
        subtitle_filter = SubtitleFilterConfig(
            languages=languages,
            preserve_forced=phase.subtitle_filter.preserve_forced,
            remove_all=phase.subtitle_filter.remove_all,
        )

    # Convert attachment_filter
    attachment_filter: AttachmentFilterConfig | None = None
    if phase.attachment_filter is not None:
        attachment_filter = AttachmentFilterConfig(
            remove_all=phase.attachment_filter.remove_all,
        )

    # Convert track_order
    track_order: tuple[TrackType, ...] | None = None
    if phase.track_order is not None:
        track_order = tuple(TrackType(t) for t in phase.track_order)

    # Convert default_flags
    default_flags: DefaultFlagsConfig | None = None
    if phase.default_flags is not None:
        default_flags = DefaultFlagsConfig(
            set_first_video_default=phase.default_flags.set_first_video_default,
            set_preferred_audio_default=phase.default_flags.set_preferred_audio_default,
            set_preferred_subtitle_default=phase.default_flags.set_preferred_subtitle_default,
            clear_other_defaults=phase.default_flags.clear_other_defaults,
            set_subtitle_default_when_audio_differs=phase.default_flags.set_subtitle_default_when_audio_differs,
            set_subtitle_forced_when_audio_differs=phase.default_flags.set_subtitle_forced_when_audio_differs,
        )

    # Convert conditional rules
    conditional: tuple[ConditionalRule, ...] | None = None
    if phase.conditional is not None:
        conditional = _convert_conditional_rules(phase.conditional)

    # Convert audio_synthesis
    audio_synthesis: AudioSynthesisConfig | None = None
    if phase.audio_synthesis is not None:
        audio_synthesis = _convert_audio_synthesis(phase.audio_synthesis)

    # Convert transcode (V6-style)
    transcode: VideoTranscodeConfig | None = None
    audio_transcode: AudioTranscodeConfig | None = None
    if phase.transcode is not None:
        transcode = _convert_video_transcode_config(phase.transcode.video)
        audio_transcode = _convert_audio_transcode_config(phase.transcode.audio)

    # Convert transcription
    transcription: TranscriptionPolicyOptions | None = None
    if phase.transcription is not None:
        transcription = TranscriptionPolicyOptions(
            enabled=phase.transcription.enabled,
            update_language_from_transcription=phase.transcription.update_language_from_transcription,
            confidence_threshold=phase.transcription.confidence_threshold,
            detect_commentary=phase.transcription.detect_commentary,
            reorder_commentary=phase.transcription.reorder_commentary,
        )

    # Convert audio_actions
    audio_actions: AudioActionsConfig | None = None
    if phase.audio_actions is not None:
        audio_actions = AudioActionsConfig(
            clear_all_forced=phase.audio_actions.clear_all_forced,
            clear_all_default=phase.audio_actions.clear_all_default,
            clear_all_titles=phase.audio_actions.clear_all_titles,
        )

    # Convert subtitle_actions
    subtitle_actions: SubtitleActionsConfig | None = None
    if phase.subtitle_actions is not None:
        subtitle_actions = SubtitleActionsConfig(
            clear_all_forced=phase.subtitle_actions.clear_all_forced,
            clear_all_default=phase.subtitle_actions.clear_all_default,
            clear_all_titles=phase.subtitle_actions.clear_all_titles,
        )

    # Convert skip_when condition
    skip_when: PhaseSkipCondition | None = None
    if phase.skip_when is not None:
        skip_when = PhaseSkipCondition(
            video_codec=(
                tuple(phase.skip_when.video_codec)
                if phase.skip_when.video_codec
                else None
            ),
            audio_codec_exists=phase.skip_when.audio_codec_exists,
            subtitle_language_exists=phase.skip_when.subtitle_language_exists,
            container=(
                tuple(phase.skip_when.container) if phase.skip_when.container else None
            ),
            resolution=phase.skip_when.resolution,
            resolution_under=phase.skip_when.resolution_under,
            file_size_under=phase.skip_when.file_size_under,
            file_size_over=phase.skip_when.file_size_over,
            duration_under=phase.skip_when.duration_under,
            duration_over=phase.skip_when.duration_over,
        )

    # Convert depends_on
    depends_on: tuple[str, ...] | None = None
    if phase.depends_on is not None:
        depends_on = tuple(phase.depends_on)

    # Convert run_if condition
    run_if: RunIfCondition | None = None
    if phase.run_if is not None:
        run_if = RunIfCondition(
            phase_modified=phase.run_if.phase_modified,
            phase_completed=phase.run_if.phase_completed,
        )

    # Convert on_error override
    on_error_map = {
        "skip": OnErrorMode.SKIP,
        "continue": OnErrorMode.CONTINUE,
        "fail": OnErrorMode.FAIL,
    }
    on_error: OnErrorMode | None = None
    if phase.on_error is not None:
        on_error = on_error_map[phase.on_error]

    return PhaseDefinition(
        name=phase.name,
        container=container,
        audio_filter=audio_filter,
        subtitle_filter=subtitle_filter,
        attachment_filter=attachment_filter,
        track_order=track_order,
        default_flags=default_flags,
        conditional=conditional,
        audio_synthesis=audio_synthesis,
        transcode=transcode,
        audio_transcode=audio_transcode,
        transcription=transcription,
        audio_actions=audio_actions,
        subtitle_actions=subtitle_actions,
        skip_when=skip_when,
        depends_on=depends_on,
        run_if=run_if,
        on_error=on_error,
    )


def _convert_to_phased_policy_schema(model: PhasedPolicyModel) -> PhasedPolicySchema:
    """Convert PhasedPolicyModel to PhasedPolicySchema dataclass."""
    # Convert global config
    on_error_map = {
        "skip": OnErrorMode.SKIP,
        "continue": OnErrorMode.CONTINUE,
        "fail": OnErrorMode.FAIL,
    }
    global_config = GlobalConfig(
        audio_language_preference=tuple(model.config.audio_language_preference),
        subtitle_language_preference=tuple(model.config.subtitle_language_preference),
        commentary_patterns=tuple(model.config.commentary_patterns),
        on_error=on_error_map[model.config.on_error],
    )

    # Convert phases
    phases = tuple(_convert_phase_model(p) for p in model.phases)

    return PhasedPolicySchema(
        schema_version=12,
        config=global_config,
        phases=phases,
    )


# Backward compatibility alias (deprecated)
_convert_to_v11_policy_schema = _convert_to_phased_policy_schema


def load_policy(policy_path: Path) -> PolicySchema | PhasedPolicySchema:
    """Load and validate a policy from a YAML file.

    Args:
        policy_path: Path to the YAML policy file.

    Returns:
        Validated PolicySchema (flat format) or PhasedPolicySchema (phased format).

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


def load_policy_from_dict(data: dict[str, Any]) -> PolicySchema | PhasedPolicySchema:
    """Load and validate a policy from a dictionary.

    Args:
        data: Dictionary containing policy configuration.

    Returns:
        Validated PolicySchema (flat format) or PhasedPolicySchema (phased format).

    Raises:
        PolicyValidationError: If the policy data is invalid.
    """
    # Check schema version - only V12 is supported
    schema_version = data.get("schema_version")
    if schema_version != 12:
        raise PolicyValidationError(
            f"Only schema_version 12 is supported, got {schema_version}"
        )

    # Route to phased loader if 'phases' key is present
    has_phases = "phases" in data
    if has_phases:
        return load_phased_policy_from_dict(data)

    try:
        model = PolicyModel.model_validate(data)
    except Exception as e:
        # Transform Pydantic errors to user-friendly messages
        error_msg = _format_validation_error(e)
        raise PolicyValidationError(error_msg) from e

    return _convert_to_policy_schema(model)


def load_phased_policy_from_dict(data: dict[str, Any]) -> PhasedPolicySchema:
    """Load and validate a phased policy from a dictionary.

    Args:
        data: Dictionary containing phased policy configuration.

    Returns:
        Validated PhasedPolicySchema object.

    Raises:
        PolicyValidationError: If the policy data is invalid.
    """
    try:
        model = PhasedPolicyModel.model_validate(data)
    except Exception as e:
        # Transform Pydantic errors to user-friendly messages
        error_msg = _format_validation_error(e)
        raise PolicyValidationError(error_msg) from e

    return _convert_to_phased_policy_schema(model)


# Backward compatibility alias (deprecated)
load_v11_policy_from_dict = load_phased_policy_from_dict


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
