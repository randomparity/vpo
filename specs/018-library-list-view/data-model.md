# Data Model: Library List View

**Feature**: 018-library-list-view
**Date**: 2025-11-23

## Overview

This document defines the data models for the Library list view feature. The feature leverages existing database schema (files and tracks tables) and adds new view models for API responses and template rendering.

## Existing Database Entities (No Changes)

### FileRecord (files table)

Already defined in `db/models.py`. Key fields for Library view:

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| path | str | Full file path |
| filename | str | Filename only |
| directory | str | Parent directory |
| extension | str | File extension |
| size_bytes | int | File size |
| scanned_at | str | ISO-8601 UTC timestamp |
| scan_status | str | "ok", "error", "pending" |
| scan_error | str | Error message if scan_status == "error" |

### TrackRecord (tracks table)

Already defined in `db/models.py`. Key fields for Library view:

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| file_id | int | Foreign key to files |
| track_type | str | "video", "audio", "subtitle" |
| codec | str | Codec name |
| language | str | ISO 639-2 language code |
| title | str | Track title |
| width | int | Video width (video tracks only) |
| height | int | Video height (video tracks only) |

## New View Models (server/ui/models.py)

### LibraryFilterParams

Query parameter validation for `/api/library` endpoint.

```python
@dataclass
class LibraryFilterParams:
    """Validate and parse query parameters for /api/library.

    Attributes:
        status: Filter by scan status (None = all, "ok", "error").
        limit: Page size (1-100, default 50).
        offset: Pagination offset (>= 0, default 0).
    """

    status: str | None = None
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, query: dict) -> LibraryFilterParams:
        """Create LibraryFilterParams from request query dict."""
        try:
            limit = int(query.get("limit", 50))
            limit = max(1, min(100, limit))
        except (ValueError, TypeError):
            limit = 50

        try:
            offset = int(query.get("offset", 0))
            offset = max(0, offset)
        except (ValueError, TypeError):
            offset = 0

        status = query.get("status")
        if status not in (None, "", "ok", "error"):
            status = None

        return cls(
            status=status if status else None,
            limit=limit,
            offset=offset,
        )
```

### FileListItem

File data for API response and template rendering.

```python
@dataclass
class FileListItem:
    """File data for Library API response.

    Attributes:
        id: Database file ID.
        filename: Short filename for display.
        path: Full file path (for tooltip).
        title: Track title if available, else None.
        resolution: Human-readable resolution (e.g., "1080p", "4K").
        audio_languages: Formatted language list (e.g., "eng, jpn").
        scanned_at: ISO-8601 UTC timestamp.
        scan_status: "ok" or "error".
        scan_error: Error message if scan_status == "error".
    """

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
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "filename": self.filename,
            "path": self.path,
            "title": self.title,
            "resolution": self.resolution,
            "audio_languages": self.audio_languages,
            "scanned_at": self.scanned_at,
            "scan_status": self.scan_status,
            "scan_error": self.scan_error,
        }
```

### FileListResponse

API response wrapper with pagination metadata.

```python
@dataclass
class FileListResponse:
    """API response wrapper for /api/library.

    Attributes:
        files: File items for current page.
        total: Total files matching filters.
        limit: Page size used.
        offset: Current offset.
        has_filters: True if any filter was applied.
    """

    files: list[FileListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "files": [f.to_dict() for f in self.files],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
        }
```

### LibraryContext

Template context for library.html.

```python
@dataclass
class LibraryContext:
    """Template context for library.html.

    Attributes:
        status_options: Available scan status filter options.
    """

    status_options: list[dict]

    @classmethod
    def default(cls) -> LibraryContext:
        """Create default context with filter options."""
        return cls(
            status_options=[
                {"value": "", "label": "All files"},
                {"value": "ok", "label": "Scanned OK"},
                {"value": "error", "label": "Scan errors"},
            ],
        )
```

## Database Query Function (db/models.py)

### get_files_filtered()

New function for paginated file queries with track aggregation.

```python
def get_files_filtered(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    """Get files with track metadata for Library view.

    Returns file records with aggregated track data (resolution, languages).

    Args:
        conn: Database connection.
        status: Filter by scan_status (None = all, "ok", "error").
        limit: Maximum files to return.
        offset: Pagination offset.
        return_total: If True, return tuple of (files, total_count).

    Returns:
        List of file dicts with track data, or tuple with total count.
    """
```

**Query Structure**:

```sql
-- Main query with track aggregation
SELECT
    f.id,
    f.path,
    f.filename,
    f.scanned_at,
    f.scan_status,
    f.scan_error,
    -- First video track title (for display title)
    (SELECT title FROM tracks WHERE file_id = f.id AND track_type = 'video' LIMIT 1) as video_title,
    -- Primary video resolution
    (SELECT width FROM tracks WHERE file_id = f.id AND track_type = 'video' LIMIT 1) as width,
    (SELECT height FROM tracks WHERE file_id = f.id AND track_type = 'video' LIMIT 1) as height,
    -- Aggregated audio languages (comma-separated)
    (SELECT GROUP_CONCAT(DISTINCT language)
     FROM tracks WHERE file_id = f.id AND track_type = 'audio') as audio_languages
FROM files f
WHERE 1=1
    [AND f.scan_status = ?]  -- optional status filter
ORDER BY f.scanned_at DESC
LIMIT ? OFFSET ?
```

## Helper Functions (server/ui/models.py)

### get_resolution_label()

```python
def get_resolution_label(width: int | None, height: int | None) -> str:
    """Map video dimensions to human-readable resolution label.

    Args:
        width: Video width in pixels.
        height: Video height in pixels.

    Returns:
        Resolution label (e.g., "1080p", "4K") or "—" if unknown.
    """
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
    else:
        return "—"
```

### format_audio_languages()

```python
def format_audio_languages(languages_csv: str | None) -> str:
    """Format comma-separated language codes for display.

    Args:
        languages_csv: Comma-separated language codes from GROUP_CONCAT.

    Returns:
        Formatted string (e.g., "eng, jpn" or "eng, jpn +2 more").
    """
    if not languages_csv:
        return "—"

    languages = [lang.strip() for lang in languages_csv.split(",") if lang.strip()]

    if not languages:
        return "—"

    if len(languages) <= 3:
        return ", ".join(languages)

    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"
```

## Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  GET /api/      │     │  get_files_      │     │  files +        │
│  library?       │────▶│  filtered()      │────▶│  tracks tables  │
│  status&limit   │     │  (db/models.py)  │     │  (SQLite)       │
└────────┬────────┘     └────────┬─────────┘     └─────────────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         │              │  Raw file rows   │
         │              │  + track data    │
         │              └────────┬─────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         │              │  FileListItem    │
         │              │  (with computed  │
         │              │  resolution &    │
         │              │  languages)      │
         │              └────────┬─────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌──────────────────┐
│  FileList       │◀────│  Transform &     │
│  Response       │     │  format          │
│  (JSON)         │     │  (view models)   │
└─────────────────┘     └──────────────────┘
```

## Validation Rules

| Field | Rule | Error Handling |
|-------|------|----------------|
| limit | 1-100, default 50 | Clamp to bounds |
| offset | >= 0, default 0 | Clamp to 0 |
| status | "ok", "error", or null | Ignore invalid values |
| resolution | Computed from width/height | Return "—" if missing |
| audio_languages | From GROUP_CONCAT | Return "—" if no audio tracks |

## State Transitions

Files table `scan_status` values:

```
┌─────────┐
│ pending │ ──── (scan starts) ────▶ ┌───────────┐
└─────────┘                          │  (scan    │
                                     │  running) │
                                     └─────┬─────┘
                                           │
                         ┌─────────────────┴─────────────────┐
                         │                                   │
                         ▼                                   ▼
                    ┌─────────┐                        ┌─────────┐
                    │   ok    │                        │  error  │
                    └─────────┘                        └─────────┘
                         │                                   │
                         │                                   │
                         └─────── (rescan) ──────────────────┘
                                     │
                                     ▼
                               ┌─────────┐
                               │ pending │
                               └─────────┘
```

## Index Requirements

Existing indexes should be sufficient:

| Table | Index | Purpose |
|-------|-------|---------|
| files | PRIMARY KEY (id) | Lookup by ID |
| files | UNIQUE (path) | Lookup by path |
| files | (scanned_at) | Sort by scan time |
| tracks | (file_id) | Join to files |
| tracks | (file_id, track_type) | Filter by track type |

If performance issues arise with large libraries, consider:
- Composite index on `files(scan_status, scanned_at DESC)`
