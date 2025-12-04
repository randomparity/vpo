"""Database schema management for Video Policy Orchestrator."""

import sqlite3

SCHEMA_VERSION = 18

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
    job_id TEXT,  -- Links file to scan job that discovered/updated it
    -- JSON: plugin-provided enrichment data keyed by plugin name.
    -- NOTE: SQLite cannot index json_extract() predicates directly, so
    -- queries filtering by plugin name require full table scan. For large
    -- libraries (100K+ files), consider: (1) generated column for common
    -- plugin names, or (2) application-level caching. Current scale acceptable.
    plugin_metadata TEXT
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
    -- HDR color metadata (034-conditional-video-transcode)
    color_transfer TEXT,
    color_primaries TEXT,
    color_space TEXT,
    color_range TEXT,
    -- Track duration (035-multi-language-audio-detection)
    duration_seconds REAL,
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
        track_type IN ('main', 'commentary', 'alternate', 'music', 'sfx', 'non_speech')
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

-- Language analysis results table (035-multi-language-audio-detection)
CREATE TABLE IF NOT EXISTS language_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,
    file_hash TEXT NOT NULL,
    primary_language TEXT NOT NULL,
    primary_percentage REAL NOT NULL,
    classification TEXT NOT NULL,
    analysis_metadata TEXT,  -- JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    CONSTRAINT valid_percentage CHECK (
        primary_percentage >= 0.0 AND primary_percentage <= 1.0
    ),
    CONSTRAINT valid_classification CHECK (
        classification IN ('SINGLE_LANGUAGE', 'MULTI_LANGUAGE')
    )
);

CREATE INDEX IF NOT EXISTS idx_lang_analysis_track
    ON language_analysis_results(track_id);
CREATE INDEX IF NOT EXISTS idx_lang_analysis_hash
    ON language_analysis_results(file_hash);
CREATE INDEX IF NOT EXISTS idx_lang_analysis_classification
    ON language_analysis_results(classification);

-- Language segments table (035-multi-language-audio-detection)
CREATE TABLE IF NOT EXISTS language_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    language_code TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    confidence REAL NOT NULL,
    FOREIGN KEY (analysis_id)
        REFERENCES language_analysis_results(id) ON DELETE CASCADE,
    CONSTRAINT valid_times CHECK (end_time > start_time),
    CONSTRAINT valid_confidence CHECK (
        confidence >= 0.0 AND confidence <= 1.0
    )
);

CREATE INDEX IF NOT EXISTS idx_lang_segments_analysis
    ON language_segments(analysis_id);
CREATE INDEX IF NOT EXISTS idx_lang_segments_language
    ON language_segments(language_code);

-- Processing statistics table (040-processing-stats)
CREATE TABLE IF NOT EXISTS processing_stats (
    id TEXT PRIMARY KEY,                    -- UUIDv4
    file_id INTEGER NOT NULL,               -- FK to files.id
    processed_at TEXT NOT NULL,             -- ISO-8601 UTC timestamp
    policy_name TEXT NOT NULL,              -- Name of policy used

    -- Size metrics
    size_before INTEGER NOT NULL,           -- File size (bytes) before
    size_after INTEGER NOT NULL,            -- File size (bytes) after
    size_change INTEGER NOT NULL,           -- Bytes saved (+) or added (-)

    -- Track counts (before)
    audio_tracks_before INTEGER NOT NULL DEFAULT 0,
    subtitle_tracks_before INTEGER NOT NULL DEFAULT 0,
    attachments_before INTEGER NOT NULL DEFAULT 0,

    -- Track counts (after)
    audio_tracks_after INTEGER NOT NULL DEFAULT 0,
    subtitle_tracks_after INTEGER NOT NULL DEFAULT 0,
    attachments_after INTEGER NOT NULL DEFAULT 0,

    -- Track counts (removed)
    audio_tracks_removed INTEGER NOT NULL DEFAULT 0,
    subtitle_tracks_removed INTEGER NOT NULL DEFAULT 0,
    attachments_removed INTEGER NOT NULL DEFAULT 0,

    -- Processing metrics
    duration_seconds REAL NOT NULL,         -- Total wall-clock time
    phases_completed INTEGER NOT NULL DEFAULT 0,
    phases_total INTEGER NOT NULL DEFAULT 0,
    total_changes INTEGER NOT NULL DEFAULT 0,

    -- Transcode info
    video_source_codec TEXT,                -- Original video codec
    video_target_codec TEXT,                -- Target codec (NULL if not transcoded)
    video_transcode_skipped INTEGER NOT NULL DEFAULT 0,  -- 1 if skipped
    video_skip_reason TEXT,                 -- Skip reason (codec_matches, etc.)
    audio_tracks_transcoded INTEGER NOT NULL DEFAULT 0,
    audio_tracks_preserved INTEGER NOT NULL DEFAULT 0,

    -- File integrity
    hash_before TEXT,                       -- File hash before processing
    hash_after TEXT,                        -- File hash after processing

    -- Status
    success INTEGER NOT NULL,               -- 1 = success, 0 = failure
    error_message TEXT,                     -- Error details if failed

    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stats_file ON processing_stats(file_id);
CREATE INDEX IF NOT EXISTS idx_stats_policy ON processing_stats(policy_name);
CREATE INDEX IF NOT EXISTS idx_stats_time ON processing_stats(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_stats_success ON processing_stats(success);

-- Action results table (040-processing-stats)
CREATE TABLE IF NOT EXISTS action_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stats_id TEXT NOT NULL,                 -- FK to processing_stats.id
    action_type TEXT NOT NULL,              -- set_default, remove, transcode, etc.
    track_type TEXT,                        -- audio, video, subtitle, attachment
    track_index INTEGER,                    -- Track index affected

    -- State tracking (JSON for flexibility)
    before_state TEXT,                      -- JSON: {"codec": "aac", ...}
    after_state TEXT,                       -- JSON: {"codec": "aac", ...}

    -- Result
    success INTEGER NOT NULL,               -- 1 = success, 0 = failure
    duration_ms INTEGER,                    -- Time taken for this action
    rule_reference TEXT,                    -- Policy rule that triggered this action
    message TEXT,                           -- Human-readable result message

    FOREIGN KEY (stats_id) REFERENCES processing_stats(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_action_stats_id ON action_results(stats_id);
CREATE INDEX IF NOT EXISTS idx_action_type ON action_results(action_type);
CREATE INDEX IF NOT EXISTS idx_action_track_type ON action_results(track_type);

-- Performance metrics table (040-processing-stats)
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stats_id TEXT NOT NULL,                 -- FK to processing_stats.id
    phase_name TEXT NOT NULL,               -- Phase name (analyze, transcode, etc.)

    -- Timing
    wall_time_seconds REAL NOT NULL,        -- Wall-clock duration

    -- I/O metrics
    bytes_read INTEGER,                     -- Bytes read from disk
    bytes_written INTEGER,                  -- Bytes written to disk

    -- FFmpeg-specific metrics (for transcode phases)
    encoding_fps REAL,                      -- Average encoding FPS
    encoding_bitrate INTEGER,               -- Average output bitrate (bits/sec)

    FOREIGN KEY (stats_id) REFERENCES processing_stats(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_perf_stats_id ON performance_metrics(stats_id);
CREATE INDEX IF NOT EXISTS idx_perf_phase ON performance_metrics(phase_name);
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


def migrate_v12_to_v13(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 12 to version 13.

    Adds HDR color metadata columns to the tracks table for the
    conditional video transcode feature (034-conditional-video-transcode):
    - color_transfer: Transfer characteristics (e.g., smpte2084, arib-std-b67)
    - color_primaries: Color primaries (e.g., bt2020)
    - color_space: Color space (e.g., bt2020nc)
    - color_range: Color range (e.g., tv, pc)

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if columns already exist by looking at table info
    cursor = conn.execute("PRAGMA table_info(tracks)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Add each HDR color metadata column if it doesn't exist
    # Using explicit statements instead of dynamic SQL for clarity
    if "color_transfer" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN color_transfer TEXT")
    if "color_primaries" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN color_primaries TEXT")
    if "color_space" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN color_space TEXT")
    if "color_range" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN color_range TEXT")

    # Update schema version to 13
    conn.execute(
        "UPDATE _meta SET value = '13' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v13_to_v14(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 13 to version 14.

    Adds language analysis tables for multi-language audio detection
    (035-multi-language-audio-detection):
    - language_analysis_results: Stores aggregated language analysis per track
    - language_segments: Stores individual language detections within tracks

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if language_analysis_results table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='language_analysis_results'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS language_analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                primary_language TEXT NOT NULL,
                primary_percentage REAL NOT NULL,
                classification TEXT NOT NULL,
                analysis_metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                CONSTRAINT valid_percentage CHECK (
                    primary_percentage >= 0.0 AND primary_percentage <= 1.0
                ),
                CONSTRAINT valid_classification CHECK (
                    classification IN ('SINGLE_LANGUAGE', 'MULTI_LANGUAGE')
                )
            );

            CREATE INDEX IF NOT EXISTS idx_lang_analysis_track
                ON language_analysis_results(track_id);
            CREATE INDEX IF NOT EXISTS idx_lang_analysis_hash
                ON language_analysis_results(file_hash);
            CREATE INDEX IF NOT EXISTS idx_lang_analysis_classification
                ON language_analysis_results(classification);
        """)

    # Check if language_segments table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='language_segments'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS language_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                language_code TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                confidence REAL NOT NULL,
                FOREIGN KEY (analysis_id)
                    REFERENCES language_analysis_results(id) ON DELETE CASCADE,
                CONSTRAINT valid_times CHECK (end_time > start_time),
                CONSTRAINT valid_confidence CHECK (
                    confidence >= 0.0 AND confidence <= 1.0
                )
            );

            CREATE INDEX IF NOT EXISTS idx_lang_segments_analysis
                ON language_segments(analysis_id);
            CREATE INDEX IF NOT EXISTS idx_lang_segments_language
                ON language_segments(language_code);
        """)

    # Update schema version to 14
    conn.execute(
        "UPDATE _meta SET value = '14' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v14_to_v15(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 14 to version 15.

    Adds duration_seconds column to tracks table for accurate track duration
    storage (035-multi-language-audio-detection).

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if column already exists (idempotent)
    cursor = conn.execute("PRAGMA table_info(tracks)")
    columns = {row[1] for row in cursor.fetchall()}
    if "duration_seconds" not in columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN duration_seconds REAL")

    # Update schema version to 15
    conn.execute(
        "UPDATE _meta SET value = '15' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v15_to_v16(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 15 to version 16.

    Expands track_type CHECK constraint in transcription_results table to
    include new audio track classifications (music/sfx detection feature):
    - music: Score, soundtrack (metadata-identified)
    - sfx: Sound effects, ambient (metadata-identified)
    - non_speech: Unlabeled track detected as no speech

    SQLite doesn't allow altering CHECK constraints, so we must recreate
    the table while preserving existing data.

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if migration is already done by attempting to insert a test value
    # that would only work with the expanded constraint
    try:
        # Test if 'music' is already a valid value
        cursor = conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='transcription_results'"
        )
        row = cursor.fetchone()
        if row and "'music'" in row[0]:
            # Constraint already includes new values, just update version
            conn.execute(
                "UPDATE _meta SET value = '16' WHERE key = 'schema_version'",
            )
            conn.commit()
            return
    except sqlite3.Error:
        pass

    # Recreate transcription_results table with expanded constraint
    conn.executescript("""
        -- Create new table with expanded track_type constraint
        CREATE TABLE IF NOT EXISTS transcription_results_new (
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
                track_type IN (
                    'main', 'commentary', 'alternate', 'music', 'sfx', 'non_speech'
                )
            )
        );

        -- Copy data from old table
        INSERT INTO transcription_results_new (
            id, track_id, detected_language, confidence_score, track_type,
            transcript_sample, plugin_name, created_at, updated_at
        )
        SELECT
            id, track_id, detected_language, confidence_score, track_type,
            transcript_sample, plugin_name, created_at, updated_at
        FROM transcription_results;

        -- Drop old table
        DROP TABLE transcription_results;

        -- Rename new table
        ALTER TABLE transcription_results_new RENAME TO transcription_results;

        -- Recreate indexes
        CREATE INDEX IF NOT EXISTS idx_transcription_track_id
            ON transcription_results(track_id);
        CREATE INDEX IF NOT EXISTS idx_transcription_language
            ON transcription_results(detected_language);
        CREATE INDEX IF NOT EXISTS idx_transcription_type
            ON transcription_results(track_type);
        CREATE INDEX IF NOT EXISTS idx_transcription_plugin
            ON transcription_results(plugin_name);
    """)

    # Update schema version to 16
    conn.execute(
        "UPDATE _meta SET value = '16' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v16_to_v17(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 16 to version 17.

    Adds plugin_metadata column to files table for storing plugin-provided
    enrichment data (039-plugin-metadata-policy):
    - plugin_metadata: JSON text storing plugin enrichment keyed by plugin name

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if column already exists (idempotent)
    cursor = conn.execute("PRAGMA table_info(files)")
    columns = {row[1] for row in cursor.fetchall()}
    if "plugin_metadata" not in columns:
        conn.execute("ALTER TABLE files ADD COLUMN plugin_metadata TEXT")

    # Update schema version to 17
    conn.execute(
        "UPDATE _meta SET value = '17' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v17_to_v18(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 17 to version 18.

    Adds processing statistics tables for metrics tracking (040-processing-stats):
    - processing_stats: Core statistics per processing run
    - action_results: Per-action details within a processing run
    - performance_metrics: Per-phase performance data

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if processing_stats table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='processing_stats'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS processing_stats (
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

                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_stats_file
                ON processing_stats(file_id);
            CREATE INDEX IF NOT EXISTS idx_stats_policy
                ON processing_stats(policy_name);
            CREATE INDEX IF NOT EXISTS idx_stats_time
                ON processing_stats(processed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_stats_success
                ON processing_stats(success);
        """)

    # Check if action_results table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='action_results'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS action_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stats_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                track_type TEXT,
                track_index INTEGER,

                before_state TEXT,
                after_state TEXT,

                success INTEGER NOT NULL,
                duration_ms INTEGER,
                rule_reference TEXT,
                message TEXT,

                FOREIGN KEY (stats_id) REFERENCES processing_stats(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_action_stats_id
                ON action_results(stats_id);
            CREATE INDEX IF NOT EXISTS idx_action_type
                ON action_results(action_type);
            CREATE INDEX IF NOT EXISTS idx_action_track_type
                ON action_results(track_type);
        """)

    # Check if performance_metrics table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='performance_metrics'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stats_id TEXT NOT NULL,
                phase_name TEXT NOT NULL,

                wall_time_seconds REAL NOT NULL,

                bytes_read INTEGER,
                bytes_written INTEGER,

                encoding_fps REAL,
                encoding_bitrate INTEGER,

                FOREIGN KEY (stats_id) REFERENCES processing_stats(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_perf_stats_id
                ON performance_metrics(stats_id);
            CREATE INDEX IF NOT EXISTS idx_perf_phase
                ON performance_metrics(phase_name);
        """)

    # Update schema version to 18
    conn.execute(
        "UPDATE _meta SET value = '18' WHERE key = 'schema_version'",
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
            current_version = 12
        if current_version == 12:
            migrate_v12_to_v13(conn)
            current_version = 13
        if current_version == 13:
            migrate_v13_to_v14(conn)
            current_version = 14
        if current_version == 14:
            migrate_v14_to_v15(conn)
            current_version = 15
        if current_version == 15:
            migrate_v15_to_v16(conn)
            current_version = 16
        if current_version == 16:
            migrate_v16_to_v17(conn)
            current_version = 17
        if current_version == 17:
            migrate_v17_to_v18(conn)
