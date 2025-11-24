# Quickstart: File Detail View

**Feature**: 020-file-detail-view
**Date**: 2025-11-23

## Overview

This document provides implementation guidance for the file detail view feature, including code patterns to follow and verification steps.

## Prerequisites

- VPO development environment set up (`uv pip install -e ".[dev]"`)
- Rust extension built (`uv run maturin develop`)
- Database initialized with test data (run a scan against sample media)

## Implementation Order

### Phase 1: Database Layer

1. Add `get_file_by_id()` to `src/video_policy_orchestrator/db/models.py`
2. Add `get_transcriptions_for_tracks()` to retrieve transcription data by track IDs
3. Test with existing database

### Phase 2: UI Models

1. Add to `src/video_policy_orchestrator/server/ui/models.py`:
   - `TrackDetailItem` dataclass
   - `TrackTranscriptionInfo` dataclass
   - `FileDetailItem` dataclass
   - `FileDetailResponse` dataclass
   - `FileDetailContext` dataclass
   - `format_file_size()` helper function

### Phase 3: Route Handlers

1. Add to `src/video_policy_orchestrator/server/ui/routes.py`:
   - `file_detail_handler()` - HTML page handler
   - `api_file_detail_handler()` - JSON API handler
   - Route registration in `setup_ui_routes()`

### Phase 4: Template

1. Create `src/video_policy_orchestrator/server/ui/templates/sections/file_detail.html`
2. Follow structure of `job_detail.html` as reference

### Phase 5: Library List Integration

1. Update library.html template to make file rows clickable
2. Add JavaScript to handle row click navigation

## Code Patterns

### Model Pattern (from JobDetailItem)

```python
@dataclass
class FileDetailItem:
    """Full file data for detail view API response."""

    id: int
    path: str
    # ... other fields

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "path": self.path,
            # ... other fields
        }
```

### Handler Pattern (from job_detail_handler)

```python
async def file_detail_handler(request: web.Request) -> dict:
    """Handle GET /library/{file_id} - File detail HTML page."""
    import asyncio
    from video_policy_orchestrator.db.connection import DaemonConnectionPool

    file_id_str = request.match_info["file_id"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid file ID format")

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        raise web.HTTPServiceUnavailable(reason="Database not available")

    # Query file from database
    def _query_file():
        with connection_pool.transaction() as conn:
            file_record = get_file_by_id(conn, file_id)
            if file_record is None:
                return None, [], {}
            tracks = get_tracks_for_file(conn, file_record.id)
            # Get transcriptions for audio tracks
            audio_track_ids = [t.id for t in tracks if t.track_type == "audio"]
            transcriptions = get_transcriptions_for_tracks(conn, audio_track_ids)
            return file_record, tracks, transcriptions

    file_record, tracks, transcriptions = await asyncio.to_thread(_query_file)

    if file_record is None:
        raise web.HTTPNotFound(reason="File not found")

    # Build FileDetailItem...
```

### Route Registration Pattern

```python
def setup_ui_routes(app: web.Application) -> None:
    # ... existing routes ...

    # File detail routes (020-file-detail-view)
    app.router.add_get(
        "/library/{file_id}",
        aiohttp_jinja2.template("sections/file_detail.html")(file_detail_handler),
    )
    app.router.add_get("/api/library/{file_id}", api_file_detail_handler)
```

### Template Pattern (from job_detail.html)

```html
{% extends "base.html" %}

{% block content %}
<div class="section-header">
    <a href="{{ back_url }}" class="back-link">&larr; Back to Library</a>
    <h1>{{ file.filename }}</h1>
</div>

<div class="file-info">
    <div class="info-row">
        <span class="label">Path:</span>
        <span class="value">{{ file.path }}</span>
    </div>
    <!-- More info rows -->
</div>

{% if file.video_tracks %}
<div class="track-section {% if file.has_many_tracks %}collapsible{% endif %}">
    <h2>Video Tracks ({{ file.video_tracks|length }})</h2>
    <!-- Track list -->
</div>
{% endif %}

<!-- Audio, subtitle, other track sections -->
{% endblock %}
```

## Verification Steps

### Unit Tests

```bash
# Run unit tests for new models
uv run pytest tests/unit/test_file_detail_models.py -v

# Run existing model tests to ensure no regression
uv run pytest tests/unit/ -v
```

### Integration Tests

```bash
# Run API endpoint tests
uv run pytest tests/integration/test_file_detail_api.py -v

# Test with running server
uv run vpo serve --port 8080
# Then visit http://localhost:8080/library
# Click on a file to view detail page
```

### Manual Verification

1. Start the daemon: `uv run vpo serve --port 8080`
2. Scan a directory: `uv run vpo scan /path/to/videos`
3. Open http://localhost:8080/library
4. Click on a file row → should navigate to `/library/{id}`
5. Verify:
   - File metadata displays correctly
   - All tracks are grouped by type
   - Default/forced badges appear for flagged tracks
   - Back button returns to Library (with filters preserved)
   - Collapsible sections work for files with 5+ tracks

### Error Cases

1. Navigate to `/library/999999` (non-existent ID) → should show 404
2. Navigate to `/library/abc` (invalid format) → should show 400
3. Stop database and try to load page → should show 503

## Common Issues

### Issue: Track data not showing

**Check**: Ensure `get_tracks_for_file()` is being called after getting the file record.

### Issue: Transcription data missing

**Check**: Verify audio track IDs are being passed to transcription query. Transcription data is optional.

### Issue: Back button loses filters

**Check**: Ensure `FileDetailContext.from_file_and_request()` is correctly parsing referer URL.

## Files to Modify

| File | Changes |
|------|---------|
| `db/models.py` | Add `get_file_by_id()`, `get_transcriptions_for_tracks()` |
| `server/ui/models.py` | Add 5 new dataclasses + helpers |
| `server/ui/routes.py` | Add 2 handlers + route registration |
| `server/ui/templates/sections/file_detail.html` | New template |
| `server/ui/templates/sections/library.html` | Add row click handler |
| `server/static/js/library.js` | Add row navigation JavaScript |
