# Data Model: Operational UX

**Feature**: 008-operational-ux
**Date**: 2025-11-22

## Overview

This document defines the data model changes for incremental scanning, job history expansion, configuration profiles, and structured logging.

---

## Entity Changes

### 1. JobType Enum (Extended)

**Location**: `src/video_policy_orchestrator/db/models.py`

```python
class JobType(Enum):
    """Type of job in the queue."""
    TRANSCODE = "transcode"
    MOVE = "move"
    SCAN = "scan"      # NEW: Directory scan operation
    APPLY = "apply"    # NEW: Policy application operation
```

**Changes**: Added `SCAN` and `APPLY` values to track all operation types uniformly.

---

### 2. Job Entity (Extended)

**Location**: `src/video_policy_orchestrator/db/models.py`

**New Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `files_affected_json` | `str \| None` | JSON array of file paths affected by this job |
| `summary_json` | `str \| None` | Job-specific summary (e.g., scan counts) |

**Schema Changes** (migration v6→v7):

```sql
-- Extend job_type constraint
-- SQLite doesn't support ALTER CONSTRAINT, so this requires table recreation
-- or using CHECK constraint modification workaround

-- Add new columns
ALTER TABLE jobs ADD COLUMN files_affected_json TEXT;
ALTER TABLE jobs ADD COLUMN summary_json TEXT;
```

**ScanSummary Structure** (stored in `summary_json` for SCAN jobs):

```json
{
  "total_discovered": 1000,
  "scanned": 10,
  "skipped": 985,
  "added": 5,
  "removed": 0,
  "errors": 0
}
```

---

### 3. Profile Entity (New)

**Location**: `src/video_policy_orchestrator/config/models.py`

```python
@dataclass
class Profile:
    """Named configuration profile."""

    name: str                           # Profile identifier (from filename)
    description: str | None = None      # Human-readable description
    default_policy: Path | None = None  # Default policy file for this profile

    # Override sections (optional, merged with base config)
    tools: ToolPathsConfig | None = None
    behavior: BehaviorConfig | None = None
    logging: LoggingConfig | None = None
    jobs: JobsConfig | None = None
```

**Storage**: YAML files in `~/.vpo/profiles/<name>.yaml`

**Example Profile** (`~/.vpo/profiles/movies.yaml`):

```yaml
name: movies
description: Settings for movie library processing

default_policy: ~/policies/movies-standard.yaml

behavior:
  warn_on_missing_features: false
  show_upgrade_suggestions: true

logging:
  level: info
  file: ~/.vpo/logs/movies.log
```

---

### 4. LoggingConfig Entity (New)

**Location**: `src/video_policy_orchestrator/config/models.py`

```python
@dataclass
class LoggingConfig:
    """Configuration for structured logging."""

    level: str = "info"              # debug, info, warning, error
    file: Path | None = None         # Log file path (None = stderr only)
    format: str = "text"             # text, json
    include_stderr: bool = True      # Also log to stderr when file is set
    max_bytes: int = 10_485_760      # 10MB rotation threshold
    backup_count: int = 5            # Number of rotated files to keep

    def __post_init__(self) -> None:
        """Validate configuration."""
        valid_levels = {"debug", "info", "warning", "error"}
        if self.level.lower() not in valid_levels:
            raise ValueError(f"level must be one of {valid_levels}")
        valid_formats = {"text", "json"}
        if self.format.lower() not in valid_formats:
            raise ValueError(f"format must be one of {valid_formats}")
```

---

### 5. ScanResult Entity (New)

**Location**: `src/video_policy_orchestrator/scanner/models.py`

```python
@dataclass
class ScanResult:
    """Result of a directory scan operation."""

    job_id: str                    # UUID of the scan job
    directory: Path                # Root directory scanned
    started_at: datetime           # UTC timestamp
    completed_at: datetime | None  # UTC timestamp

    # Counts
    total_discovered: int = 0      # Files found on disk
    scanned: int = 0               # Files introspected
    skipped: int = 0               # Files unchanged (incremental)
    added: int = 0                 # New files added to DB
    removed: int = 0               # Files marked missing/deleted
    errors: int = 0                # Files with scan errors

    # Mode
    incremental: bool = True       # Whether incremental mode was used

    def to_summary_json(self) -> str:
        """Serialize counts for job storage."""
        return json.dumps({
            "total_discovered": self.total_discovered,
            "scanned": self.scanned,
            "skipped": self.skipped,
            "added": self.added,
            "removed": self.removed,
            "errors": self.errors,
        })
```

---

## Database Schema Changes

### Migration v6 → v7

**File**: `src/video_policy_orchestrator/db/schema.py`

```python
SCHEMA_VERSION = 7

def migrate_v6_to_v7(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 6 to version 7.

    Extends jobs table for unified operation tracking:
    - Expands job_type to include 'scan' and 'apply'
    - Adds files_affected_json for multi-file operations
    - Adds summary_json for job-specific results

    This migration is idempotent - safe to run multiple times.
    """
    # Check if columns exist
    cursor = conn.execute("PRAGMA table_info(jobs)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Add new columns if missing
    if "files_affected_json" not in existing_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN files_affected_json TEXT")

    if "summary_json" not in existing_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN summary_json TEXT")

    # Note: SQLite CHECK constraints cannot be altered after table creation
    # New job types will work; constraint is informational only

    conn.execute(
        "UPDATE _meta SET value = '7' WHERE key = 'schema_version'"
    )
    conn.commit()
```

---

## Entity Relationships

```
┌─────────────┐
│   Profile   │──────────────────────────────────────┐
│  (YAML file)│                                      │
└─────────────┘                                      │
                                                     │ references
┌─────────────┐      ┌─────────────┐                 │
│   VPOConfig │◄─────│LoggingConfig│                 │
│   (runtime) │      │  (embedded) │                 │
└─────────────┘      └─────────────┘                 │
                                                     │
┌─────────────┐                                      ▼
│    Job      │──────────────────────────────►┌─────────────┐
│ (DB table)  │  files_affected_json          │   Policy    │
│             │                               │ (YAML file) │
└─────────────┘                               └─────────────┘
       │
       │ file_id (FK)
       ▼
┌─────────────┐
│    File     │
│ (DB table)  │
└─────────────┘
```

---

## Validation Rules

### Profile Validation

| Field | Rule | Error Message |
|-------|------|---------------|
| `name` | Non-empty, alphanumeric + hyphen/underscore | "Profile name must be alphanumeric" |
| `default_policy` | File must exist if specified | "Policy file not found: {path}" |
| `logging.level` | One of: debug, info, warning, error | "Invalid log level: {value}" |
| `logging.format` | One of: text, json | "Invalid log format: {value}" |

### Job Type Validation

| Operation | Job Type | Required Fields |
|-----------|----------|-----------------|
| `vpo scan` | `scan` | `file_path` (directory), `summary_json` |
| `vpo apply` | `apply` | `file_id`, `policy_name`, `policy_json` |
| `vpo transcode` | `transcode` | `file_id`, `policy_json`, `output_path` |

---

## State Transitions

### Job Status Flow

```
           ┌──────────────────────────┐
           ▼                          │
      ┌─────────┐                     │
      │ QUEUED  │────────────────┐    │
      └────┬────┘                │    │
           │ start()             │    │
           ▼                     │    │
      ┌─────────┐           cancel()  │
      │ RUNNING │────────────────┼────┤
      └────┬────┘                │    │
           │                     │    │
     ┌─────┴─────┐               │    │
     │           │               ▼    │
 complete()   fail()        ┌─────────┐
     │           │          │CANCELLED│
     ▼           ▼          └─────────┘
┌─────────┐ ┌─────────┐
│COMPLETED│ │ FAILED  │
└─────────┘ └─────────┘
```

### File Scan Status Flow

```
                 ┌─────────┐
    new file ───►│ pending │
                 └────┬────┘
                      │ introspect()
                      ▼
                 ┌─────────┐
           ┌─────│   ok    │◄────┐
           │     └────┬────┘     │
           │          │          │
      error()    disappear()  rescan()
           │          │          │
           ▼          ▼          │
      ┌─────────┐ ┌─────────┐    │
      │  error  │ │ missing │────┘
      └─────────┘ └─────────┘
                      │
                  prune()
                      │
                      ▼
                  [DELETED]
```
