"""Library list view query functions."""

import sqlite3

from ..types import FileListViewItem, LanguageOption
from .helpers import _clamp_limit


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
    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

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
            "id": row["id"],
            "path": row["path"],
            "filename": row["filename"],
            "scanned_at": row["scanned_at"],
            "scan_status": row["scan_status"],
            "scan_error": row["scan_error"],
            "video_title": row["video_title"],
            "width": row["width"],
            "height": row["height"],
            "audio_languages": row["audio_languages"],
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


def get_missing_files(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
) -> list[dict]:
    """Get files with scan_status='missing'.

    Returns files that were previously scanned but are no longer found
    on the filesystem.

    Args:
        conn: Database connection.
        limit: Maximum files to return.

    Returns:
        List of dicts with id, path, filename, size_bytes, scanned_at.
    """
    limit = _clamp_limit(limit)

    query = """
        SELECT id, path, filename, size_bytes, scanned_at
        FROM files
        WHERE scan_status = 'missing'
        ORDER BY scanned_at DESC
        LIMIT ?
    """
    cursor = conn.execute(query, (limit,))
    return [
        {
            "id": row["id"],
            "path": row["path"],
            "filename": row["filename"],
            "size_bytes": row["size_bytes"],
            "scanned_at": row["scanned_at"],
        }
        for row in cursor.fetchall()
    ]


def get_distinct_audio_languages(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> list[dict]:
    """Get distinct audio language codes present in the library.

    Returns list of language options for the filter dropdown.

    Args:
        conn: Database connection.
        limit: Maximum languages to return.

    Returns:
        List of dicts with 'code' and 'label' keys, sorted by code.
    """
    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

    query = """
        SELECT DISTINCT language
        FROM tracks
        WHERE track_type = 'audio' AND language IS NOT NULL AND language != ''
        ORDER BY language
        LIMIT ?
    """
    cursor = conn.execute(query, (limit,))
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
