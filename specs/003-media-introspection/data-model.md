# Data Model: Media Introspection & Track Modeling

**Feature**: 003-media-introspection
**Date**: 2025-11-21

## Entity Relationship

```
┌─────────────────────────────────────┐
│             FileInfo                │
│  (existing from 002-library-scanner)│
├─────────────────────────────────────┤
│  path: Path (unique)                │
│  filename: str                      │
│  directory: Path                    │
│  extension: str                     │
│  size_bytes: int                    │
│  modified_at: datetime              │
│  content_hash: str | None           │
│  container_format: str | None       │
│  scanned_at: datetime               │
│  scan_status: str                   │
│  scan_error: str | None             │
│  tracks: list[TrackInfo]            │
└────────────────┬────────────────────┘
                 │ 1:N
                 ▼
┌─────────────────────────────────────┐
│            TrackInfo                │
│       (extended for 003)            │
├─────────────────────────────────────┤
│  index: int                         │
│  track_type: str                    │
│  codec: str | None                  │
│  language: str | None               │
│  title: str | None                  │
│  is_default: bool                   │
│  is_forced: bool                    │
│  # NEW FIELDS (003)                 │
│  channels: int | None (audio)       │
│  channel_layout: str | None (audio) │
│  width: int | None (video)          │
│  height: int | None (video)         │
│  frame_rate: str | None (video)     │
└─────────────────────────────────────┘
```

## Domain Models (Python dataclasses)

### TrackInfo (extended)

```python
@dataclass
class TrackInfo:
    """Represents a media track within a video file."""

    index: int                          # Stream index from ffprobe
    track_type: str                     # "video", "audio", "subtitle", "attachment", "other"
    codec: str | None = None            # Codec name (e.g., "h264", "aac", "srt")
    language: str | None = None         # ISO 639-2/B code or "und"
    title: str | None = None            # Track title tag
    is_default: bool = False            # Default flag
    is_forced: bool = False             # Forced flag

    # Audio-specific (003-media-introspection)
    channels: int | None = None         # Number of audio channels
    channel_layout: str | None = None   # Human-readable: "stereo", "5.1", etc.

    # Video-specific (003-media-introspection)
    width: int | None = None            # Video width in pixels
    height: int | None = None           # Video height in pixels
    frame_rate: str | None = None       # Frame rate as string (e.g., "24000/1001")
```

### TrackRecord (extended)

```python
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

    # New fields (003)
    channels: int | None
    channel_layout: str | None
    width: int | None
    height: int | None
    frame_rate: str | None
```

### IntrospectionResult (new)

```python
@dataclass
class IntrospectionResult:
    """Result of media file introspection."""

    file_path: Path
    container_format: str | None        # e.g., "matroska,webm" or "mov,mp4,m4a"
    tracks: list[TrackInfo]
    warnings: list[str] = field(default_factory=list)  # Non-fatal issues
    error: str | None = None            # Fatal error if introspection failed

    @property
    def success(self) -> bool:
        return self.error is None
```

## Database Schema Changes

### tracks table (extended)

```sql
-- Migration: Add new columns to tracks table
ALTER TABLE tracks ADD COLUMN channels INTEGER;
ALTER TABLE tracks ADD COLUMN channel_layout TEXT;
ALTER TABLE tracks ADD COLUMN width INTEGER;
ALTER TABLE tracks ADD COLUMN height INTEGER;
ALTER TABLE tracks ADD COLUMN frame_rate TEXT;

-- Updated CREATE TABLE (for new installations)
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
    -- New columns (003-media-introspection)
    channels INTEGER,
    channel_layout TEXT,
    width INTEGER,
    height INTEGER,
    frame_rate TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    UNIQUE(file_id, track_index)
);
```

## Validation Rules

| Field | Validation | Error Handling |
|-------|------------|----------------|
| index | >= 0 | Required, from ffprobe stream index |
| track_type | Enum: video/audio/subtitle/attachment/other | Map unknown to "other" |
| language | ISO 639-2/B or "und" | Default to "und" if missing |
| channels | > 0 | Only set for audio tracks |
| width/height | > 0 | Only set for video tracks |
| frame_rate | Rational string "N/D" or decimal | Preserve as-is from ffprobe |

## State Transitions

Tracks are immutable once created. On file rescan:

1. **Match by index**: Find existing tracks with same `file_id` and `track_index`
2. **Update matched**: Overwrite all fields with new values
3. **Insert new**: Create records for tracks not previously present
4. **Delete stale**: Remove tracks no longer in file (by index)

This is the "smart merge" strategy from clarifications.

## Database Operations (New for 003)

### upsert_tracks_for_file

```python
def upsert_tracks_for_file(conn: sqlite3.Connection, file_id: int, tracks: list[TrackInfo]) -> None:
    """Smart merge tracks for a file: update existing, insert new, delete missing.

    Args:
        conn: Database connection.
        file_id: ID of the parent file.
        tracks: List of TrackInfo objects from introspection.

    Algorithm:
        1. Get existing track indices for file_id
        2. For each new track:
           - If track_index exists: UPDATE all fields
           - If track_index is new: INSERT
        3. DELETE tracks with indices not in new list
    """
```
