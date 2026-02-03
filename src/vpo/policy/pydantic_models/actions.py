"""Action Pydantic models for policy parsing.

This module contains models for conditional rule actions:
- SetForcedActionModel: Set forced flag on tracks
- SetDefaultActionModel: Set default flag on tracks
- PluginMetadataReferenceModel: Reference plugin metadata values
- SetLanguageActionModel: Set language tag on tracks
- ActionModel: Union of all action types
- ConditionalRuleModel: Conditional rule with when/then/else
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vpo.policy.pydantic_models.conditions import ConditionModel


class SetForcedActionModel(BaseModel):
    """Pydantic model for set_forced action.

    Sets the forced flag on matching subtitle tracks.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_type: Literal["subtitle"] = "subtitle"
    language: str | None = None
    value: bool = True


class SetDefaultActionModel(BaseModel):
    """Pydantic model for set_default action.

    Sets the default flag on matching tracks.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_type: Literal["video", "audio", "subtitle"]
    language: str | None = None
    value: bool = True


class PluginMetadataReferenceModel(BaseModel):
    """Pydantic model for referencing plugin metadata values.

    Used to dynamically pull values from plugin metadata at runtime.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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


class SetContainerMetadataActionModel(BaseModel):
    """Pydantic model for set_container_metadata action.

    Sets or clears a container-level metadata tag. Either value or
    from_plugin_metadata must be specified, but not both.
    An empty string value clears the tag.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    value: str | None = None
    from_plugin_metadata: PluginMetadataReferenceModel | None = None

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Validate and normalize field name to lowercase."""
        if not v or not v.strip():
            raise ValueError("field name cannot be empty")
        return v.strip().casefold()

    @model_validator(mode="after")
    def validate_value_source(self) -> "SetContainerMetadataActionModel":
        """Validate that exactly one value source is specified."""
        has_static = self.value is not None
        has_dynamic = self.from_plugin_metadata is not None

        if not has_static and not has_dynamic:
            raise ValueError(
                "set_container_metadata must specify either 'value' or "
                "'from_plugin_metadata'"
            )
        if has_static and has_dynamic:
            raise ValueError(
                "set_container_metadata cannot specify both 'value' and "
                "'from_plugin_metadata'"
            )
        return self


class ActionModel(BaseModel):
    """Pydantic model for conditional action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    # Container metadata actions
    set_container_metadata: SetContainerMetadataActionModel | None = None

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
            self.set_container_metadata,
        ]
        if not any(a is not None for a in actions):
            raise ValueError(
                "Action must specify at least one action "
                "(skip_video_transcode/skip_audio_transcode/skip_track_filter/"
                "warn/fail/set_forced/set_default/set_language/"
                "set_container_metadata)"
            )
        return self


class ConditionalRuleModel(BaseModel):
    """Pydantic model for a conditional rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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
