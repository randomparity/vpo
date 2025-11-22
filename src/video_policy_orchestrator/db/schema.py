"""Database schema management for Video Policy Orchestrator."""

import sqlite3

SCHEMA_VERSION = 1

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
    modified_at TEXT NOT NULL,
    content_hash TEXT,
    container_format TEXT,
    scanned_at TEXT NOT NULL,
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
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    UNIQUE(file_id, track_index)
);

CREATE INDEX IF NOT EXISTS idx_tracks_file_id ON tracks(file_id);
CREATE INDEX IF NOT EXISTS idx_tracks_type ON tracks(track_type);
CREATE INDEX IF NOT EXISTS idx_tracks_language ON tracks(language);

-- Operations table (future-ready)
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER,
    operation_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    parameters TEXT,
    result TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL
);

-- Policies table (future-ready)
CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    definition TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
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
        cursor = conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None
    except sqlite3.OperationalError:
        # Table doesn't exist
        return None


def initialize_database(conn: sqlite3.Connection) -> None:
    """Initialize the database with schema, creating tables if needed.

    Args:
        conn: An open database connection.
    """
    current_version = get_schema_version(conn)

    if current_version is None:
        create_schema(conn)
    elif current_version < SCHEMA_VERSION:
        # Future: handle migrations
        create_schema(conn)
