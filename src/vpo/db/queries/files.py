"""File and track CRUD operations for Video Policy Orchestrator database.

This module contains database query functions for files and tracks:
- File insert, upsert, get, delete operations
- Track insert, get, delete, upsert operations
"""

import sqlite3
from pathlib import Path

from vpo.db.types import (
    FileRecord,
    TrackInfo,
    TrackRecord,
)

from .helpers import _row_to_file_record, _row_to_track_record

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

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            modified_at, content_hash, container_format,
            scanned_at, scan_status, scan_error, job_id, plugin_metadata,
            container_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            record.container_tags,
        ),
    )
    return cursor.lastrowid


def upsert_file(conn: sqlite3.Connection, record: FileRecord) -> int:
    """Insert or update a file record (upsert by path).

    Args:
        conn: Database connection.
        record: File record to insert or update.

    Returns:
        The ID of the inserted/updated record.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            modified_at, content_hash, container_format,
            scanned_at, scan_status, scan_error, job_id, plugin_metadata,
            container_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            job_id = COALESCE(files.job_id, excluded.job_id),
            plugin_metadata = excluded.plugin_metadata,
            container_tags = excluded.container_tags
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
            record.container_tags,
        ),
    )
    result = cursor.fetchone()
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
               scanned_at, scan_status, scan_error, job_id, plugin_metadata,
               container_tags
        FROM files WHERE path = ?
        """,
        (path,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return _row_to_file_record(row)


def get_files_by_paths(
    conn: sqlite3.Connection,
    paths: list[str],
    chunk_size: int = 900,
) -> dict[str, FileRecord]:
    """Get multiple file records by path in a single query.

    Uses chunked queries to handle lists larger than SQLite's 999 parameter
    limit. Each chunk executes as a separate query with a WHERE path IN (...)
    clause.

    Args:
        conn: Database connection.
        paths: List of file paths to look up.
        chunk_size: Maximum paths per query (default 900, max 999 for SQLite).

    Returns:
        Dictionary mapping path to FileRecord for all found records.
        Missing paths are not included in the result.
    """
    if not paths:
        return {}

    result: dict[str, FileRecord] = {}

    for i in range(0, len(paths), chunk_size):
        chunk = paths[i : i + chunk_size]
        placeholders = ",".join("?" * len(chunk))
        cursor = conn.execute(
            f"""
            SELECT id, path, filename, directory, extension, size_bytes,
                   modified_at, content_hash, container_format,
                   scanned_at, scan_status, scan_error, job_id, plugin_metadata,
                   container_tags
            FROM files WHERE path IN ({placeholders})
            """,
            tuple(chunk),
        )
        for row in cursor.fetchall():
            record = _row_to_file_record(row)
            result[record.path] = record

    return result


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
               scanned_at, scan_status, scan_error, job_id, plugin_metadata,
               container_tags
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

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))


def update_file_path(conn: sqlite3.Connection, file_id: int, new_path: str) -> bool:
    """Update a file's path after move or container conversion.

    Updates path, filename, directory, and extension fields atomically.

    Args:
        conn: Database connection.
        file_id: ID of the file to update.
        new_path: New absolute path for the file.

    Returns:
        True if file was updated, False if not found.

    Raises:
        sqlite3.IntegrityError: If new_path already exists in database.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    path = Path(new_path)
    # Extract extension without leading dot, or None for files without extension
    extension = path.suffix.lstrip(".") or None
    try:
        cursor = conn.execute(
            """
            UPDATE files SET
                path = ?,
                filename = ?,
                directory = ?,
                extension = ?
            WHERE id = ?
            """,
            (
                str(path),
                path.name,
                str(path.parent),
                extension,
                file_id,
            ),
        )
        return cursor.rowcount > 0
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: files.path" in str(e):
            raise sqlite3.IntegrityError(
                f"Path already exists in database: {new_path}"
            ) from e
        raise


_SENTINEL = object()


def update_file_attributes(
    conn: sqlite3.Connection,
    file_id: int,
    size_bytes: int,
    modified_at: str,
    content_hash: str | None,
    container_tags_json: str | None = _SENTINEL,
) -> bool:
    """Update file physical attributes after processing.

    Args:
        conn: Database connection.
        file_id: ID of the file to update.
        size_bytes: New file size in bytes.
        modified_at: New modification time (ISO 8601 UTC).
        content_hash: New content hash (may be None if hashing failed).
        container_tags_json: JSON string of container tags. When provided
            (including None), updates the column. When omitted (sentinel),
            leaves the column unchanged.

    Returns:
        True if file was updated, False if not found.

    Raises:
        ValueError: If parameters are invalid.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    # Validate inputs
    if file_id <= 0:
        raise ValueError(f"file_id must be positive, got {file_id}")
    if size_bytes < 0:
        raise ValueError(f"size_bytes must be non-negative, got {size_bytes}")
    if content_hash is not None and not content_hash:
        raise ValueError("content_hash cannot be empty string (use None)")

    if container_tags_json is _SENTINEL:
        cursor = conn.execute(
            """
            UPDATE files SET
                size_bytes = ?,
                modified_at = ?,
                content_hash = ?
            WHERE id = ?
            """,
            (size_bytes, modified_at, content_hash, file_id),
        )
    else:
        cursor = conn.execute(
            """
            UPDATE files SET
                size_bytes = ?,
                modified_at = ?,
                content_hash = ?,
                container_tags = ?
            WHERE id = ?
            """,
            (size_bytes, modified_at, content_hash, container_tags_json, file_id),
        )
    return cursor.rowcount > 0


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

    Note:
        This function does NOT commit. Caller must manage transactions.
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

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    conn.execute("DELETE FROM tracks WHERE file_id = ?", (file_id,))


def upsert_tracks_for_file(
    conn: sqlite3.Connection, file_id: int, tracks: list[TrackInfo]
) -> None:
    """Smart merge tracks for a file: update existing, insert new, delete missing.

    Uses fail-fast busy_timeout with retry logic for concurrent access.
    If already in a transaction, operates within it. Otherwise, creates
    its own transaction with BEGIN IMMEDIATE.

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
    from vpo.db.connection import execute_with_retry

    # Store original busy_timeout for restoration
    original_busy_timeout: int | None = None
    attempt_count = 0

    def do_upsert() -> None:
        nonlocal original_busy_timeout, attempt_count
        attempt_count += 1

        # On retry, ensure connection is in a clean state.
        # This handles the case where a previous attempt failed mid-transaction.
        # Don't do this on first attempt - allow participating in caller's transaction.
        if attempt_count > 1 and conn.in_transaction:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass

        # Check if already in a transaction
        manage_transaction = not conn.in_transaction

        if manage_transaction:
            # Set short busy_timeout for fail-fast behavior with retries
            cursor = conn.execute("PRAGMA busy_timeout")
            row = cursor.fetchone()
            original_busy_timeout = row[0] if row else 10000
            conn.execute("PRAGMA busy_timeout = 100")
            conn.execute("BEGIN IMMEDIATE")

        try:
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
                            is_default = ?, is_forced = ?, channels = ?,
                            channel_layout = ?, width = ?, height = ?,
                            frame_rate = ?, duration_seconds = ?,
                            color_transfer = ?, color_primaries = ?,
                            color_space = ?, color_range = ?
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
                            channels, channel_layout, width, height,
                            frame_rate, duration_seconds, color_transfer,
                            color_primaries, color_space, color_range
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
                    "DELETE FROM tracks WHERE file_id = ? "
                    f"AND track_index IN ({placeholders})",
                    (file_id, *stale_indices),
                )

            if manage_transaction:
                conn.execute("COMMIT")

        except Exception:
            if manage_transaction:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise
        finally:
            # Restore original busy_timeout if we changed it
            if manage_transaction and original_busy_timeout is not None:
                try:
                    conn.execute(f"PRAGMA busy_timeout = {original_busy_timeout}")
                except sqlite3.Error:
                    pass

    execute_with_retry(do_upsert)
