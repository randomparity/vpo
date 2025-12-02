# Data Model: Processing Statistics and Metrics Tracking

**Feature**: 040-processing-stats
**Date**: 2025-12-01

## Overview

This document defines the data model for processing statistics, including database schema, dataclasses, and relationships.

## Entity Relationship Diagram

```
┌─────────────┐       ┌───────────────────┐       ┌──────────────────────┐
│   files     │       │ processing_stats  │       │   action_results     │
├─────────────┤       ├───────────────────┤       ├──────────────────────┤
│ id (PK)     │◄──┐   │ id (PK)           │◄──────│ id (PK)              │
│ path        │   │   │ file_id (FK)      │───┐   │ stats_id (FK)        │
│ size_bytes  │   │   │ processed_at      │   │   │ action_type          │
│ ...         │   │   │ policy_name       │   │   │ track_type           │
└─────────────┘   │   │ size_before       │   │   │ track_index          │
                  │   │ size_after        │   │   │ before_state (JSON)  │
                  │   │ size_change       │   │   │ after_state (JSON)   │
                  │   │ ...               │   │   │ success              │
                  │   └───────────────────┘   │   │ duration_ms          │
                  │             │             │   │ rule_reference       │
                  │             │             │   │ message              │
                  │             ▼             │   └──────────────────────┘
                  │   ┌───────────────────┐   │
                  │   │performance_metrics│   │
                  │   ├───────────────────┤   │
                  │   │ id (PK)           │   │
                  │   │ stats_id (FK)     │───┘
                  │   │ phase_name        │
                  │   │ wall_time_seconds │
                  │   │ bytes_read        │
                  │   │ bytes_written     │
                  │   │ encoding_fps      │
                  │   │ encoding_bitrate  │
                  │   └───────────────────┘
                  │
                  └─── 1:N relationship
```

## Database Tables

### processing_stats

Core statistics for each processing operation.

```sql
CREATE TABLE IF NOT EXISTS processing_stats (
    id TEXT PRIMARY KEY,                    -- UUIDv4
    file_id INTEGER NOT NULL,               -- FK to files.id
    processed_at TEXT NOT NULL,             -- ISO-8601 UTC timestamp
    policy_name TEXT NOT NULL,              -- Name of policy used

    -- Size metrics
    size_before INTEGER NOT NULL,           -- File size in bytes before processing
    size_after INTEGER NOT NULL,            -- File size in bytes after processing
    size_change INTEGER NOT NULL,           -- Bytes saved (positive) or added (negative)

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
    video_target_codec TEXT,                -- Target video codec (NULL if not transcoded)
    video_transcode_skipped INTEGER NOT NULL DEFAULT 0,  -- 1 if skipped due to skip_if
    video_skip_reason TEXT,                 -- Reason for skip (codec_matches, etc.)
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

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_stats_file_id ON processing_stats(file_id);
CREATE INDEX IF NOT EXISTS idx_stats_policy ON processing_stats(policy_name);
CREATE INDEX IF NOT EXISTS idx_stats_processed_at ON processing_stats(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_stats_success ON processing_stats(success);
```

### action_results

Per-action details within a processing operation.

```sql
CREATE TABLE IF NOT EXISTS action_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stats_id TEXT NOT NULL,                 -- FK to processing_stats.id
    action_type TEXT NOT NULL,              -- set_default, set_language, remove, transcode, etc.
    track_type TEXT,                        -- audio, video, subtitle, attachment
    track_index INTEGER,                    -- Track index affected

    -- State tracking (JSON for flexibility)
    before_state TEXT,                      -- JSON: {"codec": "aac", "language": "eng", ...}
    after_state TEXT,                       -- JSON: {"codec": "aac", "language": "jpn", ...}

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
```

### performance_metrics

Per-phase performance data.

```sql
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stats_id TEXT NOT NULL,                 -- FK to processing_stats.id
    phase_name TEXT NOT NULL,               -- Phase name (analyze, remux, transcode, etc.)

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
```

## Dataclass Definitions

### ProcessingStatsRecord

```python
@dataclass
class ProcessingStatsRecord:
    """Database record for processing_stats table."""

    id: str  # UUIDv4
    file_id: int
    processed_at: str  # ISO-8601 UTC
    policy_name: str

    # Size metrics
    size_before: int
    size_after: int
    size_change: int

    # Track counts (before)
    audio_tracks_before: int
    subtitle_tracks_before: int
    attachments_before: int

    # Track counts (after)
    audio_tracks_after: int
    subtitle_tracks_after: int
    attachments_after: int

    # Track counts (removed)
    audio_tracks_removed: int
    subtitle_tracks_removed: int
    attachments_removed: int

    # Processing metrics
    duration_seconds: float
    phases_completed: int
    phases_total: int
    total_changes: int

    # Transcode info
    video_source_codec: str | None
    video_target_codec: str | None
    video_transcode_skipped: bool
    video_skip_reason: str | None
    audio_tracks_transcoded: int
    audio_tracks_preserved: int

    # File integrity
    hash_before: str | None
    hash_after: str | None

    # Status
    success: bool
    error_message: str | None
```

### ActionResultRecord

```python
@dataclass
class ActionResultRecord:
    """Database record for action_results table."""

    id: int | None
    stats_id: str  # FK to processing_stats
    action_type: str  # set_default, set_language, remove, transcode, etc.
    track_type: str | None  # audio, video, subtitle, attachment
    track_index: int | None

    # State (JSON serialized)
    before_state: str | None  # JSON
    after_state: str | None   # JSON

    # Result
    success: bool
    duration_ms: int | None
    rule_reference: str | None
    message: str | None
```

### PerformanceMetricsRecord

```python
@dataclass
class PerformanceMetricsRecord:
    """Database record for performance_metrics table."""

    id: int | None
    stats_id: str  # FK to processing_stats
    phase_name: str

    # Timing
    wall_time_seconds: float

    # I/O metrics
    bytes_read: int | None
    bytes_written: int | None

    # FFmpeg metrics
    encoding_fps: float | None
    encoding_bitrate: int | None
```

## View Model Dataclasses

### StatsSummary

Aggregate statistics for dashboard display.

```python
@dataclass
class StatsSummary:
    """Summary statistics for display."""

    total_files_processed: int
    total_successful: int
    total_failed: int
    success_rate: float  # 0.0 - 1.0

    total_size_before: int  # bytes
    total_size_after: int   # bytes
    total_size_saved: int   # bytes (positive = saved)
    avg_savings_percent: float

    total_audio_removed: int
    total_subtitles_removed: int
    total_attachments_removed: int

    total_videos_transcoded: int
    total_videos_skipped: int
    total_audio_transcoded: int

    avg_processing_time: float  # seconds

    # Time range
    earliest_processing: str | None  # ISO-8601
    latest_processing: str | None    # ISO-8601
```

### PolicyStats

Per-policy breakdown.

```python
@dataclass
class PolicyStats:
    """Statistics for a single policy."""

    policy_name: str
    files_processed: int
    success_rate: float

    total_size_saved: int
    avg_savings_percent: float

    audio_tracks_removed: int
    subtitle_tracks_removed: int
    attachments_removed: int

    videos_transcoded: int
    audio_transcoded: int

    avg_processing_time: float

    last_used: str  # ISO-8601
```

### FileProcessingHistory

Processing history for a specific file.

```python
@dataclass
class FileProcessingHistory:
    """Processing history entry for a file."""

    stats_id: str
    processed_at: str
    policy_name: str

    size_before: int
    size_after: int
    size_change: int

    audio_removed: int
    subtitle_removed: int
    attachments_removed: int

    duration_seconds: float
    success: bool
    error_message: str | None
```

## State Transitions

Processing statistics are append-only. Each processing run creates a new record:

```
[File Created]
    ↓
[First Processing] → ProcessingStats(id=uuid1)
    ↓
[Re-Processing]    → ProcessingStats(id=uuid2)  # New record, history preserved
    ↓
[Re-Processing]    → ProcessingStats(id=uuid3)  # Another new record
    ↓
[Manual Purge]     → Old records deleted (optional)
```

## Validation Rules

### ProcessingStatsRecord

- `id`: Must be valid UUIDv4
- `file_id`: Must reference existing file in files table
- `processed_at`: Must be valid ISO-8601 UTC timestamp
- `size_before`, `size_after`: Must be >= 0
- `size_change`: Must equal `size_before - size_after`
- `*_before`, `*_after`: Must be >= 0
- `*_removed`: Must equal `*_before - *_after`, >= 0
- `duration_seconds`: Must be >= 0
- `phases_completed`: Must be <= `phases_total`
- `success`: Boolean (0 or 1)

### ActionResultRecord

- `stats_id`: Must reference existing processing_stats record
- `action_type`: Must be valid action type string
- `before_state`, `after_state`: Must be valid JSON if not null
- `success`: Boolean (0 or 1)
- `duration_ms`: Must be >= 0 if not null

### PerformanceMetricsRecord

- `stats_id`: Must reference existing processing_stats record
- `wall_time_seconds`: Must be >= 0
- `bytes_read`, `bytes_written`: Must be >= 0 if not null
- `encoding_fps`, `encoding_bitrate`: Must be >= 0 if not null

## Migration Strategy

Schema version bump: 17 → 18

```python
def migrate_v17_to_v18(conn: sqlite3.Connection) -> None:
    """Add processing statistics tables."""

    # Create processing_stats table
    conn.executescript(PROCESSING_STATS_SQL)

    # Create action_results table
    conn.executescript(ACTION_RESULTS_SQL)

    # Create performance_metrics table
    conn.executescript(PERFORMANCE_METRICS_SQL)

    # Update schema version
    conn.execute(
        "UPDATE _meta SET value = '18' WHERE key = 'schema_version'"
    )
    conn.commit()
```

The migration is additive-only (new tables, no existing table modifications), making it safe and reversible.
