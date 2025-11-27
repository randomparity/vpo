"""Job tracking for scan and apply operations.

This module provides functions to create and update job records
for scan and policy application operations.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from video_policy_orchestrator.db.models import (
    Job,
    JobStatus,
    JobType,
    insert_job,
)

if TYPE_CHECKING:
    import sqlite3

    from video_policy_orchestrator.config.models import JobsConfig


def create_scan_job(
    conn: sqlite3.Connection,
    directory: str,
    *,
    incremental: bool = True,
    prune: bool = False,
    verify_hash: bool = False,
) -> Job:
    """Create a new scan job record.

    Args:
        conn: Database connection.
        directory: Directory being scanned.
        incremental: Whether incremental mode is enabled.
        prune: Whether to prune missing files.
        verify_hash: Whether to verify content hashes.

    Returns:
        The created Job record.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Serialize scan configuration to policy_json
    config = {
        "incremental": incremental,
        "prune": prune,
        "verify_hash": verify_hash,
    }

    job = Job(
        id=job_id,
        file_id=None,  # Scan jobs don't target a specific file
        file_path=directory,
        job_type=JobType.SCAN,
        status=JobStatus.RUNNING,
        priority=100,
        policy_name=None,
        policy_json=json.dumps(config),
        progress_percent=0.0,
        progress_json=None,
        created_at=now,
        started_at=now,
    )

    insert_job(conn, job)
    return job


def complete_scan_job(
    conn: sqlite3.Connection,
    job_id: str,
    summary: dict[str, int],
    *,
    error_message: str | None = None,
) -> None:
    """Mark a scan job as completed.

    Args:
        conn: Database connection.
        job_id: ID of the job to complete.
        summary: Summary dict with scan counts (total_discovered, scanned,
            skipped, added, removed, errors).
        error_message: Error message if job failed.
    """
    now = datetime.now(timezone.utc).isoformat()
    status = JobStatus.FAILED if error_message else JobStatus.COMPLETED
    summary_json = json.dumps(summary)

    # Single atomic update for all completion fields
    cursor = conn.execute(
        """
        UPDATE jobs SET
            status = ?,
            error_message = ?,
            completed_at = ?,
            summary_json = ?,
            progress_percent = 100.0
        WHERE id = ?
        """,
        (status.value, error_message, now, summary_json, job_id),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"Job {job_id} not found")
    conn.commit()


def cancel_scan_job(
    conn: sqlite3.Connection,
    job_id: str,
    reason: str = "Cancelled by user",
) -> None:
    """Mark a scan job as cancelled (e.g., user pressed Ctrl+C).

    Args:
        conn: Database connection.
        job_id: ID of the job to cancel.
        reason: Reason for cancellation.
    """
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        UPDATE jobs SET
            status = ?,
            error_message = ?,
            completed_at = ?
        WHERE id = ?
        """,
        (JobStatus.CANCELLED.value, reason, now, job_id),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"Job {job_id} not found")
    conn.commit()


def fail_scan_job(
    conn: sqlite3.Connection,
    job_id: str,
    error_message: str,
) -> None:
    """Mark a scan job as failed due to an error.

    Args:
        conn: Database connection.
        job_id: ID of the job to fail.
        error_message: Description of the error.
    """
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        UPDATE jobs SET
            status = ?,
            error_message = ?,
            completed_at = ?
        WHERE id = ?
        """,
        (JobStatus.FAILED.value, error_message, now, job_id),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"Job {job_id} not found")
    conn.commit()


def maybe_purge_old_jobs(conn: sqlite3.Connection, config: JobsConfig) -> int:
    """Purge old jobs if auto_purge is enabled.

    Args:
        conn: Database connection.
        config: Jobs configuration with retention settings.

    Returns:
        Number of jobs purged.
    """
    from video_policy_orchestrator.jobs.maintenance import purge_old_jobs

    return purge_old_jobs(
        conn,
        config.retention_days,
        auto_purge=config.auto_purge,
    )
