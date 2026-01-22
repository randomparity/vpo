"""Processing statistics CRUD operations for Video Policy Orchestrator database.

This module contains database query functions for processing statistics:
- Processing stats insert, get, delete operations
- Action result and performance metric operations
"""

import sqlite3

from vpo.db.types import (
    ActionResultRecord,
    PerformanceMetricsRecord,
    ProcessingStatsRecord,
)


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
