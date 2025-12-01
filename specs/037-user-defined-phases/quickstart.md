# Quickstart: User-Defined Processing Phases

**Feature**: 037-user-defined-phases
**Date**: 2025-11-30

## Overview

This guide explains how to use V11 policies with user-defined phases in VPO.

## Creating a V11 Policy

### Basic Structure

```yaml
schema_version: 11

config:
  audio_language_preference: [eng, und]
  on_error: continue

phases:
  - name: my-first-phase
    # operations go here
```

### Key Differences from V10

| V10 | V11 |
|-----|-----|
| `workflow.phases: [apply, transcode]` | `phases:` array with named phases |
| `workflow.on_error: continue` | `config.on_error: continue` |
| Operations at root level | Operations inside phase definitions |
| Fixed phase names (analyze, apply, transcode) | User-defined phase names |

## Example: Complete Media Normalization

```yaml
schema_version: 11

config:
  audio_language_preference: [eng, und]
  subtitle_language_preference: [eng, und]
  commentary_patterns: [commentary, director]
  on_error: continue

phases:
  - name: cleanup
    audio_filter:
      languages: [eng, und]
      minimum: 1
    subtitle_filter:
      languages: [eng, und]
      preserve_forced: true
    attachment_filter:
      remove_all: true

  - name: organize
    track_order:
      - video
      - audio_main
      - audio_alternate
      - subtitle_main
      - subtitle_forced
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true

  - name: enhance
    audio_synthesis:
      tracks:
        - name: "AAC Stereo"
          codec: aac
          channels: "2.0"
          bitrate: "192k"
          source:
            prefer:
              - codec: [truehd, dts-hd, flac]

  - name: compress
    transcode:
      video:
        target_codec: hevc
        skip_if:
          codec_matches: [hevc, h265]
        quality:
          mode: crf
          crf: 20
      audio:
        preserve_codecs: [truehd, dts-hd, flac, aac]
        transcode_to: aac
        transcode_bitrate: 128k
```

## Running Policies

### Process All Phases

```bash
# Process a single file
vpo process -p my-policy.yaml /path/to/video.mkv

# Process a directory
vpo process -p my-policy.yaml -R /path/to/videos/

# Dry-run to preview changes
vpo process -p my-policy.yaml -n /path/to/video.mkv
```

### Run Specific Phases

```bash
# Run only the cleanup phase
vpo process -p my-policy.yaml --phases cleanup /path/to/video.mkv

# Run cleanup and organize phases
vpo process -p my-policy.yaml --phases cleanup,organize /path/to/video.mkv

# Run only transcode (skips earlier phases)
vpo process -p my-policy.yaml --phases compress /path/to/video.mkv
```

### Error Handling

```bash
# Override on_error setting
vpo process -p my-policy.yaml --on-error fail /path/to/videos/

# Continue processing even if some files fail
vpo process -p my-policy.yaml --on-error continue /path/to/videos/
```

## Phase Naming Rules

Valid phase names:
- Start with a letter (a-z, A-Z)
- Contain only letters, numbers, hyphens, underscores
- Maximum 64 characters
- Must be unique within the policy

```yaml
# Good phase names
phases:
  - name: cleanup
  - name: audio-normalize
  - name: video_transcode_v2
  - name: Phase1

# Bad phase names (will cause validation errors)
phases:
  - name: 1-first        # Can't start with number
  - name: "my phase"     # No spaces
  - name: config         # Reserved word
  - name: schema_version # Reserved word
```

## Operation Order Within Phases

When a phase contains multiple operations, they execute in this order:

1. container (format conversion)
2. audio_filter (remove audio tracks)
3. subtitle_filter (remove subtitle tracks)
4. attachment_filter (remove attachments)
5. track_order (reorder tracks)
6. default_flags (set default/forced flags)
7. conditional (conditional rules)
8. audio_synthesis (create new audio tracks)
9. transcode (video/audio encoding)
10. transcription (language analysis)

You don't need to worry about ordering—VPO handles it automatically.

## Understanding Output

### Console Output

```
Processing: /path/to/video.mkv
  Phase 1/4 [cleanup]: Filtering tracks...
    - Removed 2 audio tracks
    - Removed 3 subtitle tracks
  Phase 2/4 [organize]: Reordering tracks...
    - Reordered 5 tracks
  Phase 3/4 [enhance]: Synthesizing audio...
    - Created AAC Stereo track
  Phase 4/4 [compress]: Transcoding...
    - Transcoded video to HEVC
    - Transcoded 1 audio track to AAC
Completed: 4 phases, 8 changes
```

### JSON Output

```bash
vpo process -p my-policy.yaml --json /path/to/video.mkv
```

```json
{
  "success": true,
  "files_processed": 1,
  "results": [
    {
      "file": "/path/to/video.mkv",
      "success": true,
      "phases": [
        {"name": "cleanup", "success": true, "changes": 5},
        {"name": "organize", "success": true, "changes": 5},
        {"name": "enhance", "success": true, "changes": 1},
        {"name": "compress", "success": true, "changes": 2}
      ],
      "total_changes": 13
    }
  ]
}
```

## Error Recovery

If a phase fails mid-execution, VPO automatically rolls back all changes from that phase:

```
Processing: /path/to/video.mkv
  Phase 1/3 [cleanup]: Filtering tracks...
    - Removed 2 audio tracks
  Phase 2/3 [transcode]: Transcoding...
    ERROR: Encoder 'libx265' not found
    Rolling back phase changes...
  Phase 2/3 [transcode]: FAILED (rolled back)

File processing failed at phase 'transcode'
```

The file is restored to its state before the failed phase started.

## Web UI Phase Editor

When editing policies in the web UI:

1. Click "Add Phase" to create a new phase
2. Enter a name for the phase
3. Enable operations using the toggles
4. Configure each operation as needed
5. Drag phases to reorder them
6. Click "Save" to save changes

The YAML preview updates in real-time as you make changes.

## Migration from V10

V11 is not backward compatible with V10. To migrate:

1. Create a new V11 policy file
2. Set `schema_version: 11`
3. Create a `config:` section with global settings
4. Create a `phases:` array with your workflow phases
5. Move operations into the appropriate phases

See [data-model.md](./data-model.md) for a complete migration example.

## Common Patterns

### Two-Pass Workflow

```yaml
phases:
  - name: prepare
    container:
      target: mkv
    audio_filter:
      languages: [eng]
  - name: process
    transcode:
      video:
        target_codec: hevc
```

### Analysis-Only

```yaml
phases:
  - name: analyze
    transcription:
      enabled: true
```

### Transcode-Only

```yaml
phases:
  - name: compress
    transcode:
      video:
        target_codec: hevc
      audio:
        transcode_to: aac
```

### Conditional Finalization

```yaml
phases:
  - name: normalize
    audio_filter:
      languages: [eng, und]
  - name: finalize
    conditional:
      - name: force-subs-for-foreign
        when:
          not:
            exists:
              track_type: audio
              language: eng
        then:
          - set_forced:
              track_type: subtitle
              language: eng
              value: true
```
