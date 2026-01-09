# Data Model: Analyze-Language CLI Commands

**Feature**: 042-analyze-language-cli
**Date**: 2025-12-04

## Overview

This feature does not introduce new entities or database tables. It provides CLI access to existing data structures from the language analysis module (issue #270).

## Existing Entities (Reference)

### LanguageAnalysisResult

Stores aggregated analysis results per audio track.

| Field | Type | Description |
|-------|------|-------------|
| track_id | int | FK to tracks table |
| file_hash | str | File content hash for cache invalidation |
| primary_language | str | ISO 639-2 language code |
| primary_percentage | float | Percentage of track (0-100) |
| classification | enum | SINGLE_LANGUAGE or MULTI_LANGUAGE |
| secondary_languages | json | List of {language, percentage} |
| analyzed_at | datetime | UTC timestamp |
| analysis_duration_ms | int | Time to analyze |
| sample_count | int | Number of samples analyzed |

**Location**: `src/vpo/language_analysis/models.py`

### LanguageSegment

Stores per-segment detection results.

| Field | Type | Description |
|-------|------|-------------|
| track_id | int | FK to tracks table |
| start_ms | int | Segment start time |
| end_ms | int | Segment end time |
| language | str | ISO 639-2 code |
| confidence | float | Detection confidence (0-1) |

**Location**: `src/vpo/language_analysis/models.py`

## New Query Interfaces

### Status Queries (db/views.py)

```python
@dataclass
class AnalysisStatusSummary:
    """Summary of language analysis status across library."""
    total_files: int
    total_tracks: int
    analyzed_tracks: int
    pending_tracks: int
    multi_language_count: int
    single_language_count: int

def get_analysis_status_summary(conn: Connection) -> AnalysisStatusSummary:
    """Get overall analysis status for the library."""
    pass

@dataclass
class FileAnalysisStatus:
    """Analysis status for a single file."""
    file_id: int
    file_path: str
    track_count: int
    analyzed_count: int
    classifications: list[str]  # e.g., ["MULTI_LANGUAGE", "SINGLE_LANGUAGE"]

def get_files_analysis_status(
    conn: Connection,
    filter_classification: str | None = None,
    path_prefix: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[FileAnalysisStatus]:
    """Get per-file analysis status with optional filtering."""
    pass

def get_file_analysis_detail(
    conn: Connection,
    file_path: str,
) -> list[LanguageAnalysisResultRecord] | None:
    """Get detailed analysis results for a specific file's tracks."""
    pass
```

### Deletion Queries (db/queries.py)

```python
def delete_analysis_for_track(conn: Connection, track_id: int) -> bool:
    """Delete analysis result and segments for a track."""
    pass

def delete_analysis_for_file(conn: Connection, file_id: int) -> int:
    """Delete all analysis results for a file's tracks.

    Returns: Number of tracks cleared.
    """
    pass

def delete_analysis_by_path_prefix(conn: Connection, path_prefix: str) -> int:
    """Delete analysis for all files matching path prefix.

    Returns: Number of files affected.
    """
    pass

def delete_all_analysis(conn: Connection) -> int:
    """Delete all language analysis results.

    Returns: Total records deleted.
    """
    pass
```

### File Resolution Queries (db/queries.py)

```python
def get_file_ids_by_path_prefix(
    conn: Connection,
    path_prefix: str,
    include_subdirs: bool = True,
) -> list[int]:
    """Get file IDs matching a path prefix.

    Args:
        path_prefix: Directory path to match.
        include_subdirs: If True, matches recursively.

    Returns: List of file IDs.
    """
    pass
```

## View Model for CLI Output

```python
@dataclass
class AnalysisRunResult:
    """Result of running analysis on a single file."""
    file_path: str
    success: bool
    track_count: int
    analyzed_count: int
    cached_count: int
    error: str | None = None
    duration_ms: int = 0

@dataclass
class AnalysisBatchResult:
    """Aggregate result of batch analysis."""
    total_files: int
    successful: int
    failed: int
    cached: int
    tracks_analyzed: int
    total_duration_ms: int
    errors: list[tuple[str, str]]  # (path, error)
```

## Database Tables (Existing)

No new tables. Uses existing tables from schema version 17:

```sql
-- language_analysis_results table
CREATE TABLE IF NOT EXISTS language_analysis_results (
    id INTEGER PRIMARY KEY,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    file_hash TEXT NOT NULL,
    primary_language TEXT NOT NULL,
    primary_percentage REAL NOT NULL,
    classification TEXT NOT NULL,
    secondary_languages TEXT,  -- JSON
    analyzed_at TEXT NOT NULL,
    analysis_duration_ms INTEGER,
    sample_count INTEGER,
    UNIQUE(track_id)
);

-- language_segments table
CREATE TABLE IF NOT EXISTS language_segments (
    id INTEGER PRIMARY KEY,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    language TEXT NOT NULL,
    confidence REAL NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_language_analysis_track ON language_analysis_results(track_id);
CREATE INDEX IF NOT EXISTS idx_language_segments_track ON language_segments(track_id);
```

## Validation Rules

No new validation rules. Existing rules from language_analysis module apply:
- Track must exist in database before analysis
- File hash must match for cache validity
- Language codes must be ISO 639-2
- Percentages must sum to approximately 100%
