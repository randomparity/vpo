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
    AttachmentFilterConfig,
    AudioFilterConfig,
    ContainerConfig,
    DefaultFlagsConfig,
    LanguageFallbackConfig,
    PolicySchema,
    SubtitleFilterConfig,
    TrackType,
    TranscodePolicyConfig,
    TranscriptionPolicyOptions,
)

# Current maximum supported schema version
MAX_SCHEMA_VERSION = 4


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

    @model_validator(mode="after")
    def validate_v3_fields_require_v3_schema(self) -> "PolicyModel":
        """Validate that V3 fields are only used with schema_version >= 3."""
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
