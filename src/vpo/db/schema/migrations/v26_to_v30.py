"""Database migrations from schema version 26 to 30.

This module contains migrations for missing file management features:
- v25→v26: Add 'prune' job type, create library_snapshots table
"""

import sqlite3


def migrate_v25_to_v26(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 25 to version 26.

    Adds:
    - 'prune' to valid_job_type CHECK constraint (requires table rebuild)
    - library_snapshots table for tracking library size trends

    The jobs table must be rebuilt because SQLite doesn't support ALTER
    TABLE to modify CHECK constraints.

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # --- Part 1: Rebuild jobs table with updated CHECK constraint ---

    # Check if 'prune' is already in the constraint
    cursor = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
    )
    row = cursor.fetchone()
    if row and "'prune'" in (row[0] or ""):
        # Constraint already includes 'prune', skip rebuild
        pass
    else:
        # Get current column info to preserve structure
        cursor = conn.execute("PRAGMA table_info(jobs)")
        columns = [r[1] for r in cursor.fetchall()]

        # Wrap rebuild in explicit transaction to prevent partial state
        # (e.g., crash between DROP and RENAME leaving no jobs table)
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Create new jobs table with updated constraint
            conn.execute("""
                CREATE TABLE jobs_new (
                    id TEXT PRIMARY KEY,
                    file_id INTEGER,
                    file_path TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 100,
                    policy_name TEXT,
                    policy_json TEXT,
                    progress_percent REAL NOT NULL DEFAULT 0.0,
                    progress_json TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error_message TEXT,
                    output_path TEXT,
                    summary_json TEXT,
                    worker_pid INTEGER,
                    worker_heartbeat TEXT,
                    backup_path TEXT,
                    files_affected_json TEXT,
                    log_path TEXT,
                    origin TEXT,
                    batch_id TEXT,

                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                    CONSTRAINT valid_status CHECK (
                        status IN (
                            'queued', 'running', 'completed',
                            'failed', 'cancelled'
                        )
                    ),
                    CONSTRAINT valid_job_type CHECK (
                        job_type IN (
                            'transcode', 'move', 'scan',
                            'apply', 'process', 'prune'
                        )
                    ),
                    CONSTRAINT valid_progress CHECK (
                        progress_percent >= 0.0 AND progress_percent <= 100.0
                    ),
                    CONSTRAINT valid_priority CHECK (
                        priority >= 0 AND priority <= 1000
                    )
                )
            """)

            # Build column list for copy (use only columns that exist in both)
            col_list = ", ".join(columns)
            conn.execute(
                f"INSERT INTO jobs_new ({col_list}) SELECT {col_list} FROM jobs"
            )

            # Drop old table and rename
            conn.execute("DROP TABLE jobs")
            conn.execute("ALTER TABLE jobs_new RENAME TO jobs")

            # Recreate indexes (canonical names from definition.py)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_priority_created "
                "ON jobs(priority, created_at)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_origin ON jobs(origin)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id)"
            )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # --- Part 2: Create library_snapshots table ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS library_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_at TEXT NOT NULL,
            total_files INTEGER NOT NULL,
            total_size_bytes INTEGER NOT NULL,
            missing_files INTEGER NOT NULL,
            error_files INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_library_snapshots_time "
        "ON library_snapshots(snapshot_at)"
    )

    # Update schema version
    conn.execute("UPDATE _meta SET value = '26' WHERE key = 'schema_version'")
    conn.commit()
