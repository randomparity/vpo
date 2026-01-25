"""Job maintenance operations (purge, cleanup).

This module consolidates job maintenance functions that were previously
scattered across worker.py and tracking.py.
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from vpo.db.queries import delete_old_jobs

logger = logging.getLogger(__name__)


def purge_old_jobs(
    conn: sqlite3.Connection,
    retention_days: int,
    *,
    auto_purge: bool = True,
) -> int:
    """Purge old completed/failed/cancelled jobs.

    Single implementation for all job purge operations. Consolidates
    worker._purge_old_jobs() and tracking.maybe_purge_old_jobs().

    Args:
        conn: Database connection.
        retention_days: Days to retain jobs before purging.
        auto_purge: If False, returns 0 without purging.

    Returns:
        Number of jobs deleted.
    """
    if not auto_purge:
        return 0

    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

    count = delete_old_jobs(conn, cutoff)
    conn.commit()
    return count


def cleanup_orphaned_cli_jobs(
    conn: sqlite3.Connection,
    stale_threshold_hours: int = 24,
) -> int:
    """Mark orphaned CLI jobs (stuck in RUNNING) as failed.

    CLI jobs don't have heartbeats like daemon jobs, so we use the created_at
    timestamp to identify jobs that were started but never completed. This
    typically happens when the process crashes or is killed without graceful
    shutdown.

    This function is safe to call multiple times; it only affects jobs that:
    - Have origin='cli' (CLI-initiated jobs)
    - Are currently in 'running' status
    - Were created more than stale_threshold_hours ago

    Args:
        conn: Database connection.
        stale_threshold_hours: Hours after which a running CLI job is
            considered orphaned. Defaults to 24 hours.

    Returns:
        Number of jobs marked as failed.

    Example:
        >>> from vpo.jobs.maintenance import cleanup_orphaned_cli_jobs
        >>> from vpo.db import get_connection
        >>> with get_connection(db_path) as conn:
        ...     count = cleanup_orphaned_cli_jobs(conn, stale_threshold_hours=24)
        ...     print(f"Cleaned up {count} orphaned jobs")
    """
    if stale_threshold_hours < 1:
        raise ValueError("stale_threshold_hours must be at least 1")

    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=stale_threshold_hours)
    ).isoformat()
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        UPDATE jobs SET
            status = 'failed',
            error_message = 'Job orphaned (process terminated without cleanup)',
            completed_at = ?
        WHERE origin = 'cli'
          AND status = 'running'
          AND created_at < ?
        """,
        (now, cutoff),
    )

    count = cursor.rowcount
    conn.commit()

    if count > 0:
        logger.info(
            "Cleaned up %d orphaned CLI job(s) older than %d hours",
            count,
            stale_threshold_hours,
        )

    return count
