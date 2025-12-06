# Data Model: Audio Track Classification

**Feature**: 044-audio-track-classification
**Date**: 2025-12-05

## Overview

This document defines the data model for audio track classification, including domain models, database records, and enums.

---

## Enums

### OriginalDubbedStatus

Classification of audio track as original or dubbed.

| Value | Description |
|-------|-------------|
| `original` | Track is the original theatrical audio |
| `dubbed` | Track is a dubbed version |
| `unknown` | Cannot determine original/dubbed status |

### CommentaryStatus

Classification of audio track as commentary or main.

| Value | Description |
|-------|-------------|
| `commentary` | Track contains commentary (director, cast, etc.) |
| `main` | Track contains main audio (dialogue, music, effects) |
| `unknown` | Cannot determine commentary status |

### DetectionMethod

Method used to determine classification.

| Value | Description |
|-------|-------------|
| `metadata` | Determined from external metadata (Radarr/Sonarr/TMDB) |
| `acoustic` | Determined from acoustic analysis |
| `combined` | Multiple signals combined |
| `position` | Determined from track position heuristic |

---

## Domain Models

### AcousticProfile

Extracted audio characteristics for classification.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `speech_density` | float | Ratio of speech frames to total frames | 0.0 - 1.0 |
| `avg_pause_duration` | float | Average silence duration in seconds | >= 0.0 |
| `voice_count_estimate` | int | Estimated number of distinct speakers | >= 0 |
| `dynamic_range_db` | float | Peak-to-average ratio in dB | >= 0.0 |
| `has_background_audio` | bool | Whether film audio detected underneath | - |

**Validation Rules**:
- `speech_density` must be between 0.0 and 1.0
- `avg_pause_duration` must be non-negative
- `voice_count_estimate` must be non-negative

### TrackClassificationResult

Complete classification result for an audio track.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `track_id` | int | Database ID of the classified audio track | FK to tracks.id |
| `file_hash` | str | Content hash of the file for cache validation | Required |
| `original_dubbed_status` | OriginalDubbedStatus | Original or dubbed classification | Required |
| `commentary_status` | CommentaryStatus | Commentary or main classification | Required |
| `confidence` | float | Classification confidence score | 0.0 - 1.0 |
| `detection_method` | DetectionMethod | How classification was determined | Required |
| `acoustic_profile` | AcousticProfile | None | Acoustic analysis results (if performed) | Optional |
| `created_at` | datetime | UTC timestamp when created | Required |
| `updated_at` | datetime | UTC timestamp when last updated | Required |

**Validation Rules**:
- `confidence` must be between 0.0 and 1.0
- `created_at` and `updated_at` must be timezone-aware UTC

**State Transitions**:
- Results are immutable once created
- Cache invalidation replaces rather than updates

---

## Policy Condition Models

### IsOriginalCondition

Policy condition for matching original audio tracks.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `language` | str | None | None | Filter by track language (ISO 639-2) |
| `min_confidence` | float | 0.7 | Minimum confidence threshold |

**Evaluation**:
- Returns True if track's `original_dubbed_status` is `original`
- AND track's `confidence` >= `min_confidence`
- AND (if `language` specified) track's language matches

### IsDubbedCondition

Policy condition for matching dubbed audio tracks.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `original_language` | str | None | None | Filter by original language (what it's dubbed from) |
| `min_confidence` | float | 0.7 | Minimum confidence threshold |

**Evaluation**:
- Returns True if track's `original_dubbed_status` is `dubbed`
- AND track's `confidence` >= `min_confidence`
- AND (if `original_language` specified) original track language matches

---

## Database Schema

### Table: track_classification_results

```sql
CREATE TABLE IF NOT EXISTS track_classification_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,
    file_hash TEXT NOT NULL,
    original_dubbed_status TEXT NOT NULL,
    commentary_status TEXT NOT NULL,
    confidence REAL NOT NULL,
    detection_method TEXT NOT NULL,
    acoustic_profile_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    CONSTRAINT valid_confidence CHECK (
        confidence >= 0.0 AND confidence <= 1.0
    ),
    CONSTRAINT valid_od_status CHECK (
        original_dubbed_status IN ('original', 'dubbed', 'unknown')
    ),
    CONSTRAINT valid_commentary_status CHECK (
        commentary_status IN ('commentary', 'main', 'unknown')
    ),
    CONSTRAINT valid_method CHECK (
        detection_method IN ('metadata', 'acoustic', 'combined', 'position')
    )
);

CREATE INDEX IF NOT EXISTS idx_classification_track
    ON track_classification_results(track_id);
CREATE INDEX IF NOT EXISTS idx_classification_hash
    ON track_classification_results(file_hash);
CREATE INDEX IF NOT EXISTS idx_classification_od_status
    ON track_classification_results(original_dubbed_status);
```

### Record Type: TrackClassificationRecord

Database record dataclass for track_classification_results table.

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | None | Primary key (None for inserts) |
| `track_id` | int | Foreign key to tracks.id |
| `file_hash` | str | Content hash for cache validation |
| `original_dubbed_status` | str | Enum value as string |
| `commentary_status` | str | Enum value as string |
| `confidence` | float | Confidence score |
| `detection_method` | str | Enum value as string |
| `acoustic_profile_json` | str | None | JSON serialized AcousticProfile |
| `created_at` | str | ISO-8601 UTC timestamp |
| `updated_at` | str | ISO-8601 UTC timestamp |

---

## Entity Relationships

```
files (1) ─────── (N) tracks (1) ─────── (0..1) track_classification_results
   │                    │
   │                    └──── (0..1) language_analysis_results
   │                    │
   │                    └──── (0..1) transcription_results
   │
   └──── plugin_metadata (JSON column with Radarr/Sonarr data)
```

**Notes**:
- Each track can have at most one classification result (UNIQUE constraint)
- Classification references file_hash for cache validation
- Plugin metadata on files table provides production country/original language
- Language analysis results can inform classification (multi-language → likely dubbed)

---

## JSON Serialization

### AcousticProfile JSON Format

```json
{
  "speech_density": 0.82,
  "avg_pause_duration": 1.5,
  "voice_count_estimate": 2,
  "dynamic_range_db": 12.3,
  "has_background_audio": true
}
```

---

## Migration Notes

**Schema Version**: 18 → 19

**Migration SQL**:
```sql
-- Add track_classification_results table
CREATE TABLE IF NOT EXISTS track_classification_results (
    -- ... (full schema above)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_classification_track
    ON track_classification_results(track_id);
CREATE INDEX IF NOT EXISTS idx_classification_hash
    ON track_classification_results(file_hash);
CREATE INDEX IF NOT EXISTS idx_classification_od_status
    ON track_classification_results(original_dubbed_status);
```

**Backward Compatibility**:
- New table, no changes to existing tables
- Existing queries unaffected
- Classification is opt-in (requires explicit flag)
