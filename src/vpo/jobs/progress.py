"""Progress reporting abstraction for CLI and daemon modes.

This module provides a unified protocol for progress reporting across
different execution contexts (CLI, daemon, tests).
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import threading
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vpo.db.connection import DaemonConnectionPool

logger = logging.getLogger(__name__)


class ProgressReporter(Protocol):
    """Protocol for progress reporting during file processing.

    Implementations provide context-specific progress display:
    - CLI: stderr progress bar
    - Daemon: database progress updates
    - Tests: null/silent reporter
    """

    def on_start(self, total: int) -> None:
        """Initialize progress tracking with total item count.

        Args:
            total: Total number of items to process.
        """
        ...

    def on_item_start(self, index: int, message: str = "") -> None:
        """Signal that an item is starting processing.

        Args:
            index: Zero-based index of the item starting.
            message: Optional description of the item.
        """
        ...

    def on_item_complete(self, index: int, success: bool, message: str = "") -> None:
        """Signal that an item has completed processing.

        Args:
            index: Zero-based index of the completed item.
            success: Whether the item processed successfully.
            message: Optional status message.
        """
        ...

    def on_progress(self, percent: float, message: str = "") -> None:
        """Update progress percentage (for long-running single operations).

        Args:
            percent: Progress percentage (0-100).
            message: Optional status message.
        """
        ...

    def on_complete(self, success: bool = True) -> None:
        """Signal that all processing is complete.

        Args:
            success: Whether the overall batch succeeded.
        """
        ...


class StderrProgressReporter:
    """Progress reporter that writes to stderr with in-place updates.

    Suitable for CLI batch processing where multiple files are processed
    and progress should be shown on the terminal.
    """

    def __init__(self, enabled: bool = True) -> None:
        """Initialize stderr progress reporter.

        Args:
            enabled: If False, suppresses output (for JSON mode or tests).
        """
        self.enabled = enabled
        self.total = 0
        self.completed = 0
        self.active = 0
        self.failed = 0
        self._lock = threading.Lock()

    def on_start(self, total: int) -> None:
        """Initialize with total item count."""
        with self._lock:
            self.total = total
            self.completed = 0
            self.active = 0
            self.failed = 0
        self._update_display()

    def on_item_start(self, index: int, message: str = "") -> None:
        """Mark an item as starting."""
        with self._lock:
            self.active += 1
        self._update_display()

    def on_item_complete(self, index: int, success: bool, message: str = "") -> None:
        """Mark an item as completed."""
        with self._lock:
            # Validate state before mutation
            if self.active < 1:
                logger.warning(
                    "Progress tracking: on_item_complete called without matching "
                    "on_item_start (active=%d, completed=%d, total=%d)",
                    self.active,
                    self.completed,
                    self.total,
                )
                # Don't decrement below zero
            else:
                self.active -= 1

            self.completed += 1

            # Warn if over-completed
            if self.completed > self.total > 0:
                logger.warning(
                    "Progress tracking: completed (%d) exceeds total (%d)",
                    self.completed,
                    self.total,
                )

            if not success:
                self.failed += 1
        self._update_display()

    def on_progress(self, percent: float, message: str = "") -> None:
        """Update single-item progress (not used for batch processing)."""
        # For batch processing, we track items, not percentage
        pass

    def on_complete(self, success: bool = True) -> None:
        """Complete progress display with newline."""
        if self.enabled:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def _update_display(self) -> None:
        """Update progress display on stderr."""
        if not self.enabled:
            return

        with self._lock:
            completed = self.completed
            total = self.total
            active = self.active

        msg = f"\rProcessing: {completed}/{total} [{active} active]"
        sys.stderr.write(msg)
        sys.stderr.flush()


class DatabaseProgressReporter:
    """Progress reporter that updates job progress in the database.

    Suitable for daemon mode where job progress should be persisted
    for monitoring via the web UI or API.

    Thread-safe: uses a lock to protect counter mutations from concurrent
    access when multiple workers update progress simultaneously.
    """

    def __init__(
        self,
        pool: DaemonConnectionPool,
        job_id: str,
    ) -> None:
        """Initialize database progress reporter.

        Args:
            pool: Database connection pool.
            job_id: ID of the job to update progress for.
        """
        self.pool = pool
        self.job_id = job_id
        self.total = 0
        self.completed = 0
        self._lock = threading.Lock()

    def on_start(self, total: int) -> None:
        """Initialize with total item count."""
        with self._lock:
            self.total = total
            self.completed = 0
        self._update_db(0.0)

    def on_item_start(self, index: int, message: str = "") -> None:
        """Mark an item as starting (no DB update needed)."""
        pass

    def on_item_complete(self, index: int, success: bool, message: str = "") -> None:
        """Mark an item as completed and update progress."""
        with self._lock:
            self.completed += 1
            if self.total > 0:
                percent = (self.completed / self.total) * 100
            else:
                percent = 0.0
        # I/O outside lock to avoid blocking other workers
        self._update_db(percent)

    def on_progress(self, percent: float, message: str = "") -> None:
        """Update progress percentage directly."""
        self._update_db(percent)

    def on_complete(self, success: bool = True) -> None:
        """Mark processing as complete (100%)."""
        self._update_db(100.0)

    def _update_db(self, percent: float) -> None:
        """Update job progress in database.

        Handles errors gracefully since progress updates are non-critical.
        """
        try:
            self.pool.execute_write(
                "UPDATE jobs SET progress_percent = ? WHERE id = ?",
                (percent, self.job_id),
            )
        except sqlite3.Error:
            # Database errors are expected and non-critical for progress
            pass
        except RuntimeError as e:
            if "closed" in str(e).casefold():
                # Pool closed - expected during shutdown
                pass
            else:
                logger.debug("Unexpected error updating job progress: %s", e)
        except Exception as e:
            # Log unexpected errors for investigation
            logger.debug("Unexpected error updating job progress: %s", e)


class NullProgressReporter:
    """No-op progress reporter for dry-run mode or tests.

    All methods are no-ops, suitable for contexts where progress
    reporting is not needed.
    """

    def on_start(self, total: int) -> None:
        """No-op."""
        pass

    def on_item_start(self, index: int, message: str = "") -> None:
        """No-op."""
        pass

    def on_item_complete(self, index: int, success: bool, message: str = "") -> None:
        """No-op."""
        pass

    def on_progress(self, percent: float, message: str = "") -> None:
        """No-op."""
        pass

    def on_complete(self, success: bool = True) -> None:
        """No-op."""
        pass


class CompositeProgressReporter:
    """Progress reporter that delegates to multiple reporters.

    Useful when you need to update both stderr and database, or
    combine any reporters.
    """

    def __init__(self, reporters: list[ProgressReporter]) -> None:
        """Initialize with list of reporters.

        Args:
            reporters: List of progress reporters to delegate to.
        """
        self.reporters = reporters

    def on_start(self, total: int) -> None:
        """Delegate to all reporters."""
        for reporter in self.reporters:
            reporter.on_start(total)

    def on_item_start(self, index: int, message: str = "") -> None:
        """Delegate to all reporters."""
        for reporter in self.reporters:
            reporter.on_item_start(index, message)

    def on_item_complete(self, index: int, success: bool, message: str = "") -> None:
        """Delegate to all reporters."""
        for reporter in self.reporters:
            reporter.on_item_complete(index, success, message)

    def on_progress(self, percent: float, message: str = "") -> None:
        """Delegate to all reporters."""
        for reporter in self.reporters:
            reporter.on_progress(percent, message)

    def on_complete(self, success: bool = True) -> None:
        """Delegate to all reporters."""
        for reporter in self.reporters:
            reporter.on_complete(success)
