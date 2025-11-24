# Quickstart: Library List View Implementation

**Feature**: 018-library-list-view
**Date**: 2025-11-23

## Overview

This guide provides a quick reference for implementing the Library list view feature. The implementation follows established patterns from the Jobs dashboard.

## Implementation Order

1. **Database query function** (`db/models.py`)
2. **View models** (`server/ui/models.py`)
3. **Route handlers** (`server/ui/routes.py`)
4. **HTML template** (`server/ui/templates/sections/library.html`)
5. **JavaScript** (`server/static/js/library.js`)
6. **CSS styles** (`server/static/css/main.css`)
7. **Tests**

## 1. Database Query Function

**File**: `src/video_policy_orchestrator/db/models.py`

Add after `get_jobs_filtered()`:

```python
def get_files_filtered(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    """Get files with track metadata for Library view."""
    # Build WHERE clause
    conditions = []
    params: list[str | int] = []

    if status is not None:
        conditions.append("f.scan_status = ?")
        params.append(status)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    # Get total count if requested
    total = 0
    if return_total:
        count_query = "SELECT COUNT(*) FROM files f" + where_clause
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

    # Main query with subqueries for track data
    query = """
        SELECT
            f.id,
            f.path,
            f.filename,
            f.scanned_at,
            f.scan_status,
            f.scan_error,
            (SELECT title FROM tracks WHERE file_id = f.id AND track_type = 'video' LIMIT 1) as video_title,
            (SELECT width FROM tracks WHERE file_id = f.id AND track_type = 'video' LIMIT 1) as width,
            (SELECT height FROM tracks WHERE file_id = f.id AND track_type = 'video' LIMIT 1) as height,
            (SELECT GROUP_CONCAT(DISTINCT language) FROM tracks WHERE file_id = f.id AND track_type = 'audio') as audio_languages
        FROM files f
    """
    query += where_clause
    query += " ORDER BY f.scanned_at DESC"

    # Apply pagination
    pagination_params = list(params)
    if limit is not None:
        query += " LIMIT ?"
        pagination_params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            pagination_params.append(offset)

    cursor = conn.execute(query, pagination_params)
    files = [
        {
            "id": row[0],
            "path": row[1],
            "filename": row[2],
            "scanned_at": row[3],
            "scan_status": row[4],
            "scan_error": row[5],
            "video_title": row[6],
            "width": row[7],
            "height": row[8],
            "audio_languages": row[9],
        }
        for row in cursor.fetchall()
    ]

    if return_total:
        return files, total
    return files
```

## 2. View Models

**File**: `src/video_policy_orchestrator/server/ui/models.py`

Add these classes and helper functions:

```python
def get_resolution_label(width: int | None, height: int | None) -> str:
    """Map video dimensions to human-readable resolution label."""
    if width is None or height is None:
        return "—"
    if height >= 2160:
        return "4K"
    elif height >= 1440:
        return "1440p"
    elif height >= 1080:
        return "1080p"
    elif height >= 720:
        return "720p"
    elif height >= 480:
        return "480p"
    elif height > 0:
        return f"{height}p"
    return "—"


def format_audio_languages(languages_csv: str | None) -> str:
    """Format comma-separated language codes for display."""
    if not languages_csv:
        return "—"
    languages = [lang.strip() for lang in languages_csv.split(",") if lang.strip()]
    if not languages:
        return "—"
    if len(languages) <= 3:
        return ", ".join(languages)
    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"


@dataclass
class LibraryFilterParams:
    """Query parameters for /api/library."""
    status: str | None = None
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, query: dict) -> LibraryFilterParams:
        # ... (see data-model.md for full implementation)


@dataclass
class FileListItem:
    """File data for Library API response."""
    id: int
    filename: str
    path: str
    title: str | None
    resolution: str
    audio_languages: str
    scanned_at: str
    scan_status: str
    scan_error: str | None = None

    def to_dict(self) -> dict:
        # ... (see data-model.md)


@dataclass
class FileListResponse:
    """API response for /api/library."""
    files: list[FileListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        # ... (see data-model.md)


@dataclass
class LibraryContext:
    """Template context for library.html."""
    status_options: list[dict]

    @classmethod
    def default(cls) -> LibraryContext:
        return cls(
            status_options=[
                {"value": "", "label": "All files"},
                {"value": "ok", "label": "Scanned OK"},
                {"value": "error", "label": "Scan errors"},
            ],
        )
```

## 3. Route Handlers

**File**: `src/video_policy_orchestrator/server/ui/routes.py`

Add handlers:

```python
@aiohttp_jinja2.template("sections/library.html")
async def library_handler(request: web.Request) -> dict:
    """Render the Library page."""
    return _create_template_context(
        active_id="library",
        section_title="Library",
        library_context=LibraryContext.default(),
    )


async def library_api_handler(request: web.Request) -> web.Response:
    """GET /api/library - List library files with pagination."""
    params = LibraryFilterParams.from_query(dict(request.query))

    def _query_files() -> tuple[list[dict], int]:
        with request.app["db_pool"].transaction() as conn:
            return get_files_filtered(
                conn,
                status=params.status,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )

    files_data, total = await asyncio.to_thread(_query_files)

    # Transform to FileListItem
    files = [
        FileListItem(
            id=f["id"],
            filename=f["filename"],
            path=f["path"],
            title=f["video_title"],
            resolution=get_resolution_label(f["width"], f["height"]),
            audio_languages=format_audio_languages(f["audio_languages"]),
            scanned_at=f["scanned_at"],
            scan_status=f["scan_status"],
            scan_error=f["scan_error"],
        )
        for f in files_data
    ]

    response = FileListResponse(
        files=files,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=params.status is not None,
    )

    return web.json_response(response.to_dict())
```

Register routes in `setup_ui_routes()`:

```python
app.router.add_get("/library", library_handler)
app.router.add_get("/api/library", library_api_handler)
```

## 4. HTML Template

**File**: `src/video_policy_orchestrator/server/ui/templates/sections/library.html`

Replace placeholder content. Use `jobs.html` as reference for structure.

Key elements:
- Filter bar with status dropdown
- Table with columns: Filename, Title, Resolution, Audio, Scanned, Policy
- Empty state message
- Pagination controls

## 5. JavaScript

**File**: `src/video_policy_orchestrator/server/static/js/library.js`

Follow `jobs.js` patterns:
- `fetchLibrary()` - Initial load
- `renderLibraryTable(files)` - Render/update table
- `updatePagination()` - Pagination controls
- Filter change handlers

## 6. CSS

**File**: `src/video_policy_orchestrator/server/static/css/main.css`

Add library-specific classes (mostly mirrors jobs styles):

```css
.library-filters { /* same as .jobs-filters */ }
.library-table { /* same as .jobs-table */ }
.library-empty { /* same as .jobs-empty */ }
.library-pagination { /* same as .jobs-pagination */ }
```

## Testing Checklist

- [ ] Unit tests for `get_files_filtered()` with various filters
- [ ] Unit tests for `get_resolution_label()` edge cases
- [ ] Unit tests for `format_audio_languages()` edge cases
- [ ] Integration test for `/api/library` endpoint
- [ ] Integration test for `/library` HTML page
- [ ] Manual test with empty library
- [ ] Manual test with large library (100+ files)
- [ ] Manual test with scan errors

## Reference Files

| Pattern | Reference File |
|---------|---------------|
| Database query | `db/models.py` → `get_jobs_filtered()` |
| View models | `server/ui/models.py` → `JobListItem`, `JobListResponse` |
| Route handler | `server/ui/routes.py` → `jobs_api_handler()` |
| HTML template | `server/ui/templates/sections/jobs.html` |
| JavaScript | `server/static/js/jobs.js` |
