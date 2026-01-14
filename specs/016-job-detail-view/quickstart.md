# Quickstart: Job Detail View with Logs

**Feature**: 016-job-detail-view
**Date**: 2025-11-23

## Overview

This feature adds a job detail view to the VPO web UI, accessible from the Jobs dashboard. The detail view shows full job metadata, human-readable summaries, and log output.

## Key Components

### 1. Database Migration (v7 → v8)

Add `log_path` column to jobs table:

```python
# src/vpo/db/schema.py

def migrate_v7_to_v8(conn: sqlite3.Connection) -> None:
    """Add log_path column to jobs table."""
    cursor = conn.execute("PRAGMA table_info(jobs)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "log_path" not in existing_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN log_path TEXT")

    conn.execute("UPDATE _meta SET value = '8' WHERE key = 'schema_version'")
    conn.commit()
```

### 2. Log File Utilities

New module for log file operations:

```python
# src/vpo/jobs/logs.py

from pathlib import Path

def get_log_directory() -> Path:
    """Get the logs directory path."""
    from vpo.config.loader import get_data_dir
    return get_data_dir() / "logs"

def get_log_path(job_id: str) -> Path:
    """Get the log file path for a job."""
    return get_log_directory() / f"{job_id}.log"

def read_log_tail(job_id: str, lines: int = 500, offset: int = 0) -> tuple[list[str], int, bool]:
    """Read log lines from end of file.

    Returns:
        Tuple of (lines, total_lines, has_more)
    """
    log_path = get_log_path(job_id)
    if not log_path.exists():
        return [], 0, False

    # Read all lines and return requested chunk
    all_lines = log_path.read_text().splitlines()
    total = len(all_lines)

    # Calculate slice indices
    start = offset
    end = offset + lines
    chunk = all_lines[start:end]
    has_more = end < total

    return chunk, total, has_more
```

### 3. API Routes

Add new route handlers:

```python
# src/vpo/server/ui/routes.py

async def job_detail_handler(request: web.Request) -> dict:
    """Handle GET /jobs/{job_id} - Job detail page."""
    job_id = request.match_info["job_id"]
    # Fetch job, generate summary, return template context
    ...

async def api_job_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs/{job_id} - Job detail JSON."""
    job_id = request.match_info["job_id"]
    # Validate UUID, fetch job, return JSON response
    ...

async def api_job_logs_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs/{job_id}/logs - Job logs JSON."""
    job_id = request.match_info["job_id"]
    lines = int(request.query.get("lines", 500))
    offset = int(request.query.get("offset", 0))
    # Read logs, return paginated response
    ...
```

### 4. Template Structure

```html
<!-- templates/sections/job_detail.html -->
{% extends "base.html" %}

{% block content %}
<div class="job-detail">
    <!-- Back navigation -->
    <a href="{{ back_url }}" class="job-detail-back">← Back to Jobs</a>

    <!-- Job header with status badge -->
    <header class="job-detail-header">
        <h1>Job {{ job.id_short }}</h1>
        <span class="status-badge status-{{ job.status }}">{{ job.status }}</span>
    </header>

    <!-- Metadata section -->
    <section class="job-detail-meta">
        <dl>
            <dt>Type</dt><dd>{{ job.job_type }}</dd>
            <dt>Target</dt><dd>{{ job.file_path }}</dd>
            <dt>Created</dt><dd data-timestamp="{{ job.created_at }}">{{ job.created_at }}</dd>
            <!-- ... more fields ... -->
        </dl>
    </section>

    <!-- Summary section -->
    <section class="job-detail-summary">
        <h2>Summary</h2>
        <p>{{ job.summary or "No summary available" }}</p>
    </section>

    <!-- Logs section -->
    <section class="job-detail-logs">
        <h2>Logs</h2>
        <div id="logs-container" class="logs-container">
            <!-- Loaded by JavaScript -->
        </div>
        <button id="load-more-logs" style="display: none;">Load More</button>
    </section>
</div>

<script src="/static/js/job_detail.js"></script>
{% endblock %}
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/jobs/test_logs.py

def test_get_log_path():
    """Test log path generation."""
    path = get_log_path("550e8400-e29b-41d4-a716-446655440000")
    assert path.name == "550e8400-e29b-41d4-a716-446655440000.log"

def test_read_log_tail_missing_file():
    """Test reading non-existent log file."""
    lines, total, has_more = read_log_tail("nonexistent-id")
    assert lines == []
    assert total == 0
    assert has_more is False
```

### Integration Tests

```python
# tests/integration/test_job_detail_api.py

async def test_get_job_detail(client, sample_job):
    """Test job detail API endpoint."""
    response = await client.get(f"/api/jobs/{sample_job.id}")
    assert response.status == 200
    data = await response.json()
    assert data["id"] == sample_job.id

async def test_get_job_not_found(client):
    """Test 404 for missing job."""
    response = await client.get("/api/jobs/nonexistent-uuid")
    assert response.status == 404
```

## File Checklist

New files to create:
- [ ] `src/vpo/jobs/logs.py`
- [ ] `src/vpo/server/ui/templates/sections/job_detail.html`
- [ ] `src/vpo/server/static/js/job_detail.js`
- [ ] `tests/unit/jobs/test_logs.py`
- [ ] `tests/unit/server/ui/test_job_detail_routes.py`
- [ ] `tests/integration/test_job_detail_api.py`

Files to modify:
- [ ] `src/vpo/db/models.py` - Add log_path to Job
- [ ] `src/vpo/db/schema.py` - Add v7→v8 migration
- [ ] `src/vpo/server/ui/models.py` - Add JobDetailItem, JobLogsResponse
- [ ] `src/vpo/server/ui/routes.py` - Add new handlers
- [ ] `src/vpo/server/ui/templates/sections/jobs.html` - Add row click handler
