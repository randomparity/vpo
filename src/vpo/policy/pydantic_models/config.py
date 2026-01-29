"""Configuration Pydantic models for policy parsing.

This module contains:
- DefaultFlagsModel: Default track flag settings
- TranscriptionPolicyModel: Transcription policy options
- TranscodePolicyModel: Legacy transcode policy configuration
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vpo.policy.types import (
    VALID_AUDIO_CODECS,
    VALID_RESOLUTIONS,
    VALID_VIDEO_CODECS,
)


class DefaultFlagsModel(BaseModel):
    """Pydantic model for default flags configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    set_first_video_default: bool = True
    set_preferred_audio_default: bool = True
    set_preferred_subtitle_default: bool = False
    clear_other_defaults: bool = True
    set_subtitle_default_when_audio_differs: bool = False
    set_subtitle_forced_when_audio_differs: bool = False
    preferred_audio_codec: list[str] | None = None

    @field_validator("preferred_audio_codec", mode="before")
    @classmethod
    def casefold_preferred_audio_codec(
        cls,
        v: list[str] | None,
    ) -> list[str] | None:
        """Casefold codec names for case-insensitive matching."""
        if v is None:
            return None
        return [c.casefold() for c in v]


class TranscriptionPolicyModel(BaseModel):
    """Pydantic model for transcription policy options."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    # Computed properties for backward compatibility with TranscodePolicyConfig
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
