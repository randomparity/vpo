# Data Model: Library Filters and Search

**Feature**: 019-library-filters-search
**Date**: 2025-11-23

## Overview

This feature uses existing database schema (no migrations required). This document describes the data models that will be extended or added for filter/search functionality.

## Existing Entities (No Changes)

### FileRecord (files table)
Already contains all needed fields:
- `id`: Primary key
- `path`: Full file path (searchable)
- `filename`: File name only (searchable)
- `scan_status`: "ok" | "error" (existing filter)

### TrackRecord (tracks table)
Already contains all needed fields:
- `file_id`: Foreign key to files
- `track_type`: "video" | "audio" | "subtitle" | "attachment" | "other"
- `language`: ISO 639 language code (nullable)
- `title`: Track title (searchable)
- `width`, `height`: Video dimensions (for resolution filtering)

## Extended Models

### LibraryFilterParams (Python dataclass)

Extends existing model with new filter parameters.

```python
@dataclass
class LibraryFilterParams:
    """Validate and parse query parameters for /api/library."""

    # Existing fields
    status: str | None = None          # "ok" | "error" | None
    limit: int = 50                     # Page size (1-100)
    offset: int = 0                     # Pagination offset

    # New fields (019-library-filters-search)
    search: str | None = None           # Text search (filename/title)
    resolution: str | None = None       # "4k" | "1080p" | "720p" | "480p" | "other"
    audio_lang: list[str] | None = None # ISO 639 codes, OR logic
    subtitles: str | None = None        # "yes" | "no" | None
```

**Validation Rules**:
- `search`: Trimmed, max 200 characters
- `resolution`: Must be one of allowed values or None
- `audio_lang`: Each code must be 2-3 lowercase characters
- `subtitles`: Must be "yes", "no", or None

### Resolution Categories

Mapping from filter value to height ranges:

| Filter Value | Height Range | Label |
|--------------|--------------|-------|
| `4k` | >= 2160 | 4K / UHD |
| `1080p` | >= 1080, < 2160 | 1080p |
| `720p` | >= 720, < 1080 | 720p |
| `480p` | >= 480, < 720 | 480p |
| `other` | < 480 | Other |

### LibraryContext (Python dataclass)

Extends existing template context with new filter options.

```python
@dataclass
class LibraryContext:
    """Template context for library.html."""

    # Existing fields
    status_options: list[dict]

    # New fields (019-library-filters-search)
    resolution_options: list[dict]
    subtitles_options: list[dict]
    # Note: audio_lang options populated dynamically via API
```

### FileListResponse (Python dataclass)

Response model remains unchanged structurally; `has_filters` logic expanded:

```python
has_filters = any([
    params.status,
    params.search,
    params.resolution,
    params.audio_lang,
    params.subtitles,
])
```

## Filter State (Frontend)

JavaScript state object for tracking active filters:

```javascript
{
    status: '',           // '' | 'ok' | 'error'
    search: '',           // Text search term
    resolution: '',       // '' | '4k' | '1080p' | '720p' | '480p' | 'other'
    audio_lang: [],       // Array of language codes
    subtitles: ''         // '' | 'yes' | 'no'
}
```

## Query Parameter Schema

URL query parameters for shareable filter state:

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `status` | string | `status=error` | Existing parameter |
| `search` | string | `search=avatar` | URL-encoded |
| `resolution` | string | `resolution=1080p` | Single value |
| `audio_lang` | string[] | `audio_lang=eng&audio_lang=jpn` | Multiple values |
| `subtitles` | string | `subtitles=yes` | yes/no/omitted |
| `limit` | int | `limit=50` | Pagination (existing) |
| `offset` | int | `offset=100` | Pagination (existing) |

## State Transitions

### Filter Change Flow

```
User changes filter
    ↓
Update JavaScript state
    ↓
Update URL (history.replaceState)
    ↓
Reset pagination to offset=0
    ↓
Fetch /api/library?{params}
    ↓
Render updated table
```

### Page Load Flow

```
Page load
    ↓
Parse URL query params
    ↓
Initialize filter controls from params
    ↓
Fetch /api/library?{params}
    ↓
Fetch /api/library/languages (for dropdown)
    ↓
Populate language dropdown
    ↓
Render table
```
