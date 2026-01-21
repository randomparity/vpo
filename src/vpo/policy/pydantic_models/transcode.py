"""V6 Transcode Pydantic models for policy parsing.

This module contains models for conditional video/audio transcoding:
- SkipConditionModel: Skip transcode conditions
- QualitySettingsModel: Video quality settings
- ScalingSettingsModel: Video scaling settings
- HardwareAccelConfigModel: Hardware acceleration settings
- VideoTranscodeConfigModel: Video transcode configuration
- AudioTranscodeConfigModel: Audio transcode configuration
- TranscodeV6Model: Combined V6 transcode configuration
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vpo.policy.types import (
    VALID_AUDIO_CODECS,
    VALID_PRESETS,
    VALID_RESOLUTIONS,
    VALID_VIDEO_CODECS,
    X264_X265_TUNES,
    parse_bitrate,
)


class SkipConditionModel(BaseModel):
    """Pydantic model for skip condition configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: Literal["auto", "nvenc", "qsv", "vaapi", "none"] = "auto"
    fallback_to_cpu: bool = True


class VideoTranscodeConfigModel(BaseModel):
    """Pydantic model for V6 video transcode configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

    video: VideoTranscodeConfigModel | None = None
    audio: AudioTranscodeConfigModel | None = None
