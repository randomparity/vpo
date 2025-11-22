# Data Model: Audio Transcription & Language Detection

**Feature**: 007-audio-transcription
**Date**: 2025-11-22

## Entity Relationship Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────────┐
│     files       │────<│     tracks      │────<│  transcription_results  │
├─────────────────┤     ├─────────────────┤     ├─────────────────────────┤
│ id (PK)         │     │ id (PK)         │     │ id (PK)                 │
│ path            │     │ file_id (FK)    │     │ track_id (FK, UNIQUE)   │
│ filename        │     │ track_index     │     │ detected_language       │
│ ...             │     │ track_type      │     │ confidence_score        │
└─────────────────┘     │ language        │     │ track_type              │
                        │ ...             │     │ transcript_sample       │
                        └─────────────────┘     │ plugin_name             │
                                                │ created_at              │
                                                │ updated_at              │
                                                └─────────────────────────┘
```

## Entities

### TranscriptionResult (Domain Model)

Result of transcription analysis for a single audio track.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| track_id | int | Yes | Foreign key to tracks.id |
| detected_language | str \| None | No | ISO 639-1/639-2 language code (e.g., "en", "fra") |
| confidence_score | float | Yes | Confidence level 0.0-1.0 |
| track_type | TrackClassification | Yes | Classification: main, commentary, alternate |
| transcript_sample | str \| None | No | Optional text sample (first ~100 chars) |
| plugin_name | str | Yes | Name of plugin that produced result |
| created_at | datetime | Yes | UTC timestamp of initial detection |
| updated_at | datetime | Yes | UTC timestamp of last update |

**Validation Rules**:
- `confidence_score` must be between 0.0 and 1.0 inclusive
- `detected_language` must be valid ISO 639-1 (2-char) or ISO 639-2 (3-char) code if present
- `track_type` must be one of: "main", "commentary", "alternate"
- `plugin_name` must be non-empty string

**State Transitions**: None (immutable after creation, replaced on re-detection)

### TranscriptionResultRecord (Database Record)

SQLite representation of TranscriptionResult.

| Column | SQLite Type | Constraints | Description |
|--------|-------------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Auto-generated ID |
| track_id | INTEGER | NOT NULL UNIQUE, FK tracks(id) | Link to track |
| detected_language | TEXT | | ISO language code |
| confidence_score | REAL | NOT NULL, CHECK 0.0-1.0 | Confidence |
| track_type | TEXT | NOT NULL DEFAULT 'main' | Classification |
| transcript_sample | TEXT | | Optional sample text |
| plugin_name | TEXT | NOT NULL | Plugin identifier |
| created_at | TEXT | NOT NULL | ISO-8601 UTC |
| updated_at | TEXT | NOT NULL | ISO-8601 UTC |

### TrackClassification (Enum)

```python
class TrackClassification(Enum):
    """Classification of audio track purpose."""
    MAIN = "main"           # Primary audio track
    COMMENTARY = "commentary"  # Director/cast commentary
    ALTERNATE = "alternate"    # Alternate mix, isolated score, etc.
```

### TranscriptionConfig (Configuration Model)

User configuration for transcription behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled_plugin | str \| None | None | Plugin to use (None = auto-detect) |
| model_size | str | "base" | Whisper model: tiny, base, small, medium, large |
| sample_duration | int | 60 | Seconds to sample (0 = full track) |
| gpu_enabled | bool | True | Use GPU if available |

### TranscriptionPolicyOptions (Policy Model)

Policy options for transcription-based operations.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | False | Enable transcription analysis |
| update_language_from_transcription | bool | False | Update track language tags |
| confidence_threshold | float | 0.8 | Min confidence for updates |
| detect_commentary | bool | False | Enable commentary detection |
| reorder_commentary | bool | False | Move commentary to end |

**Validation Rules**:
- `confidence_threshold` must be between 0.0 and 1.0
- `reorder_commentary` requires `detect_commentary` to be true

## Database Schema Changes

### Migration v5 → v6

```sql
-- New transcription_results table
CREATE TABLE IF NOT EXISTS transcription_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,
    detected_language TEXT,
    confidence_score REAL NOT NULL,
    track_type TEXT NOT NULL DEFAULT 'main',
    transcript_sample TEXT,
    plugin_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    CONSTRAINT valid_confidence CHECK (
        confidence_score >= 0.0 AND confidence_score <= 1.0
    ),
    CONSTRAINT valid_track_type CHECK (
        track_type IN ('main', 'commentary', 'alternate')
    )
);

CREATE INDEX IF NOT EXISTS idx_transcription_track_id
    ON transcription_results(track_id);
CREATE INDEX IF NOT EXISTS idx_transcription_language
    ON transcription_results(detected_language);
CREATE INDEX IF NOT EXISTS idx_transcription_type
    ON transcription_results(track_type);
```

## Data Operations

### Insert/Upsert Transcription Result

```python
def upsert_transcription_result(
    conn: sqlite3.Connection,
    record: TranscriptionResultRecord
) -> int:
    """Insert or update transcription result for a track.

    Uses ON CONFLICT to handle re-detection scenarios.
    Returns the record ID.
    """
```

### Get Transcription Result for Track

```python
def get_transcription_result(
    conn: sqlite3.Connection,
    track_id: int
) -> TranscriptionResultRecord | None:
    """Get transcription result for a track, if exists."""
```

### Get Tracks Needing Transcription

```python
def get_tracks_without_transcription(
    conn: sqlite3.Connection,
    file_id: int | None = None,
    track_type: str = "audio"
) -> list[TrackRecord]:
    """Get audio tracks that don't have transcription results."""
```

### Delete Transcription Results for File

```python
def delete_transcription_results_for_file(
    conn: sqlite3.Connection,
    file_id: int
) -> int:
    """Delete all transcription results for tracks in a file.

    Called when file is re-scanned or deleted.
    Returns count of deleted records.
    """
```

## Domain Model Conversions

### TranscriptionResultRecord ↔ TranscriptionResult

```python
@dataclass
class TranscriptionResult:
    """Domain model for transcription analysis result."""

    track_id: int
    detected_language: str | None
    confidence_score: float
    track_type: TrackClassification
    transcript_sample: str | None
    plugin_name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: TranscriptionResultRecord) -> "TranscriptionResult":
        """Create domain model from database record."""
        return cls(
            track_id=record.track_id,
            detected_language=record.detected_language,
            confidence_score=record.confidence_score,
            track_type=TrackClassification(record.track_type),
            transcript_sample=record.transcript_sample,
            plugin_name=record.plugin_name,
            created_at=datetime.fromisoformat(record.created_at),
            updated_at=datetime.fromisoformat(record.updated_at),
        )
```

## Index Strategy

| Index | Columns | Purpose |
|-------|---------|---------|
| idx_transcription_track_id | track_id | Fast lookup by track |
| idx_transcription_language | detected_language | Query by detected language |
| idx_transcription_type | track_type | Filter by classification |

## Data Integrity

- **Cascade Delete**: When a track is deleted, its transcription result is automatically deleted
- **Unique Constraint**: One transcription result per track (track_id UNIQUE)
- **Foreign Key**: track_id must reference existing track
- **Check Constraints**: Valid confidence range, valid track type values
