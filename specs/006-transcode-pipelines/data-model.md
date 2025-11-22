# Data Model: Transcoding & File Movement Pipelines

**Date**: 2025-11-22
**Feature**: 006-transcode-pipelines

## Entity Overview

```
┌─────────────────┐       ┌─────────────────┐
│      Job        │──────▶│     File        │ (existing)
└─────────────────┘       └─────────────────┘
        │
        ▼
┌─────────────────┐       ┌─────────────────┐
│  TranscodeJob   │       │    MoveJob      │
│   (job_type)    │       │   (job_type)    │
└─────────────────┘       └─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│ TranscodePolicy │◀──────│  PolicySchema   │ (extend existing)
└─────────────────┘       └─────────────────┘
        │
        ▼
┌─────────────────┐       ┌─────────────────┐
│AudioPreservation│       │DestinationTmpl │
└─────────────────┘       └─────────────────┘

┌─────────────────┐
│ ParsedMetadata  │ (extracted from filename)
└─────────────────┘
```

## New Entities

### Job

Represents a queued or running transcode/move operation.

```python
@dataclass
class Job:
    """Database record for jobs table."""

    id: str                     # UUID v4
    file_id: int                # FK to files.id
    file_path: str              # Path at time of job creation
    job_type: JobType           # TRANSCODE or MOVE
    status: JobStatus           # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    priority: int               # Lower = higher priority (default: 100)

    # Policy reference
    policy_name: str | None     # Name of policy used
    policy_json: str            # Serialized policy settings for this job

    # Progress tracking
    progress_percent: float     # 0.0 - 100.0
    progress_json: str | None   # Detailed progress (frames, time, etc.)

    # Timing
    created_at: str             # ISO-8601 UTC
    started_at: str | None      # ISO-8601 UTC
    completed_at: str | None    # ISO-8601 UTC

    # Worker tracking
    worker_pid: int | None      # PID of worker processing this job
    worker_heartbeat: str | None # ISO-8601 UTC, updated periodically

    # Results
    output_path: str | None     # Path to output file
    backup_path: str | None     # Path to backup of original
    error_message: str | None   # Error details if FAILED
```

**Validation Rules**:
- `id` must be valid UUID v4
- `file_id` must reference existing file
- `status` must be valid JobStatus value
- `priority` must be >= 0
- `progress_percent` must be 0.0-100.0

**State Transitions**:
```
QUEUED ──▶ RUNNING ──▶ COMPLETED
   │          │
   │          ├──▶ FAILED
   │          │
   └──────────┴──▶ CANCELLED
```

### JobType (Enum)

```python
class JobType(Enum):
    TRANSCODE = "transcode"  # Video/audio transcoding
    MOVE = "move"            # File movement/organization
```

### JobStatus (Enum)

```python
class JobStatus(Enum):
    QUEUED = "queued"        # Waiting to be processed
    RUNNING = "running"      # Currently being processed
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"        # Error during processing
    CANCELLED = "cancelled"  # Cancelled by user
```

### TranscodePolicyConfig

Extension to existing PolicySchema for transcoding settings.

```python
@dataclass(frozen=True)
class TranscodePolicyConfig:
    """Transcoding-specific policy configuration."""

    # Video settings
    target_video_codec: str | None = None      # hevc, h264, vp9, av1
    target_crf: int | None = None              # 0-51 for x264/x265
    target_bitrate: str | None = None          # e.g., "5M", "2500k"
    max_resolution: str | None = None          # 1080p, 720p, 4k
    max_width: int | None = None               # Max width in pixels
    max_height: int | None = None              # Max height in pixels

    # Audio preservation
    audio_preserve_codecs: tuple[str, ...] = ()  # Codecs to copy
    audio_transcode_to: str = "aac"              # Target for others
    audio_transcode_bitrate: str = "192k"        # Bitrate for transcoded
    audio_downmix: str | None = None             # None, "stereo", "5.1"

    # Destination
    destination: str | None = None             # Template string
    destination_fallback: str = "Unknown"      # Fallback for missing metadata
```

**Validation Rules**:
- `target_crf` must be 0-51 if set
- `max_resolution` must be one of: "480p", "720p", "1080p", "1440p", "4k", "8k"
- `audio_preserve_codecs` entries must be lowercase codec names
- `audio_transcode_to` must be valid output codec
- `destination` must contain at least one placeholder or be None

### AudioPreservationRule

Defines handling for a specific audio codec.

```python
@dataclass(frozen=True)
class AudioPreservationRule:
    """Rule for handling specific audio codec."""

    codec_pattern: str       # Codec name or pattern (e.g., "truehd", "dts*")
    action: str              # "preserve", "transcode", "remove"
    transcode_to: str | None = None    # Target codec if action=transcode
    transcode_bitrate: str | None = None  # Target bitrate
```

### DestinationTemplate

Parsed destination template with placeholders.

```python
@dataclass(frozen=True)
class DestinationTemplate:
    """Parsed destination template."""

    raw_template: str                    # Original template string
    placeholders: tuple[str, ...]        # Extracted placeholder names
    fallback_values: dict[str, str]      # Fallback for missing metadata

    def render(self, metadata: dict[str, str]) -> Path:
        """Render template with metadata values."""
        ...
```

**Supported Placeholders**:
- `{title}` - Movie/episode title
- `{year}` - Release year
- `{series}` - TV series name
- `{season}` - Season number (padded: 01, 02)
- `{episode}` - Episode number (padded: 01, 02)
- `{resolution}` - Video resolution (1080p, 720p, etc.)
- `{codec}` - Video codec
- `{source}` - Source type (BluRay, WEB-DL, etc.)

### ParsedMetadata

Metadata extracted from filename.

```python
@dataclass
class ParsedMetadata:
    """Metadata parsed from filename."""

    original_filename: str

    # Parsed fields (None if not found)
    title: str | None = None
    year: int | None = None
    series: str | None = None
    season: int | None = None
    episode: int | None = None
    resolution: str | None = None
    codec: str | None = None
    source: str | None = None

    # Parsing metadata
    pattern_matched: str | None = None  # Pattern that matched
    confidence: float = 0.0             # 0.0-1.0
```

### JobProgress

Detailed progress information for running job.

```python
@dataclass
class JobProgress:
    """Detailed progress for a running job."""

    percent: float           # Overall percentage 0-100

    # For transcoding jobs
    frame_current: int | None = None
    frame_total: int | None = None
    time_current: float | None = None   # Seconds
    time_total: float | None = None     # Seconds
    fps: float | None = None            # Current encoding FPS
    bitrate: str | None = None          # Current bitrate
    size_current: int | None = None     # Output size so far (bytes)

    # Estimates
    eta_seconds: int | None = None      # Estimated time remaining
```

## Database Schema Changes

### New Table: jobs

```sql
-- Schema version 5
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
```

### Migration: v4 → v5

```python
def migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """Add jobs table for transcoding/movement queue."""

    # Check if table already exists (idempotent)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='jobs'"
    )
    if cursor.fetchone() is None:
        conn.executescript(JOBS_TABLE_SQL)

    # Update schema version
    conn.execute(
        "UPDATE _meta SET value = '5' WHERE key = 'schema_version'"
    )
    conn.commit()
```

## Extended Policy Schema

```yaml
# Example policy with transcode settings
schema_version: 2

# Existing track ordering settings
track_order: [video, audio_main, subtitle_main, ...]
audio_language_preference: [eng, jpn]

# NEW: Transcoding settings
transcode:
  target_video_codec: hevc
  target_crf: 20
  max_resolution: 1080p

  # Audio handling
  audio_preserve_codecs:
    - truehd
    - dts-hd
    - flac
  audio_transcode_to: aac
  audio_transcode_bitrate: 192k
  audio_downmix: stereo  # Create additional stereo track

# NEW: Directory organization
destination: "Movies/{year}/{title}"
destination_fallback: "Unknown"
```

## Configuration Extensions

```yaml
# In ~/.vpo/config.yaml

# NEW: Jobs configuration
jobs:
  retention_days: 30      # How long to keep completed jobs
  auto_purge: true        # Purge old jobs on worker start
  temp_directory: null    # Use source directory if null
  backup_original: true   # Keep backup after successful transcode

# NEW: Worker defaults
worker:
  max_files: null         # No limit by default
  max_duration: null      # No limit by default
  end_by: null            # No deadline by default
  cpu_cores: null         # Use all cores by default
```

## Relationships

| From | To | Relationship | Notes |
|------|-----|--------------|-------|
| Job | File | Many-to-One | Job references existing scanned file |
| Job | Policy | Embedded | Policy config serialized in job |
| TranscodePolicyConfig | PolicySchema | Extension | Added to existing schema |
| ParsedMetadata | File | Derived | Extracted from file.filename |
