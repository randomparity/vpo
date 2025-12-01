"""Workflow orchestration for video file processing.

This module provides a unified workflow system for processing video files
through multiple phases: analyze → apply → transcode.

V11 adds support for user-defined phases via V11WorkflowProcessor.
"""

from video_policy_orchestrator.workflow.processor import (
    FileProcessingResult,
    WorkflowProcessor,
)
from video_policy_orchestrator.workflow.v11_processor import V11WorkflowProcessor

__all__ = [
    "FileProcessingResult",
    "WorkflowProcessor",
    "V11WorkflowProcessor",
]
