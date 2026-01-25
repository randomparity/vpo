"""Database schema definition for Video Policy Orchestrator.

This module contains the schema DDL (Data Definition Language) and schema
creation logic. The schema defines all tables, indexes, and constraints
used by the VPO database.
"""

import sqlite3

SCHEMA_VERSION = 24

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

    -- Origin and batch tracking (unified CLI/daemon jobs)
    origin TEXT,      -- 'cli' or 'daemon' (NULL = legacy)
    batch_id TEXT,    -- UUID grouping CLI batch operations

    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    CONSTRAINT valid_status CHECK (
        status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
    ),
    CONSTRAINT valid_job_type CHECK (
        job_type IN ('transcode', 'move', 'scan', 'apply', 'process')
    ),
    CONSTRAINT valid_progress CHECK (
        progress_percent >= 0.0 AND progress_percent <= 100.0
    ),
    CONSTRAINT valid_priority CHECK (
        priority >= 0 AND priority <= 1000
    )
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_priority_created ON jobs(priority, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_origin ON jobs(origin);
CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id);

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

    -- Hardware encoder tracking (Issue #264)
    encoder_type TEXT,                      -- 'hardware', 'software', or NULL

    -- Job linkage (unified CLI/daemon tracking)
    job_id TEXT,                            -- FK to jobs.id (NULL = legacy)

    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stats_file ON processing_stats(file_id);
CREATE INDEX IF NOT EXISTS idx_stats_job ON processing_stats(job_id);
CREATE INDEX IF NOT EXISTS idx_stats_policy ON processing_stats(policy_name);
CREATE INDEX IF NOT EXISTS idx_stats_time ON processing_stats(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_stats_success ON processing_stats(success);
CREATE INDEX IF NOT EXISTS idx_stats_file_time
    ON processing_stats(file_id, processed_at DESC);

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

-- Track classification results table (044-audio-track-classification)
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
