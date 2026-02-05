# V11 Migration Guide: User-Defined Phases

**Purpose:**
This guide helps you migrate V10 policies to V11, which introduces user-defined processing phases for more flexible workflow control.

---

## Overview

V11 replaces the fixed V9/V10 workflow phases (ANALYZE → APPLY → TRANSCODE) with user-defined phases. This allows you to:

- Create multiple named phases with descriptive names
- Choose which operations run in each phase
- Control execution order and error handling
- Selectively run specific phases from the CLI

---

## Quick Migration

### Before (V10)

```yaml
schema_version: 10
track_order:
  - video
  - audio_main
  - subtitle_main
audio_language_preference:
  - eng
  - jpn
transcode:
  video:
    target_codec: hevc
workflow:
  phases: [ANALYZE, APPLY, TRANSCODE]
  on_error: skip
```

### After (V11)

```yaml
schema_version: 11
config:
  on_error: skip
phases:
  - name: organize
    track_order:
      - video
      - audio_main
      - subtitle_main
    audio_filter:
      languages: [eng, jpn]
  - name: compress
    transcode:
      target_codec: hevc
```

---

## Key Changes

### 1. Schema Version

Change `schema_version: 10` to `schema_version: 11`.

> **Note:** V12 is the current schema version. The V11 migration steps here remain valid as an intermediate step, but new policies should target `schema_version: 12`. See the V12 features documented in [CLAUDE.md](../../CLAUDE.md) for additions beyond V11.

### 2. Global Configuration

The `workflow` section becomes `config`:

```yaml
# V10
workflow:
  on_error: skip

# V11
config:
  on_error: skip
```

### 3. Phases Array

All operations move into named phases:

```yaml
# V10 (implicit fixed phases)
track_order: [...]
audio_filter: {...}
transcode: {...}

# V11 (explicit named phases)
phases:
  - name: phase_name
    track_order: [...]
    audio_filter: {...}
  - name: another_phase
    transcode: {...}
```

### 4. Phase Naming Rules

Phase names must:
- Start with a letter (a-z, A-Z)
- Contain only letters, numbers, hyphens, underscores
- Be 1-64 characters long
- Be unique within the policy
- Not use reserved names: `config`, `schema_version`, `phases`

---

## Migration Strategies

### Strategy 1: Single Phase (Simplest)

Put all operations in one phase for behavior identical to V10:

```yaml
schema_version: 11
config:
  on_error: skip
phases:
  - name: main
    track_order: [video, audio_main, subtitle_main]
    audio_filter:
      languages: [eng, jpn]
    default_flags:
      set_first_video_default: true
    transcode:
      target_codec: hevc
```

### Strategy 2: Logical Grouping

Split operations by purpose:

```yaml
schema_version: 11
config:
  on_error: skip
phases:
  - name: cleanup
    audio_filter:
      languages: [eng, jpn]
    subtitle_filter:
      languages: [eng]
  - name: organize
    track_order: [video, audio_main, subtitle_main]
    default_flags:
      set_first_video_default: true
  - name: optimize
    transcode:
      target_codec: hevc
      quality:
        mode: crf
        crf: 20
```

### Strategy 3: Progressive Processing

Create phases for different processing stages:

```yaml
schema_version: 11
config:
  on_error: continue
phases:
  - name: analyze
    transcription:
      enabled: true
  - name: filter
    audio_filter:
      languages: [eng]
    conditional:
      - when:
          exists: subtitle
          filters:
            languages: [eng]
        then:
          set_default:
            track_type: subtitle
  - name: finalize
    track_order: [video, audio_main, subtitle_main]
```

---

## Operation Reference

Operations within each phase execute in this canonical order:

| Order | Operation | Description |
|-------|-----------|-------------|
| 1 | `container` | Container format conversion |
| 2 | `audio_filter` | Filter audio tracks by language |
| 3 | `subtitle_filter` | Filter subtitle tracks by language |
| 4 | `attachment_filter` | Remove attachments |
| 5 | `track_order` | Reorder tracks by type |
| 6 | `default_flags` | Set default track flags |
| 7 | `conditional` | Apply conditional rules |
| 8 | `audio_synthesis` | Create synthesized audio tracks |
| 9 | `transcode` | Video/audio transcoding |
| 10 | `transcription` | Transcription analysis |

---

## CLI Usage

### Run All Phases

```bash
vpo process -p policy.yaml /path/to/video.mkv
```

### Run Specific Phases

```bash
# Run only the cleanup and organize phases
vpo process -p policy.yaml --phases cleanup,organize /path/to/video.mkv
```

### Dry Run

```bash
vpo process -p policy.yaml --dry-run /path/to/video.mkv
```

### JSON Output

```bash
vpo process -p policy.yaml --json /path/to/video.mkv
```

---

## Common Migration Patterns

### Track Ordering + Language Filtering

```yaml
# V10
track_order: [video, audio_main]
audio_language_preference: [eng, jpn]

# V11
phases:
  - name: organize
    track_order: [video, audio_main]
    audio_filter:
      languages: [eng, jpn]
```

### Transcoding with Conditional Skip

```yaml
# V10
transcode:
  video:
    target_codec: hevc
    skip_if:
      codec_matches: [hevc]

# V11
phases:
  - name: compress
    transcode:
      target_codec: hevc
      skip_if:
        codec_matches: [hevc]
```

### Commentary Detection + Reordering

```yaml
# V10
transcription:
  detect_commentary: true
  reorder_commentary: true
track_order: [video, audio_main, audio_commentary]

# V11
phases:
  - name: analyze
    transcription:
      detect_commentary: true
      reorder_commentary: true
  - name: organize
    track_order: [video, audio_main, audio_commentary]
```

---

## Backward Compatibility

**Important:** The flat policy format (V10 and earlier) is no longer supported. All policies must use the V12 phased format with `phases` and optional `config` sections.

If you have existing V10 policies, you must migrate them to the phased format using the patterns shown in this guide.

---

## Troubleshooting

### "Invalid phase name"

Phase names must match the pattern `^[a-zA-Z][a-zA-Z0-9_-]{0,63}$`:
- Must start with a letter
- Can only contain alphanumeric characters, hyphens, and underscores
- Maximum 64 characters

### "Phase 'X' already exists"

Each phase must have a unique name within the policy.

### "Invalid phase name(s): X" (CLI)

The `--phases` option specified names that don't exist in the policy. Check your policy file for the correct phase names.

---

## Related docs

- [Policy Editor Guide](policy-editor.md) - GUI-based policy editing
- [Architecture Overview](../overview/architecture.md) - System architecture
- [Policies Guide](policies.md) - General policy configuration
- [Transcode Policy Guide](transcode-policy.md) - Transcoding settings
- [Conditional Policies](conditional-policies.md) - Conditional rules
