"""Workflow orchestration for video file processing.

This module provides a unified workflow system for processing video files
through multiple phases: analyze → apply → transcode.

V11 adds support for user-defined phases via V11WorkflowProcessor.
"""

from vpo.workflow.processor import (
    FileProcessingResult,
    WorkflowProcessor,
)
from vpo.workflow.stats_capture import (
    ActionCapture,
    PhaseMetrics,
    StatsCollector,
    compute_partial_hash,
    count_tracks_by_type,
)
from vpo.workflow.v11_processor import V11WorkflowProcessor

__all__ = [
    "ActionCapture",
    "FileProcessingResult",
    "PhaseMetrics",
    "StatsCollector",
    "V11WorkflowProcessor",
    "WorkflowProcessor",
    "compute_partial_hash",
    "count_tracks_by_type",
]
