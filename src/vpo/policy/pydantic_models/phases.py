"""Phase and policy Pydantic models for policy parsing.

This module contains models for phased policy definitions:
- GlobalConfigModel: Global policy configuration
- PhaseSkipConditionModel: Phase skip conditions
- RunIfConditionModel: Run-if conditions
- PhaseModel: Phase definition
- PolicyModel: Full policy definition
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vpo.policy.matchers import validate_regex_patterns
from vpo.policy.parsing import (
    parse_duration as _parse_duration,
)
from vpo.policy.parsing import (
    parse_file_size as _parse_file_size,
)
from vpo.policy.pydantic_models.actions import ConditionalRuleModel
from vpo.policy.pydantic_models.base import (
    PHASE_NAME_PATTERN,
    RESERVED_PHASE_NAMES,
)
from vpo.policy.pydantic_models.config import (
    DefaultFlagsModel,
    TranscriptionPolicyModel,
)
from vpo.policy.pydantic_models.filters import (
    AttachmentFilterModel,
    AudioActionsModel,
    AudioFilterModel,
    ContainerModel,
    FileTimestampModel,
    SubtitleActionsModel,
    SubtitleFilterModel,
)
from vpo.policy.pydantic_models.synthesis import AudioSynthesisModel
from vpo.policy.pydantic_models.transcode import TranscodeV6Model
from vpo.policy.types import TrackType


class GlobalConfigModel(BaseModel):
    """Pydantic model for V11 global configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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


class PhaseSkipConditionModel(BaseModel):
    """Pydantic model for phase skip conditions.

    Multiple conditions use OR logic - phase is skipped if ANY matches.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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
    file_timestamp: FileTimestampModel | None = None
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


class PolicyModel(BaseModel):
    """Pydantic model for phased policy with user-defined phases."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[12] = 12
    """Schema version, must be exactly 12."""

    description: str | None = None
    """Optional policy description for documentation purposes."""

    category: str | None = None
    """Optional category for filtering/grouping policies (e.g., organize, transcode)."""

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
    def validate_phase_references(self) -> "PolicyModel":
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
