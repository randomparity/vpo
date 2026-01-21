"""Track classification CRUD operations for Video Policy Orchestrator database.

This module contains database query functions for track classification results:
- Track classification upsert, get, delete operations
"""

import sqlite3

from vpo.db.types import TrackClassificationRecord


def upsert_track_classification(
    conn: sqlite3.Connection, record: TrackClassificationRecord
) -> int:
    """Insert or update track classification result for a track.

    Uses ON CONFLICT to handle re-classification scenarios. Uses BEGIN IMMEDIATE
    with retry logic to handle concurrent write contention gracefully.

    Args:
        conn: Database connection.
        record: TrackClassificationRecord to insert/update.

    Returns:
        The record ID.

    Raises:
        sqlite3.Error: If database operation fails after retries.
    """
    from vpo.db.connection import execute_with_retry

    # Store original busy_timeout for restoration
    original_busy_timeout: int | None = None
    attempt_count = 0

    def do_upsert() -> int:
        nonlocal original_busy_timeout, attempt_count
        attempt_count += 1

        # On retry, ensure connection is in a clean state.
        if attempt_count > 1 and conn.in_transaction:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass

        # Check if already in a transaction
        manage_transaction = not conn.in_transaction

        if manage_transaction:
            cursor = conn.execute("PRAGMA busy_timeout")
            row = cursor.fetchone()
            original_busy_timeout = row[0] if row else 10000
            conn.execute("PRAGMA busy_timeout = 100")  # 100ms fail-fast
            conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                """
                INSERT INTO track_classification_results (
                    track_id, file_hash, original_dubbed_status, commentary_status,
                    confidence, detection_method, acoustic_profile_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    original_dubbed_status = excluded.original_dubbed_status,
                    commentary_status = excluded.commentary_status,
                    confidence = excluded.confidence,
                    detection_method = excluded.detection_method,
                    acoustic_profile_json = excluded.acoustic_profile_json,
                    updated_at = excluded.updated_at
                RETURNING id
                """,
                (
                    record.track_id,
                    record.file_hash,
                    record.original_dubbed_status,
                    record.commentary_status,
                    record.confidence,
                    record.detection_method,
                    record.acoustic_profile_json,
                    record.created_at,
                    record.updated_at,
                ),
            )
            row = cursor.fetchone()
            result_id = row[0] if row else 0

            if manage_transaction:
                conn.execute("COMMIT")

            return result_id

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


def get_track_classification(
    conn: sqlite3.Connection, track_id: int
) -> TrackClassificationRecord | None:
    """Get track classification result for a track, if exists.

    Args:
        conn: Database connection.
        track_id: ID of the track.

    Returns:
        TrackClassificationRecord if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, track_id, file_hash, original_dubbed_status, commentary_status,
               confidence, detection_method, acoustic_profile_json,
               created_at, updated_at
        FROM track_classification_results
        WHERE track_id = ?
        """,
        (track_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return TrackClassificationRecord(
        id=row[0],
        track_id=row[1],
        file_hash=row[2],
        original_dubbed_status=row[3],
        commentary_status=row[4],
        confidence=row[5],
        detection_method=row[6],
        acoustic_profile_json=row[7],
        created_at=row[8],
        updated_at=row[9],
    )


def delete_track_classification(conn: sqlite3.Connection, track_id: int) -> bool:
    """Delete track classification result for a track.

    Args:
        conn: Database connection.
        track_id: ID of the track.

    Returns:
        True if a record was deleted, False if not found.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        "DELETE FROM track_classification_results WHERE track_id = ?",
        (track_id,),
    )
    return cursor.rowcount > 0


def get_classifications_for_file(
    conn: sqlite3.Connection, file_id: int
) -> list[TrackClassificationRecord]:
    """Get all track classification results for tracks in a file.

    Args:
        conn: Database connection.
        file_id: ID of the file.

    Returns:
        List of TrackClassificationRecord for all classified tracks in the file.
    """
    cursor = conn.execute(
        """
        SELECT tcr.id, tcr.track_id, tcr.file_hash, tcr.original_dubbed_status,
               tcr.commentary_status, tcr.confidence, tcr.detection_method,
               tcr.acoustic_profile_json, tcr.created_at, tcr.updated_at
        FROM track_classification_results tcr
        JOIN tracks t ON tcr.track_id = t.id
        WHERE t.file_id = ?
        ORDER BY t.track_index
        """,
        (file_id,),
    )

    results = []
    for row in cursor.fetchall():
        results.append(
            TrackClassificationRecord(
                id=row[0],
                track_id=row[1],
                file_hash=row[2],
                original_dubbed_status=row[3],
                commentary_status=row[4],
                confidence=row[5],
                detection_method=row[6],
                acoustic_profile_json=row[7],
                created_at=row[8],
                updated_at=row[9],
            )
        )

    return results


def delete_classifications_for_file(conn: sqlite3.Connection, file_id: int) -> int:
    """Delete all track classification results for tracks in a file.

    Called when file is re-scanned or deleted.

    Args:
        conn: Database connection.
        file_id: ID of the file.

    Returns:
        Count of deleted records.
    """
    cursor = conn.execute(
        """
        DELETE FROM track_classification_results
        WHERE track_id IN (SELECT id FROM tracks WHERE file_id = ?)
        """,
        (file_id,),
    )
    conn.commit()
    return cursor.rowcount


def get_classifications_for_tracks(
    conn: sqlite3.Connection, track_ids: list[int]
) -> dict[int, TrackClassificationRecord]:
    """Get track classification results for a list of track IDs.

    Args:
        conn: Database connection.
        track_ids: List of track IDs to query.

    Returns:
        Dictionary mapping track_id to TrackClassificationRecord.
    """
    if not track_ids:
        return {}

    placeholders = ",".join("?" * len(track_ids))
    cursor = conn.execute(
        f"""
        SELECT id, track_id, file_hash, original_dubbed_status, commentary_status,
               confidence, detection_method, acoustic_profile_json,
               created_at, updated_at
        FROM track_classification_results
        WHERE track_id IN ({placeholders})
        """,
        tuple(track_ids),
    )

    result = {}
    for row in cursor.fetchall():
        record = TrackClassificationRecord(
            id=row[0],
            track_id=row[1],
            file_hash=row[2],
            original_dubbed_status=row[3],
            commentary_status=row[4],
            confidence=row[5],
            detection_method=row[6],
            acoustic_profile_json=row[7],
            created_at=row[8],
            updated_at=row[9],
        )
        result[record.track_id] = record

    return result
