"""Periodic maintenance task for the daemon.

This module provides a background task that runs maintenance operations
periodically while the daemon is running.

Maintenance tasks:
- Log compression: Compress old log files (default: > 7 days)
- Log deletion: Delete old log files (default: > 90 days)

The maintenance task runs daily by default, with the first run occurring
shortly after server startup.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from video_policy_orchestrator.config import get_config
from video_policy_orchestrator.jobs.logs import run_log_maintenance

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default interval between maintenance runs (24 hours)
DEFAULT_MAINTENANCE_INTERVAL_SECONDS = 86400

# Delay before first maintenance run after startup (5 minutes)
STARTUP_DELAY_SECONDS = 300


class MaintenanceTask:
    """Background maintenance task for the daemon.

    Runs periodic maintenance operations including log compression
    and deletion. Uses asyncio for non-blocking execution.

    Usage:
        task = MaintenanceTask()
        asyncio.create_task(task.run())
        # ... later ...
        task.stop()
    """

    def __init__(
        self,
        interval_seconds: int = DEFAULT_MAINTENANCE_INTERVAL_SECONDS,
        startup_delay_seconds: int = STARTUP_DELAY_SECONDS,
    ) -> None:
        """Initialize the maintenance task.

        Args:
            interval_seconds: Seconds between maintenance runs.
            startup_delay_seconds: Seconds to wait before first run.
        """
        self.interval_seconds = interval_seconds
        self.startup_delay_seconds = startup_delay_seconds
        self._stop_event = asyncio.Event()
        self._last_run: datetime | None = None
        self._running = False

    async def run(self) -> None:
        """Run the maintenance loop.

        This method runs indefinitely until stop() is called.
        It should be run as an asyncio task.
        """
        if self._running:
            logger.warning("Maintenance task already running")
            return

        self._running = True
        logger.info(
            "Maintenance task started (first run in %d seconds, interval %d seconds)",
            self.startup_delay_seconds,
            self.interval_seconds,
        )

        try:
            # Wait for startup delay
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.startup_delay_seconds,
                )
                # Stop event was set during startup delay
                return
            except asyncio.TimeoutError:
                pass  # Normal case - startup delay elapsed

            # Run maintenance loop
            while not self._stop_event.is_set():
                await self._run_maintenance()

                # Wait for next run or stop
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.interval_seconds,
                    )
                    # Stop event was set
                    break
                except asyncio.TimeoutError:
                    pass  # Normal case - interval elapsed

        finally:
            self._running = False
            logger.info("Maintenance task stopped")

    def stop(self) -> None:
        """Signal the maintenance task to stop.

        This method is thread-safe and can be called from any thread.
        """
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Check if the maintenance task is running."""
        return self._running

    @property
    def last_run(self) -> datetime | None:
        """Get the timestamp of the last maintenance run."""
        return self._last_run

    async def _run_maintenance(self) -> None:
        """Run all maintenance operations."""
        start_time = datetime.now(timezone.utc)
        logger.info("Starting maintenance run")

        try:
            # Get config
            config = get_config()
            compression_days = config.jobs.log_compression_days
            deletion_days = config.jobs.log_deletion_days

            # Run log maintenance in a thread pool to avoid blocking
            compression_stats, deletion_stats = await asyncio.to_thread(
                run_log_maintenance,
                compression_days=compression_days,
                deletion_days=deletion_days,
                dry_run=False,
            )

            # Log results
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self._last_run = start_time

            if compression_stats.compressed_count > 0:
                logger.info(
                    "Compressed %d log file(s) (%d bytes -> %d bytes)",
                    compression_stats.compressed_count,
                    compression_stats.compressed_bytes_before,
                    compression_stats.compressed_bytes_after,
                )

            if deletion_stats.deleted_count > 0:
                logger.info(
                    "Deleted %d log file(s) (%d bytes freed)",
                    deletion_stats.deleted_count,
                    deletion_stats.deleted_bytes,
                )

            # Log errors if any
            compression_errors = compression_stats.errors or []
            deletion_errors = deletion_stats.errors or []
            all_errors = compression_errors + deletion_errors
            if all_errors:
                logger.warning(
                    "Maintenance completed with %d error(s)",
                    len(all_errors),
                )
                for error in all_errors[:5]:
                    logger.warning("  %s", error)
            else:
                logger.info("Maintenance completed in %.1f seconds", duration)

        except Exception as e:
            logger.exception("Maintenance run failed: %s", e)


async def run_maintenance_once() -> tuple[int, int]:
    """Run maintenance once (for manual invocation).

    Returns:
        Tuple of (compressed_count, deleted_count).
    """
    config = get_config()

    compression_stats, deletion_stats = await asyncio.to_thread(
        run_log_maintenance,
        compression_days=config.jobs.log_compression_days,
        deletion_days=config.jobs.log_deletion_days,
        dry_run=False,
    )

    return compression_stats.compressed_count, deletion_stats.deleted_count
