# Data Model: Multi-Language Audio Detection

**Feature**: 035-multi-language-audio-detection
**Date**: 2025-11-26

## Overview

This document defines the data entities, relationships, and validation rules for multi-language audio detection.

---

## 1. Domain Entities

### 1.1 LanguageSegment

Represents a detected language within a specific time range of an audio track.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `language_code` | string | ISO 639-2/B, 3 chars | Detected language (e.g., "eng", "fre", "ger") |
| `start_time` | float | >= 0.0 | Start position in seconds |
| `end_time` | float | > start_time | End position in seconds |
| `confidence` | float | 0.0-1.0 | Detection confidence score |

**Validation Rules**:
- `end_time > start_time`
- `confidence` between 0.0 and 1.0 inclusive
- `language_code` must be valid ISO 639-2/B code

---

### 1.2 LanguageAnalysisResult

Aggregated language analysis result for an entire audio track.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `track_id` | int | FK to tracks.id | Associated audio track |
| `file_hash` | string | Non-empty | Content hash for cache validation |
| `primary_language` | string | ISO 639-2/B | Language with highest percentage |
| `primary_percentage` | float | 0.0-1.0 | Percentage of primary language |
| `secondary_languages` | list | LanguagePercentage[] | Other detected languages |
| `classification` | enum | SINGLE_LANGUAGE, MULTI_LANGUAGE | Track classification |
| `segments` | list | LanguageSegment[] | Individual language segments |
| `analysis_metadata` | object | AnalysisMetadata | Processing details |
| `created_at` | datetime | UTC, ISO-8601 | First analysis timestamp |
| `updated_at` | datetime | UTC, ISO-8601 | Last update timestamp |

**Derived Fields**:
- `classification`: SINGLE_LANGUAGE if `primary_percentage >= 0.95`, else MULTI_LANGUAGE

**Validation Rules**:
- `primary_percentage` + sum of `secondary_languages` percentages = 1.0 (±0.01 tolerance)
- `primary_percentage >= max(secondary_language.percentage)` for all secondary languages

---

### 1.3 LanguagePercentage

Secondary language with its percentage of total speech time.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `language_code` | string | ISO 639-2/B | Language code |
| `percentage` | float | 0.0-1.0 | Percentage of speech time |

---

### 1.4 AnalysisMetadata

Processing details for the analysis.

| Field | Type | Description |
|-------|------|-------------|
| `plugin_name` | string | Plugin that performed analysis |
| `plugin_version` | string | Plugin version |
| `model_name` | string | ML model used (e.g., "whisper-base") |
| `sample_positions` | list[float] | Sample positions in seconds |
| `sample_duration` | float | Duration of each sample |
| `total_duration` | float | Track total duration |
| `speech_ratio` | float | Ratio of detected speech to silence |

---

### 1.5 MultiLanguageCondition (Policy Condition)

Policy condition for checking multi-language audio.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `track_selector` | TrackFilters | None | Optional track filter |
| `primary_language` | string | None | Expected primary language |
| `secondary_language_threshold` | float | 0.05 | Minimum secondary percentage |

**YAML Syntax Variants**:
```yaml
# Boolean shorthand
when:
  audio_is_multi_language: true

# With threshold
when:
  audio_is_multi_language:
    secondary_language_threshold: 0.10

# With primary language constraint
when:
  audio_is_multi_language:
    primary_language: eng
    secondary_language_threshold: 0.05

# Combined with track selector
when:
  audio_is_multi_language:
    track_selector:
      is_default: true
    primary_language: eng
```

---

### 1.6 SetForcedAction (Policy Action)

Action to set forced flag on a subtitle track.

| Field | Type | Description |
|-------|------|-------------|
| `track_type` | string | Must be "subtitle" |
| `language` | string | ISO 639-2/B language code |
| `is_forced` | bool | Value to set (default: true) |

---

### 1.7 SetDefaultAction (Policy Action)

Action to set default flag on a track.

| Field | Type | Description |
|-------|------|-------------|
| `track_type` | string | "audio", "subtitle", or "video" |
| `language` | string | Optional language filter |
| `is_forced` | bool | Optional forced flag filter |
| `title_contains` | string | Optional title filter |

---

## 2. Entity Relationships

```
┌─────────────────┐      ┌──────────────────────────┐
│     tracks      │      │ language_analysis_results│
│─────────────────│      │──────────────────────────│
│ id (PK)         │──┐   │ id (PK)                  │
│ file_id (FK)    │  └──►│ track_id (FK, UNIQUE)    │
│ type            │      │ file_hash                │
│ language        │      │ primary_language         │
│ ...             │      │ primary_percentage       │
└─────────────────┘      │ classification           │
                         │ analysis_metadata (JSON) │
                         │ created_at               │
                         │ updated_at               │
                         └───────────┬──────────────┘
                                     │
                                     │ 1:N
                                     ▼
                         ┌──────────────────────────┐
                         │    language_segments     │
                         │──────────────────────────│
                         │ id (PK)                  │
                         │ analysis_id (FK)         │
                         │ language_code            │
                         │ start_time               │
                         │ end_time                 │
                         │ confidence               │
                         └──────────────────────────┘
```

**Relationship Cardinality**:
- `tracks` 1:0..1 `language_analysis_results` (optional analysis per track)
- `language_analysis_results` 1:N `language_segments` (multiple segments per analysis)

---

## 3. Database Schema

### 3.1 language_analysis_results Table

```sql
CREATE TABLE IF NOT EXISTS language_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,
    file_hash TEXT NOT NULL,
    primary_language TEXT NOT NULL,
    primary_percentage REAL NOT NULL,
    classification TEXT NOT NULL,
    analysis_metadata TEXT,  -- JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,

    CONSTRAINT valid_percentage CHECK (
        primary_percentage >= 0.0 AND primary_percentage <= 1.0
    ),
    CONSTRAINT valid_classification CHECK (
        classification IN ('SINGLE_LANGUAGE', 'MULTI_LANGUAGE')
    )
);

CREATE INDEX idx_lang_analysis_track ON language_analysis_results(track_id);
CREATE INDEX idx_lang_analysis_hash ON language_analysis_results(file_hash);
CREATE INDEX idx_lang_analysis_classification ON language_analysis_results(classification);
```

### 3.2 language_segments Table

```sql
CREATE TABLE IF NOT EXISTS language_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    language_code TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    confidence REAL NOT NULL,

    FOREIGN KEY (analysis_id) REFERENCES language_analysis_results(id) ON DELETE CASCADE,

    CONSTRAINT valid_times CHECK (end_time > start_time),
    CONSTRAINT valid_confidence CHECK (
        confidence >= 0.0 AND confidence <= 1.0
    )
);

CREATE INDEX idx_lang_segments_analysis ON language_segments(analysis_id);
CREATE INDEX idx_lang_segments_language ON language_segments(language_code);
```

---

## 4. State Transitions

### 4.1 LanguageAnalysisResult Lifecycle

```
                    ┌──────────────────────┐
                    │      NO_ANALYSIS     │
                    │ (no record exists)   │
                    └──────────┬───────────┘
                               │
                               │ analyze_track()
                               ▼
                    ┌──────────────────────┐
                    │     ANALYZING        │
                    │ (in-progress)        │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
    │ SINGLE_LANGUAGE │ │ MULTI_LANGUAGE│ │    ERROR        │
    │ (>= 95% primary)│ │ (< 95% primary)│ │ (analysis failed)│
    └─────────────────┘ └──────────────┘ └─────────────────┘
              │                │                │
              │                │                │
              └────────────────┼────────────────┘
                               │
                               │ file content changed
                               │ (hash mismatch)
                               ▼
                    ┌──────────────────────┐
                    │    STALE             │
                    │ (re-analysis needed) │
                    └──────────┬───────────┘
                               │
                               │ re-analyze
                               ▼
                         (back to ANALYZING)
```

### 4.2 Valid Classification Transitions

| From | To | Trigger |
|------|-----|---------|
| NO_ANALYSIS | SINGLE_LANGUAGE | Analysis completes with >=95% primary |
| NO_ANALYSIS | MULTI_LANGUAGE | Analysis completes with <95% primary |
| NO_ANALYSIS | ERROR | Analysis fails |
| SINGLE_LANGUAGE | STALE | File hash changes |
| MULTI_LANGUAGE | STALE | File hash changes |
| STALE | SINGLE_LANGUAGE | Re-analysis completes |
| STALE | MULTI_LANGUAGE | Re-analysis completes |

---

## 5. Python Dataclass Definitions

### 5.1 Domain Models

```python
# Location: src/video_policy_orchestrator/language_analysis/models.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LanguageClassification(Enum):
    """Classification of audio track language composition."""
    SINGLE_LANGUAGE = "SINGLE_LANGUAGE"
    MULTI_LANGUAGE = "MULTI_LANGUAGE"


@dataclass(frozen=True)
class LanguageSegment:
    """A detected language within a time range."""
    language_code: str  # ISO 639-2/B
    start_time: float   # Seconds
    end_time: float     # Seconds
    confidence: float   # 0.0-1.0

    def __post_init__(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class LanguagePercentage:
    """A language with its percentage of speech time."""
    language_code: str  # ISO 639-2/B
    percentage: float   # 0.0-1.0


@dataclass(frozen=True)
class AnalysisMetadata:
    """Processing details for the analysis."""
    plugin_name: str
    plugin_version: str
    model_name: str
    sample_positions: tuple[float, ...]
    sample_duration: float
    total_duration: float
    speech_ratio: float


@dataclass
class LanguageAnalysisResult:
    """Complete language analysis result for an audio track."""
    track_id: int
    file_hash: str
    primary_language: str
    primary_percentage: float
    secondary_languages: tuple[LanguagePercentage, ...]
    classification: LanguageClassification
    segments: tuple[LanguageSegment, ...]
    metadata: AnalysisMetadata
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_segments(
        cls,
        track_id: int,
        file_hash: str,
        segments: list[LanguageSegment],
        metadata: AnalysisMetadata,
    ) -> "LanguageAnalysisResult":
        """Create result by aggregating segments."""
        # Implementation aggregates segments into percentages
        ...
```

### 5.2 Policy Condition Model

```python
# Location: src/video_policy_orchestrator/policy/models.py

@dataclass(frozen=True)
class AudioIsMultiLanguageCondition:
    """Check if audio track contains multiple spoken languages."""
    track_selector: TrackFilters | None = None
    primary_language: str | None = None
    secondary_language_threshold: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 <= self.secondary_language_threshold <= 1.0:
            raise ValueError(
                "secondary_language_threshold must be between 0.0 and 1.0"
            )
```

### 5.3 Policy Action Models

```python
# Location: src/video_policy_orchestrator/policy/models.py

@dataclass(frozen=True)
class SetForcedAction:
    """Set forced flag on a subtitle track."""
    track_type: str  # Must be "subtitle"
    language: str    # ISO 639-2/B
    is_forced: bool = True

    def __post_init__(self) -> None:
        if self.track_type != "subtitle":
            raise ValueError("set_forced action only applies to subtitle tracks")


@dataclass(frozen=True)
class SetDefaultAction:
    """Set default flag on a track."""
    track_type: str  # "audio", "subtitle", or "video"
    language: str | None = None
    is_forced: bool | None = None
    title_contains: str | None = None

    def __post_init__(self) -> None:
        valid_types = {"audio", "subtitle", "video"}
        if self.track_type not in valid_types:
            raise ValueError(f"track_type must be one of {valid_types}")
```

### 5.4 Database Record Models

```python
# Location: src/video_policy_orchestrator/db/models.py

@dataclass
class LanguageAnalysisResultRecord:
    """Database record for language_analysis_results table."""
    id: int | None
    track_id: int
    file_hash: str
    primary_language: str
    primary_percentage: float
    classification: str  # 'SINGLE_LANGUAGE' or 'MULTI_LANGUAGE'
    analysis_metadata: str | None  # JSON string
    created_at: str  # ISO-8601 UTC
    updated_at: str  # ISO-8601 UTC


@dataclass
class LanguageSegmentRecord:
    """Database record for language_segments table."""
    id: int | None
    analysis_id: int
    language_code: str
    start_time: float
    end_time: float
    confidence: float
```

---

## 6. Validation Rules Summary

| Entity | Field | Rule |
|--------|-------|------|
| LanguageSegment | end_time | Must be > start_time |
| LanguageSegment | confidence | Must be 0.0-1.0 |
| LanguageSegment | language_code | Must be valid ISO 639-2/B |
| LanguageAnalysisResult | primary_percentage | Must be 0.0-1.0 |
| LanguageAnalysisResult | classification | SINGLE_LANGUAGE if primary >= 0.95 |
| LanguageAnalysisResult | percentages | Sum must equal 1.0 (±0.01) |
| AudioIsMultiLanguageCondition | threshold | Must be 0.0-1.0 |
| SetForcedAction | track_type | Must be "subtitle" |
| SetDefaultAction | track_type | Must be audio/subtitle/video |
