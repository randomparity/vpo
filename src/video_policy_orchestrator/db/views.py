"""View query functions for Video Policy Orchestrator database.

This module contains query functions that return aggregated/joined data
for UI views. These functions typically:
- JOIN multiple tables
- Use GROUP BY for aggregation
- Return view model dataclasses for typed results

The dict-returning versions are kept for backward compatibility.
New code should use the _typed variants that return dataclasses.
"""

import sqlite3

from .types import (
    FileListViewItem,
    LanguageOption,
    ScanErrorView,
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
        params.extend([lang.lower() for lang in audio_lang])

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
