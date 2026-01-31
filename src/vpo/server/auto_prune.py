"""Background auto-prune task for the daemon.

This module provides a background task that periodically prunes
files with scan_status='missing' from the library database.

The task is disabled by default and can be enabled via configuration:
- config.toml: jobs.auto_prune_enabled = true
- env var: VPO_AUTO_PRUNE_ENABLED=true
- profile YAML: jobs.auto_prune_enabled: true
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from vpo.jobs.services.prune import PruneJobService
from vpo.jobs.tracking import complete_prune_job, create_prune_job

if TYPE_CHECKING:
    from vpo.db.connection import DaemonConnectionPool

logger = logging.getLogger(__name__)

# Delay before first prune run after startup (10 minutes)
STARTUP_DELAY_SECONDS = 600

# Number of consecutive failures before marking unhealthy
_UNHEALTHY_THRESHOLD = 3


class AutoPruneTask:
    """Background task that periodically prunes missing files.

    Follows the same pattern as MaintenanceTask for consistency.

    Usage:
        task = AutoPruneTask(
            interval_seconds=604800,
            connection_pool=pool,
            lifecycle=lifecycle,
        )
        asyncio.create_task(task.run())
        # ... later ...
        task.stop()
    """

    def __init__(
        self,
        *,
        interval_seconds: int,
        connection_pool: DaemonConnectionPool | None = None,
        lifecycle: object | None = None,
        startup_delay_seconds: int = STARTUP_DELAY_SECONDS,
    ) -> None:
        """Initialize the auto-prune task.

        Args:
            interval_seconds: Seconds between prune runs.
            connection_pool: DaemonConnectionPool for database access.
            lifecycle: DaemonLifecycle instance (unused currently, reserved).
            startup_delay_seconds: Seconds to wait before first run.
        """
        self.interval_seconds = interval_seconds
        self.startup_delay_seconds = startup_delay_seconds
        self._pool = connection_pool
        self._lifecycle = lifecycle
        self._stop_event = asyncio.Event()
        self._last_run: datetime | None = None
        self._running = False
        self._state_lock = asyncio.Lock()
        self._consecutive_failures: int = 0
        self._is_healthy: bool = True

    async def run(self) -> None:
        """Run the auto-prune loop.

        This method runs indefinitely until stop() is called.
        It should be run as an asyncio task.
        """
        async with self._state_lock:
            if self._running:
                logger.warning("Auto-prune task already running")
                return
            self._running = True

        logger.info(
            "Auto-prune task started (first run in %d seconds, interval %d seconds)",
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
                return
            except asyncio.TimeoutError:
                pass  # Normal case - startup delay elapsed
            except asyncio.CancelledError:
                return

            # Run prune loop
            while not self._stop_event.is_set():
                await self._run_prune()

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.interval_seconds,
                    )
                    break
                except asyncio.TimeoutError:
                    pass  # Normal case - interval elapsed
                except asyncio.CancelledError:
                    break

        except asyncio.CancelledError:
            pass
        finally:
            async with self._state_lock:
                self._running = False
            logger.info("Auto-prune task stopped")

    def stop(self) -> None:
        """Signal the auto-prune task to stop."""
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Check if the auto-prune task is running."""
        return self._running

    @property
    def last_run(self) -> datetime | None:
        """Get the timestamp of the last prune run."""
        return self._last_run

    @property
    def is_healthy(self) -> bool:
        """Check if the auto-prune task is healthy."""
        return self._is_healthy

    async def _run_prune(self) -> None:
        """Execute a single prune run."""
        start_time = datetime.now(timezone.utc)
        logger.info("Starting auto-prune run")

        try:
            pool = self._pool
            if pool is None:
                logger.warning("Auto-prune: connection pool not available")
                return

            conn = pool.get_connection()

            def _do_prune():
                job = create_prune_job(conn)
                service = PruneJobService(conn)
                result = service.process()
                summary = {"files_pruned": result.files_pruned}
                complete_prune_job(
                    conn,
                    job.id,
                    summary,
                    error_message=result.error_message,
                )
                return result

            try:
                result = await asyncio.to_thread(_do_prune)
            except asyncio.CancelledError:
                return

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            async with self._state_lock:
                self._last_run = start_time

            # Reset failure tracking on success
            self._consecutive_failures = 0
            if not self._is_healthy:
                self._is_healthy = True
                logger.info("Auto-prune recovered, marking healthy")

            if result.files_pruned > 0:
                logger.info(
                    "Auto-prune completed: pruned %d file(s) in %.1f seconds",
                    result.files_pruned,
                    duration,
                )
            else:
                logger.info(
                    "Auto-prune completed: no missing files to prune (%.1f seconds)",
                    duration,
                )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._consecutive_failures += 1
            if self._consecutive_failures >= _UNHEALTHY_THRESHOLD:
                if self._is_healthy:
                    self._is_healthy = False
                    logger.error(
                        "Auto-prune marked unhealthy after %d consecutive failures",
                        self._consecutive_failures,
                    )
            logger.exception("Auto-prune run failed: %s", e)
