# Quickstart: Audio Track Classification

**Feature**: 044-audio-track-classification
**Date**: 2025-12-05

## Overview

This guide provides step-by-step instructions for implementing audio track classification in VPO.

---

## Prerequisites

1. **Multi-Language Audio Detection (035)**: Classification integrates with language analysis results.

2. **Audio Transcription Plugin (007)**: Acoustic analysis uses the Whisper integration.

3. **Radarr/Sonarr Metadata Plugin**: Production country metadata used for original language detection.

---

## Implementation Order

### Phase 1: Data Model & Storage

1. **Add database table** (`db/schema.py`)
   - `track_classification_results` table
   - Bump SCHEMA_VERSION to 19

2. **Add database types** (`db/types.py`)
   - `OriginalDubbedStatus` enum
   - `CommentaryStatus` enum
   - `DetectionMethod` enum
   - `TrackClassificationRecord` dataclass

3. **Add domain models** (`track_classification/models.py`)
   - `AcousticProfile` dataclass
   - `TrackClassificationResult` dataclass

4. **Add database operations** (`db/queries.py`)
   - `upsert_track_classification()`
   - `get_track_classification()`
   - `delete_track_classification()`
   - `get_classifications_for_file()`

### Phase 2: Acoustic Analysis

1. **Add acoustic profile extraction** (`track_classification/acoustic.py`)
   - `extract_acoustic_profile()` - analyze audio for speech density, dynamic range
   - `is_commentary_by_acoustic()` - evaluate profile for commentary indicators

2. **Extend TranscriptionPlugin protocol** (`transcription/interface.py`)
   - Add `get_acoustic_profile()` method signature
   - Add `"acoustic_analysis"` feature flag

3. **Implement in Whisper plugin** (`plugins/whisper_transcriber/plugin.py`)
   - Implement `get_acoustic_profile()` using VAD and audio analysis

### Phase 3: Original/Dubbed Detection

1. **Add metadata integration** (`track_classification/metadata.py`)
   - `get_original_language_from_metadata()` - extract from Radarr/Sonarr
   - `determine_original_track()` - apply detection priority

2. **Create service layer** (`track_classification/service.py`)
   - `classify_track()` - main classification function
   - `classify_file_tracks()` - classify all tracks in a file
   - Add caching logic (check file hash before analysis)
   - Add result persistence

### Phase 4: Policy Conditions

1. **Add condition dataclasses** (`policy/models.py`)
   - `IsOriginalCondition` dataclass
   - `IsDubbedCondition` dataclass
   - Update `Condition` union type

2. **Add Pydantic models** (`policy/loader.py`)
   - `IsOriginalModel` validation model
   - `IsDubbedModel` validation model
   - Update `ConditionModel` to include new types
   - Add conversion functions

3. **Add evaluation logic** (`policy/conditions.py`)
   - `evaluate_is_original()` function
   - `evaluate_is_dubbed()` function
   - Update `evaluate_condition()` to handle new types

4. **Update policy evaluator** (`policy/evaluator.py`)
   - Fetch classification results when needed
   - Pass to condition evaluation chain

### Phase 5: CLI Integration

1. **Add inspect flag** (`cli/inspect.py`)
   - `--classify-tracks` option
   - Output formatting for classification results

2. **Add scan flag** (`cli/scan.py`)
   - `--classify-tracks` option
   - Integration with classification service

3. **Create classify command** (`cli/classify.py`)
   - `run` subcommand - run classification
   - `status` subcommand - show classification status
   - `clear` subcommand - clear cached results

4. **Register command** (`cli/__init__.py`)
   - Add `classify` command group

### Phase 6: Schema Version & Tests

1. **Update schema** (`db/schema.py`)
   - Add migration for version 19
   - Add track_classification_results table

2. **Add unit tests**
   - `tests/unit/track_classification/test_models.py`
   - `tests/unit/track_classification/test_service.py`
   - `tests/unit/track_classification/test_acoustic.py`
   - `tests/unit/policy/test_conditions.py` (extend)

3. **Add integration tests**
   - `tests/integration/test_track_classification.py`

---

## Key File Locations

| Component | File Path |
|-----------|-----------|
| Domain models | `src/video_policy_orchestrator/track_classification/models.py` |
| Acoustic analysis | `src/video_policy_orchestrator/track_classification/acoustic.py` |
| Metadata integration | `src/video_policy_orchestrator/track_classification/metadata.py` |
| Service layer | `src/video_policy_orchestrator/track_classification/service.py` |
| Database schema | `src/video_policy_orchestrator/db/schema.py` |
| Database types | `src/video_policy_orchestrator/db/types.py` |
| Policy models | `src/video_policy_orchestrator/policy/models.py` |
| Policy loader | `src/video_policy_orchestrator/policy/loader.py` |
| Condition evaluation | `src/video_policy_orchestrator/policy/conditions.py` |
| CLI commands | `src/video_policy_orchestrator/cli/*.py` |

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/track_classification/test_models.py
def test_acoustic_profile_validation():
    """Test AcousticProfile validates constraints."""
    with pytest.raises(ValueError):
        AcousticProfile(
            speech_density=1.5,  # Invalid: > 1.0
            avg_pause_duration=1.0,
            voice_count_estimate=2,
            dynamic_range_db=15.0,
            has_background_audio=False,
        )

# tests/unit/track_classification/test_acoustic.py
def test_is_commentary_by_acoustic_high_speech_density():
    """Test commentary detection with high speech density."""
    profile = AcousticProfile(
        speech_density=0.85,
        avg_pause_duration=1.2,
        voice_count_estimate=2,
        dynamic_range_db=12.0,
        has_background_audio=True,
    )
    is_commentary, confidence = is_commentary_by_acoustic(profile)
    assert is_commentary is True
    assert confidence >= 0.7

# tests/unit/policy/test_conditions.py
def test_is_original_condition_true():
    """Test is_original condition evaluates true."""
    condition = IsOriginalCondition(min_confidence=0.7)
    classification = TrackClassificationResult(
        track_id=1,
        original_dubbed_status=OriginalDubbedStatus.ORIGINAL,
        confidence=0.9,
        # ...
    )
    result, reason = evaluate_is_original(condition, classification)
    assert result is True
```

### Integration Tests

```python
# tests/integration/test_track_classification.py
def test_classify_file_with_multiple_tracks(test_video_path, db_connection):
    """Test classifying a file with original and dubbed tracks."""
    # Setup: Create file with Japanese and English audio tracks
    result = classify_file_tracks(test_video_path, db_connection)

    assert len(result) == 2
    # Japanese should be original (from metadata)
    jpn_track = next(r for r in result if r.language == "jpn")
    assert jpn_track.original_dubbed_status == OriginalDubbedStatus.ORIGINAL

    # English should be dubbed
    eng_track = next(r for r in result if r.language == "eng")
    assert eng_track.original_dubbed_status == OriginalDubbedStatus.DUBBED
```

### Test Fixtures

Create test fixtures in `tests/fixtures/classification/`:
- `original-japanese.json` - File metadata with Japanese original
- `dubbed-english.json` - Classification result for English dub
- `commentary-profile.json` - Acoustic profile for commentary track

---

## Example Policy

```yaml
# policies/original-audio.yaml
schema_version: 12

# Prefer original audio
audio:
  order:
    - is_original: true
    - "*"
  default:
    is_original: true

# Conditional rules for classification
conditional:
  # Warn about dubbed tracks
  - name: "Flag dubbed audio"
    when:
      is_dubbed:
        min_confidence: 0.8
    then:
      - warn: "{filename} has dubbed audio track"

  # Handle anime specifically
  - name: "Japanese anime original"
    when:
      and:
        - is_dubbed:
            original_language: jpn
        - not:
            is_original: true
    then:
      - warn: "English dub detected for Japanese anime"

  # Commentary handling with acoustic detection
  - name: "Detected unlabeled commentary"
    when:
      and:
        - is_commentary: true
        - not:
            exists:
              track_type: audio
              title_contains: "commentary"
    then:
      - warn: "Acoustically detected commentary track without metadata"
```

---

## Usage Examples

```bash
# Classify single file
vpo inspect ~/Movies/anime.mkv --classify-tracks

# Classify during scan
vpo scan ~/Movies --classify-tracks

# Batch classification
vpo classify run ~/Movies

# Check classification status
vpo classify status ~/Movies/anime.mkv

# Clear cached classification
vpo classify clear ~/Movies/anime.mkv

# Apply policy using classification
vpo apply --policy policies/original-audio.yaml ~/Movies/ --dry-run
```

---

## Common Issues

### Issue: "Classification not available"

**Cause**: Classification hasn't been run on the file.
**Solution**: Run `vpo inspect --classify-tracks` or `vpo classify run`.

### Issue: "Cannot determine original language"

**Cause**: No external metadata available (Radarr/Sonarr not configured).
**Solution**: Configure Radarr/Sonarr metadata plugin, or classification will use position heuristic.

### Issue: "Low confidence classification"

**Cause**: Insufficient signals for reliable classification.
**Solution**: Confidence reflects uncertainty. Use `min_confidence` in policy conditions to filter.

### Issue: "Commentary detection false positive"

**Cause**: Audio track has commentary-like characteristics (high speech density, low dynamic range).
**Solution**: Metadata-based detection takes precedence. Ensure track titles are accurate.
