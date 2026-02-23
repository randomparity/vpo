"""Audio synthesis Pydantic models for policy parsing.

This module contains models for audio synthesis configuration:
- ChannelPreferenceModel: Channel preference in source selection
- PreferenceCriterionModel: Source selection preference criterion
- SourcePreferencesModel: Source track preferences
- SkipIfExistsModel: Skip synthesis criteria
- SynthesisTrackDefinitionModel: Synthesis track definition
- AudioSynthesisModel: Audio synthesis configuration
"""

from typing import TYPE_CHECKING, Literal, Union

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from vpo.policy.pydantic_models.base import (
    VALID_CHANNEL_CONFIGS,
    VALID_SYNTHESIS_CODECS,
)

if TYPE_CHECKING:
    from vpo.policy.pydantic_models.conditions import ComparisonModel, ConditionModel


class ChannelPreferenceModel(BaseModel):
    """Pydantic model for channel preference in source selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    codec: str
    channels: str | int
    source: SourcePreferencesModel
    bitrate: str | None = None
    create_if: "str | ConditionModel | None" = None
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

    model_config = ConfigDict(extra="forbid", frozen=True)

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


# Update forward references for runtime
def _update_forward_refs() -> None:
    """Update forward references for models that reference conditions."""
    from vpo.policy.pydantic_models.conditions import ComparisonModel, ConditionModel

    SkipIfExistsModel.model_rebuild(
        _types_namespace={"ComparisonModel": ComparisonModel}
    )
    SynthesisTrackDefinitionModel.model_rebuild(
        _types_namespace={"ConditionModel": ConditionModel}
    )


# Call at module load time
_update_forward_refs()
