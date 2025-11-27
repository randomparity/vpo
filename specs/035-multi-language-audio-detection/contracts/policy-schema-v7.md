# Contract: Policy Schema Version 7

**Feature**: 035-multi-language-audio-detection
**Version**: 1.0.0
**Date**: 2025-11-26

## Overview

Schema version 7 extends the conditional policy system with multi-language audio detection conditions and track flag manipulation actions.

---

## Schema Version

```yaml
schema_version: 7
```

**Backward Compatibility**: V6 policies continue to work. V7 adds new condition and action types.

---

## New Condition Type: `audio_is_multi_language`

### Purpose

Evaluates whether an audio track contains multiple spoken languages based on language analysis results.

### Syntax Variants

#### Boolean Shorthand

```yaml
conditional:
  - name: "Multi-language content detected"
    when:
      audio_is_multi_language: true
    then:
      - warn: "File contains multi-language audio"
```

#### With Threshold

```yaml
conditional:
  - name: "Significant secondary language"
    when:
      audio_is_multi_language:
        secondary_language_threshold: 0.10  # 10% minimum
    then:
      - warn: "Secondary language detected (>10%)"
```

#### With Primary Language Constraint

```yaml
conditional:
  - name: "English with foreign dialogue"
    when:
      audio_is_multi_language:
        primary_language: eng
        secondary_language_threshold: 0.05
    then:
      - set_forced:
          track_type: subtitle
          language: eng
```

#### With Track Selector

```yaml
conditional:
  - name: "Default track is multi-language"
    when:
      audio_is_multi_language:
        track_selector:
          is_default: true
        secondary_language_threshold: 0.05
    then:
      - set_default:
          track_type: subtitle
          language: eng
          is_forced: true
```

### Field Definitions

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `audio_is_multi_language` | bool \| object | Yes | - | Condition specification |
| `track_selector` | TrackFilters | No | None | Filter to select specific audio track |
| `primary_language` | string | No | None | Expected primary language (ISO 639-2/B) |
| `secondary_language_threshold` | float | No | 0.05 | Minimum percentage for secondary languages |

### Evaluation Logic

```python
def evaluate_audio_is_multi_language(
    condition: AudioIsMultiLanguageCondition,
    tracks: list[TrackInfo],
    language_results: dict[int, LanguageAnalysisResult],
) -> tuple[bool, str]:
    """Evaluate audio_is_multi_language condition.

    Returns:
        (result, reason) tuple
    """
    # 1. Find matching audio tracks
    audio_tracks = [t for t in tracks if t.type == "audio"]
    if condition.track_selector:
        audio_tracks = filter_tracks(audio_tracks, condition.track_selector)

    if not audio_tracks:
        return (False, "no matching audio tracks")

    # 2. Check each track's language analysis
    for track in audio_tracks:
        result = language_results.get(track.id)
        if result is None:
            continue  # Skip tracks without analysis

        # 3. Check classification
        if result.classification != LanguageClassification.MULTI_LANGUAGE:
            continue  # Not multi-language

        # 4. Check primary language if specified
        if condition.primary_language:
            if result.primary_language != condition.primary_language:
                continue  # Wrong primary language

        # 5. Check secondary threshold
        secondary_total = 1.0 - result.primary_percentage
        if secondary_total >= condition.secondary_language_threshold:
            return (True, f"track {track.id} is multi-language ({secondary_total:.1%} secondary)")

    return (False, "no multi-language tracks matching criteria")
```

---

## New Action Type: `set_forced`

### Purpose

Sets or clears the forced flag on a subtitle track.

### Syntax

```yaml
then:
  - set_forced:
      track_type: subtitle
      language: eng
      is_forced: true  # Optional, default: true
```

### Field Definitions

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `track_type` | string | Yes | - | Must be "subtitle" |
| `language` | string | Yes | - | ISO 639-2/B language code |
| `is_forced` | bool | No | true | Value to set |

### Behavior

1. Find first subtitle track matching language
2. Set forced flag to specified value
3. If no matching track found, emit warning

---

## New Action Type: `set_default`

### Purpose

Sets a track as the default for its type.

### Syntax

```yaml
then:
  - set_default:
      track_type: subtitle
      language: eng
      is_forced: true  # Optional filter
```

### Field Definitions

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `track_type` | string | Yes | - | "audio", "subtitle", or "video" |
| `language` | string | No | None | ISO 639-2/B filter |
| `is_forced` | bool | No | None | Forced flag filter |
| `title_contains` | string | No | None | Title substring filter |

### Behavior

1. Find first track of type matching filters
2. Set as default for that track type
3. Clear default flag from other tracks of same type
4. If no matching track found, emit warning

---

## Combined Example

Complete policy for multi-language audio handling:

```yaml
schema_version: 7

# Track ordering and default settings
audio:
  order:
    - language: eng
    - language: jpn
    - "*"
  default:
    language: eng

subtitle:
  order:
    - language: eng
      is_forced: true
    - language: eng
    - "*"

# Conditional rules for multi-language handling
conditional:
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
      - warn: "{filename} has multi-language audio but no forced English subtitles"
```

---

## Validation Rules

### Condition Validation

1. `audio_is_multi_language: true` is valid boolean shorthand
2. When object form used:
   - `secondary_language_threshold` must be 0.0-1.0
   - `primary_language` must be valid ISO 639-2/B if specified
   - `track_selector` must be valid TrackFilters if specified

### Action Validation

1. `set_forced`:
   - `track_type` must be "subtitle"
   - `language` is required
   - `is_forced` defaults to true

2. `set_default`:
   - `track_type` must be "audio", "subtitle", or "video"
   - At least one filter should be specified (warning if none)

---

## Error Messages

| Error | Cause | Resolution |
|-------|-------|------------|
| `"audio_is_multi_language requires language analysis"` | No analysis available | Run with `--analyze-languages` |
| `"No matching track for set_forced action"` | No subtitle matches | Check language code |
| `"No matching track for set_default action"` | No track matches filters | Review filter criteria |
| `"Invalid secondary_language_threshold"` | Value outside 0.0-1.0 | Use valid percentage |

---

## Migration from V6

1. Existing V6 policies work unchanged
2. To use new features, update `schema_version: 7`
3. No data migration required
4. New conditions/actions only evaluated in V7 mode

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-26 | Initial V7 schema with multi-language support |
