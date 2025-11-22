# Data Model: Library Scanner

**Feature**: 002-library-scanner
**Date**: 2025-11-21

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                            _meta                                 │
├─────────────────────────────────────────────────────────────────┤
│ key (TEXT PK)                                                    │
│ value (TEXT)                                                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                            files                                 │
├─────────────────────────────────────────────────────────────────┤
│ id (INTEGER PK AUTOINCREMENT)                                    │
│ path (TEXT UNIQUE NOT NULL)                                      │
│ filename (TEXT NOT NULL)                                         │
│ directory (TEXT NOT NULL)                                        │
│ extension (TEXT NOT NULL)                                        │
│ size_bytes (INTEGER NOT NULL)                                    │
│ modified_at (TEXT NOT NULL)  -- ISO 8601 timestamp               │
│ content_hash (TEXT)          -- xxh64 partial hash               │
│ container_format (TEXT)      -- e.g., "matroska", "mp4"          │
│ scanned_at (TEXT NOT NULL)   -- ISO 8601 timestamp               │
│ scan_status (TEXT NOT NULL)  -- "ok", "error", "pending"         │
│ scan_error (TEXT)            -- error message if status="error"  │
├─────────────────────────────────────────────────────────────────┤
│ INDEX idx_files_directory ON files(directory)                    │
│ INDEX idx_files_extension ON files(extension)                    │
│ INDEX idx_files_content_hash ON files(content_hash)              │
└─────────────────────────────────────────────────────────────────┘
          │
          │ 1:N
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                           tracks                                 │
├─────────────────────────────────────────────────────────────────┤
│ id (INTEGER PK AUTOINCREMENT)                                    │
│ file_id (INTEGER NOT NULL FK → files.id ON DELETE CASCADE)       │
│ track_index (INTEGER NOT NULL)                                   │
│ track_type (TEXT NOT NULL)   -- "video", "audio", "subtitle"     │
│ codec (TEXT)                 -- e.g., "hevc", "aac", "subrip"    │
│ language (TEXT)              -- ISO 639-2 code, e.g., "eng"      │
│ title (TEXT)                 -- track label                      │
│ is_default (INTEGER NOT NULL DEFAULT 0)  -- boolean as 0/1       │
│ is_forced (INTEGER NOT NULL DEFAULT 0)   -- boolean as 0/1       │
├─────────────────────────────────────────────────────────────────┤
│ UNIQUE(file_id, track_index)                                     │
│ INDEX idx_tracks_file_id ON tracks(file_id)                      │
│ INDEX idx_tracks_type ON tracks(track_type)                      │
│ INDEX idx_tracks_language ON tracks(language)                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         operations                               │
├─────────────────────────────────────────────────────────────────┤
│ id (INTEGER PK AUTOINCREMENT)                                    │
│ file_id (INTEGER FK → files.id ON DELETE SET NULL)               │
│ operation_type (TEXT NOT NULL)                                   │
│ status (TEXT NOT NULL)       -- "pending", "running", "done"     │
│ created_at (TEXT NOT NULL)                                       │
│ completed_at (TEXT)                                              │
│ parameters (TEXT)            -- JSON blob                        │
│ result (TEXT)                -- JSON blob or error message       │
└─────────────────────────────────────────────────────────────────┘
Note: Operations table is future-ready; minimal use in Sprint 1.

┌─────────────────────────────────────────────────────────────────┐
│                          policies                                │
├─────────────────────────────────────────────────────────────────┤
│ id (INTEGER PK AUTOINCREMENT)                                    │
│ name (TEXT UNIQUE NOT NULL)                                      │
│ version (INTEGER NOT NULL DEFAULT 1)                             │
│ definition (TEXT NOT NULL)   -- YAML/JSON policy content         │
│ created_at (TEXT NOT NULL)                                       │
│ updated_at (TEXT NOT NULL)                                       │
└─────────────────────────────────────────────────────────────────┘
Note: Policies table is future-ready; minimal use in Sprint 1.
```

## Python Dataclasses

### FileInfo (Domain Model)

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TrackInfo:
    """Represents a media track within a video file."""
    index: int
    track_type: str  # "video", "audio", "subtitle", "other"
    codec: str | None = None
    language: str | None = None
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False


@dataclass
class FileInfo:
    """Represents a scanned video file with its tracks."""
    path: Path
    filename: str
    directory: Path
    extension: str
    size_bytes: int
    modified_at: datetime
    content_hash: str | None = None
    container_format: str | None = None
    scanned_at: datetime = field(default_factory=datetime.now)
    scan_status: str = "ok"  # "ok", "error", "pending"
    scan_error: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)
```

### Database Models (Persistence Layer)

```python
@dataclass
class FileRecord:
    """Database record for files table."""
    id: int | None
    path: str
    filename: str
    directory: str
    extension: str
    size_bytes: int
    modified_at: str  # ISO 8601
    content_hash: str | None
    container_format: str | None
    scanned_at: str  # ISO 8601
    scan_status: str
    scan_error: str | None


@dataclass
class TrackRecord:
    """Database record for tracks table."""
    id: int | None
    file_id: int
    track_index: int
    track_type: str
    codec: str | None
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
```

## State Transitions

### File Scan Status

```
                    ┌──────────┐
                    │ pending  │
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          │          ▼
         ┌────────┐      │     ┌─────────┐
         │   ok   │◄─────┘     │  error  │
         └────────┘            └─────────┘
              │                     │
              │    (re-scan)        │
              └──────────┬──────────┘
                         │
                         ▼
                    ┌──────────┐
                    │ pending  │
                    └──────────┘
```

### Scan Process Flow

```
1. Discover file path
2. Check if exists in DB (by path)
   ├── Not exists → INSERT with status="pending"
   └── Exists → Check if modified_at changed
       ├── Changed → UPDATE status="pending"
       └── Unchanged → SKIP (already scanned)
3. For pending files:
   ├── Compute hash → UPDATE content_hash
   ├── Extract metadata → INSERT tracks
   └── UPDATE status="ok" or "error"
4. Return scan summary
```

## Validation Rules

### Files Table

| Field | Validation |
|-------|------------|
| path | Must be absolute path; must be unique |
| filename | Non-empty; extracted from path |
| directory | Non-empty; parent of path |
| extension | Lowercase; one of supported extensions |
| size_bytes | Non-negative integer |
| modified_at | Valid ISO 8601 timestamp |
| content_hash | Optional; format: `xxh64:<hex>:<hex>:<size>` |
| scan_status | One of: "ok", "error", "pending" |

### Tracks Table

| Field | Validation |
|-------|------------|
| file_id | Must reference existing file |
| track_index | Non-negative integer; unique per file |
| track_type | One of: "video", "audio", "subtitle", "other" |
| language | Optional; ISO 639-2 three-letter code |

## SQL Schema

```sql
-- Schema version tracking
CREATE TABLE IF NOT EXISTS _meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO _meta (key, value) VALUES ('schema_version', '1');

-- Main files table
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    directory TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    content_hash TEXT,
    container_format TEXT,
    scanned_at TEXT NOT NULL,
    scan_status TEXT NOT NULL DEFAULT 'pending',
    scan_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_directory ON files(directory);
CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
CREATE INDEX IF NOT EXISTS idx_files_content_hash ON files(content_hash);

-- Tracks table (one-to-many with files)
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    track_index INTEGER NOT NULL,
    track_type TEXT NOT NULL,
    codec TEXT,
    language TEXT,
    title TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    is_forced INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    UNIQUE(file_id, track_index)
);

CREATE INDEX IF NOT EXISTS idx_tracks_file_id ON tracks(file_id);
CREATE INDEX IF NOT EXISTS idx_tracks_type ON tracks(track_type);
CREATE INDEX IF NOT EXISTS idx_tracks_language ON tracks(language);

-- Operations table (future-ready)
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER,
    operation_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    parameters TEXT,
    result TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL
);

-- Policies table (future-ready)
CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    definition TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```
