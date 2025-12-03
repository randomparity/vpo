"""Structured logging module for VPO.

Provides configurable logging with JSON format support and file rotation.
Includes worker context support for parallel processing.
"""

from video_policy_orchestrator.logging.config import configure_logging
from video_policy_orchestrator.logging.context import (
    WorkerContextFilter,
    clear_worker_context,
    get_worker_context,
    set_worker_context,
    worker_context,
)
from video_policy_orchestrator.logging.handlers import JSONFormatter

__all__ = [
    "JSONFormatter",
    "WorkerContextFilter",
    "clear_worker_context",
    "configure_logging",
    "get_worker_context",
    "set_worker_context",
    "worker_context",
]
