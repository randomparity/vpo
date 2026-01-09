"""Database query functions for reports."""

import json
import logging
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from video_policy_orchestrator.reports.filters import TimeFilter
from video_policy_orchestrator.reports.formatters import (
    calculate_duration_seconds,
    format_duration,
    format_timestamp_local,
)

logger = logging.getLogger(__name__)


@dataclass
class JobReportRow:
    """Represents a single row in the jobs report."""

    job_id: str
    type: str
    status: str
    target: str
    started_at: str
    completed_at: str
    duration: str
    error: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for formatting."""
        return asdict(self)


@dataclass
class LibraryReportRow:
    """Represents a single file in the library report."""

    path: str
    title: str
    container: str
    resolution: str
    audio_languages: str
    has_subtitles: str | bool
    scanned_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for formatting."""
        return asdict(self)


@dataclass
class ScanReportRow:
    """Represents a single scan operation."""

    scan_id: str
    started_at: str
    completed_at: str
    duration: str
    files_scanned: int
    files_new: int
    files_changed: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for formatting."""
        return asdict(self)


@dataclass
class TranscodeReportRow:
    """Represents a single transcode operation."""

    job_id: str
    file_path: str
    source_codec: str
    target_codec: str
    started_at: str
    completed_at: str
    duration: str
    status: str
    size_change: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for formatting."""
        return asdict(self)


@dataclass
class PolicyApplyReportRow:
    """Represents a single policy application summary."""

    operation_id: str
    policy_name: str
    files_affected: int
    metadata_changes: int
    heavy_changes: int
    status: str
    started_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for formatting."""
        return asdict(self)


@dataclass
class PolicyApplyDetailRow:
    """Represents per-file details for verbose policy apply report."""

    file_path: str
    changes: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for formatting."""
        return asdict(self)


MAX_LIMIT = 10000


def _validate_limit(limit: int | None) -> None:
    """Validate limit parameter.

    Args:
        limit: Limit value to validate.

    Raises:
        ValueError: If limit is negative or exceeds MAX_LIMIT.
    """
    if limit is not None:
        if limit < 0:
            raise ValueError(f"Limit must be non-negative, got {limit}")
        if limit > MAX_LIMIT:
            raise ValueError(f"Limit too large (max {MAX_LIMIT}), got {limit}")


def get_resolution_category(width: int | None, height: int | None) -> str:
    """Categorize resolution from dimensions.

    Args:
        width: Video width in pixels.
        height: Video height in pixels.

    Returns:
        Resolution category: "4K", "1080p", "720p", "480p", "SD", or "unknown".
    """
    if width is None or height is None:
        return "unknown"

    if height >= 2160:
        return "4K"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    if height >= 480:
        return "480p"
    return "SD"


def extract_scan_summary(summary_json: str | None) -> dict[str, int]:
    """Extract scan summary from JSON field.

    Args:
        summary_json: JSON string containing scan summary.

    Returns:
        Dictionary with files_scanned, files_new, files_changed keys.
    """
    default = {"files_scanned": 0, "files_new": 0, "files_changed": 0}
    if not summary_json:
        return default

    try:
        data = json.loads(summary_json)
        return {
            "files_scanned": data.get("files_scanned", data.get("total", 0)),
            "files_new": data.get("files_new", data.get("new", 0)),
            "files_changed": data.get("files_changed", data.get("changed", 0)),
        }
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Failed to parse scan summary JSON: %s, returning defaults", e)
        return default


def _build_time_filter_clause(
    time_filter: TimeFilter | None,
    column: str = "created_at",
) -> tuple[str, list[str]]:
    """Build SQL WHERE clause for time filtering.

    Args:
        time_filter: TimeFilter instance or None.
        column: Column name to filter on.

    Returns:
        Tuple of (SQL clause string, parameter list).
    """
    if not time_filter:
        return "", []

    clauses = []
    params = []

    since_iso, until_iso = time_filter.to_iso_strings()

    if since_iso:
        clauses.append(f"{column} >= ?")
        params.append(since_iso)

    if until_iso:
        clauses.append(f"{column} <= ?")
        params.append(until_iso)

    if clauses:
        return " AND " + " AND ".join(clauses), params

    return "", []


def get_jobs_report(
    conn: sqlite3.Connection,
    *,
    job_type: str | None = None,
    status: str | None = None,
    time_filter: TimeFilter | None = None,
    limit: int | None = 100,
) -> list[dict[str, Any]]:
    """Query jobs table with filters.

    Args:
        conn: Database connection.
        job_type: Filter by job type (scan, apply, transcode, move).
        status: Filter by status (queued, running, completed, failed, cancelled).
        time_filter: Time range filter.
        limit: Maximum rows to return (None for no limit).

    Returns:
        List of job row dictionaries.

    Raises:
        ValueError: If limit is negative or exceeds MAX_LIMIT.
    """
    _validate_limit(limit)
    query = """
        SELECT
            id,
            job_type,
            status,
            file_path,
            started_at,
            completed_at,
            error_message
        FROM jobs
        WHERE 1=1
    """
    params: list[Any] = []

    if job_type:
        query += " AND job_type = ?"
        params.append(job_type)

    if status:
        query += " AND status = ?"
        params.append(status)

    time_clause, time_params = _build_time_filter_clause(time_filter, "created_at")
    query += time_clause
    params.extend(time_params)

    query += " ORDER BY created_at DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    result = []
    for row in rows:
        duration_seconds = calculate_duration_seconds(row[4], row[5])
        report_row = JobReportRow(
            job_id=row[0][:8] if row[0] else "-",
            type=row[1] or "-",
            status=row[2] or "-",
            target=row[3] or "-",
            started_at=format_timestamp_local(row[4]),
            completed_at=format_timestamp_local(row[5]),
            duration=format_duration(duration_seconds),
            error=row[6][:50] if row[6] else "-",
        )
        result.append(report_row.to_dict())

    return result


def get_library_report(
    conn: sqlite3.Connection,
    *,
    resolution: str | None = None,
    language: str | None = None,
    has_subtitles: bool | None = None,
    limit: int | None = 100,
) -> list[dict[str, Any]]:
    """Query files and tracks with filters.

    Args:
        conn: Database connection.
        resolution: Filter by resolution category (4K, 1080p, 720p, 480p, SD).
        language: Filter by audio language (ISO 639-2 code).
        has_subtitles: Filter by subtitle presence (True, False, or None).
        limit: Maximum rows to return (None for no limit).

    Returns:
        List of library row dictionaries.

    Raises:
        ValueError: If limit is negative or exceeds MAX_LIMIT.
    """
    _validate_limit(limit)
    # First, get file info with aggregated track data
    query = """
        SELECT
            f.id,
            f.path,
            f.filename,
            f.container_format,
            f.scanned_at,
            (
                SELECT MAX(t.height)
                FROM tracks t
                WHERE t.file_id = f.id AND t.track_type = 'video'
            ) as max_height,
            (
                SELECT MAX(t.width)
                FROM tracks t
                WHERE t.file_id = f.id AND t.track_type = 'video'
            ) as max_width,
            (
                SELECT GROUP_CONCAT(DISTINCT t.language)
                FROM tracks t
                WHERE t.file_id = f.id
                  AND t.track_type = 'audio'
                  AND t.language IS NOT NULL
            ) as audio_languages,
            (
                SELECT COUNT(*)
                FROM tracks t
                WHERE t.file_id = f.id AND t.track_type = 'subtitle'
            ) as subtitle_count
        FROM files f
        WHERE f.scan_status = 'scanned'
    """
    params: list[Any] = []

    # Language filter via subquery
    if language:
        query += """
            AND EXISTS (
                SELECT 1 FROM tracks t
                WHERE t.file_id = f.id
                AND t.track_type = 'audio'
                AND LOWER(t.language) = LOWER(?)
            )
        """
        params.append(language)

    # Subtitle filter
    if has_subtitles is True:
        query += """
            AND EXISTS (
                SELECT 1 FROM tracks t
                WHERE t.file_id = f.id AND t.track_type = 'subtitle'
            )
        """
    elif has_subtitles is False:
        query += """
            AND NOT EXISTS (
                SELECT 1 FROM tracks t
                WHERE t.file_id = f.id AND t.track_type = 'subtitle'
            )
        """

    query += " ORDER BY f.path"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    result = []
    for row in rows:
        file_path = row[1] or ""
        resolution_cat = get_resolution_category(row[6], row[5])

        # Filter by resolution after query (since it's computed)
        if resolution and resolution_cat.upper() != resolution.upper():
            continue

        audio_langs = row[7] or ""
        subtitle_present = (row[8] or 0) > 0

        report_row = LibraryReportRow(
            path=file_path,
            title=row[2] or Path(file_path).stem if file_path else "-",
            container=row[3] or "-",
            resolution=resolution_cat,
            audio_languages=audio_langs or "-",
            has_subtitles="Yes" if subtitle_present else "No",
            scanned_at=format_timestamp_local(row[4]),
        )
        result.append(report_row.to_dict())

    return result


def get_scans_report(
    conn: sqlite3.Connection,
    *,
    time_filter: TimeFilter | None = None,
    limit: int | None = 100,
) -> list[dict[str, Any]]:
    """Query scan jobs and extract summary data.

    Args:
        conn: Database connection.
        time_filter: Time range filter.
        limit: Maximum rows to return (None for no limit).

    Returns:
        List of scan row dictionaries.

    Raises:
        ValueError: If limit is negative or exceeds MAX_LIMIT.
    """
    _validate_limit(limit)
    query = """
        SELECT
            id,
            started_at,
            completed_at,
            status,
            summary_json
        FROM jobs
        WHERE job_type = 'scan'
    """
    params: list[Any] = []

    time_clause, time_params = _build_time_filter_clause(time_filter, "created_at")
    query += time_clause
    params.extend(time_params)

    query += " ORDER BY created_at DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    result = []
    for row in rows:
        duration_seconds = calculate_duration_seconds(row[1], row[2])
        summary = extract_scan_summary(row[4])

        report_row = ScanReportRow(
            scan_id=row[0][:8] if row[0] else "-",
            started_at=format_timestamp_local(row[1]),
            completed_at=format_timestamp_local(row[2]),
            duration=format_duration(duration_seconds),
            files_scanned=summary["files_scanned"],
            files_new=summary["files_new"],
            files_changed=summary["files_changed"],
            status=row[3] or "-",
        )
        result.append(report_row.to_dict())

    return result


def get_transcodes_report(
    conn: sqlite3.Connection,
    *,
    codec: str | None = None,
    time_filter: TimeFilter | None = None,
    limit: int | None = 100,
) -> list[dict[str, Any]]:
    """Query transcode jobs with codec filtering.

    Args:
        conn: Database connection.
        codec: Filter by target codec (case-insensitive).
        time_filter: Time range filter.
        limit: Maximum rows to return (None for no limit).

    Returns:
        List of transcode row dictionaries.

    Raises:
        ValueError: If limit is negative or exceeds MAX_LIMIT.
    """
    _validate_limit(limit)
    query = """
        SELECT
            j.id,
            j.file_path,
            j.started_at,
            j.completed_at,
            j.status,
            j.policy_json,
            f.size_bytes as original_size
        FROM jobs j
        LEFT JOIN files f ON j.file_id = f.id
        WHERE j.job_type = 'transcode'
    """
    params: list[Any] = []

    time_clause, time_params = _build_time_filter_clause(time_filter, "j.created_at")
    query += time_clause
    params.extend(time_params)

    query += " ORDER BY j.created_at DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    result = []
    for row in rows:
        # Extract codec info from policy_json
        source_codec = "-"
        target_codec = "-"
        if row[5]:
            try:
                policy_data = json.loads(row[5])
                source_codec = policy_data.get("source_codec", "-")
                target_codec = policy_data.get(
                    "target_codec", policy_data.get("codec", "-")
                )
            except (json.JSONDecodeError, TypeError):
                pass

        # Filter by codec if specified
        if codec and codec.casefold() != target_codec.casefold():
            continue

        duration_seconds = calculate_duration_seconds(row[2], row[3])

        # Calculate size change (placeholder - would need output file size)
        size_change = "N/A"

        report_row = TranscodeReportRow(
            job_id=row[0][:8] if row[0] else "-",
            file_path=row[1] or "-",
            source_codec=source_codec,
            target_codec=target_codec,
            started_at=format_timestamp_local(row[2]),
            completed_at=format_timestamp_local(row[3]),
            duration=format_duration(duration_seconds),
            status=row[4] or "-",
            size_change=size_change,
        )
        result.append(report_row.to_dict())

    return result


def get_policy_apply_report(
    conn: sqlite3.Connection,
    *,
    policy_name: str | None = None,
    verbose: bool = False,
    time_filter: TimeFilter | None = None,
    limit: int | None = 100,
) -> list[dict[str, Any]]:
    """Query policy apply jobs/operations.

    Args:
        conn: Database connection.
        policy_name: Filter by policy name.
        verbose: If True, return per-file details instead of summary.
        time_filter: Time range filter.
        limit: Maximum rows to return (None for no limit).

    Returns:
        List of policy apply row dictionaries.

    Raises:
        ValueError: If limit is negative or exceeds MAX_LIMIT.
    """
    _validate_limit(limit)
    query = """
        SELECT
            id,
            policy_name,
            files_affected_json,
            status,
            started_at,
            completed_at
        FROM jobs
        WHERE job_type = 'apply'
    """
    params: list[Any] = []

    if policy_name:
        query += " AND policy_name LIKE ? ESCAPE '\\'"
        # Escape SQL wildcards to prevent injection
        escaped = policy_name.replace("\\", "\\\\")
        escaped = escaped.replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")

    time_clause, time_params = _build_time_filter_clause(time_filter, "created_at")
    query += time_clause
    params.extend(time_params)

    query += " ORDER BY created_at DESC"

    if limit and not verbose:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    if verbose:
        # Return per-file details
        result = []
        for row in rows:
            files_affected = []
            if row[2]:
                try:
                    files_affected = json.loads(row[2])
                except (json.JSONDecodeError, TypeError):
                    pass

            for file_info in files_affected:
                if isinstance(file_info, dict):
                    file_path = file_info.get("path", file_info.get("file_path", "-"))
                    changes = file_info.get("changes", file_info.get("actions", "-"))
                    if isinstance(changes, list):
                        changes = ", ".join(str(c) for c in changes)
                else:
                    file_path = str(file_info)
                    changes = "-"

                detail_row = PolicyApplyDetailRow(
                    file_path=file_path,
                    changes=str(changes),
                )
                result.append(detail_row.to_dict())

                if limit and len(result) >= limit:
                    return result

        return result

    # Return summary
    result = []
    for row in rows:
        files_affected_count = 0
        metadata_changes = 0
        heavy_changes = 0

        if row[2]:
            try:
                files_data = json.loads(row[2])
                if isinstance(files_data, list):
                    files_affected_count = len(files_data)
                    for f in files_data:
                        if isinstance(f, dict):
                            actions = f.get("actions", [])
                            if isinstance(actions, list):
                                for action in actions:
                                    if isinstance(action, dict):
                                        action_type = action.get("type", "")
                                    else:
                                        action_type = str(action)
                                    if action_type in ("transcode", "move", "remux"):
                                        heavy_changes += 1
                                    else:
                                        metadata_changes += 1
            except (json.JSONDecodeError, TypeError):
                pass

        report_row = PolicyApplyReportRow(
            operation_id=row[0][:8] if row[0] else "-",
            policy_name=row[1] or "-",
            files_affected=files_affected_count,
            metadata_changes=metadata_changes,
            heavy_changes=heavy_changes,
            status=row[3] or "-",
            started_at=format_timestamp_local(row[4]),
        )
        result.append(report_row.to_dict())

    return result
