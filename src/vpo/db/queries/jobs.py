"""Job queue CRUD operations for Video Policy Orchestrator database.

This module contains database query functions for job management:
- Job insert, get, update, delete operations
- Job filtering and querying by status, type, date
"""

import sqlite3

from vpo.db.types import (
    Job,
    JobStatus,
    JobType,
)

from .helpers import _escape_like_pattern, _row_to_job

# Whitelist of sortable columns for get_jobs_filtered (prevent SQL injection)
SORTABLE_JOB_COLUMNS = frozenset(
    {"created_at", "job_type", "status", "file_path", "duration"}
)


def insert_job(conn: sqlite3.Connection, job: Job) -> str:
    """Insert a new job record.

    Args:
        conn: Database connection.
        job: Job to insert.

    Returns:
        The ID of the inserted job.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    conn.execute(
        """
        INSERT INTO jobs (
            id, file_id, file_path, job_type, status, priority,
            policy_name, policy_json, progress_percent, progress_json,
            created_at, started_at, completed_at,
            worker_pid, worker_heartbeat,
            output_path, backup_path, error_message,
            files_affected_json, summary_json, log_path,
            origin, batch_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job.id,
            job.file_id,
            job.file_path,
            job.job_type.value,
            job.status.value,
            job.priority,
            job.policy_name,
            job.policy_json,
            job.progress_percent,
            job.progress_json,
            job.created_at,
            job.started_at,
            job.completed_at,
            job.worker_pid,
            job.worker_heartbeat,
            job.output_path,
            job.backup_path,
            job.error_message,
            job.files_affected_json,
            job.summary_json,
            job.log_path,
            job.origin,
            job.batch_id,
        ),
    )
    return job.id


def get_job(conn: sqlite3.Connection, job_id: str) -> Job | None:
    """Get a job by ID.

    Args:
        conn: Database connection.
        job_id: Job UUID.

    Returns:
        Job if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, file_id, file_path, job_type, status, priority,
               policy_name, policy_json, progress_percent, progress_json,
               created_at, started_at, completed_at,
               worker_pid, worker_heartbeat,
               output_path, backup_path, error_message,
               files_affected_json, summary_json, log_path,
               origin, batch_id
        FROM jobs WHERE id = ?
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_job(row)


def update_job_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: JobStatus,
    error_message: str | None = None,
    completed_at: str | None = None,
) -> bool:
    """Update a job's status.

    Args:
        conn: Database connection.
        job_id: Job UUID.
        status: New status.
        error_message: Error message if status is FAILED.
        completed_at: Completion timestamp (ISO-8601 UTC).

    Returns:
        True if job was updated, False if job not found.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        UPDATE jobs SET status = ?, error_message = ?, completed_at = ?
        WHERE id = ?
        """,
        (status.value, error_message, completed_at, job_id),
    )
    return cursor.rowcount > 0


def update_job_progress(
    conn: sqlite3.Connection,
    job_id: str,
    progress_percent: float,
    progress_json: str | None = None,
) -> bool:
    """Update a job's progress.

    Args:
        conn: Database connection.
        job_id: Job UUID.
        progress_percent: Progress percentage (0-100).
        progress_json: JSON-encoded detailed progress.

    Returns:
        True if job was updated, False if job not found.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        UPDATE jobs SET progress_percent = ?, progress_json = ?
        WHERE id = ?
        """,
        (progress_percent, progress_json, job_id),
    )
    return cursor.rowcount > 0


def update_job_worker(
    conn: sqlite3.Connection,
    job_id: str,
    worker_pid: int | None,
    worker_heartbeat: str | None,
    started_at: str | None = None,
) -> bool:
    """Update a job's worker info.

    Args:
        conn: Database connection.
        job_id: Job UUID.
        worker_pid: Worker process ID.
        worker_heartbeat: Heartbeat timestamp (ISO-8601 UTC).
        started_at: Start timestamp (ISO-8601 UTC).

    Returns:
        True if job was updated, False if job not found.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    if started_at:
        cursor = conn.execute(
            """
            UPDATE jobs SET worker_pid = ?, worker_heartbeat = ?, started_at = ?
            WHERE id = ?
            """,
            (worker_pid, worker_heartbeat, started_at, job_id),
        )
    else:
        cursor = conn.execute(
            """
            UPDATE jobs SET worker_pid = ?, worker_heartbeat = ?
            WHERE id = ?
            """,
            (worker_pid, worker_heartbeat, job_id),
        )
    return cursor.rowcount > 0


def update_job_output(
    conn: sqlite3.Connection,
    job_id: str,
    output_path: str | None,
    backup_path: str | None = None,
) -> bool:
    """Update a job's output paths.

    Args:
        conn: Database connection.
        job_id: Job UUID.
        output_path: Path to output file.
        backup_path: Path to backup of original.

    Returns:
        True if job was updated, False if job not found.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        UPDATE jobs SET output_path = ?, backup_path = ?
        WHERE id = ?
        """,
        (output_path, backup_path, job_id),
    )
    return cursor.rowcount > 0


def get_queued_jobs(conn: sqlite3.Connection, limit: int | None = None) -> list[Job]:
    """Get queued jobs ordered by priority and creation time.

    Args:
        conn: Database connection.
        limit: Maximum number of jobs to return.

    Returns:
        List of Job objects.
    """
    query = """
        SELECT id, file_id, file_path, job_type, status, priority,
               policy_name, policy_json, progress_percent, progress_json,
               created_at, started_at, completed_at,
               worker_pid, worker_heartbeat,
               output_path, backup_path, error_message,
               files_affected_json, summary_json, log_path,
               origin, batch_id
        FROM jobs
        WHERE status = 'queued'
        ORDER BY priority ASC, created_at ASC
    """
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0 or limit > 10000:
            raise ValueError(f"Invalid limit value: {limit}")
        cursor = conn.execute(query + " LIMIT ?", (limit,))
    else:
        cursor = conn.execute(query)
    return [_row_to_job(row) for row in cursor.fetchall()]


def get_jobs_by_status(
    conn: sqlite3.Connection, status: JobStatus, limit: int | None = None
) -> list[Job]:
    """Get jobs by status.

    Args:
        conn: Database connection.
        status: Job status to filter by.
        limit: Maximum number of jobs to return.

    Returns:
        List of Job objects.
    """
    query = """
        SELECT id, file_id, file_path, job_type, status, priority,
               policy_name, policy_json, progress_percent, progress_json,
               created_at, started_at, completed_at,
               worker_pid, worker_heartbeat,
               output_path, backup_path, error_message,
               files_affected_json, summary_json, log_path,
               origin, batch_id
        FROM jobs
        WHERE status = ?
        ORDER BY created_at DESC
    """
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0 or limit > 10000:
            raise ValueError(f"Invalid limit value: {limit}")
        cursor = conn.execute(query + " LIMIT ?", (status.value, limit))
    else:
        cursor = conn.execute(query, (status.value,))
    return [_row_to_job(row) for row in cursor.fetchall()]


def get_all_jobs(conn: sqlite3.Connection, limit: int | None = None) -> list[Job]:
    """Get all jobs ordered by creation time (newest first).

    Args:
        conn: Database connection.
        limit: Maximum number of jobs to return.

    Returns:
        List of Job objects.
    """
    query = """
        SELECT id, file_id, file_path, job_type, status, priority,
               policy_name, policy_json, progress_percent, progress_json,
               created_at, started_at, completed_at,
               worker_pid, worker_heartbeat,
               output_path, backup_path, error_message,
               files_affected_json, summary_json, log_path,
               origin, batch_id
        FROM jobs
        ORDER BY created_at DESC
    """
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0 or limit > 10000:
            raise ValueError(f"Invalid limit value: {limit}")
        cursor = conn.execute(query + " LIMIT ?", (limit,))
    else:
        cursor = conn.execute(query)
    return [_row_to_job(row) for row in cursor.fetchall()]


def get_jobs_by_id_prefix(conn: sqlite3.Connection, prefix: str) -> list[Job]:
    """Get jobs by ID prefix.

    Efficient lookup of jobs by UUID prefix using SQL LIKE.

    Args:
        conn: Database connection.
        prefix: Job ID prefix to search for.

    Returns:
        List of matching Job objects.
    """
    query = """
        SELECT id, file_id, file_path, job_type, status, priority,
               policy_name, policy_json, progress_percent, progress_json,
               created_at, started_at, completed_at,
               worker_pid, worker_heartbeat,
               output_path, backup_path, error_message,
               files_affected_json, summary_json, log_path,
               origin, batch_id
        FROM jobs
        WHERE id LIKE ?
        ORDER BY created_at DESC
    """
    cursor = conn.execute(query, (f"{prefix}%",))
    return [_row_to_job(row) for row in cursor.fetchall()]


def get_jobs_filtered(
    conn: sqlite3.Connection,
    *,
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    since: str | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[Job] | tuple[list[Job], int]:
    """Get jobs with flexible filtering (008-operational-ux).

    Supports filtering by status, type, date range, and filename search.
    Supports sorting by various columns.

    Args:
        conn: Database connection.
        status: Filter by job status (None = all statuses).
        job_type: Filter by job type (None = all types).
        since: ISO-8601 timestamp - only return jobs created after this time.
        search: Case-insensitive substring search on file_path.
        sort_by: Column to sort by (created_at, job_type, status, file_path, duration).
        sort_order: Sort order ('asc' or 'desc').
        limit: Maximum number of jobs to return.
        offset: Number of jobs to skip (for pagination).
        return_total: If True, return tuple of (jobs, total_count).

    Returns:
        List of Job objects, ordered by specified sort or created_at DESC.
        If return_total=True, returns tuple of (jobs, total_count).
    """
    # Build WHERE clause
    conditions = []
    params: list[str | int] = []

    if status is not None:
        conditions.append("status = ?")
        params.append(status.value)

    if job_type is not None:
        conditions.append("job_type = ?")
        params.append(job_type.value)

    if since is not None:
        conditions.append("created_at >= ?")
        params.append(since)

    if search is not None:
        escaped = _escape_like_pattern(search)
        conditions.append("LOWER(file_path) LIKE LOWER(?) ESCAPE '\\'")
        params.append(f"%{escaped}%")

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    # Get total count if requested (before applying LIMIT/OFFSET)
    total = 0
    if return_total:
        count_query = "SELECT COUNT(*) FROM jobs" + where_clause
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

    # Build main query
    base_query = """
        SELECT id, file_id, file_path, job_type, status, priority,
               policy_name, policy_json, progress_percent, progress_json,
               created_at, started_at, completed_at,
               worker_pid, worker_heartbeat,
               output_path, backup_path, error_message,
               files_affected_json, summary_json, log_path,
               origin, batch_id
        FROM jobs
    """
    base_query += where_clause

    # Build ORDER BY clause (validated against whitelist)
    order_column = sort_by if sort_by in SORTABLE_JOB_COLUMNS else "created_at"
    order_direction = sort_order.upper() if sort_order in ("asc", "desc") else "DESC"

    if order_column == "duration":
        # Duration is computed: completed_at - created_at
        # Sort NULLs (running jobs) to end regardless of sort direction
        if order_direction == "ASC":
            base_query += """
                ORDER BY
                    CASE WHEN completed_at IS NULL THEN 1 ELSE 0 END,
                    (julianday(completed_at) - julianday(created_at)) ASC
            """
        else:
            base_query += """
                ORDER BY
                    CASE WHEN completed_at IS NULL THEN 1 ELSE 0 END,
                    (julianday(completed_at) - julianday(created_at)) DESC
            """
    else:
        base_query += f" ORDER BY {order_column} {order_direction}"

    # Apply pagination
    pagination_params = list(params)  # Copy params for pagination query
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0 or limit > 10000:
            raise ValueError(f"Invalid limit value: {limit}")
        base_query += " LIMIT ?"
        pagination_params.append(limit)

        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise ValueError(f"Invalid offset value: {offset}")
            base_query += " OFFSET ?"
            pagination_params.append(offset)

    cursor = conn.execute(base_query, pagination_params)
    jobs = [_row_to_job(row) for row in cursor.fetchall()]

    if return_total:
        return jobs, total
    return jobs


def delete_job(conn: sqlite3.Connection, job_id: str) -> bool:
    """Delete a job.

    Args:
        conn: Database connection.
        job_id: Job UUID.

    Returns:
        True if job was deleted, False if job not found.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    return cursor.rowcount > 0


def delete_old_jobs(
    conn: sqlite3.Connection, older_than: str, statuses: list[JobStatus] | None = None
) -> int:
    """Delete old jobs.

    Args:
        conn: Database connection.
        older_than: ISO-8601 UTC timestamp. Jobs created before this are deleted.
        statuses: If provided, only delete jobs with these statuses.
                  Defaults to [COMPLETED, FAILED, CANCELLED].

    Returns:
        Number of jobs deleted.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    if statuses is None:
        statuses = [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]

    placeholders = ",".join("?" * len(statuses))
    cursor = conn.execute(
        f"""
        DELETE FROM jobs
        WHERE created_at < ? AND status IN ({placeholders})
        """,
        (older_than, *[s.value for s in statuses]),
    )
    return cursor.rowcount
