"""Job queue operations for Video Policy Orchestrator.

This module provides queue operations with SQLite-based job management:
- Atomic job claiming with BEGIN IMMEDIATE transactions
- Priority-based ordering
- Stale job recovery for orphaned workers
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from vpo.db.models import (
    Job,
    JobStatus,
    get_job,
)

logger = logging.getLogger(__name__)

# Default heartbeat timeout (seconds) - jobs without heartbeat for this long
# are considered stale and will be recovered
DEFAULT_HEARTBEAT_TIMEOUT = 300  # 5 minutes


def claim_next_job(
    conn: sqlite3.Connection,
    worker_pid: int | None = None,
) -> Job | None:
    """Atomically claim the next available job from the queue.

    Uses BEGIN IMMEDIATE to prevent race conditions when multiple
    workers attempt to claim jobs simultaneously.

    Args:
        conn: Database connection.
        worker_pid: Worker process ID (defaults to current PID).

    Returns:
        The claimed Job, or None if queue is empty.
    """
    if worker_pid is None:
        worker_pid = os.getpid()

    now = datetime.now(timezone.utc).isoformat()

    # Use BEGIN IMMEDIATE for exclusive write lock
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Find highest priority queued job
        cursor = conn.execute(
            """
            SELECT id FROM jobs
            WHERE status = 'queued'
            ORDER BY priority ASC, created_at ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()

        if row is None:
            conn.execute("ROLLBACK")
            return None

        job_id = row[0]

        # Claim the job atomically
        conn.execute(
            """
            UPDATE jobs
            SET status = 'running',
                started_at = ?,
                worker_pid = ?,
                worker_heartbeat = ?
            WHERE id = ? AND status = 'queued'
            """,
            (now, worker_pid, now, job_id),
        )

        conn.execute("COMMIT")

        # Return the claimed job
        return get_job(conn, job_id)

    except sqlite3.OperationalError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass  # Best effort rollback
        error_msg = str(e).casefold()
        # Distinguish lock contention from other errors
        if "locked" in error_msg or "busy" in error_msg:
            logger.warning("Lock contention while claiming job: %s", e)
            return None  # Caller can retry
        logger.error("Database operational error while claiming job: %s", e)
        raise
    except sqlite3.IntegrityError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        logger.error("Database integrity error while claiming job: %s", e)
        raise
    except sqlite3.DatabaseError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        logger.error("Database error while claiming job: %s", e)
        raise


def release_job(
    conn: sqlite3.Connection,
    job_id: str,
    status: JobStatus,
    error_message: str | None = None,
    output_path: str | None = None,
    backup_path: str | None = None,
) -> bool:
    """Release a job after processing.

    Updates job status and clears worker info.

    Args:
        conn: Database connection.
        job_id: Job UUID.
        status: Final status (COMPLETED, FAILED, CANCELLED).
        error_message: Error details if FAILED.
        output_path: Path to output file if successful.
        backup_path: Path to backup file if created.

    Returns:
        True if job was released, False if not found.
    """
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        UPDATE jobs
        SET status = ?,
            completed_at = ?,
            error_message = ?,
            output_path = ?,
            backup_path = ?,
            worker_pid = NULL,
            worker_heartbeat = NULL
        WHERE id = ?
        """,
        (status.value, now, error_message, output_path, backup_path, job_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def update_heartbeat(
    conn: sqlite3.Connection,
    job_id: str,
    worker_pid: int | None = None,
) -> bool:
    """Update job heartbeat timestamp.

    Should be called periodically by workers to indicate they're still alive.

    Args:
        conn: Database connection.
        job_id: Job UUID.
        worker_pid: Worker process ID (optional).

    Returns:
        True if heartbeat updated, False if job not found.
    """
    if worker_pid is None:
        worker_pid = os.getpid()

    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        UPDATE jobs
        SET worker_heartbeat = ?, worker_pid = ?
        WHERE id = ? AND status = 'running'
        """,
        (now, worker_pid, job_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def recover_stale_jobs(
    conn: sqlite3.Connection,
    timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT,
) -> int:
    """Recover stale jobs from dead workers.

    Jobs in RUNNING status with no heartbeat update within the timeout
    are reset to QUEUED status so they can be picked up by other workers.

    Args:
        conn: Database connection.
        timeout_seconds: How long without heartbeat before recovery.

    Returns:
        Number of jobs recovered.
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
    ).isoformat()

    cursor = conn.execute(
        """
        UPDATE jobs
        SET status = 'queued',
            started_at = NULL,
            worker_pid = NULL,
            worker_heartbeat = NULL,
            progress_percent = 0.0,
            progress_json = NULL
        WHERE status = 'running'
            AND worker_heartbeat < ?
        """,
        (cutoff,),
    )
    conn.commit()

    count = cursor.rowcount
    if count > 0:
        logger.info("Recovered %d stale job(s)", count)

    return count


def get_queue_stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Get queue statistics.

    Args:
        conn: Database connection.

    Returns:
        Dictionary with counts per status.
    """
    cursor = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM jobs
        GROUP BY status
        """
    )

    stats = {
        "queued": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "total": 0,
    }

    for row in cursor.fetchall():
        status = row[0]
        count = row[1]
        stats[status] = count
        stats["total"] += count

    return stats


def get_job_health_metrics(conn: sqlite3.Connection) -> dict[str, int]:
    """Get job metrics for health endpoint.

    Args:
        conn: Database connection.

    Returns:
        Dict with jobs_queued, jobs_running, active_workers, recent_errors.
    """
    # Get queue stats (reuse existing function logic)
    queue_stats = get_queue_stats(conn)

    # Get count of distinct workers currently processing jobs
    cursor = conn.execute(
        """
        SELECT COUNT(DISTINCT worker_pid)
        FROM jobs
        WHERE status = 'running' AND worker_pid IS NOT NULL
        """
    )
    active_workers = cursor.fetchone()[0] or 0

    # Get count of failed jobs in last 24 hours
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    cursor = conn.execute(
        """
        SELECT COUNT(*) FROM jobs
        WHERE status = 'failed' AND completed_at > ?
        """,
        (cutoff,),
    )
    recent_errors = cursor.fetchone()[0] or 0

    return {
        "jobs_queued": queue_stats.get("queued", 0),
        "jobs_running": queue_stats.get("running", 0),
        "active_workers": active_workers,
        "recent_errors": recent_errors,
    }


def cancel_job(conn: sqlite3.Connection, job_id: str) -> bool:
    """Cancel a job.

    Only queued jobs can be cancelled. Running jobs should be
    stopped via their worker.

    Args:
        conn: Database connection.
        job_id: Job UUID.

    Returns:
        True if job was cancelled, False if not found or not cancellable.
    """
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        UPDATE jobs
        SET status = 'cancelled', completed_at = ?
        WHERE id = ? AND status = 'queued'
        """,
        (now, job_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def requeue_job(conn: sqlite3.Connection, job_id: str) -> bool:
    """Requeue a failed or cancelled job.

    Resets the job to queued status for retry.

    Args:
        conn: Database connection.
        job_id: Job UUID.

    Returns:
        True if job was requeued, False if not found or not requeuable.
    """
    cursor = conn.execute(
        """
        UPDATE jobs
        SET status = 'queued',
            started_at = NULL,
            completed_at = NULL,
            error_message = NULL,
            worker_pid = NULL,
            worker_heartbeat = NULL,
            progress_percent = 0.0,
            progress_json = NULL
        WHERE id = ? AND status IN ('failed', 'cancelled')
        """,
        (job_id,),
    )
    conn.commit()
    return cursor.rowcount > 0
