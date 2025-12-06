# Research: Audio Track Classification

**Feature**: 044-audio-track-classification
**Date**: 2025-12-05

## Executive Summary

This research resolves technical unknowns for implementing audio track classification by exploring the existing VPO codebase, specifically the policy condition system, language detection, and transcription plugin architecture.

---

## 1. Original vs Dubbed Detection Strategy

### Decision: External Metadata as Primary Signal

**Rationale**: External metadata (production country, original title language) is the most reliable source for identifying the original audio track. Acoustic analysis and track position are useful fallbacks but can be misleading.

### Detection Priority Order

1. **External Metadata** (highest reliability)
   - Production country from Radarr/Sonarr/TMDB integration
   - Original language from media database APIs
   - Title language metadata embedded in file

2. **Track Position** (medium reliability)
   - First audio track is often (but not always) original
   - Useful heuristic when metadata unavailable

3. **Acoustic Analysis** (lowest reliability, fallback only)
   - Audio quality comparison (original often has better dynamic range)
   - Speech timing correlation with video (lip sync proxy)

### Implementation Approach

```python
def determine_original_track(
    tracks: list[TrackInfo],
    file_metadata: FileMetadata,
    plugin_metadata: dict | None,
) -> tuple[int | None, float]:
    """
    Returns (track_index, confidence) for the original track.
    Returns (None, 0.0) if cannot determine.
    """
    # Stage 1: External metadata
    if plugin_metadata:
        original_lang = (
            plugin_metadata.get("radarr", {}).get("original_language") or
            plugin_metadata.get("sonarr", {}).get("original_language")
        )
        if original_lang:
            for track in tracks:
                if track.language == original_lang:
                    return (track.index, 0.95)  # High confidence

    # Stage 2: Track position heuristic
    audio_tracks = [t for t in tracks if t.track_type == "audio"]
    if len(audio_tracks) == 1:
        return (audio_tracks[0].index, 0.50)  # Low confidence, single track
    if audio_tracks:
        return (audio_tracks[0].index, 0.60)  # Medium confidence

    return (None, 0.0)  # Cannot determine
```

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Acoustic-only detection | Too unreliable; requires expensive analysis with low accuracy |
| User-provided hints in policy | Increases policy complexity; defeats automation goal |
| Track title parsing | Inconsistent labeling across sources; high false positive rate |

---

## 2. Commentary Detection via Acoustic Analysis

### Decision: Extend Existing Transcription Infrastructure

**Rationale**: Commentary tracks have distinct acoustic signatures that can be detected using features already available from the Whisper plugin infrastructure.

### Commentary Acoustic Signatures

| Feature | Main Audio | Commentary |
|---------|------------|------------|
| Speech density | Variable (dialogue + silence + action) | High (continuous talking) |
| Pause patterns | Dramatic pauses, varied rhythm | Conversational pauses |
| Voice count | Many voices, varied | Usually 1-3 consistent voices |
| Background audio | Full soundtrack (music, effects) | Minimal or film audio underneath |
| Dynamic range | Wide (whispers to explosions) | Narrow (conversational level) |

### Detection Algorithm

```python
@dataclass
class AcousticProfile:
    """Extracted audio characteristics for classification."""
    speech_density: float  # Ratio of speech frames to total frames (0.0-1.0)
    avg_pause_duration: float  # Average silence duration in seconds
    voice_count_estimate: int  # Estimated number of distinct speakers
    dynamic_range_db: float  # Peak-to-average ratio in dB
    has_background_audio: bool  # Whether film audio detected underneath

def is_commentary_by_acoustic(profile: AcousticProfile) -> tuple[bool, float]:
    """
    Returns (is_commentary, confidence).

    Commentary indicators:
    - High speech density (>0.7)
    - Low dynamic range (<15 dB)
    - Few speakers (1-3)
    - Conversational pause pattern
    """
    score = 0.0

    if profile.speech_density > 0.7:
        score += 0.3
    if profile.dynamic_range_db < 15.0:
        score += 0.25
    if 1 <= profile.voice_count_estimate <= 3:
        score += 0.25
    if profile.has_background_audio:
        score += 0.2  # Commentary often has film audio underneath

    confidence = min(score, 1.0)
    return (confidence >= 0.7, confidence)
```

### Integration with Existing System

The existing `detect_track_classification()` function in `transcription/models.py` uses:
1. Metadata keywords (SFX/MUSIC/COMMENTARY)
2. Speech detection + confidence
3. Transcript pattern analysis

This feature **extends** that function to include acoustic profile analysis as a fourth stage.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Separate commentary detection plugin | Overengineered; acoustic analysis fits existing transcription flow |
| Machine learning model | Requires training data; existing heuristics sufficient for 85% accuracy |
| Full transcript analysis only | Misses commentary without typical phrases; acoustic is complementary |

---

## 3. Database Schema Extension

### Decision: New `track_classification_results` Table

**Rationale**: Classification is distinct from language analysis (different data, different purpose). Separate table allows caching and prevents coupling.

### Schema Design

```sql
-- Track classification results table (044-audio-track-classification)
CREATE TABLE IF NOT EXISTS track_classification_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,
    file_hash TEXT NOT NULL,  -- Content hash for cache invalidation
    original_dubbed_status TEXT NOT NULL,  -- 'original', 'dubbed', 'unknown'
    commentary_status TEXT NOT NULL,  -- 'commentary', 'main', 'unknown'
    confidence REAL NOT NULL,  -- 0.0 to 1.0
    detection_method TEXT NOT NULL,  -- 'metadata', 'acoustic', 'combined', 'position'
    acoustic_profile_json TEXT,  -- JSON: speech_density, dynamic_range, etc.
    created_at TEXT NOT NULL,  -- ISO-8601 UTC
    updated_at TEXT NOT NULL,  -- ISO-8601 UTC
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

### Cache Invalidation

Results are invalidated when `file_hash` changes, matching the pattern established in 035-multi-language-audio-detection.

---

## 4. Policy Condition Types

### Decision: Add `is_original` and `is_dubbed` Conditions

**Rationale**: Follow the established condition pattern from `audio_is_multi_language` and `exists` conditions.

### Condition Definitions

```python
@dataclass(frozen=True)
class IsOriginalCondition:
    """Check if audio track is classified as original (not dubbed).

    Evaluates to True if track's original_dubbed_status is 'original'
    and confidence meets threshold.
    """
    language: str | None = None  # Optional: filter by language
    min_confidence: float = 0.7  # Default from clarifications

@dataclass(frozen=True)
class IsDubbedCondition:
    """Check if audio track is classified as dubbed.

    Evaluates to True if track's original_dubbed_status is 'dubbed'
    and confidence meets threshold.
    """
    original_language: str | None = None  # Filter by what it's dubbed from
    min_confidence: float = 0.7  # Default from clarifications
```

### Policy YAML Syntax

```yaml
# Simple boolean usage
conditional:
  - name: "Prefer original audio"
    when:
      is_original: true
    then:
      - set_default:
          track_type: audio

# With options
conditional:
  - name: "Handle Japanese anime dubs"
    when:
      is_dubbed:
        original_language: jpn
        min_confidence: 0.8
    then:
      - warn: "Found dubbed track from Japanese original"
```

### Commentary Condition Enhancement

Extend existing `not_commentary` filter semantics to use acoustic detection:

```yaml
audio_filter:
  not_commentary: true  # Now uses acoustic detection when metadata absent
```

---

## 5. CLI Integration

### Decision: Add `--classify-tracks` Flag to Existing Commands

**Rationale**: Consistent with `--analyze-languages` pattern from 035.

### CLI Changes

```bash
# Classify single file
vpo inspect /path/to/file.mkv --classify-tracks

# Classify during scan
vpo scan /path/to/videos --classify-tracks

# Dedicated command for batch classification
vpo classify run /path/to/videos
vpo classify status /path/to/file.mkv
vpo classify clear /path/to/file.mkv
```

---

## 6. Constitution Compliance

### Principle Verification

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps UTC ISO-8601 |
| II. Stable Identity | PASS | Uses track_id (UUIDv4 linked) |
| III. Portable Paths | N/A | No path operations |
| IV. Versioned Schemas | PASS | Schema version 19 |
| V. Idempotent Operations | PASS | Re-classification produces same results |
| VI. IO Separation | PASS | Plugin adapter for acoustic analysis |
| VII. Explicit Error Handling | PASS | Custom exceptions for errors |
| VIII. Structured Logging | PASS | Classification decisions logged |
| IX. Configuration as Data | PASS | Classification config in policy YAML |
| X. Policy Stability | PASS | New condition types, backward compatible |
| XI. Plugin Isolation | PASS | Uses existing plugin protocol |
| XII. Safe Concurrency | PASS | Per-track analysis, no shared state |
| XIII. Database Design | PASS | Normalized schema with foreign keys |
| XIV. Test Media Corpus | TODO | Need test fixtures |
| XVI. Dry-Run Default | PASS | `--dry-run` shows plan |
| XVII. Data Privacy | PASS | All analysis local, opt-in only |

---

## Summary of Key Decisions

| Area | Decision |
|------|----------|
| Original detection | External metadata primary, track position fallback |
| Commentary detection | Acoustic profile analysis (speech density, dynamic range, voice count) |
| Data storage | New `track_classification_results` table |
| Cache invalidation | On file hash change (per clarification) |
| Confidence threshold | 70% default (per clarification) |
| Policy conditions | `is_original`, `is_dubbed` with optional filters |
| CLI | `--classify-tracks` flag on inspect/scan, dedicated `classify` command |
| Schema version | Bump to 19 |
