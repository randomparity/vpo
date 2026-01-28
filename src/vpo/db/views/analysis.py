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

    total_tracks = row["total_tracks"] or 0
    analyzed = row["analyzed_tracks"] or 0

    return AnalysisStatusSummary(
        total_files=row["total_files"] or 0,
        total_tracks=total_tracks,
        analyzed_tracks=analyzed,
        pending_tracks=total_tracks - analyzed,
        multi_language_count=row["multi_language"] or 0,
        single_language_count=row["single_language"] or 0,
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
            file_id=row["id"],
            file_path=row["path"],
            track_count=row["track_count"],
            analyzed_count=row["analyzed_count"],
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
        analysis_metadata = row["analysis_metadata"]
        if analysis_metadata:
            result = parse_json_safe(analysis_metadata, context="analysis_metadata")
            if result.success and result.value:
                secondary_langs = result.value.get("secondary_languages")

        results.append(
            TrackAnalysisDetail(
                track_id=row["id"],
                track_index=row["track_index"],
                language=row["language"],
                classification=row["classification"],
                primary_language=row["primary_language"],
                primary_percentage=row["primary_percentage"] or 0.0,
                secondary_languages=secondary_langs,
                analyzed_at=row["updated_at"] or "",
            )
        )

    return results
