"""Plugin event definitions.

This module defines the event types that plugins can subscribe to and
receive during VPO operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Event name constants
FILE_SCANNED = "file.scanned"
FILE_METADATA_ENRICHED = "file.metadata_enriched"
POLICY_BEFORE_EVALUATE = "policy.before_evaluate"
POLICY_AFTER_EVALUATE = "policy.after_evaluate"
PLAN_BEFORE_EXECUTE = "plan.before_execute"
PLAN_AFTER_EXECUTE = "plan.after_execute"
PLAN_EXECUTION_FAILED = "plan.execution_failed"

# All valid event names
VALID_EVENTS = frozenset(
    [
        FILE_SCANNED,
        FILE_METADATA_ENRICHED,
        POLICY_BEFORE_EVALUATE,
        POLICY_AFTER_EVALUATE,
        PLAN_BEFORE_EXECUTE,
        PLAN_AFTER_EXECUTE,
        PLAN_EXECUTION_FAILED,
    ]
)

# Events for analyzer plugins
ANALYZER_EVENTS = frozenset(
    [
        FILE_SCANNED,
        FILE_METADATA_ENRICHED,
        POLICY_BEFORE_EVALUATE,
        POLICY_AFTER_EVALUATE,
        PLAN_AFTER_EXECUTE,
        PLAN_EXECUTION_FAILED,
    ]
)

# Events for mutator plugins
MUTATOR_EVENTS = frozenset(
    [
        PLAN_BEFORE_EXECUTE,
    ]
)


@dataclass
class FileScannedEvent:
    """Event data for file.scanned event.

    Fired after a file has been introspected via ffprobe.
    """

    file_path: Path
    file_info: Any  # FileInfo from db.models
    tracks: list[Any]  # list[TrackInfo] from db.models


@dataclass
class FileMetadataEnrichedEvent:
    """Event data for file.metadata_enriched event.

    Fired after analyzer plugins have had a chance to enrich metadata.
    """

    file_path: Path
    file_info: Any  # FileInfo from db.models
    enrichments: dict[str, Any]  # Combined enrichments from all plugins


@dataclass
class PolicyEvaluateEvent:
    """Event data for policy.before_evaluate and policy.after_evaluate events.

    For before_evaluate: plan will be None.
    For after_evaluate: plan will contain the evaluation result.
    """

    file_path: Path
    file_info: Any  # FileInfo from db.models
    policy: Any  # PolicySchema from policy.models
    plan: Any | None = None  # Plan from policy.models (after evaluation)


@dataclass
class PlanExecuteEvent:
    """Event data for plan execution events.

    For plan.before_execute: result and error are None.
    For plan.after_execute: result contains execution result.
    For plan.execution_failed: error contains the exception.
    """

    plan: Any  # Plan from policy.models
    result: Any | None = None  # ExecutorResult from executor.interface
    error: Exception | None = None


def is_valid_event(event_name: str) -> bool:
    """Check if an event name is valid.

    Args:
        event_name: Event name to check.

    Returns:
        True if valid, False otherwise.

    """
    return event_name in VALID_EVENTS


def is_analyzer_event(event_name: str) -> bool:
    """Check if an event is for analyzer plugins.

    Args:
        event_name: Event name to check.

    Returns:
        True if this is an analyzer event.

    """
    return event_name in ANALYZER_EVENTS


def is_mutator_event(event_name: str) -> bool:
    """Check if an event is for mutator plugins.

    Args:
        event_name: Event name to check.

    Returns:
        True if this is a mutator event.

    """
    return event_name in MUTATOR_EVENTS
