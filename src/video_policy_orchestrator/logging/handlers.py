"""Custom logging handlers for VPO.

Provides JSONFormatter for structured log output.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format log records as JSON objects.

    Each log entry is a valid JSON object with:
    - timestamp: ISO-8601 UTC
    - level: Log level name
    - message: Log message
    - context: Additional context from record.extra
    """

    # Standard LogRecord attributes to exclude from context
    _STANDARD_ATTRS: frozenset[str] = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "exc_info",
            "exc_text",
            "stack_info",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.

        Args:
            record: Log record to format.

        Returns:
            JSON-formatted string.
        """
        # Build base log entry using the record's actual timestamp
        record_time = datetime.fromtimestamp(record.created, tz=timezone.utc)
        log_entry: dict[str, Any] = {
            "timestamp": record_time.isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add logger name if not root
        if record.name and record.name != "root":
            log_entry["logger"] = record.name

        # Add context from extra attributes (exclude standard LogRecord attrs)
        context = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._STANDARD_ATTRS and not key.startswith("_")
        }

        if context:
            log_entry["context"] = context

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)
