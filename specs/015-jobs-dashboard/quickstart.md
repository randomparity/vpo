# Quickstart: Jobs Dashboard List View

**Feature**: 015-jobs-dashboard
**Date**: 2025-11-23

## Prerequisites

- Python 3.10+ installed
- VPO development environment set up
- SQLite database with schema v7

## Quick Setup

```bash
# Install dependencies (if not already done)
uv pip install -e ".[dev]"

# Build Rust extension (if needed)
uv run maturin develop

# Start the daemon server
uv run vpo serve --bind 127.0.0.1 --port 8080
```

## Accessing the Jobs Dashboard

1. Open a browser to `http://localhost:8080/jobs`
2. The dashboard displays all recent jobs
3. Use filters to narrow results by status, type, or time range

## API Endpoint

### List Jobs

```bash
# Get all jobs (default: 50 most recent)
curl http://localhost:8080/api/jobs

# Filter by status
curl "http://localhost:8080/api/jobs?status=failed"

# Filter by type
curl "http://localhost:8080/api/jobs?type=transcode"

# Filter by time range
curl "http://localhost:8080/api/jobs?since=24h"

# Combine filters with pagination
curl "http://localhost:8080/api/jobs?status=completed&type=scan&since=7d&limit=20&offset=0"
```

### Response Format

```json
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "job_type": "transcode",
      "status": "completed",
      "file_path": "/media/movies/example.mkv",
      "progress_percent": 100.0,
      "created_at": "2025-01-15T14:30:00Z",
      "completed_at": "2025-01-15T14:35:00Z",
      "duration_seconds": 300
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_filters": false
}
```

## Development Testing

```bash
# Run all tests
uv run pytest

# Run jobs-specific tests
uv run pytest tests/unit/server/ui/test_jobs_routes.py
uv run pytest tests/integration/server/test_jobs_api.py

# Run with coverage
uv run pytest --cov=vpo.server.ui tests/
```

## Key Files

| File | Purpose |
|------|---------|
| `src/vpo/server/app.py` | Route registration |
| `src/vpo/server/ui/routes.py` | Handler implementations |
| `src/vpo/server/ui/models.py` | Data models |
| `src/vpo/server/ui/templates/sections/jobs.html` | HTML template |
| `src/vpo/server/static/js/jobs.js` | Client-side logic |
| `src/vpo/server/static/css/main.css` | Styles |

## Troubleshooting

### No jobs displayed

1. Check if the database has jobs: `sqlite3 ~/.vpo/library.db "SELECT COUNT(*) FROM jobs;"`
2. Verify the daemon is running: `curl http://localhost:8080/health`
3. Check browser console for JavaScript errors

### Filters not working

1. Verify API response: `curl "http://localhost:8080/api/jobs?status=failed"`
2. Check query parameter spelling (case-sensitive)
3. Clear browser cache and reload

### Page loads slowly

1. Check total job count - pagination prevents loading all at once
2. Verify database indexes exist: `sqlite3 ~/.vpo/library.db ".indices jobs"`
3. Consider running job cleanup to remove old completed jobs
