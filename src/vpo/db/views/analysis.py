"""Language analysis view query functions."""

import sqlite3

from vpo.core.json_utils import parse_json_safe

from ..types import AnalysisStatusSummary, FileAnalysisStatus, TrackAnalysisDetail
from .helpers import _clamp_limit


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
    limit: int | None = None,
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
    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

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
            result = parse_json_safe(row[6], context="analysis_metadata")
            if result.success and result.value:
                secondary_langs = result.value.get("secondary_languages")

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
