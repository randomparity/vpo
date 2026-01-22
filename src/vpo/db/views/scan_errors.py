"""Scan job error view query functions."""

import sqlite3

from ..types import ScanErrorView
from .helpers import _clamp_limit


def get_scan_errors_for_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    limit: int | None = None,
) -> list[ScanErrorView] | None:
    """Get files with scan errors for a specific job.

    Returns files that failed to scan during a scan job. Used by the
    job errors API endpoint to display detailed error information.

    Args:
        conn: Database connection.
        job_id: UUID of the scan job.
        limit: Maximum errors to return.

    Returns:
        List of ScanErrorView objects if job exists and is a scan job,
        or None if job not found or is not a scan job.
    """
    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

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
        LIMIT ?
        """,
        (job_id, limit),
    )
    return [
        ScanErrorView(
            path=row["path"],
            filename=row["filename"],
            error=row["scan_error"],
        )
        for row in cursor.fetchall()
    ]
