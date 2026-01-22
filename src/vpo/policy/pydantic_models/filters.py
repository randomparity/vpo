"""Track filtering Pydantic models for policy parsing.

This module contains models for track filtering:
- LanguageFallbackModel: Language fallback behavior
- AudioFilterModel: Audio track filtering configuration
- SubtitleFilterModel: Subtitle track filtering configuration
- AttachmentFilterModel: Attachment filtering configuration
- AudioActionsModel: Audio track pre-processing actions
- SubtitleActionsModel: Subtitle track pre-processing actions
- ContainerModel: Container format configuration
- FileTimestampModel: File timestamp handling configuration
"""

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vpo.core.codecs import (
    MP4_COMPATIBLE_AUDIO_CODECS,
    MP4_COMPATIBLE_SUBTITLE_CODECS,
)
from vpo.policy.pydantic_models.base import _validate_language_codes

logger = logging.getLogger(__name__)


class LanguageFallbackModel(BaseModel):
    """Pydantic model for language fallback configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["content_language", "keep_all", "keep_first", "error"]


class AudioFilterModel(BaseModel):
    """Pydantic model for audio filter configuration.

    V10: Added support for music, sfx, and non-speech track handling.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

    remove_all: bool = False


class AudioActionsModel(BaseModel):
    """Pydantic model for audio track pre-processing actions.

    Actions are applied BEFORE filtering to clean up misconfigured metadata.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    clear_all_forced: bool = False
    clear_all_default: bool = False
    clear_all_titles: bool = False


class SubtitleActionsModel(BaseModel):
    """Pydantic model for subtitle track pre-processing actions.

    Actions are applied BEFORE filtering to clean up misconfigured metadata.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    clear_all_forced: bool = False
    clear_all_default: bool = False
    clear_all_titles: bool = False


# Known MP4-compatible codecs for validation warnings (from centralized registry)
_KNOWN_CODECS = MP4_COMPATIBLE_AUDIO_CODECS | MP4_COMPATIBLE_SUBTITLE_CODECS


class CodecTranscodeMappingModel(BaseModel):
    """Pydantic model for per-codec transcode mapping.

    Defines how a specific incompatible codec should be handled
    during container conversion.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    codec: str
    """Target codec to transcode to (e.g., 'aac', 'ac3', 'mov_text')."""

    bitrate: str | None = None
    """Target bitrate for audio transcoding (e.g., '256k', '320k')."""

    action: Literal["transcode", "convert", "remove"] | None = None
    """Override the default action for this codec."""

    @field_validator("codec")
    @classmethod
    def validate_codec(cls, v: str) -> str:
        """Validate codec is non-empty and warn if not MP4-compatible."""
        v = v.strip().lower()
        if not v:
            raise ValueError("codec cannot be empty")
        # Warn if codec is not known to be MP4-compatible
        # This helps catch typos and configuration mistakes
        if v not in _KNOWN_CODECS:
            logger.warning(
                "Codec '%s' is not a recognized MP4-compatible codec. "
                "Known audio codecs: %s. Known subtitle codecs: %s. "
                "If this is intentional, you can ignore this warning.",
                v,
                ", ".join(sorted(MP4_COMPATIBLE_AUDIO_CODECS)),
                ", ".join(sorted(MP4_COMPATIBLE_SUBTITLE_CODECS)),
            )
        return v

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str | None) -> str | None:
        """Validate bitrate format if provided.

        Requires explicit unit suffix (k for kbps, m for mbps) to avoid
        confusion. Bare numbers like "256" would be interpreted as 256 bps
        by ffmpeg, which is almost certainly not intended.

        Valid range: 32k - 1536k (or equivalent in mbps).
        """
        if v is None:
            return v
        v = v.strip().lower()
        if not v:
            return None

        # Require explicit unit suffix to avoid accidental bps values
        if v.endswith("k"):
            try:
                value = int(v[:-1])
            except ValueError:
                raise ValueError(
                    f"Invalid bitrate format '{v}'. Expected integer followed by "
                    f"'k' (e.g., '256k')"
                )
            bitrate_kbps = value
        elif v.endswith("m"):
            try:
                # Allow decimal for mbps (e.g., "1.5m")
                value = float(v[:-1])
            except ValueError:
                raise ValueError(
                    f"Invalid bitrate format '{v}'. Expected number followed by "
                    f"'m' (e.g., '1m' or '1.5m')"
                )
            bitrate_kbps = int(value * 1000)
        else:
            # Bare numbers are rejected to avoid confusion
            raise ValueError(
                f"Bitrate '{v}' must include unit suffix. Use 'k' for kbps "
                f"(e.g., '256k') or 'm' for mbps (e.g., '1m'). "
                f"Bare numbers would be interpreted as bps, which is almost "
                f"certainly not what you want."
            )

        # Validate range for audio bitrates (32k - 1536k is reasonable)
        if bitrate_kbps < 32:
            raise ValueError(
                f"Bitrate {bitrate_kbps}k is too low. Minimum is 32k for audio."
            )
        if bitrate_kbps > 1536:
            raise ValueError(
                f"Bitrate {bitrate_kbps}k is too high. Maximum is 1536k (1.5m) "
                f"for audio. For higher bitrates, consider using lossless codecs."
            )

        return v


class ContainerModel(BaseModel):
    """Pydantic model for container configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: Literal["mkv", "mp4"]
    on_incompatible_codec: Literal["error", "skip", "transcode"] = "error"
    codec_mappings: dict[str, CodecTranscodeMappingModel] | None = None
    """Per-codec transcode settings, keyed by source codec name."""

    @field_validator("codec_mappings", mode="before")
    @classmethod
    def normalize_codec_keys(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Normalize codec keys to lowercase.

        Note: At mode="before", we receive raw dict data, not model instances.
        """
        if v is None:
            return v
        return {k.lower(): val for k, val in v.items()}

    @model_validator(mode="after")
    def validate_codec_mappings_usage(self) -> "ContainerModel":
        """Warn if codec_mappings is specified but won't be used.

        codec_mappings only takes effect when on_incompatible_codec='transcode'.
        Warn users if they configure mappings but use a different mode.
        """
        if self.codec_mappings and self.on_incompatible_codec != "transcode":
            logger.warning(
                "codec_mappings is configured but on_incompatible_codec='%s'. "
                "codec_mappings only takes effect when "
                "on_incompatible_codec='transcode'. The mappings will be ignored.",
                self.on_incompatible_codec,
            )
        return self


class FileTimestampModel(BaseModel):
    """Pydantic model for file timestamp configuration.

    Controls file modification timestamp handling after processing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["preserve", "release_date", "now"] = "preserve"
    """Timestamp handling mode."""

    fallback: Literal["preserve", "now", "skip"] = "preserve"
    """Fallback behavior when release_date mode has no date available."""

    date_source: Literal["auto", "radarr", "sonarr"] = "auto"
    """Source for release date."""

    @model_validator(mode="after")
    def validate_field_usage(self) -> "FileTimestampModel":
        """Warn about unused fields based on mode.

        The fallback and date_source fields are only meaningful when
        mode is "release_date". Warn users if they specify these fields
        with other modes to help catch configuration mistakes.
        """
        if self.mode != "release_date":
            if self.fallback != "preserve":
                logger.warning(
                    "file_timestamp: fallback=%r ignored when mode=%r",
                    self.fallback,
                    self.mode,
                )
            if self.date_source != "auto":
                logger.warning(
                    "file_timestamp: date_source=%r ignored when mode=%r",
                    self.date_source,
                    self.mode,
                )
        return self
