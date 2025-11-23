"""Structured logging module for VPO.

Provides configurable logging with JSON format support and file rotation.
"""

from video_policy_orchestrator.logging.config import configure_logging
from video_policy_orchestrator.logging.handlers import JSONFormatter

__all__ = ["configure_logging", "JSONFormatter"]
