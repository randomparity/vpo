"""Language analysis CRUD operations for Video Policy Orchestrator database.

This module contains database query functions for language analysis results:
- Language analysis result upsert, get, delete operations
- Language segment operations
- Path-based queries and deletions
"""

import sqlite3

from vpo.db.types import (
    LanguageAnalysisResultRecord,
    LanguageSegmentRecord,
)

from .helpers import _escape_like_pattern


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
    from vpo.db.connection import execute_with_retry

    # Store original busy_timeout for restoration
    # Default connection timeout is 10000ms, but we want fail-fast for retries
    original_busy_timeout: int | None = None
    attempt_count = 0

    def do_upsert() -> int:
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
        # If so, just do the upsert within that transaction
        # If not, use BEGIN IMMEDIATE for fail-fast lock detection
        manage_transaction = not conn.in_transaction

        if manage_transaction:
            # Set short busy_timeout for fail-fast behavior with retries.
            # The default 10s timeout defeats the purpose of BEGIN IMMEDIATE
            # with retry logic - we want to fail quickly and retry with backoff.
            cursor = conn.execute("PRAGMA busy_timeout")
            row = cursor.fetchone()
            original_busy_timeout = row[0] if row else 10000
            conn.execute("PRAGMA busy_timeout = 100")  # 100ms fail-fast
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
        finally:
            # Restore original busy_timeout if we changed it
            if manage_transaction and original_busy_timeout is not None:
                try:
                    conn.execute(f"PRAGMA busy_timeout = {original_busy_timeout}")
                except sqlite3.Error:
                    pass  # Best effort restoration

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

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        "DELETE FROM language_analysis_results WHERE track_id = ?",
        (track_id,),
    )
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
    from vpo.db.connection import execute_with_retry

    # Store original busy_timeout for restoration
    # Default connection timeout is 10000ms, but we want fail-fast for retries
    original_busy_timeout: int | None = None
    attempt_count = 0

    def do_upsert() -> list[int]:
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
        # If so, just do the upsert within that transaction
        # If not, use BEGIN IMMEDIATE for fail-fast lock detection
        manage_transaction = not conn.in_transaction

        if manage_transaction:
            # Set short busy_timeout for fail-fast behavior with retries.
            # The default 10s timeout defeats the purpose of BEGIN IMMEDIATE
            # with retry logic - we want to fail quickly and retry with backoff.
            cursor = conn.execute("PRAGMA busy_timeout")
            row = cursor.fetchone()
            original_busy_timeout = row[0] if row else 10000
            conn.execute("PRAGMA busy_timeout = 100")  # 100ms fail-fast
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
        finally:
            # Restore original busy_timeout if we changed it
            if manage_transaction and original_busy_timeout is not None:
                try:
                    conn.execute(f"PRAGMA busy_timeout = {original_busy_timeout}")
                except sqlite3.Error:
                    pass  # Best effort restoration

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

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        DELETE FROM language_analysis_results
        WHERE track_id IN (SELECT id FROM tracks WHERE file_id = ?)
        """,
        (file_id,),
    )
    return cursor.rowcount


def delete_all_analysis(conn: sqlite3.Connection) -> int:
    """Delete all language analysis results.

    Args:
        conn: Database connection.

    Returns:
        Count of deleted records.
    """
    cursor = conn.execute("DELETE FROM language_analysis_results")
    conn.commit()
    return cursor.rowcount


def delete_analysis_by_path_prefix(
    conn: sqlite3.Connection,
    path_prefix: str,
) -> int:
    """Delete language analysis results for files under a path.

    Args:
        conn: Database connection.
        path_prefix: Directory path prefix (e.g., "/media/movies/").

    Returns:
        Count of deleted records.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    escaped_prefix = _escape_like_pattern(path_prefix)
    cursor = conn.execute(
        """
        DELETE FROM language_analysis_results
        WHERE track_id IN (
            SELECT t.id FROM tracks t
            JOIN files f ON t.file_id = f.id
            WHERE f.path LIKE ? || '%' ESCAPE '\\'
        )
        """,
        (escaped_prefix,),
    )
    return cursor.rowcount


def delete_analysis_for_file(conn: sqlite3.Connection, file_id: int) -> int:
    """Delete all language analysis results for a specific file.

    Alias for delete_language_analysis_for_file for consistency.

    Args:
        conn: Database connection.
        file_id: ID of the file.

    Returns:
        Count of deleted records.
    """
    return delete_language_analysis_for_file(conn, file_id)


def get_file_ids_by_path_prefix(
    conn: sqlite3.Connection,
    path_prefix: str,
    *,
    include_subdirs: bool = True,
) -> list[int]:
    """Get file IDs for files under a path prefix.

    Args:
        conn: Database connection.
        path_prefix: Directory path prefix.
        include_subdirs: If True, include files in subdirectories.

    Returns:
        List of file IDs matching the path prefix.
    """
    escaped_prefix = _escape_like_pattern(path_prefix)
    if include_subdirs:
        pattern = escaped_prefix + "%"
        cursor = conn.execute(
            "SELECT id FROM files WHERE path LIKE ? ESCAPE '\\'",
            (pattern,),
        )
    else:
        # Non-recursive: only direct children
        pattern = escaped_prefix
        if not path_prefix.endswith("/"):
            pattern += "/"
        # Match files in directory but not in subdirs
        cursor = conn.execute(
            """
            SELECT id FROM files
            WHERE path LIKE ? || '%' ESCAPE '\\'
            AND path NOT LIKE ? || '%/%' ESCAPE '\\'
            """,
            (pattern, pattern),
        )

    return [row[0] for row in cursor.fetchall()]
