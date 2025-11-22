"""Data models for Video Policy Orchestrator database."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class OperationStatus(Enum):
    """Status of a policy operation."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class JobType(Enum):
    """Type of job in the queue."""

    TRANSCODE = "transcode"
    MOVE = "move"


class JobStatus(Enum):
    """Status of a job in the queue."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrackClassification(Enum):
    """Classification of audio track purpose."""

    MAIN = "main"  # Primary audio track
    COMMENTARY = "commentary"  # Director/cast commentary
    ALTERNATE = "alternate"  # Alternate mix, isolated score, etc.


@dataclass
class TrackInfo:
    """Represents a media track within a video file (domain model)."""

    index: int
    track_type: str  # "video", "audio", "subtitle", "attachment", "other"
    codec: str | None = None
    language: str | None = None
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False
    # Audio-specific fields (003-media-introspection)
    channels: int | None = None
    channel_layout: str | None = None  # Human-readable: "stereo", "5.1", etc.
    # Video-specific fields (003-media-introspection)
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None  # Stored as string to preserve precision


@dataclass
class FileInfo:
    """Represents a scanned video file with its tracks (domain model)."""

    path: Path
    filename: str
    directory: Path
    extension: str
    size_bytes: int
    modified_at: datetime
    content_hash: str | None = None
    container_format: str | None = None
    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scan_status: str = "ok"  # "ok", "error", "pending"
    scan_error: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)


@dataclass
class IntrospectionResult:
    """Result of media file introspection."""

    file_path: Path
    container_format: str | None
    tracks: list[TrackInfo]
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        """Return True if introspection completed without fatal errors."""
        return self.error is None


@dataclass
class FileRecord:
    """Database record for files table."""

    id: int | None
    path: str
    filename: str
    directory: str
    extension: str
    size_bytes: int
    modified_at: str  # ISO 8601
    content_hash: str | None
    container_format: str | None
    scanned_at: str  # ISO 8601
    scan_status: str
    scan_error: str | None

    @classmethod
    def from_file_info(cls, info: FileInfo) -> "FileRecord":
        """Create a FileRecord from a FileInfo domain object."""
        return cls(
            id=None,
            path=str(info.path),
            filename=info.filename,
            directory=str(info.directory),
            extension=info.extension,
            size_bytes=info.size_bytes,
            modified_at=info.modified_at.isoformat(),
            content_hash=info.content_hash,
            container_format=info.container_format,
            scanned_at=info.scanned_at.isoformat(),
            scan_status=info.scan_status,
            scan_error=info.scan_error,
        )


@dataclass
class TrackRecord:
    """Database record for tracks table."""

    id: int | None
    file_id: int
    track_index: int
    track_type: str
    codec: str | None
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
    # New fields (003-media-introspection)
    channels: int | None = None
    channel_layout: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None

    @classmethod
    def from_track_info(cls, info: TrackInfo, file_id: int) -> "TrackRecord":
        """Create a TrackRecord from a TrackInfo domain object."""
        return cls(
            id=None,
            file_id=file_id,
            track_index=info.index,
            track_type=info.track_type,
            codec=info.codec,
            language=info.language,
            title=info.title,
            is_default=info.is_default,
            is_forced=info.is_forced,
            channels=info.channels,
            channel_layout=info.channel_layout,
            width=info.width,
            height=info.height,
            frame_rate=info.frame_rate,
        )


@dataclass
class OperationRecord:
    """Database record for operations table (audit log).

    Tracks policy operations applied to media files for audit purposes.
    """

    id: str  # UUID
    file_id: int
    file_path: str  # Path at time of operation
    policy_name: str  # Name/path of policy used
    policy_version: int  # Schema version of policy
    actions_json: str  # Serialized list of applied actions
    status: OperationStatus
    started_at: str  # ISO 8601 UTC
    error_message: str | None = None
    backup_path: str | None = None
    completed_at: str | None = None  # ISO 8601 UTC


@dataclass
class PluginAcknowledgment:
    """Database record for plugin_acknowledgments table.

    Records user acknowledgments for directory-based plugins.
    Used to track which plugins the user has explicitly trusted.
    """

    id: int | None
    plugin_name: str
    plugin_hash: str  # SHA-256 hash of plugin file(s)
    acknowledged_at: str  # ISO 8601 UTC
    acknowledged_by: str | None = None  # Hostname or user identifier


@dataclass
class JobProgress:
    """Detailed progress information for a running job."""

    percent: float  # Overall percentage 0-100

    # For transcoding jobs
    frame_current: int | None = None
    frame_total: int | None = None
    time_current: float | None = None  # Seconds
    time_total: float | None = None  # Seconds
    fps: float | None = None  # Current encoding FPS
    bitrate: str | None = None  # Current bitrate
    size_current: int | None = None  # Output size so far (bytes)

    # Estimates
    eta_seconds: int | None = None  # Estimated time remaining


@dataclass
class Job:
    """Database record for jobs table."""

    id: str  # UUID v4
    file_id: int  # FK to files.id
    file_path: str  # Path at time of job creation
    job_type: JobType  # TRANSCODE or MOVE
    status: JobStatus  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    priority: int  # Lower = higher priority (default: 100)

    # Policy reference
    policy_name: str | None  # Name of policy used
    policy_json: str  # Serialized policy settings for this job

    # Progress tracking
    progress_percent: float  # 0.0 - 100.0
    progress_json: str | None  # Detailed progress (frames, time, etc.)

    # Timing (all ISO-8601 UTC)
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None

    # Worker tracking
    worker_pid: int | None = None  # PID of worker processing this job
    worker_heartbeat: str | None = None  # ISO-8601 UTC, updated periodically

    # Results
    output_path: str | None = None  # Path to output file
    backup_path: str | None = None  # Path to backup of original
    error_message: str | None = None  # Error details if FAILED


@dataclass
class TranscriptionResultRecord:
    """Database record for transcription_results table."""

    id: int | None
    track_id: int
    detected_language: str | None
    confidence_score: float
    track_type: str  # 'main', 'commentary', 'alternate'
    transcript_sample: str | None
    plugin_name: str
    created_at: str  # ISO-8601 UTC
    updated_at: str  # ISO-8601 UTC


# Database operations
# Note: sqlite3 import is placed here (after dataclass definitions) to keep
# data models at the top of the file for readability. The noqa comment suppresses
# the E402 "module level import not at top of file" lint warning.
import sqlite3  # noqa: E402


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
            scanned_at, scan_status, scan_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            scanned_at, scan_status, scan_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            scan_error = excluded.scan_error
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
        ),
    )
    result = cursor.fetchone()
    conn.commit()
    if result is None:
        raise RuntimeError("RETURNING clause failed to return file ID")
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
               scanned_at, scan_status, scan_error
        FROM files WHERE path = ?
        """,
        (path,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return FileRecord(
        id=row[0],
        path=row[1],
        filename=row[2],
        directory=row[3],
        extension=row[4],
        size_bytes=row[5],
        modified_at=row[6],
        content_hash=row[7],
        container_format=row[8],
        scanned_at=row[9],
        scan_status=row[10],
        scan_error=row[11],
    )


def delete_file(conn: sqlite3.Connection, file_id: int) -> None:
    """Delete a file record and its associated tracks.

    Args:
        conn: Database connection.
        file_id: ID of the file to delete.
    """
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()


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
            channels, channel_layout, width, height, frame_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
               channels, channel_layout, width, height, frame_rate
        FROM tracks WHERE file_id = ?
        ORDER BY track_index
        """,
        (file_id,),
    )
    tracks = []
    for row in cursor.fetchall():
        tracks.append(
            TrackRecord(
                id=row[0],
                file_id=row[1],
                track_index=row[2],
                track_type=row[3],
                codec=row[4],
                language=row[5],
                title=row[6],
                is_default=row[7] == 1,
                is_forced=row[8] == 1,
                channels=row[9],
                channel_layout=row[10],
                width=row[11],
                height=row[12],
                frame_rate=row[13],
            )
        )
    return tracks


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
                    width = ?, height = ?, frame_rate = ?
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
                    channels, channel_layout, width, height, frame_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    conn.commit()


# Plugin acknowledgment operations


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


# Job operations


def _row_to_job(row: tuple) -> Job:
    """Convert a database row to a Job object."""
    return Job(
        id=row[0],
        file_id=row[1],
        file_path=row[2],
        job_type=JobType(row[3]),
        status=JobStatus(row[4]),
        priority=row[5],
        policy_name=row[6],
        policy_json=row[7],
        progress_percent=row[8],
        progress_json=row[9],
        created_at=row[10],
        started_at=row[11],
        completed_at=row[12],
        worker_pid=row[13],
        worker_heartbeat=row[14],
        output_path=row[15],
        backup_path=row[16],
        error_message=row[17],
    )


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
            output_path, backup_path, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
               output_path, backup_path, error_message
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
               output_path, backup_path, error_message
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
               output_path, backup_path, error_message
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
               output_path, backup_path, error_message
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
               output_path, backup_path, error_message
        FROM jobs
        WHERE id LIKE ?
        ORDER BY created_at DESC
    """
    cursor = conn.execute(query, (f"{prefix}%",))
    return [_row_to_job(row) for row in cursor.fetchall()]


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


# Transcription result operations


def upsert_transcription_result(
    conn: sqlite3.Connection, record: TranscriptionResultRecord
) -> int:
    """Insert or update transcription result for a track.

    Uses ON CONFLICT to handle re-detection scenarios.

    Args:
        conn: Database connection.
        record: TranscriptionResultRecord to insert/update.

    Returns:
        The record ID.

    Raises:
        sqlite3.Error: If database operation fails.
    """
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
        conn.commit()
        if result is None:
            raise sqlite3.Error(
                f"RETURNING clause failed for track_id={record.track_id}"
            )
        return result[0]
    except sqlite3.Error:
        conn.rollback()
        raise


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
