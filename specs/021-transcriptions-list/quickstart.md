# Quickstart: Transcriptions Overview List

**Feature**: 021-transcriptions-list
**Date**: 2025-11-24

## Prerequisites

- VPO development environment set up (`uv pip install -e ".[dev]"`)
- SQLite database with existing files and transcription results
- Web daemon running (`uv run vpo serve --port 8080`)

## Quick Implementation Guide

### 1. Database Query (db/models.py)

Add the query function after `get_distinct_audio_languages()`:

```python
def get_files_with_transcriptions(
    conn: sqlite3.Connection,
    *,
    show_all: bool = False,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    """Get files with aggregated transcription data."""
    # Build WHERE clause
    where_clause = ""
    if not show_all:
        where_clause = """
        HAVING COUNT(tr.id) > 0
        """

    # Count query
    if return_total:
        count_query = """
            SELECT COUNT(*) FROM (
                SELECT f.id
                FROM files f
                LEFT JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
                LEFT JOIN transcription_results tr ON t.id = tr.track_id
                GROUP BY f.id
                """ + where_clause + """
            )
        """
        cursor = conn.execute(count_query)
        total = cursor.fetchone()[0]

    # Main query
    query = """
        SELECT
            f.id, f.filename, f.path, f.scan_status,
            COUNT(tr.id) as transcription_count,
            GROUP_CONCAT(DISTINCT tr.detected_language) as detected_languages,
            AVG(tr.confidence_score) as avg_confidence
        FROM files f
        LEFT JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
        LEFT JOIN transcription_results tr ON t.id = tr.track_id
        GROUP BY f.id
        """ + where_clause + """
        ORDER BY f.filename
    """

    # Add pagination
    if limit is not None:
        query += f" LIMIT {limit}"
        if offset is not None:
            query += f" OFFSET {offset}"

    cursor = conn.execute(query)
    files = [
        {
            "id": row[0],
            "filename": row[1],
            "path": row[2],
            "scan_status": row[3],
            "transcription_count": row[4],
            "detected_languages": row[5],
            "avg_confidence": row[6],
        }
        for row in cursor.fetchall()
    ]

    if return_total:
        return files, total
    return files
```

### 2. UI Models (server/ui/models.py)

Add after `FileDetailContext`:

```python
def get_confidence_level(confidence: float | None) -> str | None:
    """Map confidence score to categorical level."""
    if confidence is None:
        return None
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


@dataclass
class TranscriptionFilterParams:
    show_all: bool = False
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, query: dict) -> TranscriptionFilterParams:
        show_all = query.get("show_all", "").lower() == "true"
        try:
            limit = max(1, min(100, int(query.get("limit", 50))))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(query.get("offset", 0)))
        except (ValueError, TypeError):
            offset = 0
        return cls(show_all=show_all, limit=limit, offset=offset)


@dataclass
class TranscriptionListItem:
    id: int
    filename: str
    path: str
    has_transcription: bool
    detected_languages: list[str]
    confidence_level: str | None
    confidence_avg: float | None
    transcription_count: int
    scan_status: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "path": self.path,
            "has_transcription": self.has_transcription,
            "detected_languages": self.detected_languages,
            "confidence_level": self.confidence_level,
            "confidence_avg": self.confidence_avg,
            "transcription_count": self.transcription_count,
            "scan_status": self.scan_status,
        }


@dataclass
class TranscriptionListResponse:
    files: list[TranscriptionListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        return {
            "files": [f.to_dict() for f in self.files],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
        }
```

### 3. Route Handlers (server/ui/routes.py)

Update the existing `transcriptions_handler` and add API handler:

```python
async def transcriptions_handler(request: web.Request) -> dict:
    """Handle GET /transcriptions - Transcriptions section page."""
    return _create_template_context(
        active_id="transcriptions",
        section_title="Transcriptions",
    )


async def api_transcriptions_handler(request: web.Request) -> web.Response:
    """Handle GET /api/transcriptions - Transcriptions API endpoint."""
    from video_policy_orchestrator.db.models import get_files_with_transcriptions

    params = TranscriptionFilterParams.from_query(dict(request.query))

    def _query():
        with get_connection() as conn:
            return get_files_with_transcriptions(
                conn,
                show_all=params.show_all,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )

    files_raw, total = await asyncio.to_thread(_query)

    # Transform to list items
    files = [
        TranscriptionListItem(
            id=f["id"],
            filename=f["filename"],
            path=f["path"],
            has_transcription=f["transcription_count"] > 0,
            detected_languages=(
                f["detected_languages"].split(",")
                if f["detected_languages"]
                else []
            ),
            confidence_level=get_confidence_level(f["avg_confidence"]),
            confidence_avg=f["avg_confidence"],
            transcription_count=f["transcription_count"],
            scan_status=f["scan_status"],
        )
        for f in files_raw
    ]

    response = TranscriptionListResponse(
        files=files,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=params.show_all,
    )

    return web.json_response(response.to_dict())
```

Register the API route in `setup_ui_routes()`:

```python
app.router.add_get("/api/transcriptions", api_transcriptions_handler)
```

### 4. Template (templates/sections/transcriptions.html)

Replace placeholder content - see Library template for structure pattern.

### 5. JavaScript (static/js/transcriptions.js)

Create new file following library.js patterns for:
- Fetching from `/api/transcriptions`
- Rendering table rows
- Pagination controls
- Show all toggle

## Testing

```bash
# Run unit tests
uv run pytest tests/unit/server/test_transcriptions_models.py -v

# Run integration tests
uv run pytest tests/integration/server/test_transcriptions_routes.py -v

# Manual testing
uv run vpo serve --port 8080
# Open http://localhost:8080/transcriptions
```

## Verification Checklist

- [ ] `/api/transcriptions` returns JSON with correct structure
- [ ] Default view shows only files with transcriptions
- [ ] "Show all files" toggle includes files without transcriptions
- [ ] Confidence levels display as high/medium/low
- [ ] Language codes are displayed for each file
- [ ] Clicking a file navigates to `/library/{file_id}`
- [ ] Pagination works correctly
- [ ] Empty state displays appropriate message
