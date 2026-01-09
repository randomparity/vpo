"""View query functions for Video Policy Orchestrator database.

This module contains query functions that return aggregated/joined data
for UI views. These functions typically:
- JOIN multiple tables
- Use GROUP BY for aggregation
- Return view model dataclasses for typed results

The dict-returning versions are kept for backward compatibility.
New code should use the _typed variants that return dataclasses.
"""

import json
import logging
import re
import sqlite3

from .types import (
    ActionSummary,
    AnalysisStatusSummary,
    FileAnalysisStatus,
    FileListViewItem,
    FileProcessingHistory,
    LanguageOption,
    PolicyStats,
    ScanErrorView,
    StatsDetailView,
    StatsSummary,
    TrackAnalysisDetail,
    TranscriptionDetailView,
    TranscriptionListViewItem,
)

# ==========================================================================
# Library List View Query Functions (018-library-list-view)
# ==========================================================================


def get_files_filtered(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    search: str | None = None,
    resolution: str | None = None,
    audio_lang: list[str] | None = None,
    subtitles: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    """Get files with track metadata for Library view.

    Returns file records with aggregated track data (resolution, languages).
    Files are ordered by scanned_at descending (most recent first).

    Args:
        conn: Database connection.
        status: Filter by scan_status (None = all, "ok", "error").
        search: Text search for filename/title (case-insensitive LIKE).
        resolution: Filter by resolution category (4k, 1080p, 720p, 480p, other).
        audio_lang: Filter by audio language codes (OR logic).
        subtitles: Filter by subtitle presence ("yes" or "no").
        limit: Maximum files to return.
        offset: Pagination offset.
        return_total: If True, return tuple of (files, total_count).

    Returns:
        List of file dicts with track data, or tuple with total count.
    """
    # Build WHERE clause conditions
    conditions: list[str] = []
    params: list[str | int] = []

    if status is not None:
        conditions.append("f.scan_status = ?")
        params.append(status)

    # Text search on filename and video title (019-library-filters-search)
    if search is not None:
        search_pattern = f"%{search}%"
        conditions.append(
            "(LOWER(f.filename) LIKE LOWER(?) OR "
            "LOWER(f.path) LIKE LOWER(?) OR "
            "EXISTS (SELECT 1 FROM tracks t2 WHERE t2.file_id = f.id "
            "AND t2.track_type = 'video' AND LOWER(t2.title) LIKE LOWER(?)))"
        )
        params.extend([search_pattern, search_pattern, search_pattern])

    # Resolution filter using height ranges (019-library-filters-search)
    if resolution is not None:
        # Map resolution to height condition
        resolution_conditions = {
            "4k": "t_video.height >= 2160",
            "1080p": "t_video.height >= 1080 AND t_video.height < 2160",
            "720p": "t_video.height >= 720 AND t_video.height < 1080",
            "480p": "t_video.height >= 480 AND t_video.height < 720",
            "other": "t_video.height < 480 OR t_video.height IS NULL",
        }
        if resolution in resolution_conditions:
            conditions.append(
                f"EXISTS (SELECT 1 FROM tracks t_video WHERE t_video.file_id = f.id "
                f"AND t_video.track_type = 'video' AND "
                f"({resolution_conditions[resolution]}))"
            )

    # Audio language filter with OR logic (019-library-filters-search)
    if audio_lang is not None and len(audio_lang) > 0:
        placeholders = ",".join("?" * len(audio_lang))
        conditions.append(
            f"EXISTS (SELECT 1 FROM tracks t_audio WHERE t_audio.file_id = f.id "
            f"AND t_audio.track_type = 'audio' "
            f"AND LOWER(t_audio.language) IN ({placeholders}))"
        )
        params.extend([lang.casefold() for lang in audio_lang])

    # Subtitle presence filter (019-library-filters-search)
    if subtitles == "yes":
        conditions.append(
            "EXISTS (SELECT 1 FROM tracks t_sub WHERE t_sub.file_id = f.id "
            "AND t_sub.track_type = 'subtitle')"
        )
    elif subtitles == "no":
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM tracks t_sub WHERE t_sub.file_id = f.id "
            "AND t_sub.track_type = 'subtitle')"
        )

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    # Get total count if requested (count distinct files)
    total = 0
    if return_total:
        count_query = "SELECT COUNT(DISTINCT f.id) FROM files f" + where_clause
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

    # Main query using JOIN with conditional aggregation (faster than subqueries)
    query = """
        SELECT
            f.id,
            f.path,
            f.filename,
            f.scanned_at,
            f.scan_status,
            f.scan_error,
            MAX(CASE WHEN t.track_type = 'video' THEN t.title END) as video_title,
            MAX(CASE WHEN t.track_type = 'video' THEN t.width END) as width,
            MAX(CASE WHEN t.track_type = 'video' THEN t.height END) as height,
            GROUP_CONCAT(DISTINCT CASE WHEN t.track_type = 'audio' THEN t.language END)
                as audio_languages
        FROM files f
        LEFT JOIN tracks t ON f.id = t.file_id
    """
    query += where_clause
    query += (
        " GROUP BY f.id, f.path, f.filename, f.scanned_at, f.scan_status, f.scan_error"
    )
    query += " ORDER BY f.scanned_at DESC"

    # Apply pagination
    pagination_params = list(params)
    if limit is not None:
        query += " LIMIT ?"
        pagination_params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            pagination_params.append(offset)

    cursor = conn.execute(query, pagination_params)
    files = [
        {
            "id": row[0],
            "path": row[1],
            "filename": row[2],
            "scanned_at": row[3],
            "scan_status": row[4],
            "scan_error": row[5],
            "video_title": row[6],
            "width": row[7],
            "height": row[8],
            "audio_languages": row[9],
        }
        for row in cursor.fetchall()
    ]

    if return_total:
        return files, total
    return files


def get_files_filtered_typed(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    search: str | None = None,
    resolution: str | None = None,
    audio_lang: list[str] | None = None,
    subtitles: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[FileListViewItem] | tuple[list[FileListViewItem], int]:
    """Typed version of get_files_filtered().

    Returns FileListViewItem dataclass instances instead of dicts.
    See get_files_filtered() for parameter documentation.

    Args:
        conn: Database connection.
        status: Filter by scan_status (None = all, "ok", "error").
        search: Text search for filename/title (case-insensitive LIKE).
        resolution: Filter by resolution category (4k, 1080p, 720p, 480p, other).
        audio_lang: Filter by audio language codes (OR logic).
        subtitles: Filter by subtitle presence ("yes" or "no").
        limit: Maximum files to return.
        offset: Pagination offset.
        return_total: If True, return tuple of (files, total_count).

    Returns:
        List of FileListViewItem objects, or tuple with total count.
    """
    result = get_files_filtered(
        conn,
        status=status,
        search=search,
        resolution=resolution,
        audio_lang=audio_lang,
        subtitles=subtitles,
        limit=limit,
        offset=offset,
        return_total=return_total,
    )

    if return_total:
        files, total = result
        return [FileListViewItem(**f) for f in files], total
    return [FileListViewItem(**f) for f in result]


def get_distinct_audio_languages(conn: sqlite3.Connection) -> list[dict]:
    """Get distinct audio language codes present in the library.

    Returns list of language options for the filter dropdown.

    Args:
        conn: Database connection.

    Returns:
        List of dicts with 'code' and 'label' keys, sorted by code.
    """
    query = """
        SELECT DISTINCT language
        FROM tracks
        WHERE track_type = 'audio' AND language IS NOT NULL AND language != ''
        ORDER BY language
    """
    cursor = conn.execute(query)
    languages = []
    for (code,) in cursor.fetchall():
        # Use code as label for now (could map to full names later)
        languages.append({"code": code, "label": code})
    return languages


def get_distinct_audio_languages_typed(
    conn: sqlite3.Connection,
) -> list[LanguageOption]:
    """Typed version of get_distinct_audio_languages().

    Returns LanguageOption dataclass instances instead of dicts.

    Args:
        conn: Database connection.

    Returns:
        List of LanguageOption objects, sorted by code.
    """
    return [LanguageOption(**d) for d in get_distinct_audio_languages(conn)]


# ==========================================================================
# Transcriptions Overview List Query Functions (021-transcriptions-list)
# ==========================================================================


def get_files_with_transcriptions(
    conn: sqlite3.Connection,
    *,
    show_all: bool = False,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    """Get files with aggregated transcription data.

    Args:
        conn: Database connection.
        show_all: If False, only return files with transcriptions.
                  If True, return all files.
        limit: Maximum files to return.
        offset: Pagination offset.
        return_total: If True, return tuple of (files, total_count).

    Returns:
        List of file dicts with transcription data:
        {
            "id": int,
            "filename": str,
            "path": str,
            "scan_status": str,
            "transcription_count": int,
            "detected_languages": str | None,  # CSV from GROUP_CONCAT
            "avg_confidence": float | None,
        }
    """
    # Build HAVING clause for filtering
    having_clause = ""
    if not show_all:
        having_clause = "HAVING COUNT(tr.id) > 0"

    # Count query (with same filter logic)
    total = 0
    if return_total:
        count_query = f"""
            SELECT COUNT(*) FROM (
                SELECT f.id
                FROM files f
                LEFT JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
                LEFT JOIN transcription_results tr ON t.id = tr.track_id
                GROUP BY f.id
                {having_clause}
            )
        """
        cursor = conn.execute(count_query)
        total = cursor.fetchone()[0]

    # Main query
    query = f"""
        SELECT
            f.id, f.filename, f.path, f.scan_status,
            COUNT(tr.id) as transcription_count,
            GROUP_CONCAT(DISTINCT tr.detected_language) as detected_languages,
            AVG(tr.confidence_score) as avg_confidence
        FROM files f
        LEFT JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
        LEFT JOIN transcription_results tr ON t.id = tr.track_id
        GROUP BY f.id
        {having_clause}
        ORDER BY f.filename
    """

    # Add pagination
    params: list[int] = []
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

    cursor = conn.execute(query, params)
    files = [
        {
            "id": row[0],
            "filename": row[1],
            "path": row[2],
            "scan_status": row[3],
            "transcription_count": row[4],
            "detected_languages": row[5],
            "avg_confidence": row[6],
        }
        for row in cursor.fetchall()
    ]

    if return_total:
        return files, total
    return files


def get_files_with_transcriptions_typed(
    conn: sqlite3.Connection,
    *,
    show_all: bool = False,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[TranscriptionListViewItem] | tuple[list[TranscriptionListViewItem], int]:
    """Typed version of get_files_with_transcriptions().

    Returns TranscriptionListViewItem dataclass instances instead of dicts.

    Args:
        conn: Database connection.
        show_all: If False, only return files with transcriptions.
        limit: Maximum files to return.
        offset: Pagination offset.
        return_total: If True, return tuple of (files, total_count).

    Returns:
        List of TranscriptionListViewItem objects, or tuple with total count.
    """
    result = get_files_with_transcriptions(
        conn,
        show_all=show_all,
        limit=limit,
        offset=offset,
        return_total=return_total,
    )

    if return_total:
        files, total = result
        return [TranscriptionListViewItem(**f) for f in files], total
    return [TranscriptionListViewItem(**f) for f in result]


# ==========================================================================
# Transcription Detail View Query Functions (022-transcription-detail)
# ==========================================================================


def get_transcription_detail(
    conn: sqlite3.Connection,
    transcription_id: int,
) -> dict | None:
    """Get transcription detail with track and file info.

    Args:
        conn: Database connection.
        transcription_id: ID of transcription_results record.

    Returns:
        Dictionary with transcription, track, and file data:
        {
            "id": int,
            "track_id": int,
            "detected_language": str | None,
            "confidence_score": float,
            "track_type": str,
            "transcript_sample": str | None,
            "plugin_name": str,
            "created_at": str,
            "updated_at": str,
            "track_index": int,
            "codec": str | None,
            "original_language": str | None,
            "title": str | None,
            "channels": int | None,
            "channel_layout": str | None,
            "is_default": int,
            "is_forced": int,
            "file_id": int,
            "filename": str,
            "path": str,
        }
        Returns None if transcription not found.
    """
    cursor = conn.execute(
        """
        SELECT
            tr.id,
            tr.track_id,
            tr.detected_language,
            tr.confidence_score,
            tr.track_type,
            tr.transcript_sample,
            tr.plugin_name,
            tr.created_at,
            tr.updated_at,
            t.track_index,
            t.codec,
            t.language AS original_language,
            t.title,
            t.channels,
            t.channel_layout,
            t.is_default,
            t.is_forced,
            f.id AS file_id,
            f.filename,
            f.path
        FROM transcription_results tr
        JOIN tracks t ON tr.track_id = t.id
        JOIN files f ON t.file_id = f.id
        WHERE tr.id = ?
        """,
        (transcription_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def get_transcription_detail_typed(
    conn: sqlite3.Connection,
    transcription_id: int,
) -> TranscriptionDetailView | None:
    """Typed version of get_transcription_detail().

    Returns TranscriptionDetailView dataclass instance instead of dict.

    Args:
        conn: Database connection.
        transcription_id: ID of transcription_results record.

    Returns:
        TranscriptionDetailView object, or None if not found.
    """
    result = get_transcription_detail(conn, transcription_id)
    return TranscriptionDetailView(**result) if result else None


# ==========================================================================
# Scan Job Error Query Functions
# ==========================================================================


def get_scan_errors_for_job(
    conn: sqlite3.Connection,
    job_id: str,
) -> list[ScanErrorView] | None:
    """Get files with scan errors for a specific job.

    Returns files that failed to scan during a scan job. Used by the
    job errors API endpoint to display detailed error information.

    Args:
        conn: Database connection.
        job_id: UUID of the scan job.

    Returns:
        List of ScanErrorView objects if job exists and is a scan job,
        or None if job not found or is not a scan job.
    """
    # First verify job exists and is a scan job
    cursor = conn.execute(
        "SELECT job_type FROM jobs WHERE id = ?",
        (job_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    if row["job_type"] != "scan":
        return None

    # Get files with errors for this specific job
    cursor = conn.execute(
        """
        SELECT path, filename, scan_error
        FROM files
        WHERE job_id = ?
          AND scan_status = 'error'
          AND scan_error IS NOT NULL
        ORDER BY filename
        """,
        (job_id,),
    )
    return [
        ScanErrorView(
            path=row["path"],
            filename=row["filename"],
            error=row["scan_error"],
        )
        for row in cursor.fetchall()
    ]


# ==========================================================================
# Processing Statistics View Query Functions (040-processing-stats)
# ==========================================================================


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
            MAX(processed_at) as latest_processing
        FROM processing_stats
        {where_clause}
    """

    cursor = conn.execute(query, params)
    row = cursor.fetchone()

    total = row[0] or 0
    successful = row[1] or 0
    size_before = row[3] or 0

    # Calculate derived values
    success_rate = (successful / total) if total > 0 else 0.0
    avg_savings = ((row[5] / size_before) * 100) if size_before > 0 else 0.0

    return StatsSummary(
        total_files_processed=total,
        total_successful=successful,
        total_failed=row[2] or 0,
        success_rate=success_rate,
        total_size_before=size_before,
        total_size_after=row[4] or 0,
        total_size_saved=row[5] or 0,
        avg_savings_percent=avg_savings,
        total_audio_removed=row[6] or 0,
        total_subtitles_removed=row[7] or 0,
        total_attachments_removed=row[8] or 0,
        total_videos_transcoded=row[9] or 0,
        total_videos_skipped=row[10] or 0,
        total_audio_transcoded=row[11] or 0,
        avg_processing_time=row[12] or 0.0,
        earliest_processing=row[13],
        latest_processing=row[14],
    )


def get_recent_stats(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
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
            duration_seconds, success, error_message
        FROM processing_stats
        {where_clause}
        ORDER BY processed_at DESC
        LIMIT ?
    """
    params.append(limit)

    cursor = conn.execute(query, params)
    return [
        FileProcessingHistory(
            stats_id=row[0],
            processed_at=row[1],
            policy_name=row[2],
            size_before=row[3],
            size_after=row[4],
            size_change=row[5],
            audio_removed=row[6],
            subtitle_removed=row[7],
            attachments_removed=row[8],
            duration_seconds=row[9],
            success=row[10] == 1,
            error_message=row[11],
        )
        for row in cursor.fetchall()
    ]


def get_policy_stats(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    until: str | None = None,
) -> list[PolicyStats]:
    """Get statistics grouped by policy.

    Args:
        conn: Database connection.
        since: ISO-8601 timestamp for start of date range (inclusive).
        until: ISO-8601 timestamp for end of date range (inclusive).

    Returns:
        List of PolicyStats objects, one per policy used.
    """
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
    """

    cursor = conn.execute(query, params)
    results = []
    for row in cursor.fetchall():
        files_processed = row[1] or 0
        successful = row[2] or 0
        size_before = row[4] or 0

        success_rate = (successful / files_processed) if files_processed > 0 else 0.0
        avg_savings = ((row[3] / size_before) * 100) if size_before > 0 else 0.0

        results.append(
            PolicyStats(
                policy_name=row[0],
                files_processed=files_processed,
                success_rate=success_rate,
                total_size_saved=row[3] or 0,
                avg_savings_percent=avg_savings,
                audio_tracks_removed=row[5] or 0,
                subtitle_tracks_removed=row[6] or 0,
                attachments_removed=row[7] or 0,
                videos_transcoded=row[8] or 0,
                audio_transcoded=row[9] or 0,
                avg_processing_time=row[10] or 0.0,
                last_used=row[11],
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

    files_processed = row[1] or 0
    if files_processed == 0:
        return None

    successful = row[2] or 0
    size_before = row[4] or 0

    success_rate = (successful / files_processed) if files_processed > 0 else 0.0
    avg_savings = ((row[3] / size_before) * 100) if size_before > 0 else 0.0

    return PolicyStats(
        policy_name=row[0],
        files_processed=files_processed,
        success_rate=success_rate,
        total_size_saved=row[3] or 0,
        avg_savings_percent=avg_savings,
        audio_tracks_removed=row[5] or 0,
        subtitle_tracks_removed=row[6] or 0,
        attachments_removed=row[7] or 0,
        videos_transcoded=row[8] or 0,
        audio_transcoded=row[9] or 0,
        avg_processing_time=row[10] or 0.0,
        last_used=row[11],
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
            ps.error_message
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
            action_type=a[0],
            track_type=a[1],
            track_index=a[2],
            success=a[3] == 1,
            message=a[4],
        )
        for a in actions_cursor.fetchall()
    ]

    return StatsDetailView(
        stats_id=row[0],
        file_id=row[1],
        file_path=row[2],
        filename=row[3],
        processed_at=row[4],
        policy_name=row[5],
        size_before=row[6] or 0,
        size_after=row[7] or 0,
        size_change=row[8] or 0,
        audio_tracks_before=row[9] or 0,
        audio_tracks_after=row[10] or 0,
        audio_tracks_removed=row[11] or 0,
        subtitle_tracks_before=row[12] or 0,
        subtitle_tracks_after=row[13] or 0,
        subtitle_tracks_removed=row[14] or 0,
        attachments_before=row[15] or 0,
        attachments_after=row[16] or 0,
        attachments_removed=row[17] or 0,
        video_source_codec=row[18],
        video_target_codec=row[19],
        video_transcode_skipped=row[20] == 1,
        video_skip_reason=row[21],
        audio_tracks_transcoded=row[22] or 0,
        audio_tracks_preserved=row[23] or 0,
        duration_seconds=row[24] or 0.0,
        phases_completed=row[25] or 0,
        phases_total=row[26] or 0,
        total_changes=row[27] or 0,
        hash_before=row[28],
        hash_after=row[29],
        success=row[30] == 1,
        error_message=row[31],
        actions=actions,
    )


def get_stats_for_file(
    conn: sqlite3.Connection,
    file_id: int | None = None,
    file_path: str | None = None,
) -> list[FileProcessingHistory]:
    """Get processing history for a specific file.

    Looks up file by ID or path and returns all processing stats for it.

    Args:
        conn: Database connection.
        file_id: ID of file to look up.
        file_path: Path of file to look up (used if file_id not provided).

    Returns:
        List of FileProcessingHistory entries for the file, ordered by
        processed_at DESC (most recent first). Empty list if file not found
        or no processing history.
    """
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
            duration_seconds, success, error_message
        FROM processing_stats
        WHERE file_id = ?
        ORDER BY processed_at DESC
        """,
        (file_id,),
    )
    return [
        FileProcessingHistory(
            stats_id=row[0],
            processed_at=row[1],
            policy_name=row[2],
            size_before=row[3] or 0,
            size_after=row[4] or 0,
            size_change=row[5] or 0,
            audio_removed=row[6] or 0,
            subtitle_removed=row[7] or 0,
            attachments_removed=row[8] or 0,
            duration_seconds=row[9] or 0.0,
            success=row[10] == 1,
            error_message=row[11],
        )
        for row in cursor.fetchall()
    ]


# ==========================================================================
# Plugin Data View Query Functions (236-generic-plugin-data-browser)
# ==========================================================================


def get_files_with_plugin_data(
    conn: sqlite3.Connection,
    plugin_name: str,
    *,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    """Get files that have data from a specific plugin.

    Queries files where plugin_metadata JSON contains data for the
    specified plugin name.

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier to filter by (e.g., "whisper-transcriber").
        limit: Maximum files to return.
        offset: Pagination offset.
        return_total: If True, return tuple of (files, total_count).

    Returns:
        List of file dicts with plugin data:
        {
            "id": int,
            "filename": str,
            "path": str,
            "scan_status": str,
            "plugin_data": dict,  # Parsed plugin-specific data
        }

    Raises:
        ValueError: If plugin_name contains invalid characters.
    """
    # Validate plugin name for defense in depth (routes also validate)
    if not re.match(r"^[a-zA-Z0-9_-]+$", plugin_name):
        raise ValueError(f"Invalid plugin name format: {plugin_name}")

    # Build query - use window function for total count when needed
    # This avoids a separate COUNT query (single query optimization)
    if return_total:
        query = """
            SELECT
                id, filename, path, scan_status, plugin_metadata,
                COUNT(*) OVER() as total_count
            FROM files
            WHERE plugin_metadata IS NOT NULL
            AND json_extract(plugin_metadata, ?) IS NOT NULL
            ORDER BY filename
        """
    else:
        query = """
            SELECT
                id, filename, path, scan_status, plugin_metadata
            FROM files
            WHERE plugin_metadata IS NOT NULL
            AND json_extract(plugin_metadata, ?) IS NOT NULL
            ORDER BY filename
        """

    # Add pagination
    params: list[str | int] = [f"$.{plugin_name}"]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    # Extract total from first row if using window function (or 0 if empty)
    total = rows[0][5] if return_total and rows else 0

    files = []
    for row in rows:
        plugin_metadata = json.loads(row[4]) if row[4] else {}
        files.append(
            {
                "id": row[0],
                "filename": row[1],
                "path": row[2],
                "scan_status": row[3],
                "plugin_data": plugin_metadata.get(plugin_name, {}),
            }
        )

    if return_total:
        return files, total
    return files


def get_plugin_data_for_file(
    conn: sqlite3.Connection,
    file_id: int,
) -> dict[str, dict]:
    """Get all plugin metadata for a specific file.

    Args:
        conn: Database connection.
        file_id: ID of file to look up.

    Returns:
        Dictionary keyed by plugin name with each plugin's data.
        Empty dict if file not found, no plugin metadata, or malformed JSON.
    """
    logger = logging.getLogger(__name__)

    cursor = conn.execute(
        "SELECT plugin_metadata FROM files WHERE id = ?",
        (file_id,),
    )
    row = cursor.fetchone()

    if row is None or row[0] is None:
        return {}

    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Failed to parse plugin_metadata for file_id=%d: %s", file_id, e)
        return {}


# ==========================================================================
# Language Analysis View Query Functions (042-analyze-language-cli)
# ==========================================================================


def get_analysis_status_summary(
    conn: sqlite3.Connection,
) -> AnalysisStatusSummary:
    """Get summary of language analysis status across the library.

    Counts total audio tracks, analyzed tracks, and classification breakdown.

    Args:
        conn: Database connection.

    Returns:
        AnalysisStatusSummary with counts.
    """
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT f.id) as total_files,
            COUNT(DISTINCT t.id) as total_tracks,
            COUNT(DISTINCT lar.id) as analyzed_tracks,
            SUM(CASE WHEN lar.classification = 'MULTI_LANGUAGE' THEN 1 ELSE 0 END)
                as multi_language,
            SUM(CASE WHEN lar.classification = 'SINGLE_LANGUAGE' THEN 1 ELSE 0 END)
                as single_language
        FROM files f
        JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
        LEFT JOIN language_analysis_results lar ON t.id = lar.track_id
    """)
    row = cursor.fetchone()

    total_tracks = row[1] or 0
    analyzed = row[2] or 0

    return AnalysisStatusSummary(
        total_files=row[0] or 0,
        total_tracks=total_tracks,
        analyzed_tracks=analyzed,
        pending_tracks=total_tracks - analyzed,
        multi_language_count=row[3] or 0,
        single_language_count=row[4] or 0,
    )


def get_files_analysis_status(
    conn: sqlite3.Connection,
    *,
    filter_classification: str | None = None,
    limit: int = 50,
) -> list[FileAnalysisStatus]:
    """Get analysis status for files, optionally filtered.

    Args:
        conn: Database connection.
        filter_classification: Filter by classification type:
            - "multi-language": Files with multi-language tracks
            - "single-language": Files with only single-language tracks
            - "pending": Files with unanalyzed audio tracks
            - None or "all": No filter
        limit: Maximum files to return.

    Returns:
        List of FileAnalysisStatus objects.
    """

    # Build query based on filter
    if filter_classification == "multi-language":
        query = """
            SELECT f.id, f.path,
                COUNT(DISTINCT t.id) as track_count,
                COUNT(DISTINCT lar.id) as analyzed_count
            FROM files f
            JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
            JOIN language_analysis_results lar ON t.id = lar.track_id
            WHERE lar.classification = 'MULTI_LANGUAGE'
            GROUP BY f.id
            ORDER BY f.path
            LIMIT ?
        """
    elif filter_classification == "single-language":
        query = """
            SELECT f.id, f.path,
                COUNT(DISTINCT t.id) as track_count,
                COUNT(DISTINCT lar.id) as analyzed_count
            FROM files f
            JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
            JOIN language_analysis_results lar ON t.id = lar.track_id
            WHERE lar.classification = 'SINGLE_LANGUAGE'
            GROUP BY f.id
            HAVING COUNT(DISTINCT t.id) = COUNT(DISTINCT lar.id)
            ORDER BY f.path
            LIMIT ?
        """
    elif filter_classification == "pending":
        query = """
            SELECT f.id, f.path,
                COUNT(DISTINCT t.id) as track_count,
                COUNT(DISTINCT lar.id) as analyzed_count
            FROM files f
            JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
            LEFT JOIN language_analysis_results lar ON t.id = lar.track_id
            GROUP BY f.id
            HAVING COUNT(DISTINCT t.id) > COUNT(DISTINCT lar.id)
            ORDER BY f.path
            LIMIT ?
        """
    else:
        query = """
            SELECT f.id, f.path,
                COUNT(DISTINCT t.id) as track_count,
                COUNT(DISTINCT lar.id) as analyzed_count
            FROM files f
            JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
            LEFT JOIN language_analysis_results lar ON t.id = lar.track_id
            GROUP BY f.id
            ORDER BY f.path
            LIMIT ?
        """

    cursor = conn.execute(query, (limit,))
    return [
        FileAnalysisStatus(
            file_id=row[0],
            file_path=row[1],
            track_count=row[2],
            analyzed_count=row[3],
        )
        for row in cursor.fetchall()
    ]


def get_file_analysis_detail(
    conn: sqlite3.Connection,
    file_path: str,
) -> list[TrackAnalysisDetail] | None:
    """Get detailed analysis results for a specific file.

    Args:
        conn: Database connection.
        file_path: Full path to file.

    Returns:
        List of TrackAnalysisDetail objects for each audio track,
        or None if file not found.
    """

    # First check if file exists
    cursor = conn.execute("SELECT id FROM files WHERE path = ?", (file_path,))
    if cursor.fetchone() is None:
        return None

    cursor = conn.execute(
        """
        SELECT
            t.id,
            t.track_index,
            t.language,
            lar.classification,
            lar.primary_language,
            lar.primary_percentage,
            lar.analysis_metadata,
            lar.updated_at
        FROM files f
        JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
        LEFT JOIN language_analysis_results lar ON t.id = lar.track_id
        WHERE f.path = ?
        ORDER BY t.track_index
    """,
        (file_path,),
    )

    results = []
    for row in cursor.fetchall():
        # Extract secondary_languages from analysis_metadata JSON if present
        secondary_langs = None
        if row[6]:  # analysis_metadata
            try:
                metadata = json.loads(row[6])
                secondary_langs = metadata.get("secondary_languages")
            except (json.JSONDecodeError, TypeError):
                pass

        results.append(
            TrackAnalysisDetail(
                track_id=row[0],
                track_index=row[1],
                language=row[2],
                classification=row[3],
                primary_language=row[4],
                primary_percentage=row[5] or 0.0,
                secondary_languages=secondary_langs,
                analyzed_at=row[7] or "",
            )
        )

    return results
