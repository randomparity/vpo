"""Plugin event definitions.

This module defines the event types that plugins can subscribe to and
receive during VPO operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vpo.db.types import FileInfo, TrackInfo
    from vpo.executor.interface import ExecutorResult
    from vpo.metadata.parser import ParsedMetadata
    from vpo.policy.models import Plan, PolicySchema
    from vpo.transcription.models import TranscriptionResult

# Event name constants
FILE_SCANNED = "file.scanned"
FILE_METADATA_ENRICHED = "file.metadata_enriched"
METADATA_EXTRACTED = "metadata.extracted"  # New: filename metadata extracted
POLICY_BEFORE_EVALUATE = "policy.before_evaluate"
POLICY_AFTER_EVALUATE = "policy.after_evaluate"
PLAN_BEFORE_EXECUTE = "plan.before_execute"
PLAN_AFTER_EXECUTE = "plan.after_execute"
PLAN_EXECUTION_FAILED = "plan.execution_failed"
TRANSCRIPTION_REQUESTED = "transcription.requested"
TRANSCRIPTION_COMPLETED = "transcription.completed"

# All valid event names
VALID_EVENTS = frozenset(
    [
        FILE_SCANNED,
        FILE_METADATA_ENRICHED,
        METADATA_EXTRACTED,
        POLICY_BEFORE_EVALUATE,
        POLICY_AFTER_EVALUATE,
        PLAN_BEFORE_EXECUTE,
        PLAN_AFTER_EXECUTE,
        PLAN_EXECUTION_FAILED,
        TRANSCRIPTION_REQUESTED,
        TRANSCRIPTION_COMPLETED,
    ]
)

# Events for analyzer plugins
ANALYZER_EVENTS = frozenset(
    [
        FILE_SCANNED,
        FILE_METADATA_ENRICHED,
        METADATA_EXTRACTED,
        POLICY_BEFORE_EVALUATE,
        POLICY_AFTER_EVALUATE,
        PLAN_AFTER_EXECUTE,
        PLAN_EXECUTION_FAILED,
        TRANSCRIPTION_REQUESTED,
        TRANSCRIPTION_COMPLETED,
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
    file_info: FileInfo
    tracks: list[TrackInfo]


@dataclass
class FileMetadataEnrichedEvent:
    """Event data for file.metadata_enriched event.

    Fired after analyzer plugins have had a chance to enrich metadata.
    """

    file_path: Path
    file_info: FileInfo
    enrichments: dict[str, Any]  # Combined enrichments from all plugins


@dataclass
class PolicyEvaluateEvent:
    """Event data for policy.before_evaluate and policy.after_evaluate events.

    For before_evaluate: plan will be None.
    For after_evaluate: plan will contain the evaluation result.
    """

    file_path: Path
    file_info: FileInfo
    policy: PolicySchema
    plan: Plan | None = None  # Set after evaluation


@dataclass
class PlanExecuteEvent:
    """Event data for plan execution events.

    For plan.before_execute: result and error are None.
    For plan.after_execute: result contains execution result.
    For plan.execution_failed: error contains the exception.
    """

    plan: Plan
    result: ExecutorResult | None = None
    error: Exception | None = None


@dataclass
class MetadataExtractedEvent:
    """Event data for metadata.extracted event.

    Fired after filename metadata has been extracted during directory
    organization. Plugins can use this to provide external metadata lookups
    (e.g., TMDb, TVDb) to enrich or override the parsed metadata.
    """

    file_path: Path
    parsed_metadata: ParsedMetadata
    metadata_dict: dict[str, str]  # Rendered metadata dictionary


@dataclass
class TranscriptionRequestedEvent:
    """Event requesting transcription of an audio track.

    Fired when VPO needs to transcribe an audio track for language
    detection or track classification. Plugins can handle this event
    to provide transcription services.
    """

    file_path: Path
    track: TrackInfo
    audio_data: bytes
    sample_rate: int
    options: dict[str, Any]


@dataclass
class TranscriptionCompletedEvent:
    """Event after transcription completes.

    Fired after a transcription plugin has processed an audio track.
    Provides the transcription result for storage or further processing.
    """

    file_path: Path
    track_id: int
    result: TranscriptionResult


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
