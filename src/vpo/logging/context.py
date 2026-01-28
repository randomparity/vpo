"""Worker context for structured logging.

Provides context propagation for worker threads using contextvars,
enabling automatic injection of worker_id and file_id into log records.
"""

from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

# Context variables for worker identification
_worker_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "worker_id", default=None
)
_file_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "file_id", default=None
)
_file_path: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "file_path", default=None
)


def set_worker_context(
    worker_id: str,
    file_id: str | None = None,
    file_path: Path | str | None = None,
) -> None:
    """Set the current worker context.

    Args:
        worker_id: Worker identifier (e.g., "01", "02").
        file_id: File identifier (e.g., "F001", "F002").
        file_path: Full path to file being processed, or None.
    """
    _worker_id.set(worker_id)
    _file_id.set(file_id)
    _file_path.set(str(file_path) if file_path is not None else None)


def clear_worker_context() -> None:
    """Clear the current worker context."""
    _worker_id.set(None)
    _file_id.set(None)
    _file_path.set(None)


@contextmanager
def worker_context(
    worker_id: str,
    file_id: str | None = None,
    file_path: Path | str | None = None,
) -> Generator[None, None, None]:
    """Context manager for worker processing context.

    Sets worker context on entry, clears on exit. Thread-safe via contextvars.

    Args:
        worker_id: Worker identifier (e.g., "01").
        file_id: File identifier (e.g., "F001").
        file_path: Full path to file being processed.

    Yields:
        None

    Example:
        with worker_context("01", "F001", "/path/to/file.mkv"):
            logger.info("Processing file")  # Automatically includes context
    """
    old_worker_id = _worker_id.get()
    old_file_id = _file_id.get()
    old_file_path = _file_path.get()
    try:
        set_worker_context(worker_id, file_id, file_path)
        yield
    finally:
        _worker_id.set(old_worker_id)
        _file_id.set(old_file_id)
        _file_path.set(old_file_path)


def get_worker_context() -> tuple[str | None, str | None, str | None]:
    """Get current worker context.

    Returns:
        Tuple of (worker_id, file_id, file_path), any may be None.
    """
    return _worker_id.get(), _file_id.get(), _file_path.get()


class WorkerContextFilter(logging.Filter):
    """Logging filter that injects worker context into log records.

    Adds worker_id, file_id, and file_path attributes to LogRecord from
    contextvars. For text format, also adds a formatted worker_tag for
    compact display like [W01:F001].
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Inject worker context into log record.

        Args:
            record: The log record to process.

        Returns:
            Always True (does not filter, only enriches).
        """
        worker_id, file_id, file_path = get_worker_context()

        # Add raw values for JSON format
        record.worker_id = worker_id
        record.file_id = file_id
        record.file_path = file_path

        # Create compact tag for text format: [W01:F001] or [W01] or empty
        if worker_id:
            if file_id:
                record.worker_tag = f"[W{worker_id}:{file_id}] "
            else:
                record.worker_tag = f"[W{worker_id}] "
        else:
            record.worker_tag = ""

        return True  # Never filter out records
