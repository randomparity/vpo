"""Database migrations from schema version 21 to 25.

This module contains migrations for enhanced statistics features:
- v20→v21: Add encoder_type column for hardware encoder tracking (Issue #264)
- v21→v22: Add compound index on processing_stats(file_id, processed_at DESC)
- v22→v23: Unify CLI/daemon job tracking with origin, batch_id, job_id columns
"""

import sqlite3


def migrate_v20_to_v21(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 20 to version 21.

    Adds encoder_type column to processing_stats table for tracking whether
    hardware or software encoding was used (Issue #264):
    - encoder_type: 'hardware', 'software', or NULL if unknown

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if column already exists (idempotent)
    cursor = conn.execute("PRAGMA table_info(processing_stats)")
    columns = {row[1] for row in cursor.fetchall()}
    if "encoder_type" not in columns:
        conn.execute("ALTER TABLE processing_stats ADD COLUMN encoder_type TEXT")

    # Update schema version to 21
    conn.execute(
        "UPDATE _meta SET value = '21' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v21_to_v22(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 21 to version 22.

    Adds compound index on processing_stats(file_id, processed_at DESC) to
    optimize the transcode report query's correlated subquery (Issue #293).

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_file_time "
        "ON processing_stats(file_id, processed_at DESC)"
    )
    conn.execute("UPDATE _meta SET value = '22' WHERE key = 'schema_version'")
    conn.commit()


def migrate_v22_to_v23(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 22 to version 23.

    Unifies CLI and daemon job tracking by:
    - Adding origin column to jobs table ('cli' or 'daemon')
    - Adding batch_id column to jobs table (UUID for CLI batch grouping)
    - Adding job_id column to processing_stats table (FK to jobs.id)
    - Adding index on processing_stats(job_id)
    - Adding 'process' to valid_job_type constraint (handled by SQLite)

    Note: SQLite doesn't support modifying CHECK constraints, so the
    valid_job_type constraint is only enforced for new databases.
    Existing databases will allow 'process' job_type even without
    constraint modification.

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check and add columns to jobs table
    cursor = conn.execute("PRAGMA table_info(jobs)")
    job_columns = {row[1] for row in cursor.fetchall()}

    if "origin" not in job_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN origin TEXT")

    if "batch_id" not in job_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN batch_id TEXT")

    # Check and add job_id column to processing_stats table
    cursor = conn.execute("PRAGMA table_info(processing_stats)")
    stats_columns = {row[1] for row in cursor.fetchall()}

    if "job_id" not in stats_columns:
        conn.execute("ALTER TABLE processing_stats ADD COLUMN job_id TEXT")

    # Add index on job_id
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stats_job ON processing_stats(job_id)")

    # Update schema version to 23
    conn.execute("UPDATE _meta SET value = '23' WHERE key = 'schema_version'")
    conn.commit()
