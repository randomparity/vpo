"""Database migrations from schema version 16 to 20.

This module contains migrations for stats and classification features:
- v15→v16: Expanded track_type constraint (music/sfx/non_speech)
- v16→v17: Plugin metadata column
- v17→v18: Processing statistics tables
- v18→v19: Track classification table
- v19→v20: Jobs priority constraint
"""

import sqlite3


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


def migrate_v18_to_v19(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 18 to version 19.

    Adds track_classification_results table for audio track classification
    (044-audio-track-classification):
    - Stores original/dubbed and commentary status for audio tracks
    - Includes confidence score and detection method
    - Optional acoustic profile JSON for detailed analysis data

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if track_classification_results table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='track_classification_results'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS track_classification_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                original_dubbed_status TEXT NOT NULL,
                commentary_status TEXT NOT NULL,
                confidence REAL NOT NULL,
                detection_method TEXT NOT NULL,
                acoustic_profile_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                CONSTRAINT valid_confidence CHECK (
                    confidence >= 0.0 AND confidence <= 1.0
                ),
                CONSTRAINT valid_od_status CHECK (
                    original_dubbed_status IN ('original', 'dubbed', 'unknown')
                ),
                CONSTRAINT valid_commentary_status CHECK (
                    commentary_status IN ('commentary', 'main', 'unknown')
                ),
                CONSTRAINT valid_method CHECK (
                    detection_method IN ('metadata', 'acoustic', 'combined', 'position')
                )
            );

            CREATE INDEX IF NOT EXISTS idx_classification_track
                ON track_classification_results(track_id);
            CREATE INDEX IF NOT EXISTS idx_classification_hash
                ON track_classification_results(file_hash);
            CREATE INDEX IF NOT EXISTS idx_classification_od_status
                ON track_classification_results(original_dubbed_status);
        """)

    # Update schema version to 19
    conn.execute(
        "UPDATE _meta SET value = '19' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v19_to_v20(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 19 to version 20.

    Adds CHECK constraints for numeric fields to improve data integrity:
    - jobs.priority: 0-1000 range (addresses potential invalid priority values)

    SQLite doesn't allow altering CHECK constraints, so we must recreate the
    jobs table. This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if jobs table already has the valid_priority constraint
    cursor = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
    )
    row = cursor.fetchone()
    if row and "valid_priority" in row[0]:
        # Constraint already exists, just update version
        conn.execute(
            "UPDATE _meta SET value = '20' WHERE key = 'schema_version'",
        )
        conn.commit()
        return

    # Recreate jobs table with valid_priority constraint
    conn.executescript("""
        -- Create new table with valid_priority constraint
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
            ),
            CONSTRAINT valid_priority CHECK (
                priority >= 0 AND priority <= 1000
            )
        );

        -- Copy data from old table, clamping any out-of-range priority values
        INSERT INTO jobs_new (
            id, file_id, file_path, job_type, status, priority,
            policy_name, policy_json, progress_percent, progress_json,
            created_at, started_at, completed_at,
            worker_pid, worker_heartbeat, output_path, backup_path, error_message,
            files_affected_json, summary_json, log_path
        )
        SELECT
            id, file_id, file_path, job_type, status,
            CASE
                WHEN priority < 0 THEN 0
                WHEN priority > 1000 THEN 1000
                ELSE priority
            END,
            policy_name, policy_json, progress_percent, progress_json,
            created_at, started_at, completed_at,
            worker_pid, worker_heartbeat, output_path, backup_path, error_message,
            files_affected_json, summary_json, log_path
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
        CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type);
    """)

    # Update schema version to 20
    conn.execute(
        "UPDATE _meta SET value = '20' WHERE key = 'schema_version'",
    )
    conn.commit()
