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

# Security: Forbidden shell metacharacters in ffmpeg_args to prevent injection
FORBIDDEN_FFMPEG_ARG_PATTERNS = (
    ";",
    "|",
    "&",
    "$(",
    "`",
    "${",
    ">",
    "<",
    "\\n",
    "\n",
)

# Limits for ffmpeg_args to prevent abuse
MAX_FFMPEG_ARGS_COUNT = 50
MAX_FFMPEG_ARG_LENGTH = 1024


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
    """Pydantic model for V13 video transcode configuration.

    Quality, scaling, and hardware acceleration are flattened into
    this model directly. Quality mode is inferred from which fields
    are set during conversion.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    to: str
    """Target video codec (hevc, h264, vp9, av1)."""

    skip_if: SkipConditionModel | None = None

    # Quality settings (flattened)
    crf: int | None = Field(default=None, ge=0, le=51)
    preset: str = "medium"
    tune: str | None = None
    target_bitrate: str | None = None
    min_bitrate: str | None = None
    max_bitrate: str | None = None
    two_pass: bool = False

    # Scaling settings (flattened)
    max_resolution: str | None = None
    max_width: int | None = Field(default=None, ge=1)
    max_height: int | None = Field(default=None, ge=1)
    scale_algorithm: Literal["lanczos", "bicubic", "bilinear"] = "lanczos"
    upscale: bool = False

    # Hardware acceleration (flattened)
    hw: Literal["auto", "nvenc", "qsv", "vaapi", "none"] = "auto"
    hw_fallback: bool = True

    ffmpeg_args: list[str] | None = None

    @field_validator("ffmpeg_args")
    @classmethod
    def validate_ffmpeg_args(cls, v: list[str] | None) -> list[str] | None:
        """Validate FFmpeg arguments for safety and correctness."""
        if v is None:
            return None

        # Check argument count limit
        if len(v) > MAX_FFMPEG_ARGS_COUNT:
            raise ValueError(
                f"ffmpeg_args count exceeds limit: {len(v)} > {MAX_FFMPEG_ARGS_COUNT}"
            )

        for i, arg in enumerate(v):
            if not isinstance(arg, str):
                arg_type = type(arg).__name__
                raise ValueError(f"ffmpeg_args must be strings, got {arg_type}")

            # Check individual argument length
            if len(arg) > MAX_FFMPEG_ARG_LENGTH:
                raise ValueError(
                    f"ffmpeg_args[{i}] exceeds length limit: "
                    f"{len(arg)} > {MAX_FFMPEG_ARG_LENGTH}"
                )

            # Check for forbidden shell metacharacters
            for pattern in FORBIDDEN_FFMPEG_ARG_PATTERNS:
                if pattern in arg:
                    raise ValueError(
                        f"ffmpeg_args[{i}] contains forbidden character: "
                        f"'{pattern}' (shell metacharacters not allowed)"
                    )

        return v

    @field_validator("to")
    @classmethod
    def validate_video_codec(cls, v: str) -> str:
        """Validate video codec."""
        if v.casefold() not in VALID_VIDEO_CODECS:
            raise ValueError(
                f"Invalid target codec '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_VIDEO_CODECS))}"
            )
        return v

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

    @field_validator("target_bitrate", "min_bitrate", "max_bitrate")
    @classmethod
    def validate_bitrate(cls, v: str | None) -> str | None:
        """Validate bitrate format."""
        if v is not None and parse_bitrate(v) is None:
            raise ValueError(
                f"Invalid bitrate '{v}'. "
                "Must be a number followed by M or k (e.g., '5M', '2500k')."
            )
        return v

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

    @model_validator(mode="after")
    def validate_quality_mode(self) -> "VideoTranscodeConfigModel":
        """Reject ambiguous quality mode combinations."""
        if self.crf is not None and self.target_bitrate is not None:
            raise ValueError(
                "Cannot set both 'crf' and 'target_bitrate'. "
                "Use crf alone for CRF mode, target_bitrate alone for bitrate mode, "
                "or crf + max_bitrate for constrained quality mode."
            )
        return self


class AudioTranscodeConfigModel(BaseModel):
    """Pydantic model for V13 audio transcode configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preserve: list[str] = Field(
        default_factory=lambda: ["truehd", "dts-hd", "flac", "pcm_s24le"]
    )
    """Audio codecs to preserve (stream-copy)."""

    to: str = "aac"
    """Target codec for non-preserved audio tracks."""

    bitrate: str = "192k"
    """Bitrate for transcoded audio tracks."""

    @field_validator("to")
    @classmethod
    def validate_audio_codec(cls, v: str) -> str:
        """Validate audio codec."""
        if v.casefold() not in VALID_AUDIO_CODECS:
            raise ValueError(
                f"Invalid target codec '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_AUDIO_CODECS))}"
            )
        return v

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str) -> str:
        """Validate bitrate format."""
        if parse_bitrate(v) is None:
            raise ValueError(
                f"Invalid bitrate '{v}'. "
                "Must be a number followed by k (e.g., '192k', '256k')."
            )
        return v


class TranscodeV6Model(BaseModel):
    """Pydantic model for V6 transcode configuration with video/audio sections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    video: VideoTranscodeConfigModel | None = None
    audio: AudioTranscodeConfigModel | None = None
