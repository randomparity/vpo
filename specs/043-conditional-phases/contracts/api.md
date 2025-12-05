# API Contract: Conditional Phase Execution

**Feature**: 043-conditional-phases
**Date**: 2025-12-04

## Policy Schema Extensions

### Phase Definition Schema

New optional fields added to phase definitions in V12 policies:

```yaml
phases:
  - name: string                    # Required, existing
    # ... existing operation fields ...

    # NEW: Skip conditions (optional)
    skip_when:
      video_codec: [string]         # Skip if video codec in list
      audio_codec_exists: string    # Skip if audio track with codec exists
      subtitle_language_exists: string  # Skip if subtitle with language exists
      container: [string]           # Skip if container format in list
      resolution: string            # Skip if resolution matches exactly
      resolution_under: string      # Skip if resolution under threshold
      file_size_under: string       # Skip if file size under (e.g., "5GB")
      file_size_over: string        # Skip if file size over
      duration_under: string        # Skip if duration under (e.g., "30m")
      duration_over: string         # Skip if duration over

    # NEW: Dependencies (optional)
    depends_on: [string]            # List of phase names this phase depends on

    # NEW: Positive run condition (optional)
    run_if:
      phase_modified: string        # Run only if named phase modified file

    # NEW: Error handling override (optional)
    on_error: continue | stop | skip  # Override global config.on_error
```

### Validation Rules

#### skip_when

- At least one field must be set if `skip_when` is present
- Multiple fields use OR logic (any match causes skip)
- Values:
  - `video_codec`: list of codec names (case-insensitive), e.g., `[hevc, h265, av1]`
  - `audio_codec_exists`: codec name, e.g., `truehd`, `dts-hd`
  - `subtitle_language_exists`: ISO 639-1/2 code, e.g., `eng`, `jpn`
  - `container`: list of extensions, e.g., `[mkv, mp4]`
  - `resolution`: exact match, e.g., `1080p`, `4k`, `2160p`
  - `resolution_under`: threshold, e.g., `1080p` (skip if < 1080p)
  - `file_size_under`, `file_size_over`: size with unit, e.g., `5GB`, `500MB`
  - `duration_under`, `duration_over`: duration with unit, e.g., `30m`, `2h`

#### depends_on

- List of phase names (strings)
- Each name must exist in the policy
- Self-reference is rejected
- Circular dependencies are rejected (validation error)
- Empty list `[]` is treated as no dependencies

#### run_if

- Exactly one field must be set
- `phase_modified`: referenced phase must exist and appear earlier in policy

#### on_error

- Values: `continue`, `stop`, `skip`
- If omitted, uses global `config.on_error`

---

## CLI Contract

### `vpo process` Command

No new flags required. Behavior changes:

1. **Dependency Warning** (new):
   When `--phases` filter is used and selected phases have dependencies on non-selected phases:
   ```
   Warning: Phase 'finalize' depends on 'transcode' which is not selected.
   Processing may fail or produce unexpected results.
   ```

2. **Skip Messages** (new):
   Console output indicates when phases are skipped:
   ```
   Phase 1/5 [analyze]: Processing...
   Phase 2/5 [normalize]: Processing...
   Phase 3/5 [transcode]: Skipped (video_codec matches [hevc, h265])
   Phase 4/5 [verify]: Skipped (dependency 'transcode' did not complete)
   Phase 5/5 [cleanup]: Processing...
   ```

### Exit Codes

No changes to existing exit codes:
- `0`: Success
- `1`: Processing error
- `2`: Policy validation error (including circular dependencies)
- `3`: Invalid phase name in `--phases`

---

## JSON Output Contract

### Extended Phase Result

```json
{
  "file": "/path/to/video.mkv",
  "phases": [
    {
      "name": "transcode",
      "outcome": "skipped",
      "skip_reason": {
        "type": "condition",
        "condition": "video_codec",
        "matched_value": "hevc",
        "message": "Phase 'transcode' skipped: video_codec matches [hevc, h265]"
      },
      "dependencies": {
        "normalize": "completed"
      },
      "actions": []
    },
    {
      "name": "verify",
      "outcome": "skipped",
      "skip_reason": {
        "type": "dependency",
        "dependency": "transcode",
        "dependency_outcome": "skipped",
        "message": "Phase 'verify' skipped: dependency 'transcode' did not complete"
      },
      "dependencies": {
        "transcode": "skipped"
      },
      "actions": []
    }
  ],
  "summary": {
    "total_phases": 5,
    "completed": 3,
    "skipped": 2,
    "failed": 0
  }
}
```

### Skip Reason Types

| Type | Description |
|------|-------------|
| `condition` | `skip_when` condition matched |
| `dependency` | Dependency phase did not complete |
| `run_if` | `run_if` condition not satisfied |
| `error_mode` | Skipped due to `on_error: skip` after failure |

### Phase Outcome Values

| Outcome | Description |
|---------|-------------|
| `completed` | Phase executed successfully |
| `failed` | Phase executed but encountered error |
| `skipped` | Phase was skipped (see skip_reason) |

---

## Validation Error Messages

### Circular Dependency

```
Policy validation error: Circular dependency detected
  → Phase 'A' depends on 'B'
  → Phase 'B' depends on 'C'
  → Phase 'C' depends on 'A'
```

### Missing Dependency Target

```
Policy validation error: Phase 'finalize' depends on unknown phase 'transcod'
  Did you mean 'transcode'?
```

### Self-Dependency

```
Policy validation error: Phase 'transcode' cannot depend on itself
```

### Invalid run_if Reference

```
Policy validation error: Phase 'verify' run_if references 'cleanup'
  but 'cleanup' is defined after 'verify'
```

### Empty skip_when

```
Policy validation error: Phase 'transcode' has empty skip_when
  At least one condition must be specified
```

---

## Example Policy

```yaml
schema_version: 12

config:
  audio_language_preference: [eng, und]
  on_error: continue

phases:
  - name: analyze
    transcription:
      enabled: true
    on_error: skip

  - name: normalize
    container:
      target: mkv
    audio_filter:
      languages: [eng, und]
    on_error: stop

  - name: transcode
    skip_when:
      video_codec: [hevc, h265]
      file_size_under: 1GB
    transcode:
      video:
        target_codec: hevc
        quality:
          mode: crf
          crf: 20
    depends_on: [normalize]
    on_error: stop

  - name: verify
    run_if:
      phase_modified: transcode
    conditional:
      - name: size_check
        when:
          file_size_over: 10GB
        then:
          - log_warning: "Large output file"
    depends_on: [transcode]

  - name: cleanup
    attachment_filter:
      remove_all: true
    depends_on: [normalize]
    on_error: continue
```
