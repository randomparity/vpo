"""Library information view queries."""

import logging
import sqlite3
from itertools import groupby
from operator import itemgetter

from ..types import (
    DuplicateGroup,
    LibraryInfoView,
)
from .helpers import _clamp_limit

logger = logging.getLogger(__name__)


def get_library_info(conn: sqlite3.Connection) -> LibraryInfoView:
    """Get aggregate library statistics.

    Queries file counts by scan_status, track counts by type,
    database size via PRAGMAs, and schema version.

    Args:
        conn: Database connection.

    Returns:
        LibraryInfoView with aggregate statistics.

    Raises:
        sqlite3.Error: If the database cannot be read.
    """
    try:
        # File counts by scan_status
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_files,
                COALESCE(SUM(CASE WHEN scan_status = 'ok' THEN 1 ELSE 0 END), 0)
                    AS files_ok,
                COALESCE(SUM(CASE WHEN scan_status = 'missing' THEN 1 ELSE 0 END), 0)
                    AS files_missing,
                COALESCE(SUM(CASE WHEN scan_status = 'error' THEN 1 ELSE 0 END), 0)
                    AS files_error,
                COALESCE(SUM(CASE WHEN scan_status = 'pending' THEN 1 ELSE 0 END), 0)
                    AS files_pending,
                COALESCE(SUM(size_bytes), 0) AS total_size_bytes
            FROM files
            """
        ).fetchone()

        # Track counts by type
        track_row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN track_type = 'video' THEN 1 ELSE 0 END), 0)
                    AS video_tracks,
                COALESCE(SUM(CASE WHEN track_type = 'audio' THEN 1 ELSE 0 END), 0)
                    AS audio_tracks,
                COALESCE(SUM(CASE WHEN track_type = 'subtitle' THEN 1 ELSE 0 END), 0)
                    AS subtitle_tracks,
                COALESCE(SUM(CASE WHEN track_type = 'attachment' THEN 1 ELSE 0 END), 0)
                    AS attachment_tracks
            FROM tracks
            """
        ).fetchone()

        # Database size info — PRAGMA results are single-column tuples (position 0)
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        freelist_count = conn.execute("PRAGMA freelist_count").fetchone()[0]
        db_size_bytes = page_size * page_count

        # Schema version
        version_row = conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        ).fetchone()
        schema_version = (
            int(version_row[0]) if version_row and version_row[0] is not None else 0
        )

        return LibraryInfoView(
            total_files=row["total_files"],
            files_ok=row["files_ok"],
            files_missing=row["files_missing"],
            files_error=row["files_error"],
            files_pending=row["files_pending"],
            total_size_bytes=row["total_size_bytes"],
            video_tracks=track_row["video_tracks"],
            audio_tracks=track_row["audio_tracks"],
            subtitle_tracks=track_row["subtitle_tracks"],
            attachment_tracks=track_row["attachment_tracks"],
            db_size_bytes=db_size_bytes,
            db_page_size=page_size,
            db_page_count=page_count,
            db_freelist_count=freelist_count,
            schema_version=schema_version,
        )
    except sqlite3.Error:
        logger.exception("Failed to query library info")
        raise


def get_duplicate_files(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    min_group_size: int = 2,
) -> list[DuplicateGroup]:
    """Find files sharing the same content_hash.

    Groups files by content_hash (excluding NULL and empty hashes) and
    returns groups with at least min_group_size members. Uses a single
    JOIN query to avoid N+1 lookups.

    Args:
        conn: Database connection.
        limit: Maximum number of groups to return.
        min_group_size: Minimum files per group (default: 2).

    Returns:
        List of DuplicateGroup, ordered by group size descending.

    Raises:
        sqlite3.Error: If the database cannot be read.
    """
    limit = _clamp_limit(limit)
    min_group_size = max(2, min_group_size)

    try:
        # Single query: join files against a subquery of duplicate hashes
        # to fetch all paths without N+1 lookups.
        rows = conn.execute(
            """
            SELECT f.content_hash, f.path, f.size_bytes,
                   dups.file_count, dups.total_size_bytes
            FROM files f
            JOIN (
                SELECT content_hash, COUNT(*) AS file_count,
                       SUM(size_bytes) AS total_size_bytes
                FROM files
                WHERE content_hash IS NOT NULL AND content_hash != ''
                GROUP BY content_hash
                HAVING COUNT(*) >= ?
                ORDER BY file_count DESC, total_size_bytes DESC
                LIMIT ?
            ) dups ON f.content_hash = dups.content_hash
            ORDER BY dups.file_count DESC, dups.total_size_bytes DESC, f.path
            """,
            (min_group_size, limit),
        ).fetchall()

        # Group rows by content_hash in Python
        results = []
        for hash_val, group_rows in groupby(rows, key=itemgetter("content_hash")):
            group_list = list(group_rows)
            first = group_list[0]
            results.append(
                DuplicateGroup(
                    content_hash=hash_val,
                    file_count=first["file_count"],
                    total_size_bytes=first["total_size_bytes"],
                    paths=[r["path"] for r in group_list],
                )
            )

        return results
    except sqlite3.Error:
        logger.exception("Failed to query duplicate files")
        raise
