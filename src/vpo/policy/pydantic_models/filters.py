"""Track filtering Pydantic models for policy parsing.

This module contains models for track filtering:
- LanguageFallbackModel: Language fallback behavior
- AudioFilterModel: Audio track filtering configuration
- SubtitleFilterModel: Subtitle track filtering configuration
- AttachmentFilterModel: Attachment filtering configuration
- AudioActionsModel: Audio track pre-processing actions
- SubtitleActionsModel: Subtitle track pre-processing actions
- ContainerModel: Container format configuration
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vpo.policy.pydantic_models.base import _validate_language_codes


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


class ContainerModel(BaseModel):
    """Pydantic model for container configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: Literal["mkv", "mp4"]
    on_incompatible_codec: Literal["error", "skip", "transcode"] = "error"
