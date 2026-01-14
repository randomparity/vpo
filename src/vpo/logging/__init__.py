"""Structured logging module for VPO.

Provides configurable logging with JSON format support and file rotation.
Includes worker context support for parallel processing.
"""

from vpo.logging.config import configure_logging
from vpo.logging.context import (
    WorkerContextFilter,
    clear_worker_context,
    get_worker_context,
    set_worker_context,
    worker_context,
)
from vpo.logging.handlers import JSONFormatter

__all__ = [
    "JSONFormatter",
    "WorkerContextFilter",
    "clear_worker_context",
    "configure_logging",
    "get_worker_context",
    "set_worker_context",
    "worker_context",
]
