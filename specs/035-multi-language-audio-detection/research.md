# Research: Multi-Language Audio Detection

**Feature**: 035-multi-language-audio-detection
**Date**: 2025-11-26

## Executive Summary

This research resolves technical unknowns for implementing multi-language audio detection by exploring the existing VPO codebase, specifically the conditional policy system and transcription plugin architecture.

---

## 1. Conditional Policy System Integration

### Decision: Extend Existing Condition Pattern

**Rationale**: The existing conditional policy system (schema version 4) provides a well-established pattern for adding new condition types. The `audio_is_multi_language` condition will follow this exact pattern.

### Existing Condition Types

| Condition | Purpose | File Location |
|-----------|---------|---------------|
| `ExistsCondition` | Check if track matching criteria exists | `policy/models.py:731` |
| `CountCondition` | Count matching tracks, compare to threshold | `policy/models.py:743` |
| `AndCondition` | All sub-conditions must be true | `policy/models.py:757` |
| `OrCondition` | At least one sub-condition true | `policy/models.py:764` |
| `NotCondition` | Negate a condition | `policy/models.py:771` |

### Pattern for Adding `audio_is_multi_language`

**Step 1**: Define dataclass in `policy/models.py`
```python
@dataclass(frozen=True)
class AudioIsMultiLanguageCondition:
    """Check if audio track contains multiple spoken languages."""
    track_selector: TrackFilters | None = None  # Optional: select specific audio track
    primary_language: str | None = None         # Expected primary language (ISO 639-2)
    secondary_language_threshold: float = 0.05  # Minimum % for secondary languages
```

**Step 2**: Add Pydantic model in `policy/loader.py`
```python
class AudioIsMultiLanguageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_selector: TrackFiltersModel | None = None
    primary_language: str | None = None
    secondary_language_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
```

**Step 3**: Add evaluation in `policy/conditions.py`
```python
def evaluate_audio_is_multi_language(
    condition: AudioIsMultiLanguageCondition,
    tracks: list[TrackInfo],
    language_results: dict[int, LanguageAnalysisResult],  # New parameter
) -> tuple[bool, str]:
    ...
```

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| New plugin type for conditions | Overengineered; conditions are core policy functionality |
| Metadata field on TrackInfo | Conditions should evaluate dynamically, not static fields |
| Separate evaluation phase | Would break first-match-wins semantics of conditional rules |

---

## 2. Transcription Plugin Integration

### Decision: Extend TranscriptionPlugin Protocol

**Rationale**: The existing transcription plugin already has `detect_language()` method. Multi-language detection is a logical extension requiring sampling at multiple points rather than single detection.

### Current TranscriptionPlugin Interface

```python
# Location: transcription/interface.py
class TranscriptionPlugin(Protocol):
    def detect_language(
        audio_data: bytes,
        sample_rate: int = 16000
    ) -> TranscriptionResult

    def transcribe(...) -> TranscriptionResult

    def supports_feature(feature: str) -> bool
```

### Proposed Extension

Add new method to protocol:
```python
def detect_multi_language(
    audio_data: bytes,
    sample_positions: list[float],  # Positions in seconds to sample
    sample_duration: float = 5.0,   # Duration of each sample
    sample_rate: int = 16000,
) -> MultiLanguageResult
```

Add new feature flag:
```python
def supports_feature("multi_language_detection") -> bool
```

### Whisper Sampling Strategy

**Decision**: Sample at 10-minute intervals with 5-second samples for ~2-hour films.

**Rationale**:
- Whisper's `detect_language()` uses first 30 seconds by default
- Sampling every 10 minutes captures language changes in typical film structure
- 5-second samples provide enough context for reliable language detection
- Total analysis time: ~12 samples × ~2 seconds = ~24 seconds (vs 60+ min full analysis)

| Film Length | Samples | Estimated Time |
|-------------|---------|----------------|
| 90 min | 9 | ~18 seconds |
| 120 min | 12 | ~24 seconds |
| 180 min | 18 | ~36 seconds |

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Full audio analysis | Far too slow (60+ seconds per hour of audio) |
| Fixed 30-second sample | Misses language changes in middle/end of content |
| User-configurable sampling | Complexity without clear benefit; sensible defaults work |

---

## 3. Data Storage

### Decision: New `language_analysis_results` Table

**Rationale**: Language analysis is distinct from transcription (different data, different purpose). Separate table allows caching and prevents re-analysis.

### Schema Design

```sql
CREATE TABLE IF NOT EXISTS language_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    file_hash TEXT NOT NULL,                    -- Content hash for cache invalidation
    primary_language TEXT NOT NULL,             -- ISO 639-2 code
    primary_percentage REAL NOT NULL,           -- 0.0 to 1.0
    classification TEXT NOT NULL,               -- 'SINGLE_LANGUAGE' or 'MULTI_LANGUAGE'
    analysis_metadata TEXT,                     -- JSON: sample positions, model, etc.
    created_at TEXT NOT NULL,                   -- ISO-8601 UTC
    updated_at TEXT NOT NULL,                   -- ISO-8601 UTC
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    UNIQUE(track_id)
);

CREATE TABLE IF NOT EXISTS language_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    language_code TEXT NOT NULL,                -- ISO 639-2 code
    start_time REAL NOT NULL,                   -- Seconds from start
    end_time REAL NOT NULL,                     -- Seconds from start
    confidence REAL NOT NULL,                   -- 0.0 to 1.0
    FOREIGN KEY (analysis_id) REFERENCES language_analysis_results(id) ON DELETE CASCADE
);

CREATE INDEX idx_lang_analysis_track ON language_analysis_results(track_id);
CREATE INDEX idx_lang_analysis_hash ON language_analysis_results(file_hash);
CREATE INDEX idx_lang_segments_analysis ON language_segments(analysis_id);
```

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Extend `transcription_results` table | Different data structure; would require nullable columns |
| JSON field on `tracks` table | Violates normalization; harder to query |
| In-memory only (no persistence) | Defeats caching goal; re-analysis on every policy run |

---

## 4. Policy Actions

### Decision: Reuse Existing Action Types

**Rationale**: The spec requires setting forced flag and default status on subtitles. These actions already exist in the conditional policy system.

### Existing Actions (policy/models.py:781-817)

| Action | Effect |
|--------|--------|
| `skip_video_transcode` | Skip video transcode step |
| `skip_audio_transcode` | Skip audio transcode step |
| `skip_track_filter` | Skip track filtering step |
| `warn` | Log warning, continue processing |
| `fail` | Halt processing with error |

### Required New Actions

| Action | Effect | Implementation |
|--------|--------|----------------|
| `set_forced` | Set forced flag on matching subtitle | New action type |
| `set_default` | Set default flag on matching track | New action type |

These actions need track selection criteria:
```yaml
then:
  - set_forced:
      track_type: subtitle
      language: eng
  - set_default:
      track_type: subtitle
      language: eng
      is_forced: true
```

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Separate subtitle policy section | Breaks unified conditional rule model |
| Implicit default based on condition | Less explicit; harder to understand behavior |

---

## 5. Performance & Caching

### Decision: Hash-Based Caching with Opt-In Analysis

**Rationale**: Language analysis is expensive (~24 seconds per file). Users should explicitly opt-in, and results should be cached based on file content hash.

### Caching Strategy

1. **Cache Key**: `(track_id, file_hash)` - Re-analyze only if file content changes
2. **Cache Location**: `language_analysis_results` table
3. **Cache Invalidation**: On file content change (hash mismatch)
4. **Opt-In**: Analysis only runs when `--analyze-languages` flag provided or policy requires it

### Reusing Transcription Results

When transcription exists, extract language from `transcription_results.detected_language` as single-sample approximation. Full multi-language analysis still requires dedicated sampling.

---

## 6. CLI Integration

### Decision: Add `--analyze-languages` Flag to Scan Command

**Rationale**: Consistent with existing opt-in patterns for expensive operations.

### CLI Changes

```bash
# Scan with language analysis
vpo scan /path/to/videos --analyze-languages

# Analyze single file
vpo inspect /path/to/file.mkv --analyze-languages

# Apply policy (triggers analysis if condition requires it)
vpo apply --policy policy.yaml /path/to/file.mkv
```

---

## 7. Constitution Compliance

### Principle Verification

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps UTC ISO-8601 |
| II. Stable Identity | PASS | Uses track_id (UUIDv4 linked) |
| III. Portable Paths | N/A | No path operations |
| IV. Versioned Schemas | PASS | New schema version required |
| V. Idempotent Operations | PASS | Re-analysis produces same results |
| VI. IO Separation | PASS | Plugin adapter for Whisper |
| VII. Explicit Error Handling | PASS | Custom exceptions for errors |
| VIII. Structured Logging | PASS | Analysis decisions logged |
| IX. Configuration as Data | PASS | Analysis config in policy YAML |
| X. Policy Stability | PASS | New condition type, backward compatible |
| XI. Plugin Isolation | PASS | Uses existing plugin protocol |
| XII. Safe Concurrency | PASS | Analysis per-track, no shared state |
| XIII. Database Design | PASS | Normalized schema with foreign keys |
| XIV. Test Media Corpus | TODO | Need multi-language test fixtures |
| XVI. Dry-Run Default | PASS | `--dry-run` shows what would be analyzed |
| XVII. Data Privacy | PASS | Whisper runs locally, opt-in only |

---

## 8. Schema Version

### Decision: Bump to Schema Version 7

**Rationale**: New condition type (`audio_is_multi_language`) and new action types (`set_forced`, `set_default`) require schema version bump for backward compatibility.

### Migration Path

- V6 policies continue to work (no `audio_is_multi_language` conditions)
- V7 adds new condition and action types
- Loader validates schema version before parsing new constructs

---

## Summary of Key Decisions

| Area | Decision |
|------|----------|
| Condition Type | Extend existing pattern with `AudioIsMultiLanguageCondition` |
| Plugin Integration | Add `detect_multi_language()` to TranscriptionPlugin protocol |
| Sampling Strategy | 10-minute intervals, 5-second samples |
| Data Storage | New `language_analysis_results` and `language_segments` tables |
| Policy Actions | Add `set_forced` and `set_default` action types |
| Caching | Hash-based with opt-in analysis |
| Schema Version | Bump to V7 |
| CLI | Add `--analyze-languages` flag |
