"""Transcription view query functions."""

import sqlite3

from ..types import TranscriptionDetailView, TranscriptionListViewItem
from .helpers import _clamp_limit


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
    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

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
            "id": row["id"],
            "filename": row["filename"],
            "path": row["path"],
            "scan_status": row["scan_status"],
            "transcription_count": row["transcription_count"],
            "detected_languages": row["detected_languages"],
            "avg_confidence": row["avg_confidence"],
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
