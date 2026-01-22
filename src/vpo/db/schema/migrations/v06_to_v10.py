"""Database migrations from schema version 6 to 10.

This module contains migrations for jobs and indexing features:
- v5→v6: Transcription results table
- v6→v7: Jobs table expansion (scan/apply types, extended fields)
- v7→v8: Jobs log_path column
- v8→v9: Files job_id column
- v9→v10: Composite index for library view
"""

import sqlite3


def migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 5 to version 6.

    Adds transcription_results table for audio transcription feature:
    - Stores language detection and transcription results per track
    - Links to tracks via foreign key with cascade delete
    - Includes constraints for valid confidence and track type values

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.

    Raises:
        sqlite3.Error: If migration fails.
    """
    # Check if table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='transcription_results'"
    )
    if cursor.fetchone() is None:
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS transcription_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL UNIQUE,
                    detected_language TEXT,
                    confidence_score REAL NOT NULL,
                    track_type TEXT NOT NULL DEFAULT 'main',
                    transcript_sample TEXT,
                    plugin_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                    CONSTRAINT valid_confidence CHECK (
                        confidence_score >= 0.0 AND confidence_score <= 1.0
                    ),
                    CONSTRAINT valid_track_type CHECK (
                        track_type IN ('main', 'commentary', 'alternate')
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_transcription_track_id
                    ON transcription_results(track_id);
                CREATE INDEX IF NOT EXISTS idx_transcription_language
                    ON transcription_results(detected_language);
                CREATE INDEX IF NOT EXISTS idx_transcription_type
                    ON transcription_results(track_type);
                CREATE INDEX IF NOT EXISTS idx_transcription_plugin
                    ON transcription_results(plugin_name);
            """)

            # Validate table was created correctly
            cursor = conn.execute("PRAGMA table_info(transcription_results)")
            columns = {row[1] for row in cursor.fetchall()}
            required_columns = {
                "id",
                "track_id",
                "detected_language",
                "confidence_score",
                "track_type",
                "transcript_sample",
                "plugin_name",
                "created_at",
                "updated_at",
            }
            if not required_columns.issubset(columns):
                missing = required_columns - columns
                raise sqlite3.Error(
                    f"Migration v5→v6 failed: missing columns {missing}"
                )
        except sqlite3.Error:
            conn.rollback()
            raise

    # Update schema version to 6
    conn.execute(
        "UPDATE _meta SET value = '6' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v6_to_v7(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 6 to version 7.

    Extends jobs table for unified operation tracking (008-operational-ux):
    - Expands job_type CHECK constraint to include 'scan' and 'apply'
    - Adds files_affected_json for multi-file operations
    - Adds summary_json for job-specific results (e.g., scan counts)

    SQLite doesn't allow altering CHECK constraints, so we must recreate the table.
    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if jobs table needs migration by checking columns
    cursor = conn.execute("PRAGMA table_info(jobs)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # If new columns already exist, migration was already done
    if "summary_json" in existing_columns and "files_affected_json" in existing_columns:
        # Just update version and return
        conn.execute(
            "UPDATE _meta SET value = '7' WHERE key = 'schema_version'",
        )
        conn.commit()
        return

    # Recreate jobs table with expanded constraint and new columns
    conn.executescript("""
        -- Create new table with expanded job_type constraint
        CREATE TABLE IF NOT EXISTS jobs_new (
            id TEXT PRIMARY KEY,
            file_id INTEGER,
            file_path TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            priority INTEGER NOT NULL DEFAULT 100,

            -- Policy
            policy_name TEXT,
            policy_json TEXT,

            -- Progress
            progress_percent REAL NOT NULL DEFAULT 0.0,
            progress_json TEXT,

            -- Timing
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,

            -- Worker
            worker_pid INTEGER,
            worker_heartbeat TEXT,

            -- Results
            output_path TEXT,
            backup_path TEXT,
            error_message TEXT,

            -- New columns for 008-operational-ux
            files_affected_json TEXT,
            summary_json TEXT,

            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
            CONSTRAINT valid_status CHECK (
                status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
            ),
            CONSTRAINT valid_job_type CHECK (
                job_type IN ('transcode', 'move', 'scan', 'apply')
            ),
            CONSTRAINT valid_progress CHECK (
                progress_percent >= 0.0 AND progress_percent <= 100.0
            )
        );

        -- Copy data from old table
        INSERT INTO jobs_new (
            id, file_id, file_path, job_type, status, priority,
            policy_name, policy_json, progress_percent, progress_json,
            created_at, started_at, completed_at,
            worker_pid, worker_heartbeat, output_path, backup_path, error_message
        )
        SELECT
            id, file_id, file_path, job_type, status, priority,
            policy_name, policy_json, progress_percent, progress_json,
            created_at, started_at, completed_at,
            worker_pid, worker_heartbeat, output_path, backup_path, error_message
        FROM jobs;

        -- Drop old table
        DROP TABLE jobs;

        -- Rename new table
        ALTER TABLE jobs_new RENAME TO jobs;

        -- Recreate indexes
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_priority_created
            ON jobs(priority, created_at);
    """)

    # Update schema version to 7
    conn.execute(
        "UPDATE _meta SET value = '7' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v7_to_v8(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 7 to version 8.

    Adds log_path column to jobs table for job detail view:
    - log_path: Relative path to log file from VPO data directory

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check existing columns in jobs table
    cursor = conn.execute("PRAGMA table_info(jobs)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Add log_path column if it doesn't exist
    if "log_path" not in existing_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN log_path TEXT")

    # Update schema version to 8
    conn.execute(
        "UPDATE _meta SET value = '8' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v8_to_v9(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 8 to version 9.

    Adds job_id column to files table to link files to scan jobs:
    - job_id: TEXT (UUID of the scan job that discovered/updated the file)

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check existing columns in files table
    cursor = conn.execute("PRAGMA table_info(files)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Add job_id column if it doesn't exist
    if "job_id" not in existing_columns:
        conn.execute("ALTER TABLE files ADD COLUMN job_id TEXT")

    # Create index for job_id (idempotent)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_job_id ON files(job_id)")

    # Update schema version to 9
    conn.execute(
        "UPDATE _meta SET value = '9' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v9_to_v10(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 9 to version 10.

    Adds composite index for library view queries:
    - idx_files_status_scanned: (scan_status, scanned_at DESC)

    This index optimizes the library list view which filters by status
    and orders by scanned_at descending.

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Create composite index for library view queries (idempotent)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_files_status_scanned "
        "ON files(scan_status, scanned_at DESC)"
    )

    # Update schema version to 10
    conn.execute(
        "UPDATE _meta SET value = '10' WHERE key = 'schema_version'",
    )
    conn.commit()
