# Data Model: Transcriptions Overview List

**Feature**: 021-transcriptions-list
**Date**: 2025-11-24

## Overview

This feature uses existing database tables (`files`, `tracks`, `transcription_results`) without schema changes. New UI models are added for API responses and template rendering.

## Existing Database Entities

### files (existing)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | File identifier |
| path | TEXT UNIQUE | Full file path |
| filename | TEXT | Filename only |
| scan_status | TEXT | "ok" or "error" |
| scanned_at | TEXT | ISO-8601 UTC timestamp |

### tracks (existing)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Track identifier |
| file_id | INTEGER FK | Reference to files.id |
| track_index | INTEGER | Index within file |
| track_type | TEXT | "video", "audio", "subtitle", etc. |
| language | TEXT | ISO 639-2/B code |

### transcription_results (existing)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Result identifier |
| track_id | INTEGER FK UNIQUE | Reference to tracks.id |
| detected_language | TEXT | Detected language code |
| confidence_score | REAL | 0.0-1.0 confidence |
| track_type | TEXT | "main", "commentary", "alternate" |
| plugin_name | TEXT | Plugin that performed detection |
| created_at | TEXT | ISO-8601 UTC timestamp |
| updated_at | TEXT | ISO-8601 UTC timestamp |

## New UI Models

### TranscriptionFilterParams

Filter parameters for `/api/transcriptions` endpoint.

```python
@dataclass
class TranscriptionFilterParams:
    """Query parameters for /api/transcriptions.

    Attributes:
        show_all: If False (default), show only files with transcriptions.
                  If True, show all files.
        limit: Page size (1-100, default 50).
        offset: Pagination offset (>= 0, default 0).
    """
    show_all: bool = False
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, query: dict) -> TranscriptionFilterParams:
        """Create from request query dict with validation."""
        ...
```

### TranscriptionListItem

File data for transcriptions API response.

```python
@dataclass
class TranscriptionListItem:
    """File data for Transcriptions list.

    Attributes:
        id: Database file ID.
        filename: Short filename for display.
        path: Full file path (for tooltip).
        has_transcription: Whether file has any transcription results.
        detected_languages: List of detected language codes.
        confidence_level: Categorical level ("high", "medium", "low", or None).
        confidence_avg: Average confidence score (0.0-1.0), or None.
        transcription_count: Number of tracks with transcription results.
        scan_status: "ok" or "error".
    """
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
        """Convert to dictionary for JSON serialization."""
        ...
```

### TranscriptionListResponse

API response wrapper with pagination.

```python
@dataclass
class TranscriptionListResponse:
    """API response for /api/transcriptions.

    Attributes:
        files: File items for current page.
        total: Total files matching filters.
        limit: Page size used.
        offset: Current offset.
        has_filters: True if show_all filter is active.
    """
    files: list[TranscriptionListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        ...
```

### TranscriptionsContext

Template context for server-side rendering.

```python
@dataclass
class TranscriptionsContext:
    """Template context for transcriptions.html.

    Attributes:
        show_all_default: Default state for show_all toggle.
    """
    show_all_default: bool = False
```

## New Database Query Function

### get_files_with_transcriptions()

Query function to retrieve files with transcription metadata.

```python
def get_files_with_transcriptions(
    conn: sqlite3.Connection,
    *,
    show_all: bool = False,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    """Get files with aggregated transcription data.

    Args:
        conn: Database connection.
        show_all: If False, only return files with transcriptions.
                  If True, return all files.
        limit: Maximum files to return.
        offset: Pagination offset.
        return_total: If True, return tuple of (files, total_count).

    Returns:
        List of file dicts with transcription data:
        {
            "id": int,
            "filename": str,
            "path": str,
            "scan_status": str,
            "transcription_count": int,
            "detected_languages": str | None,  # CSV from GROUP_CONCAT
            "avg_confidence": float | None,
            "min_confidence": float | None,
            "max_confidence": float | None,
        }
    """
    ...
```

## Helper Functions

### get_confidence_level()

Map numeric confidence to categorical level.

```python
def get_confidence_level(confidence: float | None) -> str | None:
    """Map confidence score to categorical level.

    Args:
        confidence: Average confidence score (0.0-1.0), or None.

    Returns:
        "high" if >= 0.8
        "medium" if >= 0.5 and < 0.8
        "low" if < 0.5
        None if confidence is None
    """
    if confidence is None:
        return None
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"
```

### format_detected_languages()

Format CSV language string for display.

```python
def format_detected_languages(languages_csv: str | None) -> list[str]:
    """Parse CSV language codes into list.

    Args:
        languages_csv: Comma-separated language codes from GROUP_CONCAT.

    Returns:
        List of unique language codes, or empty list.
    """
    if not languages_csv:
        return []
    return list(set(lang.strip() for lang in languages_csv.split(",") if lang.strip()))
```

## Relationships

```
files (1) ──── (N) tracks (1) ──── (0..1) transcription_results
```

- A file has zero or more audio tracks
- Each audio track has zero or one transcription result
- The transcriptions list aggregates results across all audio tracks per file

## Validation Rules

1. **Confidence bounds**: 0.0 <= confidence_score <= 1.0
2. **Language codes**: 2-3 character ISO 639 codes
3. **Pagination limits**: 1 <= limit <= 100, offset >= 0

## State Transitions

No state transitions - this is a read-only view of existing data.

## Indexes Used

The existing indexes support efficient queries:
- `files.id` (PK) - file lookups
- `tracks.file_id` (FK) - track aggregation
- `transcription_results.track_id` (FK UNIQUE) - transcription joins
