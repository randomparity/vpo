# Quickstart: Multi-Language Audio Detection

**Feature**: 035-multi-language-audio-detection
**Date**: 2025-11-26

## Overview

This guide provides step-by-step instructions for implementing multi-language audio detection in VPO.

---

## Prerequisites

1. **Conditional Policy System** (Schema V4+): The `audio_is_multi_language` condition extends the existing conditional policy framework.

2. **Transcription Plugin**: Language detection uses the Whisper integration from the transcription plugin.

3. **Dependencies**: Ensure `openai-whisper` is installed for the Whisper plugin.

---

## Implementation Order

### Phase 1: Data Model & Storage

1. **Add database tables** (`db/schema.py`)
   - `language_analysis_results` table
   - `language_segments` table

2. **Add database models** (`db/models.py`)
   - `LanguageAnalysisResultRecord` dataclass
   - `LanguageSegmentRecord` dataclass

3. **Add domain models** (`language_analysis/models.py`)
   - `LanguageSegment` dataclass
   - `LanguagePercentage` dataclass
   - `LanguageAnalysisResult` dataclass
   - `AnalysisMetadata` dataclass
   - `LanguageClassification` enum

4. **Add database operations** (`db/models.py`)
   - `upsert_language_analysis_result()`
   - `get_language_analysis_result()`
   - `delete_language_analysis_result()`

### Phase 2: Plugin Extension

1. **Extend TranscriptionPlugin protocol** (`transcription/interface.py`)
   - Add `detect_multi_language()` method signature
   - Add `"multi_language_detection"` feature flag

2. **Implement in Whisper plugin** (`plugins/whisper_transcriber/plugin.py`)
   - Add `detect_multi_language()` implementation
   - Add sampling logic
   - Add segment aggregation

3. **Add service layer** (`language_analysis/service.py`)
   - `analyze_track_languages()` function
   - Caching logic
   - Integration with transcription plugin

### Phase 3: Policy Condition

1. **Add condition dataclass** (`policy/models.py`)
   - `AudioIsMultiLanguageCondition` dataclass
   - Update `Condition` union type

2. **Add Pydantic model** (`policy/loader.py`)
   - `AudioIsMultiLanguageModel` validation model
   - Update `ConditionModel` to include new type
   - Add `_convert_audio_is_multi_language()` function

3. **Add evaluation logic** (`policy/conditions.py`)
   - `evaluate_audio_is_multi_language()` function
   - Update `evaluate_condition()` to handle new type

### Phase 4: Policy Actions

1. **Add action dataclasses** (`policy/models.py`)
   - `SetForcedAction` dataclass
   - `SetDefaultAction` dataclass
   - Update `Action` union type

2. **Add action Pydantic models** (`policy/loader.py`)
   - `SetForcedActionModel`
   - `SetDefaultActionModel`
   - Update `ActionModel`

3. **Add action execution** (`policy/actions.py`)
   - `execute_set_forced_action()` function
   - `execute_set_default_action()` function
   - Update `execute_actions()` dispatcher

### Phase 5: CLI Integration

1. **Add scan flag** (`cli/scan.py`)
   - `--analyze-languages` option
   - Integration with language analysis service

2. **Add inspect flag** (`cli/inspect.py`)
   - `--analyze-languages` option
   - `--show-segments` option
   - Output formatting

3. **Add analyze-language command** (`cli/analyze_language.py`)
   - `run` subcommand
   - `status` subcommand
   - `clear` subcommand

4. **Update apply command** (`cli/apply.py`)
   - `--auto-analyze` option
   - Condition evaluation with language results

### Phase 6: Schema Version

1. **Bump schema version** (`policy/loader.py`)
   - Update `CURRENT_SCHEMA_VERSION = 7`
   - Update validation to allow V7 features

---

## Key File Locations

| Component | File Path |
|-----------|-----------|
| Domain models | `src/vpo/language_analysis/models.py` |
| Database schema | `src/vpo/db/schema.py` |
| Database operations | `src/vpo/db/models.py` |
| Plugin protocol | `src/vpo/transcription/interface.py` |
| Whisper plugin | `src/vpo/plugins/whisper_transcriber/plugin.py` |
| Language service | `src/vpo/language_analysis/service.py` |
| Policy models | `src/vpo/policy/models.py` |
| Policy loader | `src/vpo/policy/loader.py` |
| Condition evaluation | `src/vpo/policy/conditions.py` |
| Action execution | `src/vpo/policy/actions.py` |
| CLI commands | `src/vpo/cli/*.py` |

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/language_analysis/test_models.py
def test_language_segment_validation():
    """Test LanguageSegment validates times correctly."""
    with pytest.raises(ValueError):
        LanguageSegment(
            language_code="eng",
            start_time=10.0,
            end_time=5.0,  # Invalid: end < start
            confidence=0.95,
        )

# tests/unit/policy/test_conditions.py
def test_audio_is_multi_language_true():
    """Test condition evaluates true for multi-language track."""
    condition = AudioIsMultiLanguageCondition(
        secondary_language_threshold=0.05,
    )
    tracks = [mock_audio_track(id=1)]
    language_results = {
        1: mock_multi_language_result(primary_percentage=0.82),
    }
    result, reason = evaluate_audio_is_multi_language(
        condition, tracks, language_results
    )
    assert result is True
```

### Integration Tests

```python
# tests/integration/test_language_analysis.py
def test_scan_with_language_analysis(test_video_path, db_connection):
    """Test scanning with language analysis enabled."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", str(test_video_path), "--analyze-languages"],
    )
    assert result.exit_code == 0
    assert "analyzed for language" in result.output
```

### Test Fixtures

Create test files in `tests/fixtures/audio/`:
- `single-language-en.wav` - Pure English audio
- `multi-language-en-fr.wav` - English with French segments
- `no-speech.wav` - Music/effects only

---

## Example Policy

```yaml
# policies/multi-language.yaml
schema_version: 7

# Standard track ordering
audio:
  order:
    - language: eng
    - "*"
  default:
    language: eng

subtitle:
  order:
    - language: eng
      is_forced: true
    - language: eng
    - "*"

# Multi-language handling rules
conditional:
  # Rule 1: Enable forced subs for multi-language English audio
  - name: "Enable forced subs for multi-language audio"
    when:
      and:
        - audio_is_multi_language:
            primary_language: eng
            secondary_language_threshold: 0.05
        - exists:
            track_type: subtitle
            language: eng
            is_forced: true
    then:
      - set_default:
          track_type: subtitle
          language: eng
          is_forced: true
      - warn: "Enabled forced English subtitles for multi-language content"

  # Rule 2: Warn if no forced subs available
  - name: "Warn about missing forced subs"
    when:
      and:
        - audio_is_multi_language:
            primary_language: eng
        - not:
            exists:
              track_type: subtitle
              language: eng
              is_forced: true
    then:
      - warn: "{filename} needs forced English subtitles (multi-language audio)"
```

---

## Usage Examples

```bash
# Scan library with language analysis
vpo scan ~/Movies --analyze-languages

# Inspect single file
vpo inspect ~/Movies/movie.mkv --analyze-languages --show-segments

# Apply multi-language policy
vpo apply --policy policies/multi-language.yaml ~/Movies/movie.mkv --dry-run

# Apply with auto-analysis
vpo apply --policy policies/multi-language.yaml ~/Movies/ --auto-analyze

# Check analysis status
vpo analyze-language status ~/Movies/
```

---

## Common Issues

### Issue: "Language analysis not available"

**Cause**: Analysis hasn't been run on the file.
**Solution**: Run `vpo scan --analyze-languages` or use `--auto-analyze` with `vpo apply`.

### Issue: "Plugin dependency error"

**Cause**: `openai-whisper` not installed.
**Solution**: Install with `pip install openai-whisper`.

### Issue: Analysis takes too long

**Cause**: Using large Whisper model.
**Solution**: Use `--language-model tiny` for faster analysis with slightly lower accuracy.

### Issue: "Insufficient speech detected"

**Cause**: Audio track is primarily music/effects.
**Solution**: This is expected behavior; no language detection possible without speech.
