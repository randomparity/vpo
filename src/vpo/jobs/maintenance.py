"""Job maintenance operations (purge, cleanup).

This module consolidates job maintenance functions that were previously
scattered across worker.py and tracking.py.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

from vpo.db.queries import delete_old_jobs


def purge_old_jobs(
    conn: sqlite3.Connection,
    retention_days: int,
    *,
    auto_purge: bool = True,
) -> int:
    """Purge old completed/failed/cancelled jobs.

    Single implementation for all job purge operations. Consolidates
    worker._purge_old_jobs() and tracking.maybe_purge_old_jobs().

    Args:
        conn: Database connection.
        retention_days: Days to retain jobs before purging.
        auto_purge: If False, returns 0 without purging.

    Returns:
        Number of jobs deleted.
    """
    if not auto_purge:
        return 0

    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

    return delete_old_jobs(conn, cutoff)
