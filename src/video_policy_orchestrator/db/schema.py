"""Database schema management for Video Policy Orchestrator."""

import sqlite3

SCHEMA_VERSION = 5

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS _meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Main files table
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    directory TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at TEXT NOT NULL,  -- ISO 8601 UTC timestamp
    content_hash TEXT,
    container_format TEXT,
    scanned_at TEXT NOT NULL,   -- ISO 8601 UTC timestamp
    scan_status TEXT NOT NULL DEFAULT 'pending',
    scan_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_directory ON files(directory);
CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
CREATE INDEX IF NOT EXISTS idx_files_content_hash ON files(content_hash);

-- Tracks table (one-to-many with files)
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    track_index INTEGER NOT NULL,
    track_type TEXT NOT NULL,
    codec TEXT,
    language TEXT,
    title TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    is_forced INTEGER NOT NULL DEFAULT 0,
    -- New columns (003-media-introspection)
    channels INTEGER,
    channel_layout TEXT,
    width INTEGER,
    height INTEGER,
    frame_rate TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    UNIQUE(file_id, track_index)
);

CREATE INDEX IF NOT EXISTS idx_tracks_file_id ON tracks(file_id);
CREATE INDEX IF NOT EXISTS idx_tracks_type ON tracks(track_type);
CREATE INDEX IF NOT EXISTS idx_tracks_language ON tracks(language);

-- Operations table (policy operation audit log)
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
        status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'ROLLED_BACK')
    )
);

CREATE INDEX IF NOT EXISTS idx_operations_file_id ON operations(file_id);
CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_started_at ON operations(started_at);

-- Policies table (future-ready)
CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    definition TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Plugin acknowledgments table (005-plugin-architecture)
CREATE TABLE IF NOT EXISTS plugin_acknowledgments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name TEXT NOT NULL,
    plugin_hash TEXT NOT NULL,
    acknowledged_at TEXT NOT NULL,  -- ISO-8601 UTC
    acknowledged_by TEXT,
    UNIQUE(plugin_name, plugin_hash)
);

CREATE INDEX IF NOT EXISTS idx_plugin_ack_name
    ON plugin_acknowledgments(plugin_name);

-- Jobs table (006-transcode-pipelines)
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
CREATE INDEX IF NOT EXISTS idx_jobs_priority_created ON jobs(priority, created_at);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the database schema if it doesn't exist.

    Args:
        conn: An open database connection.
    """
    conn.executescript(SCHEMA_SQL)

    # Set schema version if not already set
    conn.execute(
        "INSERT OR IGNORE INTO _meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int | None:
    """Get the current schema version from the database.

    Args:
        conn: An open database connection.

    Returns:
        The schema version number, or None if not set.
    """
    try:
        cursor = conn.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        row = cursor.fetchone()
        return int(row[0]) if row else None
    except sqlite3.OperationalError:
        # Table doesn't exist
        return None


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

    # Whitelist of allowed columns with their types for validation
    # This prevents SQL injection through column names
    ALLOWED_COLUMNS: dict[str, str] = {
        "channels": "INTEGER",
        "channel_layout": "TEXT",
        "width": "INTEGER",
        "height": "INTEGER",
        "frame_rate": "TEXT",
    }

    # Define new columns to add (must be in whitelist)
    new_columns = [
        ("channels", "INTEGER"),
        ("channel_layout", "TEXT"),
        ("width", "INTEGER"),
        ("height", "INTEGER"),
        ("frame_rate", "TEXT"),
    ]

    # Add missing columns with validation
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            # Validate column name and type against whitelist
            if col_name not in ALLOWED_COLUMNS:
                raise ValueError(f"Unexpected column name in migration: {col_name}")
            if ALLOWED_COLUMNS[col_name] != col_type:
                raise ValueError(
                    f"Type mismatch for column {col_name}: "
                    f"expected {ALLOWED_COLUMNS[col_name]}, got {col_type}"
                )
            # Use quoted identifier for safety
            conn.execute(f'ALTER TABLE tracks ADD COLUMN "{col_name}" {col_type}')

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


def initialize_database(conn: sqlite3.Connection) -> None:
    """Initialize the database with schema, creating tables if needed.

    Args:
        conn: An open database connection.
    """
    current_version = get_schema_version(conn)

    if current_version is None:
        create_schema(conn)
    elif current_version < SCHEMA_VERSION:
        # Run migrations sequentially
        if current_version == 1:
            migrate_v1_to_v2(conn)
            current_version = 2
        if current_version == 2:
            migrate_v2_to_v3(conn)
            current_version = 3
        if current_version == 3:
            migrate_v3_to_v4(conn)
            current_version = 4
        if current_version == 4:
            migrate_v4_to_v5(conn)
