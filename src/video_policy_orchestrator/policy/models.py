"""Policy engine data models.

This module defines dataclasses for policy configuration and execution plans.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class TrackType(Enum):
    """Track type classification for policy ordering."""

    VIDEO = "video"
    AUDIO_MAIN = "audio_main"
    AUDIO_ALTERNATE = "audio_alternate"
    AUDIO_COMMENTARY = "audio_commentary"
    SUBTITLE_MAIN = "subtitle_main"
    SUBTITLE_FORCED = "subtitle_forced"
    SUBTITLE_COMMENTARY = "subtitle_commentary"
    ATTACHMENT = "attachment"


class ActionType(Enum):
    """Types of changes that can be planned."""

    REORDER = "reorder"  # Change track positions
    SET_DEFAULT = "set_default"  # Set default flag to true
    CLEAR_DEFAULT = "clear_default"  # Set default flag to false
    SET_FORCED = "set_forced"  # Set forced flag to true
    CLEAR_FORCED = "clear_forced"  # Set forced flag to false
    SET_TITLE = "set_title"  # Change track title
    SET_LANGUAGE = "set_language"  # Change language tag


@dataclass(frozen=True)
class DefaultFlagsConfig:
    """Configuration for default flag behavior in a policy."""

    set_first_video_default: bool = True
    set_preferred_audio_default: bool = True
    set_preferred_subtitle_default: bool = False
    clear_other_defaults: bool = True


# Default track order matching the policy schema
DEFAULT_TRACK_ORDER: tuple[TrackType, ...] = (
    TrackType.VIDEO,
    TrackType.AUDIO_MAIN,
    TrackType.AUDIO_ALTERNATE,
    TrackType.SUBTITLE_MAIN,
    TrackType.SUBTITLE_FORCED,
    TrackType.AUDIO_COMMENTARY,
    TrackType.SUBTITLE_COMMENTARY,
    TrackType.ATTACHMENT,
)


@dataclass(frozen=True)
class PolicySchema:
    """Validated policy configuration loaded from YAML.

    This is an immutable representation of a policy file.
    """

    schema_version: int
    track_order: tuple[TrackType, ...] = DEFAULT_TRACK_ORDER
    audio_language_preference: tuple[str, ...] = ("eng", "und")
    subtitle_language_preference: tuple[str, ...] = ("eng", "und")
    commentary_patterns: tuple[str, ...] = ("commentary", "director")
    default_flags: DefaultFlagsConfig = field(default_factory=DefaultFlagsConfig)

    def __post_init__(self) -> None:
        """Validate policy schema after initialization."""
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1")
        if not self.track_order:
            raise ValueError("track_order cannot be empty")
        if not self.audio_language_preference:
            raise ValueError("audio_language_preference cannot be empty")
        if not self.subtitle_language_preference:
            raise ValueError("subtitle_language_preference cannot be empty")


@dataclass(frozen=True)
class PlannedAction:
    """A single planned change. Immutable."""

    action_type: ActionType
    track_index: int | None  # None for REORDER (file-level action)
    current_value: Any
    desired_value: Any
    track_id: str | None = None  # Track UID if available

    @property
    def description(self) -> str:
        """Human-readable description of this action."""
        if self.action_type == ActionType.REORDER:
            return f"Reorder: {self.current_value} → {self.desired_value}"
        elif self.action_type == ActionType.SET_DEFAULT:
            return f"Track {self.track_index}: Set as default"
        elif self.action_type == ActionType.CLEAR_DEFAULT:
            return f"Track {self.track_index}: Clear default flag"
        elif self.action_type == ActionType.SET_FORCED:
            return f"Track {self.track_index}: Set as forced"
        elif self.action_type == ActionType.CLEAR_FORCED:
            return f"Track {self.track_index}: Clear forced flag"
        elif self.action_type == ActionType.SET_TITLE:
            return f"Track {self.track_index}: Set title '{self.desired_value}'"
        elif self.action_type == ActionType.SET_LANGUAGE:
            return f"Track {self.track_index}: Set language '{self.desired_value}'"
        else:
            return f"Track {self.track_index}: {self.action_type.value}"


@dataclass(frozen=True)
class Plan:
    """Immutable execution plan produced by policy evaluation."""

    file_id: str
    file_path: Path
    policy_version: int
    actions: tuple[PlannedAction, ...]
    requires_remux: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_empty(self) -> bool:
        """True if no actions needed."""
        return len(self.actions) == 0

    @property
    def summary(self) -> str:
        """Human-readable summary of changes."""
        if self.is_empty:
            return "No changes required"

        action_count = len(self.actions)
        remux_note = " (requires remux)" if self.requires_remux else ""
        return f"{action_count} change{'s' if action_count != 1 else ''}{remux_note}"
