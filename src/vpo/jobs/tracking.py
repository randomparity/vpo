"""Job tracking for scan and apply operations.

This module provides functions to create and update job records
for scan and policy application operations.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypedDict

from vpo.db import (
    Job,
    JobStatus,
    JobType,
    insert_job,
)
from vpo.db.connection import execute_with_retry
from vpo.jobs.exceptions import JobNotFoundError

if TYPE_CHECKING:
    from vpo.config.models import JobsConfig


logger = logging.getLogger(__name__)

# Default retry configuration for job failure recording
DEFAULT_MAX_RETRIES = 5


class ScanSummary(TypedDict):
    """Type definition for scan job summary.

    Attributes:
        total_discovered: Total files found in directory.
        scanned: Files that were introspected.
        skipped: Files skipped (unchanged or excluded).
        added: New files added to database.
        removed: Files removed from database.
        errors: Number of errors encountered.
    """

    total_discovered: int
    scanned: int
    skipped: int
    added: int
    removed: int
    errors: int


class ProcessSummary(TypedDict, total=False):
    """Type definition for process job summary.

    Attributes:
        phases_completed: Number of phases completed.
        total_changes: Total number of changes made.
        stats_id: ID of the processing_stats record (optional).
    """

    phases_completed: int
    total_changes: int
    stats_id: str


# =============================================================================
# Helper Functions
# =============================================================================


def _utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string.

    Returns:
        Current UTC timestamp in ISO 8601 format.
    """
    return datetime.now(timezone.utc).isoformat()


def _validate_non_empty(value: str | None, field: str) -> None:
    """Validate that a string field is not empty or whitespace-only.

    Args:
        value: The string value to validate.
        field: The field name for error messages.

    Raises:
        ValueError: If the value is None, empty, or whitespace-only.
    """
    if not value or not value.strip():
        raise ValueError(f"{field} cannot be empty")


def _update_job_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: JobStatus,
    *,
    error_message: str | None = None,
    summary_json: str | None = None,
    set_progress_100: bool = False,
    operation_name: str = "update",
) -> None:
    """Internal helper to update job status with rollback support.

    This function performs the common pattern of updating job status
    with optional error message, summary, and progress fields.

    Args:
        conn: Database connection.
        job_id: ID of the job to update.
        status: New status for the job.
        error_message: Optional error message.
        summary_json: Optional JSON summary string.
        set_progress_100: Whether to set progress to 100%.
        operation_name: Name of the operation for error messages.

    Raises:
        JobNotFoundError: If the job doesn't exist.
    """
    now = _utc_now_iso()

    try:
        if set_progress_100:
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
        else:
            cursor = conn.execute(
                """
                UPDATE jobs SET
                    status = ?,
                    error_message = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (status.value, error_message, now, job_id),
            )

        if cursor.rowcount == 0:
            raise JobNotFoundError(job_id, operation_name)

        conn.commit()
    except JobNotFoundError:
        # Don't rollback for not-found errors (no changes were made)
        raise
    except Exception:
        conn.rollback()
        raise


# =============================================================================
# Scan Job Functions
# =============================================================================


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

    Raises:
        ValueError: If directory is empty.
    """
    _validate_non_empty(directory, "directory")

    job_id = str(uuid.uuid4())
    now = _utc_now_iso()

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
    summary: ScanSummary | dict[str, int],
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

    Raises:
        JobNotFoundError: If the job doesn't exist.
        ValueError: If job_id is empty.
    """
    _validate_non_empty(job_id, "job_id")

    status = JobStatus.FAILED if error_message else JobStatus.COMPLETED
    summary_json = json.dumps(summary)

    _update_job_status(
        conn,
        job_id,
        status,
        error_message=error_message,
        summary_json=summary_json,
        set_progress_100=True,
        operation_name="complete",
    )


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

    Raises:
        JobNotFoundError: If the job doesn't exist.
        ValueError: If job_id is empty.
    """
    _validate_non_empty(job_id, "job_id")

    _update_job_status(
        conn,
        job_id,
        JobStatus.CANCELLED,
        error_message=reason,
        operation_name="cancel",
    )


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

    Raises:
        JobNotFoundError: If the job doesn't exist.
        ValueError: If job_id or error_message is empty.
    """
    _validate_non_empty(job_id, "job_id")
    _validate_non_empty(error_message, "error_message")

    _update_job_status(
        conn,
        job_id,
        JobStatus.FAILED,
        error_message=error_message,
        operation_name="fail",
    )


def maybe_purge_old_jobs(conn: sqlite3.Connection, config: JobsConfig) -> int:
    """Purge old jobs if auto_purge is enabled.

    Args:
        conn: Database connection.
        config: Jobs configuration with retention settings.

    Returns:
        Number of jobs purged.
    """
    from vpo.jobs.maintenance import purge_old_jobs

    return purge_old_jobs(
        conn,
        config.retention_days,
        auto_purge=config.auto_purge,
    )


# =============================================================================
# Process Job Functions
# =============================================================================


def create_process_job(
    conn: sqlite3.Connection,
    file_id: int | None,
    file_path: str,
    policy_name: str,
    *,
    origin: str = "cli",
    batch_id: str | None = None,
) -> Job:
    """Create a new process job record.

    Process jobs track individual file processing through the workflow,
    allowing unified reporting for both CLI and daemon operations.

    Args:
        conn: Database connection.
        file_id: Database ID of the file (None if file not in database).
        file_path: Path to the file being processed.
        policy_name: Name/path of the policy being used.
        origin: Origin of the job ('cli' or 'daemon').
        batch_id: UUID grouping CLI batch operations (None for daemon jobs).

    Returns:
        The created Job record.

    Raises:
        ValueError: If file_path or policy_name is empty.
    """
    _validate_non_empty(file_path, "file_path")
    _validate_non_empty(policy_name, "policy_name")

    job_id = str(uuid.uuid4())
    now = _utc_now_iso()

    job = Job(
        id=job_id,
        file_id=file_id,
        file_path=file_path,
        job_type=JobType.PROCESS,
        status=JobStatus.RUNNING,
        priority=100,
        policy_name=policy_name,
        policy_json=None,
        progress_percent=0.0,
        progress_json=None,
        created_at=now,
        started_at=now,
        origin=origin,
        batch_id=batch_id,
    )

    insert_job(conn, job)
    return job


def complete_process_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    success: bool,
    phases_completed: int = 0,
    total_changes: int = 0,
    error_message: str | None = None,
    stats_id: str | None = None,
) -> None:
    """Mark a process job as completed.

    Args:
        conn: Database connection.
        job_id: ID of the job to complete.
        success: Whether the processing succeeded.
        phases_completed: Number of phases completed.
        total_changes: Total number of changes made.
        error_message: Error message if job failed.
        stats_id: ID of the processing_stats record (for linkage).

    Raises:
        JobNotFoundError: If the job doesn't exist.
        ValueError: If job_id is empty.
    """
    _validate_non_empty(job_id, "job_id")

    status = JobStatus.COMPLETED if success else JobStatus.FAILED

    # Build summary JSON
    summary: ProcessSummary = {
        "phases_completed": phases_completed,
        "total_changes": total_changes,
    }
    if stats_id:
        summary["stats_id"] = stats_id
    summary_json = json.dumps(summary)

    _update_job_status(
        conn,
        job_id,
        status,
        error_message=error_message,
        summary_json=summary_json,
        set_progress_100=True,
        operation_name="complete",
    )


def cancel_process_job(
    conn: sqlite3.Connection,
    job_id: str,
    reason: str = "Cancelled by user",
) -> None:
    """Mark a process job as cancelled (e.g., user pressed Ctrl+C).

    Args:
        conn: Database connection.
        job_id: ID of the job to cancel.
        reason: Reason for cancellation.

    Raises:
        JobNotFoundError: If the job doesn't exist.
        ValueError: If job_id is empty.
    """
    _validate_non_empty(job_id, "job_id")

    _update_job_status(
        conn,
        job_id,
        JobStatus.CANCELLED,
        error_message=reason,
        operation_name="cancel",
    )


def fail_process_job(
    conn: sqlite3.Connection,
    job_id: str,
    error_message: str,
) -> None:
    """Mark a process job as failed due to an error.

    Args:
        conn: Database connection.
        job_id: ID of the job to fail.
        error_message: Description of the error.

    Raises:
        JobNotFoundError: If the job doesn't exist.
        ValueError: If job_id or error_message is empty.
    """
    _validate_non_empty(job_id, "job_id")
    _validate_non_empty(error_message, "error_message")

    _update_job_status(
        conn,
        job_id,
        JobStatus.FAILED,
        error_message=error_message,
        operation_name="fail",
    )


def fail_job_with_retry(
    conn: sqlite3.Connection,
    job_id: str,
    error_message: str,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> bool:
    """Attempt to fail a job with retry on transient DB errors.

    This is useful for error handling paths where we want to ensure
    the job failure is recorded even if the database is temporarily busy.

    Args:
        conn: Database connection.
        job_id: ID of the job to fail.
        error_message: Description of the error.
        max_retries: Maximum number of retry attempts.

    Returns:
        True if the job was successfully marked as failed, False otherwise.
    """
    try:

        def _do_fail() -> None:
            fail_process_job(conn, job_id, error_message)

        execute_with_retry(_do_fail, max_retries=max_retries)
        return True
    except JobNotFoundError:
        logger.warning("Job %s not found when trying to mark as failed", job_id)
        return False
    except Exception as e:
        logger.error("CRITICAL: Failed to mark job %s as failed: %s", job_id, e)
        return False
