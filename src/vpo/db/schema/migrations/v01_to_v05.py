"""Database migrations from schema version 1 to 5.

This module contains migrations for core schema evolution:
- v1→v2: Media introspection columns (tracks table)
- v2→v3: Policy engine operations table
- v3→v4: Plugin acknowledgments table
- v4→v5: Jobs table for transcoding queue
"""

import sqlite3


def migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 1 to version 2.

    Adds new columns to tracks table for media introspection:
    - channels, channel_layout (audio)
    - width, height, frame_rate (video)

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Get existing columns in tracks table
    cursor = conn.execute("PRAGMA table_info(tracks)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Add missing columns using explicit ALTER statements (no dynamic SQL)
    # Each column is added only if it doesn't already exist (idempotent)
    if "channels" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN channels INTEGER")
    if "channel_layout" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN channel_layout TEXT")
    if "width" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN width INTEGER")
    if "height" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN height INTEGER")
    if "frame_rate" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN frame_rate TEXT")

    # Update schema version to 2
    conn.execute(
        "UPDATE _meta SET value = '2' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 2 to version 3.

    Recreates the operations table with new schema for policy engine:
    - id: TEXT (UUID) instead of INTEGER
    - file_path, policy_name, policy_version, actions_json: new required fields
    - status: now uses OperationStatus enum values
    - started_at instead of created_at
    - error_message, backup_path: new optional fields
    - Adds indexes on file_id, status, started_at

    This migration drops the old operations table if it exists.

    Args:
        conn: An open database connection.
    """
    # Drop old operations table (was future-ready placeholder with different schema)
    conn.execute("DROP TABLE IF EXISTS operations")

    # Create new operations table with policy engine schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS operations (
            id TEXT PRIMARY KEY,
            file_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            policy_name TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            actions_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            error_message TEXT,
            backup_path TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
            CONSTRAINT valid_status CHECK (
                status IN (
                    'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'ROLLED_BACK'
                )
            )
        );

        CREATE INDEX IF NOT EXISTS idx_operations_file_id ON operations(file_id);
        CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
        CREATE INDEX IF NOT EXISTS idx_operations_started_at ON operations(started_at);
    """)

    # Update schema version to 3
    conn.execute(
        "UPDATE _meta SET value = '3' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 3 to version 4.

    Adds plugin_acknowledgments table for plugin system:
    - plugin_name, plugin_hash: identify plugin and version
    - acknowledged_at: UTC timestamp when user acknowledged
    - acknowledged_by: hostname/user identifier

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='plugin_acknowledgments'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS plugin_acknowledgments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                plugin_hash TEXT NOT NULL,
                acknowledged_at TEXT NOT NULL,
                acknowledged_by TEXT,
                UNIQUE(plugin_name, plugin_hash)
            );

            CREATE INDEX IF NOT EXISTS idx_plugin_ack_name
                ON plugin_acknowledgments(plugin_name);
        """)

    # Update schema version to 4
    conn.execute(
        "UPDATE _meta SET value = '4' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 4 to version 5.

    Adds jobs table for transcoding/movement queue:
    - Job tracking with status, progress, and worker info
    - Indexes for efficient queue operations

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                file_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 100,

                -- Policy
                policy_name TEXT,
                policy_json TEXT NOT NULL,

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

                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                CONSTRAINT valid_status CHECK (
                    status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
                ),
                CONSTRAINT valid_job_type CHECK (
                    job_type IN ('transcode', 'move')
                ),
                CONSTRAINT valid_progress CHECK (
                    progress_percent >= 0.0 AND progress_percent <= 100.0
                )
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
            CREATE INDEX IF NOT EXISTS idx_jobs_priority_created
                ON jobs(priority, created_at);
        """)

    # Update schema version to 5
    conn.execute(
        "UPDATE _meta SET value = '5' WHERE key = 'schema_version'",
    )
    conn.commit()
