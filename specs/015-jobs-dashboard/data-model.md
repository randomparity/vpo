# Data Model: Jobs Dashboard List View

**Feature**: 015-jobs-dashboard
**Date**: 2025-11-23

## Entities

### Job (Existing - Read Only)

The jobs dashboard reads from the existing `jobs` table. No schema modifications required.

**Source**: `src/vpo/db/schema.py` (schema v7)

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID) | No | Primary key |
| file_id | INTEGER | Yes | FK to files table |
| file_path | TEXT | No | Target path at job creation |
| job_type | TEXT | No | Enum: transcode, move, scan, apply |
| status | TEXT | No | Enum: queued, running, completed, failed, cancelled |
| priority | INTEGER | No | Lower = higher priority (default 100) |
| progress_percent | REAL | No | 0.0-100.0 |
| created_at | TEXT | No | ISO-8601 UTC timestamp |
| started_at | TEXT | Yes | ISO-8601 UTC timestamp |
| completed_at | TEXT | Yes | ISO-8601 UTC timestamp |
| error_message | TEXT | Yes | Error details if failed |

**Indexes Used**:
- `idx_jobs_status` - For status filtering
- `idx_jobs_created_at` - For time-based sorting and filtering

### JobType (Enum - Existing)

**Source**: `src/vpo/db/models.py`

```python
class JobType(Enum):
    TRANSCODE = "transcode"
    MOVE = "move"
    SCAN = "scan"
    APPLY = "apply"
```

### JobStatus (Enum - Existing)

**Source**: `src/vpo/db/models.py`

```python
class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

## New Models (UI Layer)

### JobFilterParams

**Purpose**: Validate and parse query parameters for /api/jobs

**Location**: `src/vpo/server/ui/models.py`

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| status | str \| None | None | Must be valid JobStatus value or None |
| job_type | str \| None | None | Must be valid JobType value or None |
| since | str \| None | None | Must be: "24h", "7d", or None (all time) |
| limit | int | 50 | 1-100 range |
| offset | int | 0 | >= 0 |

### JobListItem

**Purpose**: Job data for API response and template rendering

**Location**: `src/vpo/server/ui/models.py`

| Field | Type | Description |
|-------|------|-------------|
| id | str | Job UUID |
| job_type | str | Job type value |
| status | str | Job status value |
| file_path | str | Target file/directory path |
| progress_percent | float | 0.0-100.0 |
| created_at | str | ISO-8601 UTC timestamp |
| completed_at | str \| None | ISO-8601 UTC timestamp or None |
| duration_seconds | int \| None | Computed: completed_at - created_at |

### JobListResponse

**Purpose**: API response wrapper with pagination metadata

**Location**: `src/vpo/server/ui/models.py`

| Field | Type | Description |
|-------|------|-------------|
| jobs | list[JobListItem] | Job items for current page |
| total | int | Total jobs matching filters |
| limit | int | Page size used |
| offset | int | Current offset |
| has_filters | bool | True if any filter applied |

### JobListContext

**Purpose**: Template context for jobs.html

**Location**: `src/vpo/server/ui/models.py`

| Field | Type | Description |
|-------|------|-------------|
| status_options | list[dict] | Available status filter options |
| type_options | list[dict] | Available type filter options |
| time_options | list[dict] | Available time range options |

## State Transitions

Jobs follow this state machine (existing, not modified by this feature):

```
[created] → QUEUED → RUNNING → COMPLETED
                  ↘         ↗
                   → FAILED
                  ↘
                   → CANCELLED
```

The dashboard displays all states without modification.

## Data Volume Assumptions

| Metric | Expected Value |
|--------|----------------|
| Typical job count | 100-500 |
| Maximum job count | 10,000+ |
| Page size | 50 (configurable 1-100) |
| Retention | Jobs persist until explicit cleanup |
