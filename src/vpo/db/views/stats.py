"""Processing statistics view query functions."""

import sqlite3

from ..types import (
    ActionSummary,
    FileProcessingHistory,
    PolicyStats,
    StatsDetailView,
    StatsSummary,
    TrendDataPoint,
)
from .helpers import _clamp_limit


def get_stats_summary(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    until: str | None = None,
    policy_name: str | None = None,
) -> StatsSummary:
    """Get aggregate statistics summary.

    Calculates totals and averages across all processing runs, optionally
    filtered by date range and/or policy name.

    Args:
        conn: Database connection.
        since: ISO-8601 timestamp for start of date range (inclusive).
        until: ISO-8601 timestamp for end of date range (inclusive).
        policy_name: Filter by specific policy name.

    Returns:
        StatsSummary with aggregate metrics.
    """
    conditions: list[str] = []
    params: list[str] = []

    if since is not None:
        conditions.append("processed_at >= ?")
        params.append(since)
    if until is not None:
        conditions.append("processed_at <= ?")
        params.append(until)
    if policy_name is not None:
        conditions.append("policy_name = ?")
        params.append(policy_name)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            COUNT(*) as total_files_processed,
            COALESCE(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END), 0)
                as total_successful,
            COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0)
                as total_failed,
            COALESCE(SUM(size_before), 0) as total_size_before,
            COALESCE(SUM(size_after), 0) as total_size_after,
            COALESCE(SUM(size_change), 0) as total_size_saved,
            COALESCE(SUM(audio_tracks_removed), 0) as total_audio_removed,
            COALESCE(SUM(subtitle_tracks_removed), 0) as total_subtitles_removed,
            COALESCE(SUM(attachments_removed), 0) as total_attachments_removed,
            COALESCE(SUM(CASE WHEN video_target_codec IS NOT NULL
                AND video_transcode_skipped = 0 THEN 1 ELSE 0 END), 0)
                as total_videos_transcoded,
            COALESCE(SUM(video_transcode_skipped), 0) as total_videos_skipped,
            COALESCE(SUM(audio_tracks_transcoded), 0) as total_audio_transcoded,
            COALESCE(AVG(duration_seconds), 0.0) as avg_processing_time,
            MIN(processed_at) as earliest_processing,
            MAX(processed_at) as latest_processing,
            COALESCE(SUM(CASE WHEN encoder_type = 'hardware' THEN 1 ELSE 0 END), 0)
                as hardware_encodes,
            COALESCE(SUM(CASE WHEN encoder_type = 'software' THEN 1 ELSE 0 END), 0)
                as software_encodes
        FROM processing_stats
        {where_clause}
    """

    cursor = conn.execute(query, params)
    row = cursor.fetchone()

    total = row["total_files_processed"] or 0
    successful = row["total_successful"] or 0
    size_before = row["total_size_before"] or 0
    size_saved = row["total_size_saved"] or 0

    # Calculate derived values
    success_rate = (successful / total) if total > 0 else 0.0
    avg_savings = ((size_saved / size_before) * 100) if size_before > 0 else 0.0

    return StatsSummary(
        total_files_processed=total,
        total_successful=successful,
        total_failed=row["total_failed"] or 0,
        success_rate=success_rate,
        total_size_before=size_before,
        total_size_after=row["total_size_after"] or 0,
        total_size_saved=size_saved,
        avg_savings_percent=avg_savings,
        total_audio_removed=row["total_audio_removed"] or 0,
        total_subtitles_removed=row["total_subtitles_removed"] or 0,
        total_attachments_removed=row["total_attachments_removed"] or 0,
        total_videos_transcoded=row["total_videos_transcoded"] or 0,
        total_videos_skipped=row["total_videos_skipped"] or 0,
        total_audio_transcoded=row["total_audio_transcoded"] or 0,
        avg_processing_time=row["avg_processing_time"] or 0.0,
        earliest_processing=row["earliest_processing"],
        latest_processing=row["latest_processing"],
        hardware_encodes=row["hardware_encodes"] or 0,
        software_encodes=row["software_encodes"] or 0,
    )


def get_recent_stats(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    policy_name: str | None = None,
) -> list[FileProcessingHistory]:
    """Get recent processing history entries.

    Args:
        conn: Database connection.
        limit: Maximum number of entries to return.
        policy_name: Filter by specific policy name.

    Returns:
        List of FileProcessingHistory objects ordered by processed_at DESC.
    """
    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

    conditions: list[str] = []
    params: list[str | int] = []

    if policy_name is not None:
        conditions.append("policy_name = ?")
        params.append(policy_name)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            id, processed_at, policy_name,
            size_before, size_after, size_change,
            audio_tracks_removed, subtitle_tracks_removed, attachments_removed,
            duration_seconds, success, error_message, encoder_type
        FROM processing_stats
        {where_clause}
        ORDER BY processed_at DESC
        LIMIT ?
    """
    params.append(limit)

    cursor = conn.execute(query, params)
    return [
        FileProcessingHistory(
            stats_id=row["id"],
            processed_at=row["processed_at"],
            policy_name=row["policy_name"],
            size_before=row["size_before"],
            size_after=row["size_after"],
            size_change=row["size_change"],
            audio_removed=row["audio_tracks_removed"],
            subtitle_removed=row["subtitle_tracks_removed"],
            attachments_removed=row["attachments_removed"],
            duration_seconds=row["duration_seconds"],
            success=row["success"] == 1,
            error_message=row["error_message"],
            encoder_type=row["encoder_type"],
        )
        for row in cursor.fetchall()
    ]


def get_policy_stats(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    until: str | None = None,
    limit: int | None = None,
) -> list[PolicyStats]:
    """Get statistics grouped by policy.

    Args:
        conn: Database connection.
        since: ISO-8601 timestamp for start of date range (inclusive).
        until: ISO-8601 timestamp for end of date range (inclusive).
        limit: Maximum policies to return.

    Returns:
        List of PolicyStats objects, one per policy used.
    """
    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

    conditions: list[str] = []
    params: list[str] = []

    if since is not None:
        conditions.append("processed_at >= ?")
        params.append(since)
    if until is not None:
        conditions.append("processed_at <= ?")
        params.append(until)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            policy_name,
            COUNT(*) as files_processed,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
            SUM(size_change) as total_size_saved,
            SUM(size_before) as total_size_before,
            SUM(audio_tracks_removed) as audio_tracks_removed,
            SUM(subtitle_tracks_removed) as subtitle_tracks_removed,
            SUM(attachments_removed) as attachments_removed,
            SUM(CASE WHEN video_target_codec IS NOT NULL
                AND video_transcode_skipped = 0 THEN 1 ELSE 0 END)
                as videos_transcoded,
            SUM(audio_tracks_transcoded) as audio_transcoded,
            AVG(duration_seconds) as avg_processing_time,
            MAX(processed_at) as last_used
        FROM processing_stats
        {where_clause}
        GROUP BY policy_name
        ORDER BY files_processed DESC
        LIMIT ?
    """

    cursor = conn.execute(query, [*params, limit])
    results = []
    for row in cursor.fetchall():
        files_processed = row["files_processed"] or 0
        successful = row["successful"] or 0
        size_before = row["total_size_before"] or 0
        size_saved = row["total_size_saved"] or 0

        success_rate = (successful / files_processed) if files_processed > 0 else 0.0
        avg_savings = ((size_saved / size_before) * 100) if size_before > 0 else 0.0

        results.append(
            PolicyStats(
                policy_name=row["policy_name"],
                files_processed=files_processed,
                success_rate=success_rate,
                total_size_saved=size_saved,
                avg_savings_percent=avg_savings,
                audio_tracks_removed=row["audio_tracks_removed"] or 0,
                subtitle_tracks_removed=row["subtitle_tracks_removed"] or 0,
                attachments_removed=row["attachments_removed"] or 0,
                videos_transcoded=row["videos_transcoded"] or 0,
                audio_transcoded=row["audio_transcoded"] or 0,
                avg_processing_time=row["avg_processing_time"] or 0.0,
                last_used=row["last_used"],
            )
        )
    return results


def get_policy_stats_by_name(
    conn: sqlite3.Connection,
    policy_name: str,
    *,
    since: str | None = None,
    until: str | None = None,
) -> PolicyStats | None:
    """Get statistics for a specific policy.

    Args:
        conn: Database connection.
        policy_name: Name of the policy to query.
        since: ISO-8601 timestamp for start of date range (inclusive).
        until: ISO-8601 timestamp for end of date range (inclusive).

    Returns:
        PolicyStats for the policy, or None if no stats found for policy.
    """
    conditions: list[str] = ["policy_name = ?"]
    params: list[str] = [policy_name]

    if since is not None:
        conditions.append("processed_at >= ?")
        params.append(since)
    if until is not None:
        conditions.append("processed_at <= ?")
        params.append(until)

    where_clause = " WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            policy_name,
            COUNT(*) as files_processed,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
            SUM(size_change) as total_size_saved,
            SUM(size_before) as total_size_before,
            SUM(audio_tracks_removed) as audio_tracks_removed,
            SUM(subtitle_tracks_removed) as subtitle_tracks_removed,
            SUM(attachments_removed) as attachments_removed,
            SUM(CASE WHEN video_target_codec IS NOT NULL
                AND video_transcode_skipped = 0 THEN 1 ELSE 0 END)
                as videos_transcoded,
            SUM(audio_tracks_transcoded) as audio_transcoded,
            AVG(duration_seconds) as avg_processing_time,
            MAX(processed_at) as last_used
        FROM processing_stats
        {where_clause}
        GROUP BY policy_name
    """

    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    if row is None:
        return None

    files_processed = row["files_processed"] or 0
    if files_processed == 0:
        return None

    successful = row["successful"] or 0
    size_before = row["total_size_before"] or 0
    size_saved = row["total_size_saved"] or 0

    success_rate = (successful / files_processed) if files_processed > 0 else 0.0
    avg_savings = ((size_saved / size_before) * 100) if size_before > 0 else 0.0

    return PolicyStats(
        policy_name=row["policy_name"],
        files_processed=files_processed,
        success_rate=success_rate,
        total_size_saved=size_saved,
        avg_savings_percent=avg_savings,
        audio_tracks_removed=row["audio_tracks_removed"] or 0,
        subtitle_tracks_removed=row["subtitle_tracks_removed"] or 0,
        attachments_removed=row["attachments_removed"] or 0,
        videos_transcoded=row["videos_transcoded"] or 0,
        audio_transcoded=row["audio_transcoded"] or 0,
        avg_processing_time=row["avg_processing_time"] or 0.0,
        last_used=row["last_used"],
    )


def get_stats_detail(
    conn: sqlite3.Connection,
    stats_id: str,
) -> StatsDetailView | None:
    """Get detailed statistics for a single processing run.

    Retrieves full processing stats record with joined action results
    for detailed display of track removal and other changes.

    Args:
        conn: Database connection.
        stats_id: UUID of processing_stats record.

    Returns:
        StatsDetailView with full details and actions, or None if not found.
    """
    # Get main stats record with file info
    cursor = conn.execute(
        """
        SELECT
            ps.id,
            ps.file_id,
            f.path,
            f.filename,
            ps.processed_at,
            ps.policy_name,
            ps.size_before,
            ps.size_after,
            ps.size_change,
            ps.audio_tracks_before,
            ps.audio_tracks_after,
            ps.audio_tracks_removed,
            ps.subtitle_tracks_before,
            ps.subtitle_tracks_after,
            ps.subtitle_tracks_removed,
            ps.attachments_before,
            ps.attachments_after,
            ps.attachments_removed,
            ps.video_source_codec,
            ps.video_target_codec,
            ps.video_transcode_skipped,
            ps.video_skip_reason,
            ps.audio_tracks_transcoded,
            ps.audio_tracks_preserved,
            ps.duration_seconds,
            ps.phases_completed,
            ps.phases_total,
            ps.total_changes,
            ps.hash_before,
            ps.hash_after,
            ps.success,
            ps.error_message,
            ps.encoder_type
        FROM processing_stats ps
        LEFT JOIN files f ON ps.file_id = f.id
        WHERE ps.id = ?
        """,
        (stats_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    # Get associated actions
    actions_cursor = conn.execute(
        """
        SELECT action_type, track_type, track_index, success, message
        FROM action_results
        WHERE stats_id = ?
        ORDER BY id
        """,
        (stats_id,),
    )
    actions = [
        ActionSummary(
            action_type=a["action_type"],
            track_type=a["track_type"],
            track_index=a["track_index"],
            success=a["success"] == 1,
            message=a["message"],
        )
        for a in actions_cursor.fetchall()
    ]

    return StatsDetailView(
        stats_id=row["id"],
        file_id=row["file_id"],
        file_path=row["path"],
        filename=row["filename"],
        processed_at=row["processed_at"],
        policy_name=row["policy_name"],
        size_before=row["size_before"] or 0,
        size_after=row["size_after"] or 0,
        size_change=row["size_change"] or 0,
        audio_tracks_before=row["audio_tracks_before"] or 0,
        audio_tracks_after=row["audio_tracks_after"] or 0,
        audio_tracks_removed=row["audio_tracks_removed"] or 0,
        subtitle_tracks_before=row["subtitle_tracks_before"] or 0,
        subtitle_tracks_after=row["subtitle_tracks_after"] or 0,
        subtitle_tracks_removed=row["subtitle_tracks_removed"] or 0,
        attachments_before=row["attachments_before"] or 0,
        attachments_after=row["attachments_after"] or 0,
        attachments_removed=row["attachments_removed"] or 0,
        video_source_codec=row["video_source_codec"],
        video_target_codec=row["video_target_codec"],
        video_transcode_skipped=row["video_transcode_skipped"] == 1,
        video_skip_reason=row["video_skip_reason"],
        audio_tracks_transcoded=row["audio_tracks_transcoded"] or 0,
        audio_tracks_preserved=row["audio_tracks_preserved"] or 0,
        duration_seconds=row["duration_seconds"] or 0.0,
        phases_completed=row["phases_completed"] or 0,
        phases_total=row["phases_total"] or 0,
        total_changes=row["total_changes"] or 0,
        hash_before=row["hash_before"],
        hash_after=row["hash_after"],
        success=row["success"] == 1,
        error_message=row["error_message"],
        encoder_type=row["encoder_type"],
        actions=actions,
    )


def get_stats_for_file(
    conn: sqlite3.Connection,
    file_id: int | None = None,
    file_path: str | None = None,
    *,
    limit: int | None = None,
) -> list[FileProcessingHistory]:
    """Get processing history for a specific file.

    Looks up file by ID or path and returns all processing stats for it.

    Args:
        conn: Database connection.
        file_id: ID of file to look up.
        file_path: Path of file to look up (used if file_id not provided).
        limit: Maximum history entries to return.

    Returns:
        List of FileProcessingHistory entries for the file, ordered by
        processed_at DESC (most recent first). Empty list if file not found
        or no processing history.
    """
    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

    # Resolve file_id from path if needed
    if file_id is None and file_path is not None:
        cursor = conn.execute("SELECT id FROM files WHERE path = ?", (file_path,))
        row = cursor.fetchone()
        if row is None:
            return []
        file_id = row[0]

    if file_id is None:
        return []

    cursor = conn.execute(
        """
        SELECT
            id, processed_at, policy_name,
            size_before, size_after, size_change,
            audio_tracks_removed, subtitle_tracks_removed, attachments_removed,
            duration_seconds, success, error_message, encoder_type
        FROM processing_stats
        WHERE file_id = ?
        ORDER BY processed_at DESC
        LIMIT ?
        """,
        (file_id, limit),
    )
    return [
        FileProcessingHistory(
            stats_id=row["id"],
            processed_at=row["processed_at"],
            policy_name=row["policy_name"],
            size_before=row["size_before"] or 0,
            size_after=row["size_after"] or 0,
            size_change=row["size_change"] or 0,
            audio_removed=row["audio_tracks_removed"] or 0,
            subtitle_removed=row["subtitle_tracks_removed"] or 0,
            attachments_removed=row["attachments_removed"] or 0,
            duration_seconds=row["duration_seconds"] or 0.0,
            success=row["success"] == 1,
            error_message=row["error_message"],
            encoder_type=row["encoder_type"],
        )
        for row in cursor.fetchall()
    ]


def get_stats_trends(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    group_by: str = "day",
) -> list[TrendDataPoint]:
    """Get processing trends aggregated by time period.

    Aggregates processing statistics by day, week, or month for charting.
    Returns data points sorted by date ascending.

    Args:
        conn: Database connection.
        since: ISO-8601 timestamp for start of date range (inclusive).
        group_by: Time grouping: 'day', 'week', or 'month'.

    Returns:
        List of TrendDataPoint objects ordered by date ascending.
    """
    # Determine SQL date format based on grouping
    if group_by == "week":
        # Group by year-week (ISO week number)
        date_format = "%Y-W%W"
    elif group_by == "month":
        # Group by year-month
        date_format = "%Y-%m"
    else:
        # Default to day
        date_format = "%Y-%m-%d"

    conditions: list[str] = []
    params: list[str] = []

    if since is not None:
        conditions.append("processed_at >= ?")
        params.append(since)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            strftime('{date_format}', processed_at) as period,
            COUNT(*) as files_processed,
            COALESCE(SUM(size_change), 0) as size_saved,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as fail_count
        FROM processing_stats
        {where_clause}
        GROUP BY period
        ORDER BY period ASC
    """

    cursor = conn.execute(query, params)
    return [
        TrendDataPoint(
            date=row["period"],
            files_processed=row["files_processed"] or 0,
            size_saved=row["size_saved"] or 0,
            success_count=row["success_count"] or 0,
            fail_count=row["fail_count"] or 0,
        )
        for row in cursor.fetchall()
    ]
