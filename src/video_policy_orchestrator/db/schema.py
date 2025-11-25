"""Database schema management for Video Policy Orchestrator."""

import sqlite3

SCHEMA_VERSION = 12

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
    scan_error TEXT,
    job_id TEXT  -- Links file to scan job that discovered/updated it
);

CREATE INDEX IF NOT EXISTS idx_files_directory ON files(directory);
CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
CREATE INDEX IF NOT EXISTS idx_files_content_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_job_id ON files(job_id);
CREATE INDEX IF NOT EXISTS idx_files_status_scanned
    ON files(scan_status, scanned_at DESC);

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

-- Jobs table (006-transcode-pipelines, updated 008-operational-ux, 016-job-detail-view)
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    file_id INTEGER,  -- FK to files.id (NULL for scan jobs)
    file_path TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 100,

    -- Policy
    policy_name TEXT,
    policy_json TEXT,  -- Serialized settings (NULL for scan jobs)

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

    -- Extended fields (008-operational-ux)
    files_affected_json TEXT,
    summary_json TEXT,

    -- Log file reference (016-job-detail-view)
    log_path TEXT,

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

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_priority_created ON jobs(priority, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type);

-- Transcription results table (007-audio-transcription)
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

-- Plans table (026-plans-list-view)
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    file_id INTEGER,
    file_path TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    job_id TEXT,
    actions_json TEXT NOT NULL,
    action_count INTEGER NOT NULL,
    requires_remux INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL,
    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'approved', 'rejected', 'applied', 'canceled')
    ),
    CONSTRAINT valid_action_count CHECK (action_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
CREATE INDEX IF NOT EXISTS idx_plans_created_at ON plans(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_plans_file_id ON plans(file_id);
CREATE INDEX IF NOT EXISTS idx_plans_policy_name ON plans(policy_name);
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
    # Commit required: executescript() above commits implicitly, and this
    # INSERT starts a new implicit transaction that must be committed.
    # Without this commit, the connection remains in a transaction which
    # breaks code that tries to start its own transaction (e.g., claim_next_job).
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


def migrate_v10_to_v11(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 10 to version 11.

    Normalizes all language codes to ISO 639-2/B standard:
    - tracks.language: Converts ISO 639-1 (2-letter) and ISO 639-2/T codes
      to ISO 639-2/B (3-letter bibliographic) codes
    - transcription_results.detected_language: Same normalization

    Examples of conversions:
    - "de" -> "ger" (ISO 639-1 to 639-2/B)
    - "deu" -> "ger" (ISO 639-2/T to 639-2/B)
    - "en" -> "eng"
    - "eng" -> "eng" (already 639-2/B, unchanged)

    This migration is idempotent - safe to run multiple times.
    Uses an exclusive transaction for atomicity - all changes succeed or
    all are rolled back on error.

    Args:
        conn: An open database connection.
    """
    import logging

    from video_policy_orchestrator.language import normalize_language

    logger = logging.getLogger(__name__)

    # Start exclusive transaction for atomicity
    conn.execute("BEGIN EXCLUSIVE")
    try:
        # Normalize language codes in tracks table
        cursor = conn.execute(
            "SELECT DISTINCT language FROM tracks WHERE language IS NOT NULL"
        )
        track_languages = [row[0] for row in cursor.fetchall()]

        normalized_count = 0
        for lang in track_languages:
            normalized = normalize_language(lang, warn_on_conversion=False)
            if normalized != lang:
                # Skip unrecognized codes that would become "und"
                if normalized == "und" and lang.lower().strip() not in ("", "und"):
                    logger.warning(
                        "Migration v10→v11: Skipping unrecognized language code '%s' "
                        "(would become 'und')",
                        lang,
                    )
                    continue

                conn.execute(
                    "UPDATE tracks SET language = ? WHERE language = ?",
                    (normalized, lang),
                )
                logger.info(
                    "Migration v10→v11: Normalized track language '%s' -> '%s'",
                    lang,
                    normalized,
                )
                normalized_count += 1

        # Normalize language codes in transcription_results table
        cursor = conn.execute(
            "SELECT DISTINCT detected_language FROM transcription_results "
            "WHERE detected_language IS NOT NULL"
        )
        transcription_languages = [row[0] for row in cursor.fetchall()]

        for lang in transcription_languages:
            normalized = normalize_language(lang, warn_on_conversion=False)
            if normalized != lang:
                # Skip unrecognized codes that would become "und"
                if normalized == "und" and lang.lower().strip() not in ("", "und"):
                    logger.warning(
                        "Migration v10→v11: Skipping unrecognized language code '%s' "
                        "(would become 'und')",
                        lang,
                    )
                    continue

                conn.execute(
                    "UPDATE transcription_results SET detected_language = ? "
                    "WHERE detected_language = ?",
                    (normalized, lang),
                )
                logger.info(
                    "Migration v10→v11: Normalized transcription language '%s' -> '%s'",
                    lang,
                    normalized,
                )
                normalized_count += 1

        if normalized_count > 0:
            logger.info(
                "Migration v10→v11: Normalized %d distinct language codes",
                normalized_count,
            )

        # Update schema version to 11
        conn.execute(
            "UPDATE _meta SET value = '11' WHERE key = 'schema_version'",
        )

        # Commit transaction
        conn.execute("COMMIT")

    except Exception as e:
        # Rollback on any error
        conn.execute("ROLLBACK")
        logger.error("Migration v10→v11 failed, rolling back: %s", e)
        raise


def migrate_v11_to_v12(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 11 to version 12.

    Adds plans table for the approval workflow (026-plans-list-view):
    - Stores planned changes awaiting operator approval
    - Tracks status through pending → approved/rejected → applied/canceled
    - Foreign key to files with ON DELETE SET NULL for deleted file handling
    - Indexes for common queries: status, created_at, file_id, policy_name

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='plans'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                file_id INTEGER,
                file_path TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                policy_version INTEGER NOT NULL,
                job_id TEXT,
                actions_json TEXT NOT NULL,
                action_count INTEGER NOT NULL,
                requires_remux INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL,
                CONSTRAINT valid_status CHECK (
                    status IN ('pending', 'approved', 'rejected', 'applied', 'canceled')
                ),
                CONSTRAINT valid_action_count CHECK (action_count >= 0)
            );

            CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
            CREATE INDEX IF NOT EXISTS idx_plans_created_at ON plans(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_plans_file_id ON plans(file_id);
            CREATE INDEX IF NOT EXISTS idx_plans_policy_name ON plans(policy_name);
        """)

    # Update schema version to 12
    conn.execute(
        "UPDATE _meta SET value = '12' WHERE key = 'schema_version'",
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
            current_version = 5
        if current_version == 5:
            migrate_v5_to_v6(conn)
            current_version = 6
        if current_version == 6:
            migrate_v6_to_v7(conn)
            current_version = 7
        if current_version == 7:
            migrate_v7_to_v8(conn)
            current_version = 8
        if current_version == 8:
            migrate_v8_to_v9(conn)
            current_version = 9
        if current_version == 9:
            migrate_v9_to_v10(conn)
            current_version = 10
        if current_version == 10:
            migrate_v10_to_v11(conn)
            current_version = 11
        if current_version == 11:
            migrate_v11_to_v12(conn)
