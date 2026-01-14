"""Pydantic models for policy YAML parsing and validation.

This module contains all Pydantic BaseModel subclasses used to parse and
validate YAML policy files. These models are converted to frozen dataclasses
by the conversion functions in conversion.py.
"""

from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vpo.policy.matchers import validate_regex_patterns
from vpo.policy.parsing import (
    parse_duration as _parse_duration,
)
from vpo.policy.parsing import (
    parse_file_size as _parse_file_size,
)
from vpo.policy.types import (
    DEFAULT_TRACK_ORDER,
    VALID_AUDIO_CODECS,
    VALID_PRESETS,
    VALID_RESOLUTIONS,
    VALID_VIDEO_CODECS,
    X264_X265_TUNES,
    ProcessingPhase,
    TrackType,
    parse_bitrate,
)

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
