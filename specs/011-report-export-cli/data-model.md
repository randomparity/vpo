# Data Model: Reporting & Export CLI

**Feature**: 011-report-export-cli
**Date**: 2025-01-22

## Overview

This feature is **read-only** and does not modify the database schema. It queries existing tables and presents data in various formats. This document describes the data structures used within the reporting module.

## Existing Database Entities (Read-Only Access)

The reporting module queries these existing tables:

### jobs
| Column | Type | Used By Reports |
|--------|------|-----------------|
| id | TEXT (UUID) | jobs, scans, transcodes, policy-apply |
| file_id | INTEGER | jobs, transcodes |
| file_path | TEXT | jobs, transcodes, policy-apply |
| job_type | TEXT | jobs, scans, transcodes |
| status | TEXT | jobs, scans, transcodes, policy-apply |
| priority | INTEGER | - |
| policy_name | TEXT | policy-apply |
| policy_json | TEXT | policy-apply (verbose) |
| progress_percent | REAL | jobs |
| created_at | TEXT (ISO-8601) | all reports |
| started_at | TEXT (ISO-8601) | all reports |
| completed_at | TEXT (ISO-8601) | all reports |
| error_message | TEXT | jobs (failed only) |
| summary_json | TEXT | scans (file counts) |
| files_affected_json | TEXT | policy-apply |

### files
| Column | Type | Used By Reports |
|--------|------|-----------------|
| id | INTEGER | library |
| path | TEXT | library |
| filename | TEXT | library |
| directory | TEXT | library (filtering) |
| extension | TEXT | library |
| size_bytes | INTEGER | library, transcodes |
| container_format | TEXT | library |
| scanned_at | TEXT (ISO-8601) | library |
| scan_status | TEXT | library |

### tracks
| Column | Type | Used By Reports |
|--------|------|-----------------|
| id | INTEGER | library |
| file_id | INTEGER | library (join) |
| track_type | TEXT | library |
| codec | TEXT | library, transcodes |
| language | TEXT | library |
| width | INTEGER | library (resolution) |
| height | INTEGER | library (resolution) |
| is_default | INTEGER | library |

### operations
| Column | Type | Used By Reports |
|--------|------|-----------------|
| id | TEXT (UUID) | policy-apply |
| file_id | INTEGER | policy-apply |
| file_path | TEXT | policy-apply |
| policy_name | TEXT | policy-apply |
| actions_json | TEXT | policy-apply (verbose) |
| status | TEXT | policy-apply |
| started_at | TEXT (ISO-8601) | policy-apply |
| completed_at | TEXT (ISO-8601) | policy-apply |

## Report Data Models

### ReportFormat (Enum)

```python
class ReportFormat(Enum):
    TEXT = "text"
    CSV = "csv"
    JSON = "json"
```

### TimeFilter (Dataclass)

```python
@dataclass
class TimeFilter:
    since: datetime | None = None  # UTC
    until: datetime | None = None  # UTC

    @classmethod
    def from_strings(cls, since: str | None, until: str | None) -> "TimeFilter":
        """Parse since/until from CLI strings (relative or ISO-8601)."""
        ...
```

### JobReportRow (Dataclass)

Represents a single row in the jobs report.

```python
@dataclass
class JobReportRow:
    job_id: str           # Short ID (first 8 chars)
    job_type: str         # scan, apply, transcode, move
    status: str           # queued, running, completed, failed, cancelled
    file_path: str        # Target file or directory
    started_at: str       # Local time string
    completed_at: str     # Local time string or "-"
    duration: str         # Human-readable or "-"
    error_summary: str    # Truncated error or "-"
```

**Columns (ordered)**:
1. `job_id` - 8-char UUID prefix
2. `type` - Job type
3. `status` - Current status
4. `target` - File/directory path (truncated)
5. `started` - Start time (local)
6. `completed` - End time or "-"
7. `duration` - Elapsed time
8. `error` - Error message (truncated, failed only)

### LibraryReportRow (Dataclass)

Represents a single file in the library report.

```python
@dataclass
class LibraryReportRow:
    file_path: str        # Full path
    title: str            # From container metadata or filename
    container: str        # mkv, mp4, avi, etc.
    resolution: str       # 4K, 1080p, 720p, 480p, SD, unknown
    audio_languages: str  # Comma-separated (e.g., "eng, jpn")
    has_subtitles: bool   # True if any subtitle tracks exist
    scanned_at: str       # Local time string
```

**Columns (ordered)**:
1. `path` - File path
2. `title` - Display title
3. `container` - Container format
4. `resolution` - Video resolution category
5. `audio` - Audio languages
6. `subtitles` - Yes/No
7. `scanned` - Last scan time

### ScanReportRow (Dataclass)

Represents a single scan operation.

```python
@dataclass
class ScanReportRow:
    scan_id: str          # 8-char UUID prefix
    started_at: str       # Local time string
    completed_at: str     # Local time string or "-"
    duration: str         # Human-readable
    files_scanned: int    # Total files processed
    files_new: int        # New files discovered
    files_changed: int    # Files with changes
    status: str           # completed, failed
```

**Columns (ordered)**:
1. `scan_id` - 8-char UUID prefix
2. `started` - Start time
3. `completed` - End time
4. `duration` - Elapsed time
5. `total` - Files scanned
6. `new` - New files
7. `changed` - Changed files
8. `status` - Scan status

### TranscodeReportRow (Dataclass)

Represents a single transcode operation.

```python
@dataclass
class TranscodeReportRow:
    job_id: str           # 8-char UUID prefix
    file_path: str        # Source file
    source_codec: str     # Original video codec
    target_codec: str     # Output video codec
    started_at: str       # Local time string
    completed_at: str     # Local time string or "-"
    duration: str         # Human-readable
    status: str           # completed, failed
    size_change: str      # e.g., "-25%" or "N/A"
```

**Columns (ordered)**:
1. `job_id` - 8-char UUID prefix
2. `file` - Source file path
3. `from` - Source codec
4. `to` - Target codec
5. `started` - Start time
6. `completed` - End time
7. `duration` - Elapsed time
8. `status` - Job status
9. `savings` - Size change percentage

### PolicyApplyReportRow (Dataclass)

Represents a single policy application.

```python
@dataclass
class PolicyApplyReportRow:
    operation_id: str     # 8-char UUID prefix (or job_id for newer apply jobs)
    policy_name: str      # Policy file/name
    files_affected: int   # Number of files changed
    metadata_changes: int # Metadata-only operations
    heavy_changes: int    # Transcode/move operations
    status: str           # completed, failed
    started_at: str       # Local time string
```

**Columns (ordered)**:
1. `op_id` - Operation/job ID prefix
2. `policy` - Policy name
3. `files` - Files affected
4. `metadata` - Metadata change count
5. `heavy` - Heavy operation count
6. `status` - Operation status
7. `started` - Start time

### PolicyApplyDetailRow (Dataclass)

For verbose mode, includes per-file details.

```python
@dataclass
class PolicyApplyDetailRow:
    file_path: str        # Full path
    changes: str          # Summary of changes applied
```

## Query Functions

### get_jobs_report()
```python
def get_jobs_report(
    conn: Connection,
    *,
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    time_filter: TimeFilter | None = None,
    limit: int | None = 100,
) -> list[JobReportRow]:
    """Query jobs table with filters, return formatted rows."""
```

### get_library_report()
```python
def get_library_report(
    conn: Connection,
    *,
    resolution: str | None = None,  # "4K", "1080p", etc.
    language: str | None = None,    # ISO 639-2 code
    has_subtitles: bool | None = None,
    limit: int | None = 100,
) -> list[LibraryReportRow]:
    """Query files+tracks with filters, return formatted rows."""
```

### get_scans_report()
```python
def get_scans_report(
    conn: Connection,
    *,
    time_filter: TimeFilter | None = None,
    limit: int | None = 100,
) -> list[ScanReportRow]:
    """Query scan jobs, parse summary_json, return formatted rows."""
```

### get_transcodes_report()
```python
def get_transcodes_report(
    conn: Connection,
    *,
    codec: str | None = None,  # Target codec filter
    time_filter: TimeFilter | None = None,
    limit: int | None = 100,
) -> list[TranscodeReportRow]:
    """Query transcode jobs, return formatted rows."""
```

### get_policy_apply_report()
```python
def get_policy_apply_report(
    conn: Connection,
    *,
    policy_name: str | None = None,
    time_filter: TimeFilter | None = None,
    verbose: bool = False,
    limit: int | None = 100,
) -> list[PolicyApplyReportRow] | list[PolicyApplyDetailRow]:
    """Query apply jobs/operations, return formatted rows."""
```

## State Transitions

N/A - This feature is read-only and does not modify state.

## Validation Rules

| Field | Rule |
|-------|------|
| `resolution` filter | Must be one of: `4K`, `1080p`, `720p`, `480p`, `SD` |
| `language` filter | ISO 639-2 code (3 letters) |
| `codec` filter | Case-insensitive match against target codec |
| `limit` | Positive integer or None (no limit) |
| `time_filter.since` | Must be before `until` if both specified |

## Relationships

```
jobs (1) ──────────────── (*) files
  │                            │
  │ job_type=scan             │
  │ summary_json              │
  ▼                            ▼
ScanReport                  tracks
                              │
jobs (1)                      │
  │                            │
  │ job_type=apply            │
  ▼                            ▼
PolicyApplyReport ◄───── operations
                              │
jobs (1)                      │
  │                            │
  │ job_type=transcode        │
  ▼                            │
TranscodeReport ◄────────────┘
```
