"""Logging configuration for VPO.

Provides configure_logging() to set up logging based on LoggingConfig.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from video_policy_orchestrator.logging.context import WorkerContextFilter
from video_policy_orchestrator.logging.handlers import JSONFormatter

if TYPE_CHECKING:
    from video_policy_orchestrator.config.models import LoggingConfig

# Map of lowercase level names to logging module constants.
# CRITICAL is intentionally excluded - not exposed via CLI configuration.
_LEVEL_MAP: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def configure_logging(config: LoggingConfig) -> None:
    """Configure logging based on LoggingConfig.

    Sets up handlers for file and/or stderr output with appropriate formatters.

    Args:
        config: Logging configuration.
    """
    level = _LEVEL_MAP.get(config.level.casefold(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter based on format
    if config.format.casefold() == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        # Text format includes worker_tag for parallel processing context
        # worker_tag is "[W01:F001] " when set, empty string otherwise
        formatter = logging.Formatter(
            "%(asctime)s - %(worker_tag)s%(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )

    # Create filter to inject worker context into all log records
    context_filter = WorkerContextFilter()

    # Add file handler if configured
    file_handler_added = False
    if config.file:
        try:
            file_path = Path(config.file).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(context_filter)
            root_logger.addHandler(file_handler)
            file_handler_added = True
        except (OSError, PermissionError) as e:
            # Log file unavailable - fall back to stderr
            sys.stderr.write(f"Warning: Could not open log file {config.file}: {e}\n")

    # Add stderr handler if configured or as fallback
    if config.include_stderr or not file_handler_added:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(level)
        stderr_handler.setFormatter(formatter)
        stderr_handler.addFilter(context_filter)
        root_logger.addHandler(stderr_handler)
