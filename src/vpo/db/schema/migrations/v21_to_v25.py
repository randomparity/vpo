"""Database migrations from schema version 21 to 25.

This module contains migrations for enhanced statistics features:
- v20→v21: Add encoder_type column for hardware encoder tracking (Issue #264)
- v21→v22: Add compound index on processing_stats(file_id, processed_at DESC)
- v22→v23: Unify CLI/daemon job tracking with origin, batch_id, job_id columns
- v23→v24: Add indexes on jobs(origin) and jobs(batch_id)
- v24→v25: Add FK constraint on processing_stats(job_id) -> jobs(id)
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


def migrate_v23_to_v24(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 23 to version 24.

    Adds indexes on jobs(origin) and jobs(batch_id) to optimize queries
    filtering by job origin or batch grouping.

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Add index on origin column
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_origin ON jobs(origin)")

    # Add index on batch_id column
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id)")

    # Update schema version to 24
    conn.execute("UPDATE _meta SET value = '24' WHERE key = 'schema_version'")
    conn.commit()


def migrate_v24_to_v25(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 24 to version 25.

    Adds FK constraint on processing_stats(job_id) referencing jobs(id).
    When a job is deleted, the job_id in processing_stats is set to NULL.

    SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so this migration
    recreates the processing_stats table with the FK constraint.

    Steps:
    1. Create new table with FK constraint
    2. Copy data (setting job_id to NULL for orphaned references)
    3. Drop old table
    4. Rename new table
    5. Recreate indexes

    This migration is idempotent - checks for FK before proceeding.

    Args:
        conn: An open database connection.
    """
    # Check if FK constraint already exists by examining table SQL
    cursor = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='processing_stats'"
    )
    row = cursor.fetchone()
    if row and "REFERENCES jobs(id)" in (row[0] or ""):
        # FK already exists, just update version
        conn.execute("UPDATE _meta SET value = '25' WHERE key = 'schema_version'")
        conn.commit()
        return

    # Create new table with FK constraint
    conn.execute("""
        CREATE TABLE processing_stats_new (
            id TEXT PRIMARY KEY,
            file_id INTEGER NOT NULL,
            processed_at TEXT NOT NULL,
            policy_name TEXT NOT NULL,
            size_before INTEGER NOT NULL,
            size_after INTEGER NOT NULL,
            size_change INTEGER NOT NULL,
            audio_tracks_before INTEGER NOT NULL DEFAULT 0,
            subtitle_tracks_before INTEGER NOT NULL DEFAULT 0,
            attachments_before INTEGER NOT NULL DEFAULT 0,
            audio_tracks_after INTEGER NOT NULL DEFAULT 0,
            subtitle_tracks_after INTEGER NOT NULL DEFAULT 0,
            attachments_after INTEGER NOT NULL DEFAULT 0,
            audio_tracks_removed INTEGER NOT NULL DEFAULT 0,
            subtitle_tracks_removed INTEGER NOT NULL DEFAULT 0,
            attachments_removed INTEGER NOT NULL DEFAULT 0,
            duration_seconds REAL NOT NULL,
            phases_completed INTEGER NOT NULL DEFAULT 0,
            phases_total INTEGER NOT NULL DEFAULT 0,
            total_changes INTEGER NOT NULL DEFAULT 0,
            video_source_codec TEXT,
            video_target_codec TEXT,
            video_transcode_skipped INTEGER NOT NULL DEFAULT 0,
            video_skip_reason TEXT,
            audio_tracks_transcoded INTEGER NOT NULL DEFAULT 0,
            audio_tracks_preserved INTEGER NOT NULL DEFAULT 0,
            hash_before TEXT,
            hash_after TEXT,
            success INTEGER NOT NULL,
            error_message TEXT,
            encoder_type TEXT,
            job_id TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
        )
    """)

    # Copy data, setting job_id to NULL if it references a non-existent job
    conn.execute("""
        INSERT INTO processing_stats_new
        SELECT
            ps.id, ps.file_id, ps.processed_at, ps.policy_name,
            ps.size_before, ps.size_after, ps.size_change,
            ps.audio_tracks_before, ps.subtitle_tracks_before, ps.attachments_before,
            ps.audio_tracks_after, ps.subtitle_tracks_after, ps.attachments_after,
            ps.audio_tracks_removed, ps.subtitle_tracks_removed, ps.attachments_removed,
            ps.duration_seconds, ps.phases_completed, ps.phases_total, ps.total_changes,
            ps.video_source_codec, ps.video_target_codec,
            ps.video_transcode_skipped, ps.video_skip_reason,
            ps.audio_tracks_transcoded, ps.audio_tracks_preserved,
            ps.hash_before, ps.hash_after,
            ps.success, ps.error_message, ps.encoder_type,
            CASE WHEN j.id IS NOT NULL THEN ps.job_id ELSE NULL END
        FROM processing_stats ps
        LEFT JOIN jobs j ON ps.job_id = j.id
    """)

    # Drop old table
    conn.execute("DROP TABLE processing_stats")

    # Rename new table
    conn.execute("ALTER TABLE processing_stats_new RENAME TO processing_stats")

    # Recreate indexes
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_file ON processing_stats(file_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stats_job ON processing_stats(job_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_policy ON processing_stats(policy_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_time "
        "ON processing_stats(processed_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_success ON processing_stats(success)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_file_time "
        "ON processing_stats(file_id, processed_at DESC)"
    )

    # Update schema version
    conn.execute("UPDATE _meta SET value = '25' WHERE key = 'schema_version'")
    conn.commit()
