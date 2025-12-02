"""CRUD operations for Video Policy Orchestrator database.

This module contains all database query functions for the db layer:
- File and track CRUD operations
- Job queue operations
- Plugin acknowledgment operations
- Transcription and language analysis operations

All functions follow these conventions:
- First parameter is always `conn: sqlite3.Connection`
- Functions return typed dataclasses from `types.py`
- Functions do not manage transactions unless explicitly noted
"""

import sqlite3

from .types import (
    ActionResultRecord,
    FileRecord,
    Job,
    JobStatus,
    JobType,
    LanguageAnalysisResultRecord,
    LanguageSegmentRecord,
    PerformanceMetricsRecord,
    PluginAcknowledgment,
    ProcessingStatsRecord,
    TrackInfo,
    TrackRecord,
    TranscriptionResultRecord,
)

# ==========================================================================
# Row Mapping Helpers
# ==========================================================================


def _row_to_file_record(row: sqlite3.Row) -> FileRecord:
    """Convert a database row to FileRecord using named columns.

    Args:
        row: sqlite3.Row from a SELECT query on the files table.

    Returns:
        FileRecord instance populated from the row.
    """
    return FileRecord(
        id=row["id"],
        path=row["path"],
        filename=row["filename"],
        directory=row["directory"],
        extension=row["extension"],
        size_bytes=row["size_bytes"],
        modified_at=row["modified_at"],
        content_hash=row["content_hash"],
        container_format=row["container_format"],
        scanned_at=row["scanned_at"],
        scan_status=row["scan_status"],
        scan_error=row["scan_error"],
        job_id=row["job_id"],
        plugin_metadata=row["plugin_metadata"],
    )


def _row_to_track_record(row: sqlite3.Row) -> TrackRecord:
    """Convert a database row to TrackRecord using named columns.

    Args:
        row: sqlite3.Row from a SELECT query on the tracks table.

    Returns:
        TrackRecord instance populated from the row.
    """
    return TrackRecord(
        id=row["id"],
        file_id=row["file_id"],
        track_index=row["track_index"],
        track_type=row["track_type"],
        codec=row["codec"],
        language=row["language"],
        title=row["title"],
        is_default=row["is_default"] == 1,
        is_forced=row["is_forced"] == 1,
        channels=row["channels"],
        channel_layout=row["channel_layout"],
        width=row["width"],
        height=row["height"],
        frame_rate=row["frame_rate"],
        color_transfer=row["color_transfer"],
        color_primaries=row["color_primaries"],
        color_space=row["color_space"],
        color_range=row["color_range"],
        duration_seconds=row["duration_seconds"],
    )


def _row_to_job(row: sqlite3.Row) -> Job:
    """Convert a database row to a Job object.

    Args:
        row: sqlite3.Row from a SELECT query on the jobs table.

    Returns:
        Job instance populated from the row.
    """
    return Job(
        id=row["id"],
        file_id=row["file_id"],
        file_path=row["file_path"],
        job_type=JobType(row["job_type"]),
        status=JobStatus(row["status"]),
        priority=row["priority"],
        policy_name=row["policy_name"],
        policy_json=row["policy_json"],
        progress_percent=row["progress_percent"],
        progress_json=row["progress_json"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        worker_pid=row["worker_pid"],
        worker_heartbeat=row["worker_heartbeat"],
        output_path=row["output_path"],
        backup_path=row["backup_path"],
        error_message=row["error_message"],
        files_affected_json=row["files_affected_json"],
        summary_json=row["summary_json"],
        log_path=row["log_path"],
    )


# ==========================================================================
# File Operations
# ==========================================================================


def insert_file(conn: sqlite3.Connection, record: FileRecord) -> int:
    """Insert a new file record into the database.

    Args:
        conn: Database connection.
        record: File record to insert.

    Returns:
        The ID of the inserted record.
    """
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            modified_at, content_hash, container_format,
            scanned_at, scan_status, scan_error, job_id, plugin_metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.path,
            record.filename,
            record.directory,
            record.extension,
            record.size_bytes,
            record.modified_at,
            record.content_hash,
            record.container_format,
            record.scanned_at,
            record.scan_status,
            record.scan_error,
            record.job_id,
            record.plugin_metadata,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def upsert_file(conn: sqlite3.Connection, record: FileRecord) -> int:
    """Insert or update a file record (upsert by path).

    Args:
        conn: Database connection.
        record: File record to insert or update.

    Returns:
        The ID of the inserted/updated record.
    """
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            modified_at, content_hash, container_format,
            scanned_at, scan_status, scan_error, job_id, plugin_metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            filename = excluded.filename,
            directory = excluded.directory,
            extension = excluded.extension,
            size_bytes = excluded.size_bytes,
            modified_at = excluded.modified_at,
            content_hash = excluded.content_hash,
            container_format = excluded.container_format,
            scanned_at = excluded.scanned_at,
            scan_status = excluded.scan_status,
            scan_error = excluded.scan_error,
            job_id = excluded.job_id,
            plugin_metadata = excluded.plugin_metadata
        RETURNING id
        """,
        (
            record.path,
            record.filename,
            record.directory,
            record.extension,
            record.size_bytes,
            record.modified_at,
            record.content_hash,
            record.container_format,
            record.scanned_at,
            record.scan_status,
            record.scan_error,
            record.job_id,
            record.plugin_metadata,
        ),
    )
    result = cursor.fetchone()
    conn.commit()
    if result is None:
        raise sqlite3.IntegrityError(
            f"RETURNING clause failed to return file ID for path: {record.path}"
        )
    return result[0]


def get_file_by_path(conn: sqlite3.Connection, path: str) -> FileRecord | None:
    """Get a file record by path.

    Args:
        conn: Database connection.
        path: File path to look up.

    Returns:
        FileRecord if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, path, filename, directory, extension, size_bytes,
               modified_at, content_hash, container_format,
               scanned_at, scan_status, scan_error, job_id, plugin_metadata
        FROM files WHERE path = ?
        """,
        (path,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return _row_to_file_record(row)


def get_file_by_id(conn: sqlite3.Connection, file_id: int) -> FileRecord | None:
    """Get a file record by ID.

    Args:
        conn: Database connection.
        file_id: File primary key.

    Returns:
        FileRecord if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, path, filename, directory, extension, size_bytes,
               modified_at, content_hash, container_format,
               scanned_at, scan_status, scan_error, job_id, plugin_metadata
        FROM files WHERE id = ?
        """,
        (file_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return _row_to_file_record(row)


def delete_file(conn: sqlite3.Connection, file_id: int) -> None:
    """Delete a file record and its associated tracks.

    Args:
        conn: Database connection.
        file_id: ID of the file to delete.
    """
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()


# ==========================================================================
# Track Operations
# ==========================================================================


def insert_track(conn: sqlite3.Connection, record: TrackRecord) -> int:
    """Insert a new track record.

    Args:
        conn: Database connection.
        record: Track record to insert.

    Returns:
        The ID of the inserted record.
    """
    cursor = conn.execute(
        """
        INSERT INTO tracks (
            file_id, track_index, track_type, codec,
            language, title, is_default, is_forced,
            channels, channel_layout, width, height, frame_rate,
            color_transfer, color_primaries, color_space, color_range,
            duration_seconds
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.file_id,
            record.track_index,
            record.track_type,
            record.codec,
            record.language,
            record.title,
            1 if record.is_default else 0,
            1 if record.is_forced else 0,
            record.channels,
            record.channel_layout,
            record.width,
            record.height,
            record.frame_rate,
            record.color_transfer,
            record.color_primaries,
            record.color_space,
            record.color_range,
            record.duration_seconds,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_tracks_for_file(conn: sqlite3.Connection, file_id: int) -> list[TrackRecord]:
    """Get all tracks for a file.

    Args:
        conn: Database connection.
        file_id: ID of the file.

    Returns:
        List of TrackRecord objects.
    """
    cursor = conn.execute(
        """
        SELECT id, file_id, track_index, track_type, codec,
               language, title, is_default, is_forced,
               channels, channel_layout, width, height, frame_rate,
               color_transfer, color_primaries, color_space, color_range,
               duration_seconds
        FROM tracks WHERE file_id = ?
        ORDER BY track_index
        """,
        (file_id,),
    )
    return [_row_to_track_record(row) for row in cursor.fetchall()]


def delete_tracks_for_file(conn: sqlite3.Connection, file_id: int) -> None:
    """Delete all tracks for a file.

    Args:
        conn: Database connection.
        file_id: ID of the file.
    """
    conn.execute("DELETE FROM tracks WHERE file_id = ?", (file_id,))
    conn.commit()


def upsert_tracks_for_file(
    conn: sqlite3.Connection, file_id: int, tracks: list[TrackInfo]
) -> None:
    """Smart merge tracks for a file: update existing, insert new, delete missing.

    Note:
        This function does NOT commit. The caller is responsible for transaction
        management to ensure atomicity with the parent file record.

    Args:
        conn: Database connection.
        file_id: ID of the parent file.
        tracks: List of TrackInfo objects from introspection.

    Algorithm:
        1. Get existing track indices for file_id
        2. For each new track:
           - If track_index exists: UPDATE all fields
           - If track_index is new: INSERT
        3. DELETE tracks with indices not in new list
    """
    # Get existing track indices
    cursor = conn.execute(
        "SELECT track_index FROM tracks WHERE file_id = ?", (file_id,)
    )
    existing_indices = {row[0] for row in cursor.fetchall()}

    # Track which indices we've processed
    new_indices = {track.index for track in tracks}

    for track in tracks:
        if track.index in existing_indices:
            # Update existing track
            conn.execute(
                """
                UPDATE tracks SET
                    track_type = ?, codec = ?, language = ?, title = ?,
                    is_default = ?, is_forced = ?, channels = ?, channel_layout = ?,
                    width = ?, height = ?, frame_rate = ?, duration_seconds = ?,
                    color_transfer = ?, color_primaries = ?, color_space = ?,
                    color_range = ?
                WHERE file_id = ? AND track_index = ?
                """,
                (
                    track.track_type,
                    track.codec,
                    track.language,
                    track.title,
                    1 if track.is_default else 0,
                    1 if track.is_forced else 0,
                    track.channels,
                    track.channel_layout,
                    track.width,
                    track.height,
                    track.frame_rate,
                    track.duration_seconds,
                    track.color_transfer,
                    track.color_primaries,
                    track.color_space,
                    track.color_range,
                    file_id,
                    track.index,
                ),
            )
        else:
            # Insert new track
            record = TrackRecord.from_track_info(track, file_id)
            conn.execute(
                """
                INSERT INTO tracks (
                    file_id, track_index, track_type, codec,
                    language, title, is_default, is_forced,
                    channels, channel_layout, width, height, frame_rate,
                    duration_seconds, color_transfer, color_primaries,
                    color_space, color_range
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.file_id,
                    record.track_index,
                    record.track_type,
                    record.codec,
                    record.language,
                    record.title,
                    1 if record.is_default else 0,
                    1 if record.is_forced else 0,
                    record.channels,
                    record.channel_layout,
                    record.width,
                    record.height,
                    record.frame_rate,
                    record.duration_seconds,
                    record.color_transfer,
                    record.color_primaries,
                    record.color_space,
                    record.color_range,
                ),
            )

    # Delete tracks that are no longer present
    stale_indices = existing_indices - new_indices
    if stale_indices:
        placeholders = ",".join("?" * len(stale_indices))
        conn.execute(
            f"DELETE FROM tracks WHERE file_id = ? AND track_index IN ({placeholders})",
            (file_id, *stale_indices),
        )

    # Note: commit removed - caller (upsert_file) handles transaction boundaries


# ==========================================================================
# Plugin Acknowledgment Operations
# ==========================================================================


def get_plugin_acknowledgment(
    conn: sqlite3.Connection, plugin_name: str, plugin_hash: str
) -> PluginAcknowledgment | None:
    """Get a plugin acknowledgment by name and hash.

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier.
        plugin_hash: SHA-256 hash of plugin file(s).

    Returns:
        PluginAcknowledgment if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, plugin_name, plugin_hash, acknowledged_at, acknowledged_by
        FROM plugin_acknowledgments
        WHERE plugin_name = ? AND plugin_hash = ?
        """,
        (plugin_name, plugin_hash),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return PluginAcknowledgment(
        id=row[0],
        plugin_name=row[1],
        plugin_hash=row[2],
        acknowledged_at=row[3],
        acknowledged_by=row[4],
    )


def is_plugin_acknowledged(
    conn: sqlite3.Connection, plugin_name: str, plugin_hash: str
) -> bool:
    """Check if a plugin has been acknowledged with the given hash.

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier.
        plugin_hash: SHA-256 hash of plugin file(s).

    Returns:
        True if acknowledged, False otherwise.
    """
    return get_plugin_acknowledgment(conn, plugin_name, plugin_hash) is not None


def insert_plugin_acknowledgment(
    conn: sqlite3.Connection, record: PluginAcknowledgment
) -> int:
    """Insert a new plugin acknowledgment record.

    Args:
        conn: Database connection.
        record: PluginAcknowledgment to insert.

    Returns:
        The ID of the inserted record.
    """
    cursor = conn.execute(
        """
        INSERT INTO plugin_acknowledgments (
            plugin_name, plugin_hash, acknowledged_at, acknowledged_by
        ) VALUES (?, ?, ?, ?)
        """,
        (
            record.plugin_name,
            record.plugin_hash,
            record.acknowledged_at,
            record.acknowledged_by,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_acknowledgments_for_plugin(
    conn: sqlite3.Connection, plugin_name: str
) -> list[PluginAcknowledgment]:
    """Get all acknowledgments for a plugin (all hash versions).

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier.

    Returns:
        List of PluginAcknowledgment records.
    """
    cursor = conn.execute(
        """
        SELECT id, plugin_name, plugin_hash, acknowledged_at, acknowledged_by
        FROM plugin_acknowledgments
        WHERE plugin_name = ?
        ORDER BY acknowledged_at DESC
        """,
        (plugin_name,),
    )
    return [
        PluginAcknowledgment(
            id=row[0],
            plugin_name=row[1],
            plugin_hash=row[2],
            acknowledged_at=row[3],
            acknowledged_by=row[4],
        )
        for row in cursor.fetchall()
    ]


def delete_plugin_acknowledgment(
    conn: sqlite3.Connection, plugin_name: str, plugin_hash: str
) -> bool:
    """Delete a plugin acknowledgment.

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier.
        plugin_hash: SHA-256 hash of plugin file(s).

    Returns:
        True if a record was deleted, False otherwise.
    """
    cursor = conn.execute(
        """
        DELETE FROM plugin_acknowledgments
        WHERE plugin_name = ? AND plugin_hash = ?
        """,
        (plugin_name, plugin_hash),
    )
    conn.commit()
    return cursor.rowcount > 0


# ==========================================================================
# Job Operations
# ==========================================================================


def insert_job(conn: sqlite3.Connection, job: Job) -> str:
    """Insert a new job record.

    Args:
        conn: Database connection.
        job: Job to insert.

    Returns:
        The ID of the inserted job.
    """
    conn.execute(
        """
        INSERT INTO jobs (
            id, file_id, file_path, job_type, status, priority,
            policy_name, policy_json, progress_percent, progress_json,
            created_at, started_at, completed_at,
            worker_pid, worker_heartbeat,
            output_path, backup_path, error_message,
            files_affected_json, summary_json, log_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        ),
    )
    conn.commit()
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
               files_affected_json, summary_json, log_path
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
    """
    cursor = conn.execute(
        """
        UPDATE jobs SET status = ?, error_message = ?, completed_at = ?
        WHERE id = ?
        """,
        (status.value, error_message, completed_at, job_id),
    )
    conn.commit()
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
    """
    cursor = conn.execute(
        """
        UPDATE jobs SET progress_percent = ?, progress_json = ?
        WHERE id = ?
        """,
        (progress_percent, progress_json, job_id),
    )
    conn.commit()
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
    conn.commit()
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
    """
    cursor = conn.execute(
        """
        UPDATE jobs SET output_path = ?, backup_path = ?
        WHERE id = ?
        """,
        (output_path, backup_path, job_id),
    )
    conn.commit()
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
               files_affected_json, summary_json, log_path
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
               files_affected_json, summary_json, log_path
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
               files_affected_json, summary_json, log_path
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
               files_affected_json, summary_json, log_path
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
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[Job] | tuple[list[Job], int]:
    """Get jobs with flexible filtering (008-operational-ux).

    Supports filtering by status, type, and date range.

    Args:
        conn: Database connection.
        status: Filter by job status (None = all statuses).
        job_type: Filter by job type (None = all types).
        since: ISO-8601 timestamp - only return jobs created after this time.
        limit: Maximum number of jobs to return.
        offset: Number of jobs to skip (for pagination).
        return_total: If True, return tuple of (jobs, total_count).

    Returns:
        List of Job objects, ordered by created_at DESC.
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
               files_affected_json, summary_json, log_path
        FROM jobs
    """
    base_query += where_clause
    base_query += " ORDER BY created_at DESC"

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
    """
    cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
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
    conn.commit()
    return cursor.rowcount


# ==========================================================================
# Transcription Result Operations
# ==========================================================================


def upsert_transcription_result(
    conn: sqlite3.Connection, record: TranscriptionResultRecord
) -> int:
    """Insert or update transcription result for a track.

    Uses ON CONFLICT to handle re-detection scenarios. Uses BEGIN IMMEDIATE
    with retry logic to handle concurrent write contention gracefully.

    Args:
        conn: Database connection.
        record: TranscriptionResultRecord to insert/update.

    Returns:
        The record ID.

    Raises:
        sqlite3.Error: If database operation fails after retries.
    """
    from .connection import execute_with_retry

    def do_upsert() -> int:
        # Check if already in a transaction (implicit or explicit)
        # If so, just do the upsert within that transaction
        # If not, use BEGIN IMMEDIATE for fail-fast lock detection
        manage_transaction = not conn.in_transaction

        if manage_transaction:
            conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                """
                INSERT INTO transcription_results (
                    track_id, detected_language, confidence_score, track_type,
                    transcript_sample, plugin_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    detected_language = excluded.detected_language,
                    confidence_score = excluded.confidence_score,
                    track_type = excluded.track_type,
                    transcript_sample = excluded.transcript_sample,
                    plugin_name = excluded.plugin_name,
                    updated_at = excluded.updated_at
                RETURNING id
                """,
                (
                    record.track_id,
                    record.detected_language,
                    record.confidence_score,
                    record.track_type,
                    record.transcript_sample,
                    record.plugin_name,
                    record.created_at,
                    record.updated_at,
                ),
            )
            result = cursor.fetchone()
            if manage_transaction:
                conn.execute("COMMIT")
            if result is None:
                raise sqlite3.Error(
                    f"RETURNING clause failed for track_id={record.track_id}"
                )
            return result[0]
        except Exception:
            if manage_transaction:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass  # Original error is more important
            raise

    return execute_with_retry(do_upsert)


def get_transcription_result(
    conn: sqlite3.Connection, track_id: int
) -> TranscriptionResultRecord | None:
    """Get transcription result for a track, if exists.

    Args:
        conn: Database connection.
        track_id: ID of the track.

    Returns:
        TranscriptionResultRecord if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, track_id, detected_language, confidence_score, track_type,
               transcript_sample, plugin_name, created_at, updated_at
        FROM transcription_results
        WHERE track_id = ?
        """,
        (track_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return TranscriptionResultRecord(
        id=row[0],
        track_id=row[1],
        detected_language=row[2],
        confidence_score=row[3],
        track_type=row[4],
        transcript_sample=row[5],
        plugin_name=row[6],
        created_at=row[7],
        updated_at=row[8],
    )


def delete_transcription_results_for_file(
    conn: sqlite3.Connection, file_id: int
) -> int:
    """Delete all transcription results for tracks in a file.

    Called when file is re-scanned or deleted.

    Args:
        conn: Database connection.
        file_id: ID of the file.

    Returns:
        Count of deleted records.
    """
    cursor = conn.execute(
        """
        DELETE FROM transcription_results
        WHERE track_id IN (SELECT id FROM tracks WHERE file_id = ?)
        """,
        (file_id,),
    )
    conn.commit()
    return cursor.rowcount


def get_transcriptions_for_tracks(
    conn: sqlite3.Connection, track_ids: list[int]
) -> dict[int, TranscriptionResultRecord]:
    """Get transcription results for a list of track IDs.

    Args:
        conn: Database connection.
        track_ids: List of track IDs to query.

    Returns:
        Dictionary mapping track_id to TranscriptionResultRecord.
    """
    if not track_ids:
        return {}

    placeholders = ",".join("?" * len(track_ids))
    cursor = conn.execute(
        f"""
        SELECT id, track_id, detected_language, confidence_score, track_type,
               transcript_sample, plugin_name, created_at, updated_at
        FROM transcription_results
        WHERE track_id IN ({placeholders})
        """,
        tuple(track_ids),
    )

    result = {}
    for row in cursor.fetchall():
        record = TranscriptionResultRecord(
            id=row[0],
            track_id=row[1],
            detected_language=row[2],
            confidence_score=row[3],
            track_type=row[4],
            transcript_sample=row[5],
            plugin_name=row[6],
            created_at=row[7],
            updated_at=row[8],
        )
        result[record.track_id] = record

    return result


# ==========================================================================
# Language Analysis Operations (035-multi-language-audio-detection)
# ==========================================================================


def upsert_language_analysis_result(
    conn: sqlite3.Connection, record: LanguageAnalysisResultRecord
) -> int:
    """Insert or update language analysis result for a track.

    Uses ON CONFLICT to handle re-analysis scenarios. Uses BEGIN IMMEDIATE
    with retry logic to handle concurrent write contention gracefully.

    Args:
        conn: Database connection.
        record: LanguageAnalysisResultRecord to insert/update.

    Returns:
        The record ID.

    Raises:
        sqlite3.Error: If database operation fails after retries.
    """
    from .connection import execute_with_retry

    def do_upsert() -> int:
        # Check if already in a transaction (implicit or explicit)
        # If so, just do the upsert within that transaction
        # If not, use BEGIN IMMEDIATE for fail-fast lock detection
        manage_transaction = not conn.in_transaction

        if manage_transaction:
            conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                """
                INSERT INTO language_analysis_results (
                    track_id, file_hash, primary_language, primary_percentage,
                    classification, analysis_metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    primary_language = excluded.primary_language,
                    primary_percentage = excluded.primary_percentage,
                    classification = excluded.classification,
                    analysis_metadata = excluded.analysis_metadata,
                    updated_at = excluded.updated_at
                RETURNING id
                """,
                (
                    record.track_id,
                    record.file_hash,
                    record.primary_language,
                    record.primary_percentage,
                    record.classification,
                    record.analysis_metadata,
                    record.created_at,
                    record.updated_at,
                ),
            )
            result = cursor.fetchone()
            if manage_transaction:
                conn.execute("COMMIT")
            if result is None:
                raise sqlite3.Error(
                    f"RETURNING clause failed for track_id={record.track_id}"
                )
            return result[0]
        except Exception:
            if manage_transaction:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass  # Original error is more important
            raise

    return execute_with_retry(do_upsert)


def get_language_analysis_result(
    conn: sqlite3.Connection, track_id: int
) -> LanguageAnalysisResultRecord | None:
    """Get language analysis result for a track, if exists.

    Args:
        conn: Database connection.
        track_id: ID of the track.

    Returns:
        LanguageAnalysisResultRecord if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, track_id, file_hash, primary_language, primary_percentage,
               classification, analysis_metadata, created_at, updated_at
        FROM language_analysis_results
        WHERE track_id = ?
        """,
        (track_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return LanguageAnalysisResultRecord(
        id=row[0],
        track_id=row[1],
        file_hash=row[2],
        primary_language=row[3],
        primary_percentage=row[4],
        classification=row[5],
        analysis_metadata=row[6],
        created_at=row[7],
        updated_at=row[8],
    )


def delete_language_analysis_result(conn: sqlite3.Connection, track_id: int) -> bool:
    """Delete language analysis result for a track.

    Also deletes associated language segments via CASCADE.

    Args:
        conn: Database connection.
        track_id: ID of the track.

    Returns:
        True if a record was deleted, False otherwise.
    """
    cursor = conn.execute(
        "DELETE FROM language_analysis_results WHERE track_id = ?",
        (track_id,),
    )
    conn.commit()
    return cursor.rowcount > 0


def upsert_language_segments(
    conn: sqlite3.Connection, analysis_id: int, segments: list[LanguageSegmentRecord]
) -> list[int]:
    """Insert or replace language segments for an analysis.

    Deletes existing segments for the analysis_id and inserts new ones.
    This ensures segments stay in sync with the analysis result. Uses
    BEGIN IMMEDIATE with retry logic to handle concurrent write contention.

    Args:
        conn: Database connection.
        analysis_id: ID of the language_analysis_results record.
        segments: List of LanguageSegmentRecord to insert.

    Returns:
        List of inserted segment IDs.

    Raises:
        sqlite3.Error: If database operation fails after retries.
    """
    from .connection import execute_with_retry

    def do_upsert() -> list[int]:
        # Check if already in a transaction (implicit or explicit)
        # If so, just do the upsert within that transaction
        # If not, use BEGIN IMMEDIATE for fail-fast lock detection
        manage_transaction = not conn.in_transaction

        if manage_transaction:
            conn.execute("BEGIN IMMEDIATE")
        try:
            # Delete existing segments for this analysis
            conn.execute(
                "DELETE FROM language_segments WHERE analysis_id = ?",
                (analysis_id,),
            )

            # Insert new segments
            segment_ids = []
            for segment in segments:
                cursor = conn.execute(
                    """
                    INSERT INTO language_segments (
                        analysis_id, language_code, start_time, end_time, confidence
                    ) VALUES (?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (
                        analysis_id,
                        segment.language_code,
                        segment.start_time,
                        segment.end_time,
                        segment.confidence,
                    ),
                )
                result = cursor.fetchone()
                if result:
                    segment_ids.append(result[0])

            if manage_transaction:
                conn.execute("COMMIT")
            return segment_ids
        except Exception:
            if manage_transaction:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass  # Original error is more important
            raise

    return execute_with_retry(do_upsert)


def get_language_segments(
    conn: sqlite3.Connection, analysis_id: int
) -> list[LanguageSegmentRecord]:
    """Get all language segments for an analysis.

    Args:
        conn: Database connection.
        analysis_id: ID of the language_analysis_results record.

    Returns:
        List of LanguageSegmentRecord objects ordered by start_time.
    """
    cursor = conn.execute(
        """
        SELECT id, analysis_id, language_code, start_time, end_time, confidence
        FROM language_segments
        WHERE analysis_id = ?
        ORDER BY start_time
        """,
        (analysis_id,),
    )
    return [
        LanguageSegmentRecord(
            id=row[0],
            analysis_id=row[1],
            language_code=row[2],
            start_time=row[3],
            end_time=row[4],
            confidence=row[5],
        )
        for row in cursor.fetchall()
    ]


def get_language_analysis_by_file_hash(
    conn: sqlite3.Connection, file_hash: str
) -> list[LanguageAnalysisResultRecord]:
    """Get all language analysis results with matching file hash.

    Useful for finding cached results when file content matches.

    Args:
        conn: Database connection.
        file_hash: Content hash to search for.

    Returns:
        List of LanguageAnalysisResultRecord objects.
    """
    cursor = conn.execute(
        """
        SELECT id, track_id, file_hash, primary_language, primary_percentage,
               classification, analysis_metadata, created_at, updated_at
        FROM language_analysis_results
        WHERE file_hash = ?
        """,
        (file_hash,),
    )
    return [
        LanguageAnalysisResultRecord(
            id=row[0],
            track_id=row[1],
            file_hash=row[2],
            primary_language=row[3],
            primary_percentage=row[4],
            classification=row[5],
            analysis_metadata=row[6],
            created_at=row[7],
            updated_at=row[8],
        )
        for row in cursor.fetchall()
    ]


def delete_language_analysis_for_file(conn: sqlite3.Connection, file_id: int) -> int:
    """Delete all language analysis results for tracks in a file.

    Called when file is re-scanned or deleted.

    Args:
        conn: Database connection.
        file_id: ID of the file.

    Returns:
        Count of deleted records.
    """
    cursor = conn.execute(
        """
        DELETE FROM language_analysis_results
        WHERE track_id IN (SELECT id FROM tracks WHERE file_id = ?)
        """,
        (file_id,),
    )
    conn.commit()
    return cursor.rowcount


# ==========================================================================
# Processing Statistics Operations (040-processing-stats)
# ==========================================================================


def _row_to_processing_stats(row: sqlite3.Row) -> ProcessingStatsRecord:
    """Convert a database row to ProcessingStatsRecord.

    Args:
        row: sqlite3.Row from a SELECT query on processing_stats.

    Returns:
        ProcessingStatsRecord instance populated from the row.
    """
    return ProcessingStatsRecord(
        id=row["id"],
        file_id=row["file_id"],
        processed_at=row["processed_at"],
        policy_name=row["policy_name"],
        size_before=row["size_before"],
        size_after=row["size_after"],
        size_change=row["size_change"],
        audio_tracks_before=row["audio_tracks_before"],
        subtitle_tracks_before=row["subtitle_tracks_before"],
        attachments_before=row["attachments_before"],
        audio_tracks_after=row["audio_tracks_after"],
        subtitle_tracks_after=row["subtitle_tracks_after"],
        attachments_after=row["attachments_after"],
        audio_tracks_removed=row["audio_tracks_removed"],
        subtitle_tracks_removed=row["subtitle_tracks_removed"],
        attachments_removed=row["attachments_removed"],
        duration_seconds=row["duration_seconds"],
        phases_completed=row["phases_completed"],
        phases_total=row["phases_total"],
        total_changes=row["total_changes"],
        video_source_codec=row["video_source_codec"],
        video_target_codec=row["video_target_codec"],
        video_transcode_skipped=row["video_transcode_skipped"] == 1,
        video_skip_reason=row["video_skip_reason"],
        audio_tracks_transcoded=row["audio_tracks_transcoded"],
        audio_tracks_preserved=row["audio_tracks_preserved"],
        hash_before=row["hash_before"],
        hash_after=row["hash_after"],
        success=row["success"] == 1,
        error_message=row["error_message"],
    )


def insert_processing_stats(
    conn: sqlite3.Connection, record: ProcessingStatsRecord
) -> str:
    """Insert a new processing stats record.

    Note: Does not commit. Caller is responsible for transaction management.

    Args:
        conn: Database connection.
        record: ProcessingStatsRecord to insert.

    Returns:
        The ID (UUID) of the inserted record.
    """
    conn.execute(
        """
        INSERT INTO processing_stats (
            id, file_id, processed_at, policy_name,
            size_before, size_after, size_change,
            audio_tracks_before, subtitle_tracks_before, attachments_before,
            audio_tracks_after, subtitle_tracks_after, attachments_after,
            audio_tracks_removed, subtitle_tracks_removed, attachments_removed,
            duration_seconds, phases_completed, phases_total, total_changes,
            video_source_codec, video_target_codec, video_transcode_skipped,
            video_skip_reason, audio_tracks_transcoded, audio_tracks_preserved,
            hash_before, hash_after, success, error_message
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            record.id,
            record.file_id,
            record.processed_at,
            record.policy_name,
            record.size_before,
            record.size_after,
            record.size_change,
            record.audio_tracks_before,
            record.subtitle_tracks_before,
            record.attachments_before,
            record.audio_tracks_after,
            record.subtitle_tracks_after,
            record.attachments_after,
            record.audio_tracks_removed,
            record.subtitle_tracks_removed,
            record.attachments_removed,
            record.duration_seconds,
            record.phases_completed,
            record.phases_total,
            record.total_changes,
            record.video_source_codec,
            record.video_target_codec,
            1 if record.video_transcode_skipped else 0,
            record.video_skip_reason,
            record.audio_tracks_transcoded,
            record.audio_tracks_preserved,
            record.hash_before,
            record.hash_after,
            1 if record.success else 0,
            record.error_message,
        ),
    )
    return record.id


def insert_action_result(conn: sqlite3.Connection, record: ActionResultRecord) -> int:
    """Insert a new action result record.

    Note: Does not commit. Caller is responsible for transaction management.

    Args:
        conn: Database connection.
        record: ActionResultRecord to insert.

    Returns:
        The ID of the inserted record.
    """
    cursor = conn.execute(
        """
        INSERT INTO action_results (
            stats_id, action_type, track_type, track_index,
            before_state, after_state, success, duration_ms,
            rule_reference, message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.stats_id,
            record.action_type,
            record.track_type,
            record.track_index,
            record.before_state,
            record.after_state,
            1 if record.success else 0,
            record.duration_ms,
            record.rule_reference,
            record.message,
        ),
    )
    return cursor.lastrowid


def insert_performance_metric(
    conn: sqlite3.Connection, record: PerformanceMetricsRecord
) -> int:
    """Insert a new performance metric record.

    Note: Does not commit. Caller is responsible for transaction management.

    Args:
        conn: Database connection.
        record: PerformanceMetricsRecord to insert.

    Returns:
        The ID of the inserted record.
    """
    cursor = conn.execute(
        """
        INSERT INTO performance_metrics (
            stats_id, phase_name, wall_time_seconds,
            bytes_read, bytes_written, encoding_fps, encoding_bitrate
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.stats_id,
            record.phase_name,
            record.wall_time_seconds,
            record.bytes_read,
            record.bytes_written,
            record.encoding_fps,
            record.encoding_bitrate,
        ),
    )
    return cursor.lastrowid


def get_processing_stats_by_id(
    conn: sqlite3.Connection, stats_id: str
) -> ProcessingStatsRecord | None:
    """Get a processing stats record by ID.

    Args:
        conn: Database connection.
        stats_id: Processing stats UUID.

    Returns:
        ProcessingStatsRecord if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, file_id, processed_at, policy_name,
               size_before, size_after, size_change,
               audio_tracks_before, subtitle_tracks_before, attachments_before,
               audio_tracks_after, subtitle_tracks_after, attachments_after,
               audio_tracks_removed, subtitle_tracks_removed, attachments_removed,
               duration_seconds, phases_completed, phases_total, total_changes,
               video_source_codec, video_target_codec, video_transcode_skipped,
               video_skip_reason, audio_tracks_transcoded, audio_tracks_preserved,
               hash_before, hash_after, success, error_message
        FROM processing_stats WHERE id = ?
        """,
        (stats_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_processing_stats(row)


def get_processing_stats_for_file(
    conn: sqlite3.Connection, file_id: int, limit: int | None = None
) -> list[ProcessingStatsRecord]:
    """Get processing stats for a file.

    Args:
        conn: Database connection.
        file_id: ID of the file.
        limit: Maximum number of records to return (1-10000).

    Returns:
        List of ProcessingStatsRecord objects ordered by processed_at DESC.

    Raises:
        ValueError: If limit is not a positive integer or exceeds 10000.
    """
    query = """
        SELECT id, file_id, processed_at, policy_name,
               size_before, size_after, size_change,
               audio_tracks_before, subtitle_tracks_before, attachments_before,
               audio_tracks_after, subtitle_tracks_after, attachments_after,
               audio_tracks_removed, subtitle_tracks_removed, attachments_removed,
               duration_seconds, phases_completed, phases_total, total_changes,
               video_source_codec, video_target_codec, video_transcode_skipped,
               video_skip_reason, audio_tracks_transcoded, audio_tracks_preserved,
               hash_before, hash_after, success, error_message
        FROM processing_stats
        WHERE file_id = ?
        ORDER BY processed_at DESC
    """
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0 or limit > 10000:
            raise ValueError(f"Invalid limit value: {limit}")
        cursor = conn.execute(query + " LIMIT ?", (file_id, limit))
    else:
        cursor = conn.execute(query, (file_id,))
    return [_row_to_processing_stats(row) for row in cursor.fetchall()]


def get_action_results_for_stats(
    conn: sqlite3.Connection, stats_id: str
) -> list[ActionResultRecord]:
    """Get all action results for a processing stats record.

    Args:
        conn: Database connection.
        stats_id: Processing stats UUID.

    Returns:
        List of ActionResultRecord objects.
    """
    cursor = conn.execute(
        """
        SELECT id, stats_id, action_type, track_type, track_index,
               before_state, after_state, success, duration_ms,
               rule_reference, message
        FROM action_results
        WHERE stats_id = ?
        ORDER BY id
        """,
        (stats_id,),
    )
    return [
        ActionResultRecord(
            id=row["id"],
            stats_id=row["stats_id"],
            action_type=row["action_type"],
            track_type=row["track_type"],
            track_index=row["track_index"],
            before_state=row["before_state"],
            after_state=row["after_state"],
            success=row["success"] == 1,
            duration_ms=row["duration_ms"],
            rule_reference=row["rule_reference"],
            message=row["message"],
        )
        for row in cursor.fetchall()
    ]


def get_performance_metrics_for_stats(
    conn: sqlite3.Connection, stats_id: str
) -> list[PerformanceMetricsRecord]:
    """Get all performance metrics for a processing stats record.

    Args:
        conn: Database connection.
        stats_id: Processing stats UUID.

    Returns:
        List of PerformanceMetricsRecord objects.
    """
    cursor = conn.execute(
        """
        SELECT id, stats_id, phase_name, wall_time_seconds,
               bytes_read, bytes_written, encoding_fps, encoding_bitrate
        FROM performance_metrics
        WHERE stats_id = ?
        ORDER BY id
        """,
        (stats_id,),
    )
    return [
        PerformanceMetricsRecord(
            id=row["id"],
            stats_id=row["stats_id"],
            phase_name=row["phase_name"],
            wall_time_seconds=row["wall_time_seconds"],
            bytes_read=row["bytes_read"],
            bytes_written=row["bytes_written"],
            encoding_fps=row["encoding_fps"],
            encoding_bitrate=row["encoding_bitrate"],
        )
        for row in cursor.fetchall()
    ]


def delete_processing_stats_before(
    conn: sqlite3.Connection, before_date: str, dry_run: bool = False
) -> int:
    """Delete processing stats older than the specified date.

    Related action_results and performance_metrics are deleted via CASCADE.

    Args:
        conn: Database connection.
        before_date: ISO-8601 UTC timestamp. Stats with processed_at before
            this date are deleted.
        dry_run: If True, return count without deleting.

    Returns:
        Number of stats records deleted (or would be deleted if dry_run).
    """
    if dry_run:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM processing_stats WHERE processed_at < ?",
            (before_date,),
        )
        return cursor.fetchone()[0]

    cursor = conn.execute(
        "DELETE FROM processing_stats WHERE processed_at < ?",
        (before_date,),
    )
    conn.commit()
    return cursor.rowcount


def delete_processing_stats_by_policy(
    conn: sqlite3.Connection, policy_name: str, dry_run: bool = False
) -> int:
    """Delete processing stats for a specific policy.

    Related action_results and performance_metrics are deleted via CASCADE.

    Args:
        conn: Database connection.
        policy_name: Name of the policy to delete stats for.
        dry_run: If True, return count without deleting.

    Returns:
        Number of stats records deleted (or would be deleted if dry_run).
    """
    if dry_run:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM processing_stats WHERE policy_name = ?",
            (policy_name,),
        )
        return cursor.fetchone()[0]

    cursor = conn.execute(
        "DELETE FROM processing_stats WHERE policy_name = ?",
        (policy_name,),
    )
    conn.commit()
    return cursor.rowcount


def delete_all_processing_stats(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Delete all processing stats.

    Related action_results and performance_metrics are deleted via CASCADE.

    Args:
        conn: Database connection.
        dry_run: If True, return count without deleting.

    Returns:
        Number of stats records deleted (or would be deleted if dry_run).
    """
    if dry_run:
        cursor = conn.execute("SELECT COUNT(*) FROM processing_stats")
        return cursor.fetchone()[0]

    cursor = conn.execute("DELETE FROM processing_stats")
    conn.commit()
    return cursor.rowcount
