"""Transcription result CRUD operations for Video Policy Orchestrator database.

This module contains database query functions for transcription results:
- Transcription result upsert, get, delete operations
"""

import sqlite3

from vpo.db.types import TranscriptionResultRecord


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
        finally:
            # Restore original busy_timeout if we changed it
            if manage_transaction and original_busy_timeout is not None:
                try:
                    conn.execute(f"PRAGMA busy_timeout = {original_busy_timeout}")
                except sqlite3.Error:
                    pass  # Best effort restoration

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

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        DELETE FROM transcription_results
        WHERE track_id IN (SELECT id FROM tracks WHERE file_id = ?)
        """,
        (file_id,),
    )
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
