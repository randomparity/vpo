# Conditional Policy Guide

**Purpose:**
This document explains how to use conditional logic in VPO policies to make smart decisions based on file analysis.

---

## Overview

VPO supports conditional rules in V12 policies that let you apply different actions based on file properties. This enables a single policy to handle multiple scenarios without needing separate policy files.

**Key capabilities:**
- Check for track existence (e.g., "does English audio exist?")
- Count tracks matching criteria (e.g., "more than 2 audio tracks")
- Use boolean operators (AND, OR, NOT)
- Compare numeric properties (resolution, channel count)
- Skip processing when unnecessary
- Generate warnings or halt processing

**Contents:**
- [Policy Schema Version](#policy-schema-version)
- [Conditional Rule Structure](#conditional-rule-structure)
- [Condition Types](#condition-types)
- [Boolean Operators](#boolean-operators)
- [Actions](#actions)
- [Rule Evaluation](#rule-evaluation)
- [Complete Examples](#complete-examples)
- [Dry-Run Output](#dry-run-output)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

---

## Policy Schema Version

VPO uses V12 phased policy format. Conditional rules are placed within phases:

```yaml
schema_version: 12
phases:
  - name: check
    conditional:
      - name: "My Rule"
        when:
          exists:
            track_type: audio
            language: eng
        then:
          - warn: "English audio found"
```

---

## Conditional Rule Structure

Each conditional rule has:
- **name**: A descriptive identifier for the rule (shown in dry-run output)
- **when**: A condition that evaluates to true or false
- **then**: Actions to execute when the condition is true
- **else** (optional): Actions to execute when the condition is false

```yaml
conditional:
  - name: "Handle 4K content"
    when:
      exists:
        track_type: video
        height: { gte: 2160 }
    then:
      - skip_video_transcode: true
    else:
      - warn: "Non-4K content detected"
```

---

## Condition Types

### Exists Condition

Check if at least one track matches criteria:

```yaml
when:
  exists:
    track_type: video    # Required: video, audio, subtitle, attachment
    # Optional filters:
    language: eng        # ISO 639-2/B code or list
    codec: hevc          # Codec name or list
    is_default: true     # Boolean
    is_forced: false     # Boolean
    channels: 6          # Exact value or comparison
    width: 1920          # Exact value or comparison
    height: 1080         # Exact value or comparison
    title: "commentary"  # Substring match
```

**Multiple values** - Match any in the list:

```yaml
when:
  exists:
    track_type: audio
    language: [eng, und]  # English OR undefined
    codec: [aac, ac3]     # AAC OR AC3
```

### Count Condition

Check the number of tracks matching criteria:

```yaml
when:
  count:
    track_type: audio
    eq: 1                 # Exactly 1 audio track
```

**Comparison operators:**
- `eq`: Equal to
- `lt`: Less than
- `lte`: Less than or equal
- `gt`: Greater than
- `gte`: Greater than or equal

```yaml
when:
  count:
    track_type: audio
    language: eng
    gt: 1                 # More than 1 English audio track
```

### Numeric Property Comparisons

Compare track properties using operators:

```yaml
when:
  exists:
    track_type: video
    height: { gte: 2160 }   # 4K or higher
    width: { gte: 3840 }
```

```yaml
when:
  exists:
    track_type: audio
    channels: { gt: 2 }     # Surround sound (> stereo)
```

### Title Matching

Match track titles with substring or regex:

```yaml
# Substring match (case-insensitive)
when:
  exists:
    track_type: audio
    title: "commentary"

# Regex match
when:
  exists:
    track_type: audio
    title:
      regex: "^Director.*Commentary$"
```

---

## Boolean Operators

### AND - All conditions must be true

```yaml
when:
  and:
    - exists:
        track_type: audio
        language: jpn
    - exists:
        track_type: subtitle
        language: eng
```

### OR - At least one condition must be true

```yaml
when:
  or:
    - exists:
        track_type: video
        codec: hevc
    - exists:
        track_type: video
        codec: h264
```

### NOT - Negate a condition

```yaml
when:
  not:
    exists:
      track_type: audio
      channels: { gte: 6 }
```

### Nesting Operators

Boolean operators can be nested (up to 3 levels):

```yaml
when:
  and:
    - exists:
        track_type: video
        height: { gte: 2160 }
    - or:
        - exists:
            track_type: video
            codec: hevc
        - exists:
            track_type: video
            codec: av1
```

---

## Actions

### Skip Actions

Skip specific processing steps:

```yaml
then:
  - skip_video_transcode: true   # Skip video transcoding
  - skip_audio_transcode: true   # Skip audio transcoding
  - skip_track_filter: true      # Skip track filtering
```

**Use case:** Avoid re-encoding files already in target codec:

```yaml
conditional:
  - name: "Skip HEVC transcode"
    when:
      exists:
        track_type: video
        codec: hevc
    then:
      - skip_video_transcode: true
```

### Warn Action

Log a warning and continue processing:

```yaml
then:
  - warn: "File has no English audio"
```

### Fail Action

Halt processing with an error:

```yaml
then:
  - fail: "Cannot process - missing required tracks"
```

### Message Placeholders

Use placeholders in warn/fail messages:

| Placeholder | Value |
|-------------|-------|
| `{filename}` | File name (e.g., "movie.mkv") |
| `{path}` | Full file path |
| `{rule_name}` | Name of the matching rule |

```yaml
then:
  - warn: "{filename} has non-standard audio configuration"
```

### Multiple Actions

Multiple actions can be combined:

```yaml
then:
  - skip_video_transcode: true
  - skip_audio_transcode: true
  - warn: "Skipping all transcoding for {filename}"
```

---

## Rule Evaluation

### First-Match-Wins

Rules are evaluated in order. The first rule whose condition matches wins, and subsequent rules are not evaluated:

```yaml
conditional:
  # Rule 1: 4K HEVC - skip everything
  - name: "4K HEVC optimal"
    when:
      and:
        - exists:
            track_type: video
            height: { gte: 2160 }
        - exists:
            track_type: video
            codec: hevc
    then:
      - skip_video_transcode: true
      - skip_audio_transcode: true

  # Rule 2: 4K non-HEVC - skip audio only
  - name: "4K needs video transcode"
    when:
      exists:
        track_type: video
        height: { gte: 2160 }
    then:
      - skip_audio_transcode: true

  # Rule 3: Fallback for everything else
  - name: "Standard processing"
    when:
      exists:
        track_type: video
    then:
      - warn: "Standard transcode pipeline"
```

### Else Clause

The `else` clause executes when the condition is false:

```yaml
conditional:
  - name: "Check surround sound"
    when:
      exists:
        track_type: audio
        channels: { gte: 6 }
    then:
      - warn: "File has surround audio"
    else:
      - warn: "No surround audio - may need downmix"
```

### No Match Behavior

When no rules match (and no else clause on the last rule), processing continues with other policy sections unchanged.

---

## Complete Examples

### Example 1: Resolution-Based Transcoding

```yaml
schema_version: 12
phases:
  - name: check
    conditional:
      - name: "4K HEVC passthrough"
        when:
          and:
            - exists:
                track_type: video
                height: { gte: 2160 }
            - exists:
                track_type: video
                codec: hevc
        then:
          - skip_video_transcode: true
          - warn: "4K HEVC - no transcode needed"

      - name: "HD content"
        when:
          exists:
            track_type: video
            height: { lt: 2160 }
        then:
          - warn: "HD content will be transcoded"

  - name: filter
    audio_filter:
      languages: [eng, und]
```

### Example 2: Japanese Anime Policy

```yaml
schema_version: 12
phases:
  - name: validate
    conditional:
      - name: "Japanese with English subs"
        when:
          and:
            - exists:
                track_type: audio
                language: jpn
            - exists:
                track_type: subtitle
                language: eng
        then:
          - warn: "Proper anime setup detected"

      - name: "Missing English subs"
        when:
          and:
            - exists:
                track_type: audio
                language: jpn
            - not:
                exists:
                  track_type: subtitle
                  language: eng
        then:
          - fail: "{filename} missing English subtitles"

  - name: organize
    audio_filter:
      languages: [jpn, eng]
    subtitle_filter:
      languages: [eng]
```

### Example 3: Multi-Audio Detection

```yaml
schema_version: 12
phases:
  - name: analyze
    conditional:
      - name: "Single audio track"
        when:
          count:
            track_type: audio
            eq: 1
        then:
          - warn: "Single audio - no filtering needed"
          - skip_track_filter: true

      - name: "Multiple audio tracks"
        when:
          count:
            track_type: audio
            gt: 1
        then:
          - warn: "{filename} has multiple audio tracks"

  - name: filter
    audio_filter:
      languages: [eng, und]
      minimum: 1
```

---

## Dry-Run Output

Use `--dry-run` to preview conditional rule evaluation:

```bash
vpo policy run --policy policy.yaml --dry-run /path/to/file.mkv
```

The output shows:
- Which rules were evaluated
- The condition result (matched/not matched)
- The reason for the result
- Any warnings generated

---

## Error Handling

### ConditionalFailError

Raised when a `fail` action is triggered:

```
Error: Conditional rule "Missing required tracks" failed
File: /videos/movie.mkv
Message: Cannot process - missing required tracks
```

### Validation Errors

Invalid condition syntax is caught at policy load time:

```
Error: Invalid condition at conditional[0].when: Unknown track_type 'invalid'
```

---

## Best Practices

1. **Order rules from specific to general** - Put narrow conditions first since first match wins
2. **Use descriptive rule names** - They appear in dry-run output for debugging
3. **Include fallback rules** - Handle edge cases with a catch-all rule at the end
4. **Test with dry-run first** - Preview condition evaluation before applying
5. **Keep nesting shallow** - Maximum 3 levels; prefer simpler conditions when possible
6. **Use else clauses sparingly** - Multiple specific rules are often clearer

---

## Related docs

- [Policy Configuration Guide](policies.md)
- [CLI Usage](cli-usage.md)
- [Transcode Policy](transcode-policy.md)
- [ADR-0004: Conditional Policy Schema](../decisions/ADR-0004-conditional-policy-schema.md)
