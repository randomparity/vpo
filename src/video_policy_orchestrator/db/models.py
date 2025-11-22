"""Data models for Video Policy Orchestrator database."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TrackInfo:
    """Represents a media track within a video file (domain model)."""

    index: int
    track_type: str  # "video", "audio", "subtitle", "other"
    codec: str | None = None
    language: str | None = None
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False


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
    scanned_at: datetime = field(default_factory=datetime.now)
    scan_status: str = "ok"  # "ok", "error", "pending"
    scan_error: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)


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
        )


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
            language, title, is_default, is_forced
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
               language, title, is_default, is_forced
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
                is_default=bool(row[7]),
                is_forced=bool(row[8]),
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
