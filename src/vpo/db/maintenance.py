"""Database maintenance operations (VACUUM, integrity checks)."""

import logging
import sqlite3

from .types import (
    ForeignKeyViolation,
    IntegrityResult,
    OptimizeResult,
)

logger = logging.getLogger(__name__)


def run_integrity_check(conn: sqlite3.Connection) -> IntegrityResult:
    """Run SQLite integrity and foreign key checks.

    Executes PRAGMA integrity_check and PRAGMA foreign_key_check
    to verify database consistency.

    Args:
        conn: Database connection.

    Returns:
        IntegrityResult with check results.

    Raises:
        sqlite3.Error: If the database cannot be read.
    """
    try:
        # integrity_check returns rows with a single text column (position 0)
        integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
        integrity_errors = []
        integrity_ok = True

        for row in integrity_rows:
            msg = row[0]  # PRAGMA result: single text column
            if msg != "ok":
                integrity_ok = False
                integrity_errors.append(msg)

        # foreign_key_check returns (table, rowid, parent, fkid) per violation
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        foreign_key_errors = []
        foreign_key_ok = len(fk_rows) == 0

        for row in fk_rows:
            # PRAGMA columns: table(0), rowid(1), parent(2), fkid(3)
            foreign_key_errors.append(
                ForeignKeyViolation(
                    table=row[0],
                    rowid=row[1],
                    parent=row[2],
                    fkid=row[3],
                )
            )

        return IntegrityResult(
            integrity_ok=integrity_ok,
            integrity_errors=integrity_errors,
            foreign_key_ok=foreign_key_ok,
            foreign_key_errors=foreign_key_errors,
        )
    except sqlite3.Error:
        logger.exception("Integrity check failed")
        raise


def run_optimize(
    conn: sqlite3.Connection,
    *,
    dry_run: bool = False,
) -> OptimizeResult:
    """Run VACUUM and ANALYZE on the database.

    Rolls back any pending transactions before running VACUUM.
    In dry-run mode, reports current freelist count and estimated
    reclaimable space without making changes.

    Args:
        conn: Database connection.
        dry_run: If True, only estimate savings without making changes.

    Returns:
        OptimizeResult with before/after sizes.

    Raises:
        sqlite3.OperationalError: If database is locked by another process.
        sqlite3.Error: If a database error occurs.
    """
    try:
        # PRAGMA results: single integer column (position 0)
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        freelist_count = conn.execute("PRAGMA freelist_count").fetchone()[0]
        size_before = page_size * page_count

        if dry_run:
            estimated_savings = freelist_count * page_size
            return OptimizeResult(
                size_before=size_before,
                size_after=size_before - estimated_savings,
                space_saved=estimated_savings,
                freelist_pages=freelist_count,
                dry_run=True,
            )

        # Roll back any pending transactions before VACUUM —
        # committing unknown work is unsafe.
        if conn.in_transaction:
            logger.warning("Rolling back pending transaction before VACUUM")
            conn.rollback()

        # VACUUM reclaims free pages and defragments the database
        conn.execute("VACUUM")
        # ANALYZE updates query planner statistics
        conn.execute("ANALYZE")

        # Measure after
        page_count_after = conn.execute("PRAGMA page_count").fetchone()[0]
        size_after = page_size * page_count_after

        return OptimizeResult(
            size_before=size_before,
            size_after=size_after,
            space_saved=size_before - size_after,
            freelist_pages=freelist_count,
            dry_run=False,
        )
    except sqlite3.Error:
        logger.exception("Database optimization failed")
        raise
