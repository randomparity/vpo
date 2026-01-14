# Data Model: Job Detail View with Logs

**Feature**: 016-job-detail-view
**Date**: 2025-11-23

## Entity Overview

This feature extends the existing `Job` entity and introduces presentation models for the detail view.

---

## 1. Job Entity (Extended)

**Table**: `jobs`
**Schema Version**: 8 (upgrade from 7)

### New Field

| Field | Type | Nullable | Default | Description |
|-------|------|----------|---------|-------------|
| log_path | TEXT | Yes | NULL | Relative path to log file from VPO data directory |

### Migration Notes
- Add column: `ALTER TABLE jobs ADD COLUMN log_path TEXT`
- Index: `CREATE INDEX idx_jobs_log_path ON jobs(log_path)` (optional, for cleanup queries)
- Existing jobs will have `log_path = NULL` (no logs)

### Full Job Schema (v8)

```sql
CREATE TABLE jobs (
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
    worker_pid INTEGER,
    worker_heartbeat TEXT,
    output_path TEXT,
    backup_path TEXT,
    error_message TEXT,
    files_affected_json TEXT,
    summary_json TEXT,
    log_path TEXT,  -- NEW in v8
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);
```

---

## 2. Job Dataclass (Extended)

**File**: `src/vpo/db/models.py`

```python
@dataclass
class Job:
    """Database record for jobs table."""

    id: str  # UUID v4
    file_id: int | None
    file_path: str
    job_type: JobType
    status: JobStatus
    priority: int
    policy_name: str | None
    policy_json: str | None
    progress_percent: float
    progress_json: str | None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    worker_pid: int | None = None
    worker_heartbeat: str | None = None
    output_path: str | None = None
    backup_path: str | None = None
    error_message: str | None = None
    files_affected_json: str | None = None
    summary_json: str | None = None
    log_path: str | None = None  # NEW in v8
```

---

## 3. JobDetailItem (New Presentation Model)

**File**: `src/vpo/server/ui/models.py`

```python
@dataclass
class JobDetailItem:
    """Full job data for detail view API response.

    Extends JobListItem with additional fields for the detail view.
    """

    # Core identification
    id: str  # Full UUID
    id_short: str  # First 8 chars for display

    # Job metadata
    job_type: str  # scan, apply, transcode, move
    status: str  # queued, running, completed, failed, cancelled
    priority: int

    # Target information
    file_path: str
    policy_name: str | None

    # Timing
    created_at: str  # ISO-8601 UTC
    started_at: str | None
    completed_at: str | None
    duration_seconds: int | None  # Computed

    # Progress
    progress_percent: float

    # Results
    error_message: str | None
    output_path: str | None

    # Summary (human-readable)
    summary: str | None  # Generated from summary_json
    summary_raw: dict | None  # Parsed summary_json for detailed display

    # Logs availability
    has_logs: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "id_short": self.id_short,
            "job_type": self.job_type,
            "status": self.status,
            "priority": self.priority,
            "file_path": self.file_path,
            "policy_name": self.policy_name,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "progress_percent": self.progress_percent,
            "error_message": self.error_message,
            "output_path": self.output_path,
            "summary": self.summary,
            "summary_raw": self.summary_raw,
            "has_logs": self.has_logs,
        }
```

---

## 4. JobLogsResponse (New Presentation Model)

**File**: `src/vpo/server/ui/models.py`

```python
@dataclass
class JobLogsResponse:
    """API response for job logs endpoint.

    Supports lazy loading with pagination.
    """

    job_id: str
    lines: list[str]  # Log lines (most recent first when loading from end)
    total_lines: int  # Total lines in log file
    offset: int  # Current offset (lines from end)
    has_more: bool  # Whether more lines are available

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "lines": self.lines,
            "total_lines": self.total_lines,
            "offset": self.offset,
            "has_more": self.has_more,
        }
```

---

## 5. JobDetailContext (Template Context)

**File**: `src/vpo/server/ui/models.py`

```python
@dataclass
class JobDetailContext:
    """Template context for job_detail.html.

    Passed to Jinja2 template for server-side rendering.
    """

    job: JobDetailItem
    back_url: str  # URL to return to jobs list (with preserved filters)

    @classmethod
    def from_job_and_request(
        cls,
        job: JobDetailItem,
        referer: str | None,
    ) -> "JobDetailContext":
        """Create context from job and request data."""
        # Default back URL, or preserve filters from referer
        back_url = "/jobs"
        if referer and referer.startswith("/jobs?"):
            back_url = referer
        return cls(job=job, back_url=back_url)
```

---

## 6. Summary JSON Structure

**Field**: `jobs.summary_json`

The `summary_json` field contains job-type-specific outcome data. Structure varies by job type:

### Scan Job Summary
```json
{
    "total_files": 150,
    "new_files": 5,
    "changed_files": 3,
    "unchanged_files": 142,
    "errors": 0,
    "target_directory": "/media/movies"
}
```

### Apply Job Summary
```json
{
    "files_affected": 5,
    "policy_name": "normalize-audio",
    "actions_applied": ["set_default_audio", "reorder_tracks"]
}
```

### Transcode Job Summary
```json
{
    "input_file": "/media/movies/input.mkv",
    "output_file": "/media/movies/output.mkv",
    "input_size_bytes": 5368709120,
    "output_size_bytes": 2147483648,
    "compression_ratio": 0.4
}
```

### Move Job Summary
```json
{
    "source_path": "/media/unsorted/movie.mkv",
    "destination_path": "/media/movies/movie.mkv",
    "size_bytes": 5368709120
}
```

---

## 7. Log File Structure

**Location**: `~/.vpo/logs/{job_id}.log`

### Format
- Plain text, UTF-8 encoded
- One log entry per line
- Timestamps in ISO-8601 format at line start
- No structured format required (free-form output)

### Example
```
2025-11-23T10:15:30Z Starting scan of /media/movies
2025-11-23T10:15:31Z Found 150 media files
2025-11-23T10:15:32Z Processing file 1/150: movie1.mkv
2025-11-23T10:15:33Z Processing file 2/150: movie2.mkv
...
2025-11-23T10:20:45Z Scan complete: 150 files processed, 5 new, 3 changed
```

### Lifecycle
- Created when job starts
- Appended during job execution
- Retained after job completion
- Subject to future log retention policy (not in this feature)

---

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                         Database                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    jobs (v8)                         │   │
│  │  id (PK), file_path, job_type, status, ...          │   │
│  │  summary_json, log_path (NEW)                       │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          │ log_path references
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    File System                              │
│  ~/.vpo/logs/                                               │
│  ├── {job_id_1}.log                                        │
│  ├── {job_id_2}.log                                        │
│  └── ...                                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Validation Rules

| Field | Rule |
|-------|------|
| Job.id | Valid UUID v4 format |
| Job.log_path | Relative path, no directory traversal (`..`) |
| JobLogsResponse.offset | Non-negative integer |
| JobLogsResponse.lines | Max 500 lines per request (configurable) |
