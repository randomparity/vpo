"""Library snapshot view query functions."""

import sqlite3
from dataclasses import dataclass

from .helpers import _clamp_limit


@dataclass(frozen=True)
class LibrarySnapshotPoint:
    """A point-in-time snapshot of library state."""

    snapshot_at: str
    total_files: int
    total_size_bytes: int
    missing_files: int
    error_files: int


def insert_library_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_at: str,
    total_files: int,
    total_size_bytes: int,
    missing_files: int,
    error_files: int = 0,
) -> None:
    """Insert a library snapshot row.

    Args:
        conn: Database connection.
        snapshot_at: ISO-8601 timestamp of the snapshot.
        total_files: Total number of files in the library.
        total_size_bytes: Total size of all files in bytes.
        missing_files: Number of files with scan_status='missing'.
        error_files: Number of files with scan_status='error'.
    """
    conn.execute(
        "INSERT INTO library_snapshots "
        "(snapshot_at, total_files, total_size_bytes, "
        "missing_files, error_files) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            snapshot_at,
            total_files,
            total_size_bytes,
            missing_files,
            error_files,
        ),
    )
    conn.commit()


def get_library_snapshots(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    limit: int = 365,
) -> list[LibrarySnapshotPoint]:
    """Get library snapshots for charting.

    Args:
        conn: Database connection.
        since: ISO-8601 timestamp to filter from (inclusive).
        limit: Maximum snapshots to return.

    Returns:
        List of LibrarySnapshotPoint ordered by time ascending.
    """
    limit = _clamp_limit(limit)

    if since:
        query = (
            "SELECT snapshot_at, total_files, total_size_bytes, "
            "missing_files, error_files "
            "FROM library_snapshots "
            "WHERE snapshot_at >= ? "
            "ORDER BY snapshot_at ASC "
            "LIMIT ?"
        )
        cursor = conn.execute(query, (since, limit))
    else:
        query = (
            "SELECT snapshot_at, total_files, total_size_bytes, "
            "missing_files, error_files "
            "FROM library_snapshots "
            "ORDER BY snapshot_at ASC "
            "LIMIT ?"
        )
        cursor = conn.execute(query, (limit,))

    return [
        LibrarySnapshotPoint(
            snapshot_at=row["snapshot_at"],
            total_files=row["total_files"],
            total_size_bytes=row["total_size_bytes"],
            missing_files=row["missing_files"],
            error_files=row["error_files"],
        )
        for row in cursor.fetchall()
    ]
