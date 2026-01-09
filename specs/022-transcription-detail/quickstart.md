# Quickstart: Transcription Detail View

**Feature**: 022-transcription-detail
**Date**: 2025-11-24

## Overview

This guide helps developers quickly understand and implement the transcription detail view feature. The feature follows established patterns from existing detail views (job detail, file detail).

## Prerequisites

- VPO development environment set up (`uv pip install -e ".[dev]"`)
- SQLite database with transcription_results data (run `uv run vpo transcribe` on test files)
- Familiarity with aiohttp, Jinja2, and the existing UI patterns

## Key Files to Modify

| File | Changes |
|------|---------|
| `src/vpo/db/models.py` | Add `get_transcription_detail()` query |
| `src/vpo/server/ui/models.py` | Add `TranscriptionDetailItem`, `TranscriptionDetailContext`, helper functions |
| `src/vpo/server/ui/routes.py` | Add `transcription_detail_handler`, `api_transcription_detail_handler`, route registration |
| `src/vpo/server/ui/templates/sections/transcription_detail.html` | New template |

## Implementation Steps

### 1. Database Query (db/models.py)

Add the query function after existing transcription functions:

```python
def get_transcription_detail(
    conn: sqlite3.Connection,
    transcription_id: int,
) -> dict | None:
    """Get transcription detail with track and file info."""
    cursor = conn.execute(
        """
        SELECT
            tr.id, tr.track_id, tr.detected_language, tr.confidence_score,
            tr.track_type, tr.transcript_sample, tr.plugin_name,
            tr.created_at, tr.updated_at,
            t.track_index, t.codec, t.language AS original_language,
            t.title, t.channels, t.channel_layout, t.is_default, t.is_forced,
            f.id AS file_id, f.filename, f.path
        FROM transcription_results tr
        JOIN tracks t ON tr.track_id = t.id
        JOIN files f ON t.file_id = f.id
        WHERE tr.id = ?
        """,
        (transcription_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None
```

### 2. UI Models (server/ui/models.py)

Add after the existing `TranscriptionListResponse` class:

```python
@dataclass
class TranscriptionDetailItem:
    """Full transcription data for detail view."""
    id: int
    track_id: int
    detected_language: str | None
    confidence_score: float
    confidence_level: str
    track_classification: str
    transcript_sample: str | None
    transcript_html: str | None
    transcript_truncated: bool
    plugin_name: str
    created_at: str
    updated_at: str
    # Track metadata
    track_index: int
    track_codec: str | None
    original_language: str | None
    track_title: str | None
    channels: int | None
    channel_layout: str | None
    is_default: bool
    is_forced: bool
    # Classification
    is_commentary: bool
    classification_source: str | None
    matched_keywords: list[str]
    # Parent file
    file_id: int
    filename: str
    file_path: str

    @property
    def confidence_percent(self) -> int:
        return int(self.confidence_score * 100)

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence_score < 0.3

    def to_dict(self) -> dict:
        # ... (see data-model.md for full implementation)
```

### 3. Route Handlers (server/ui/routes.py)

Add handlers following the pattern from `file_detail_handler`:

```python
async def transcription_detail_handler(request: web.Request) -> dict:
    """Handle GET /transcriptions/{transcription_id} - Transcription detail HTML page."""
    # 1. Validate ID format (must be positive integer)
    # 2. Query database using connection_pool.transaction()
    # 3. Return 404 if not found
    # 4. Build TranscriptionDetailItem from data
    # 5. Create context with back_url from referer
    # 6. Return template context
    pass

async def api_transcription_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/transcriptions/{transcription_id} - JSON API."""
    # Similar pattern, return JSON response
    pass
```

Register routes in `setup_ui_routes()`:
```python
# Transcription detail routes (022-transcription-detail)
app.router.add_get(
    "/transcriptions/{transcription_id}",
    aiohttp_jinja2.template("sections/transcription_detail.html")(transcription_detail_handler),
)
app.router.add_get("/api/transcriptions/{transcription_id}", api_transcription_detail_handler)
```

### 4. Template (templates/sections/transcription_detail.html)

Follow the structure from `file_detail.html`:

```html
{% extends "base.html" %}

{% block content %}
<div class="section-header">
    <a href="{{ back_url }}" class="back-link">← {{ back_label }}</a>
    <h1>Transcription: Track {{ transcription.track_index }}</h1>
</div>

<div class="detail-grid">
    <!-- Track Metadata Card -->
    <div class="detail-card">
        <h2>Track Information</h2>
        <dl>
            <dt>Track Index</dt><dd>{{ transcription.track_index }}</dd>
            <dt>Codec</dt><dd>{{ transcription.track_codec or "—" }}</dd>
            <dt>Original Language</dt><dd>{{ transcription.original_language or "—" }}</dd>
            <!-- etc. -->
        </dl>
    </div>

    <!-- Detection Results Card -->
    <div class="detail-card">
        <h2>Language Detection</h2>
        <dl>
            <dt>Detected Language</dt><dd>{{ transcription.detected_language or "Unknown" }}</dd>
            <dt>Confidence</dt>
            <dd class="confidence-{{ transcription.confidence_level }}">
                {{ transcription.confidence_percent }}%
                {% if transcription.is_low_confidence %}
                <span class="warning-badge">Low confidence</span>
                {% endif %}
            </dd>
            <dt>Classification</dt>
            <dd>{{ transcription.track_classification | title }}</dd>
        </dl>
    </div>

    <!-- Commentary Reasoning Card (if commentary) -->
    {% if transcription.is_commentary %}
    <div class="detail-card">
        <h2>Commentary Detection</h2>
        <p>Classified via: {{ transcription.classification_source }}</p>
        <ul>
            {% for keyword in transcription.matched_keywords %}
            <li>{{ keyword }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}

    <!-- Transcript Text Card -->
    <div class="detail-card full-width">
        <h2>Transcription Text</h2>
        {% if transcription.transcript_html %}
        <div class="transcript-content">
            {{ transcription.transcript_html | safe }}
        </div>
        {% if transcription.transcript_truncated %}
        <p class="truncation-notice">Text truncated. Full sample not available.</p>
        {% endif %}
        {% else %}
        <p class="empty-state">No transcription text available.</p>
        {% endif %}
    </div>
</div>
{% endblock %}
```

## Testing

### Manual Testing

1. Start the server: `uv run vpo serve --port 8080`
2. Transcribe some files: `uv run vpo transcribe /path/to/videos`
3. Navigate to `/transcriptions` and click a file to see track details
4. Or go to `/library/{file_id}` and click a transcription entry

### Unit Tests

```python
# tests/unit/server/ui/test_transcription_detail_models.py
def test_transcription_detail_item_confidence_percent():
    item = TranscriptionDetailItem(confidence_score=0.85, ...)
    assert item.confidence_percent == 85

def test_transcription_detail_item_is_low_confidence():
    low = TranscriptionDetailItem(confidence_score=0.2, ...)
    high = TranscriptionDetailItem(confidence_score=0.9, ...)
    assert low.is_low_confidence
    assert not high.is_low_confidence
```

### Integration Tests

```python
# tests/integration/server/test_transcription_detail_routes.py
async def test_transcription_detail_returns_404_for_invalid_id(client):
    response = await client.get("/api/transcriptions/999999")
    assert response.status == 404

async def test_transcription_detail_returns_data(client, db_with_transcription):
    response = await client.get("/api/transcriptions/1")
    assert response.status == 200
    data = await response.json()
    assert "transcription" in data
```

## Common Patterns

### ID Validation Pattern

```python
try:
    transcription_id = int(transcription_id_str)
    if transcription_id < 1:
        raise ValueError("Invalid ID")
except ValueError:
    raise web.HTTPBadRequest(reason="Invalid transcription ID format")
```

### Database Query Pattern

```python
def _query_transcription():
    with connection_pool.transaction() as conn:
        return get_transcription_detail(conn, transcription_id)

data = await asyncio.to_thread(_query_transcription)
```

### Back URL Pattern

```python
referer = request.headers.get("Referer")
context = TranscriptionDetailContext.from_transcription_and_request(item, referer)
```

## Related Documentation

- [spec.md](./spec.md) - Feature specification
- [data-model.md](./data-model.md) - Data model details
- [research.md](./research.md) - Research findings
- [020-file-detail-view](../020-file-detail-view/) - Similar implementation pattern
- [021-transcriptions-list](../021-transcriptions-list/) - List view this links from
