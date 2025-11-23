# Research: Jobs Dashboard List View

**Feature**: 015-jobs-dashboard
**Date**: 2025-11-23
**Status**: Complete

## Research Tasks

### 1. Existing Jobs Database Schema

**Decision**: Use existing jobs table schema (v7) without modification

**Rationale**: The existing schema already contains all required fields:
- `id` (TEXT PRIMARY KEY) - Job ID column
- `job_type` (TEXT) - Type column (scan, apply, transcode, move)
- `status` (TEXT) - Status column (queued, running, completed, failed, cancelled)
- `created_at` (TEXT) - Start time (ISO-8601 UTC)
- `completed_at` (TEXT) - End time (nullable for running jobs)
- `file_path` (TEXT) - Target column

**Alternatives Considered**:
- Adding a duration column: Rejected - can be computed from created_at and completed_at/now
- Adding a display_name column: Rejected - file_path already serves this purpose

### 2. API Pattern for Jobs Listing

**Decision**: Follow existing `/api/about` pattern with JSON response

**Rationale**:
- Consistent with existing API structure in app.py
- Returns `web.json_response()` for JSON endpoints
- Handler registered in app.py alongside other API routes
- Supports query parameters for filtering

**Alternatives Considered**:
- GraphQL: Rejected - over-engineering for simple list/filter use case
- Server-side rendering only: Rejected - filtering needs client-side interactivity

### 3. Pagination Strategy

**Decision**: Offset-based pagination with limit/offset query parameters

**Rationale**:
- Simple to implement with SQLite LIMIT/OFFSET
- Existing `get_jobs_filtered()` supports limit parameter
- Standard REST pattern familiar to API consumers

**Alternatives Considered**:
- Cursor-based pagination: Rejected - unnecessary complexity for low-volume job lists
- Infinite scroll: Rejected - table layout better suited to page-based navigation

### 4. Time Range Filter Implementation

**Decision**: Predefined options ("last 24 hours", "last 7 days", "all time") with UTC comparison

**Rationale**:
- Matches spec requirements exactly
- Simple client-side selection, server-side datetime calculation
- Uses existing `get_jobs_filtered(since=datetime)` parameter

**Alternatives Considered**:
- Custom date range picker: Rejected - adds complexity; predefined options meet requirements
- Client-side filtering: Rejected - inefficient for large job lists

### 5. Duration Display for Running Jobs

**Decision**: Calculate elapsed time client-side for running jobs using JavaScript

**Rationale**:
- Provides real-time updates without page refresh
- Server provides `created_at` timestamp; client calculates "X minutes ago"
- Completed jobs show static duration from DB

**Alternatives Considered**:
- Server-side calculation on every render: Rejected - stale immediately after render
- WebSocket updates: Rejected - out of scope per spec (no live updates)

### 6. Template Rendering Approach

**Decision**: Hybrid server-side + client-side rendering

**Rationale**:
- Initial page load: Server renders empty shell with filters
- Jobs data: Fetched via `/api/jobs` JavaScript call
- Enables filter changes without full page reload
- Follows progressive enhancement pattern

**Alternatives Considered**:
- Pure server-side: Rejected - requires page reload for every filter change
- Pure client-side SPA: Rejected - inconsistent with existing architecture

### 7. Error Handling for Empty States

**Decision**: Distinct messages for "no jobs" vs "no matching jobs"

**Rationale**:
- Matches FR-010 and FR-011 requirements
- Server returns `{jobs: [], total: 0, has_filters: true/false}`
- Client displays appropriate message based on `has_filters` flag

**Alternatives Considered**:
- Single generic message: Rejected - poor UX, doesn't guide user to clear filters

## Dependencies

### Existing Code to Leverage

| Component | Location | Purpose |
|-----------|----------|---------|
| DaemonConnectionPool | `server/lifecycle.py` | Thread-safe DB access |
| get_jobs_filtered() | `db/operations.py` | Query with filters |
| JobStatus, JobType | `db/models.py` | Enum definitions |
| _create_template_context() | `server/ui/routes.py` | Template context helper |
| base.html | `templates/base.html` | Layout template |
| main.css | `static/css/main.css` | Existing styles |

### New Components Required

| Component | Purpose |
|-----------|---------|
| api_jobs_handler() | JSON API endpoint |
| JobListContext | Template context model |
| JobFilterParams | Query parameter validation |
| jobs.html | Full jobs template |
| jobs.js | Client-side filtering/pagination |
| jobs table styles | CSS for table layout |

## Technical Notes

### Query Parameters for /api/jobs

```
GET /api/jobs?status=failed&type=transcode&since=24h&limit=50&offset=0
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | (all) | Filter by status: queued, running, completed, failed, cancelled |
| type | string | (all) | Filter by type: scan, apply, transcode, move |
| since | string | (all) | Time filter: 24h, 7d, all |
| limit | int | 50 | Page size |
| offset | int | 0 | Pagination offset |

### Response Format

```json
{
  "jobs": [
    {
      "id": "uuid",
      "type": "transcode",
      "status": "completed",
      "created_at": "2025-01-15T14:30:00Z",
      "completed_at": "2025-01-15T14:35:00Z",
      "file_path": "/path/to/file.mkv",
      "progress_percent": 100.0
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_filters": true
}
```

### Status Visual Mapping

| Status | Color | Icon |
|--------|-------|------|
| queued | gray | clock |
| running | blue | spinner |
| completed | green | checkmark |
| failed | red | x |
| cancelled | orange | ban |
