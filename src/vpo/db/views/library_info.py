"""Library information and maintenance view queries."""

import logging
import sqlite3

from ..types import (
    DuplicateGroup,
    IntegrityResult,
    LibraryInfoView,
    OptimizeResult,
)

logger = logging.getLogger(__name__)


def get_library_info(conn: sqlite3.Connection) -> LibraryInfoView:
    """Get aggregate library statistics.

    Queries file counts by scan_status, track counts by type,
    database size via PRAGMAs, and schema version.

    Args:
        conn: Database connection.

    Returns:
        LibraryInfoView with aggregate statistics.
    """
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

    # Database size info
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    freelist_count = conn.execute("PRAGMA freelist_count").fetchone()[0]
    db_size_bytes = page_size * page_count

    # Schema version
    version_row = conn.execute(
        "SELECT value FROM _meta WHERE key = 'schema_version'"
    ).fetchone()
    schema_version = int(version_row[0]) if version_row else 0

    return LibraryInfoView(
        total_files=row["total_files"],
        files_ok=row["files_ok"],
        files_missing=row["files_missing"],
        files_error=row["files_error"],
        files_pending=row["files_pending"],
        total_size_bytes=row["total_size_bytes"],
        video_tracks=track_row["video_tracks"] or 0,
        audio_tracks=track_row["audio_tracks"] or 0,
        subtitle_tracks=track_row["subtitle_tracks"] or 0,
        attachment_tracks=track_row["attachment_tracks"] or 0,
        db_size_bytes=db_size_bytes,
        db_page_size=page_size,
        db_page_count=page_count,
        db_freelist_count=freelist_count,
        schema_version=schema_version,
    )


def get_duplicate_files(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    min_group_size: int = 2,
) -> list[DuplicateGroup]:
    """Find files sharing the same content_hash.

    Groups files by content_hash (excluding NULL hashes) and returns
    groups with at least min_group_size members. Uses the existing
    idx_files_content_hash index.

    Args:
        conn: Database connection.
        limit: Maximum number of groups to return.
        min_group_size: Minimum files per group (default: 2).

    Returns:
        List of DuplicateGroup, ordered by group size descending.
    """
    # Find duplicate hashes
    groups_cursor = conn.execute(
        """
        SELECT content_hash, COUNT(*) AS file_count,
               SUM(size_bytes) AS total_size_bytes
        FROM files
        WHERE content_hash IS NOT NULL AND content_hash != ''
        GROUP BY content_hash
        HAVING COUNT(*) >= ?
        ORDER BY file_count DESC, total_size_bytes DESC
        LIMIT ?
        """,
        (min_group_size, limit),
    )
    groups = groups_cursor.fetchall()

    results = []
    for g in groups:
        # Fetch paths for each group
        paths_cursor = conn.execute(
            "SELECT path FROM files WHERE content_hash = ? ORDER BY path",
            (g["content_hash"],),
        )
        paths = [r["path"] for r in paths_cursor.fetchall()]

        results.append(
            DuplicateGroup(
                content_hash=g["content_hash"],
                file_count=g["file_count"],
                total_size_bytes=g["total_size_bytes"],
                paths=paths,
            )
        )

    return results


def run_integrity_check(conn: sqlite3.Connection) -> IntegrityResult:
    """Run SQLite integrity and foreign key checks.

    Executes PRAGMA integrity_check and PRAGMA foreign_key_check
    to verify database consistency.

    Args:
        conn: Database connection.

    Returns:
        IntegrityResult with check results.
    """
    # integrity_check returns 'ok' if database is intact
    integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
    integrity_errors = []
    integrity_ok = True

    for row in integrity_rows:
        msg = row[0]
        if msg != "ok":
            integrity_ok = False
            integrity_errors.append(msg)

    # foreign_key_check returns empty if no violations
    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    foreign_key_errors = []
    foreign_key_ok = len(fk_rows) == 0

    for row in fk_rows:
        foreign_key_errors.append((row[0], row[1], row[2], row[3]))

    return IntegrityResult(
        integrity_ok=integrity_ok,
        integrity_errors=integrity_errors,
        foreign_key_ok=foreign_key_ok,
        foreign_key_errors=foreign_key_errors,
    )


def run_optimize(
    conn: sqlite3.Connection,
    *,
    dry_run: bool = False,
) -> OptimizeResult:
    """Run VACUUM and ANALYZE on the database.

    Commits any pending transactions before running VACUUM.
    In dry-run mode, reports current freelist count and estimated
    reclaimable space without making changes.

    Args:
        conn: Database connection.
        dry_run: If True, only estimate savings without making changes.

    Returns:
        OptimizeResult with before/after sizes.

    Raises:
        sqlite3.OperationalError: If database is locked by another process.
    """
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    freelist_count = conn.execute("PRAGMA freelist_count").fetchone()[0]
    size_before = page_size * page_count

    if dry_run:
        estimated_savings = freelist_count * page_size
        return OptimizeResult(
            size_before=size_before,
            size_after=size_before - estimated_savings,
            space_saved=estimated_savings,
            freelist_pages=freelist_count,
            dry_run=True,
        )

    # Commit any pending transactions before VACUUM
    if conn.in_transaction:
        conn.commit()

    # VACUUM reclaims free pages and defragments the database
    conn.execute("VACUUM")
    # ANALYZE updates query planner statistics
    conn.execute("ANALYZE")

    # Measure after
    page_count_after = conn.execute("PRAGMA page_count").fetchone()[0]
    size_after = page_size * page_count_after

    return OptimizeResult(
        size_before=size_before,
        size_after=size_after,
        space_saved=size_before - size_after,
        freelist_pages=freelist_count,
        dry_run=False,
    )
