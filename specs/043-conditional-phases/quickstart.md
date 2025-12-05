# Quickstart: Conditional Phase Execution

**Feature**: 043-conditional-phases
**Date**: 2025-12-04

## Overview

This guide demonstrates the three main capabilities added to VPO's phase system:

1. **Skip conditions** (`skip_when`) - Skip phases based on file characteristics
2. **Phase dependencies** (`depends_on`) - Skip phases when prerequisites fail
3. **Per-phase error handling** (`on_error`) - Control error behavior per phase

## Scenario 1: Skip Transcode for Already-Compliant Files

**Goal**: Skip the expensive transcode phase if the video is already HEVC.

### Policy

```yaml
schema_version: 12

config:
  on_error: continue

phases:
  - name: normalize
    container:
      target: mkv
    audio_filter:
      languages: [eng, und]

  - name: transcode
    skip_when:
      video_codec: [hevc, h265]
    transcode:
      video:
        target_codec: hevc
        quality:
          mode: crf
          crf: 20
```

### Expected Behavior

**File A** (H.264 video):
```
$ vpo process -p policy.yaml /videos/h264-movie.mkv
Phase 1/2 [normalize]: Processing... done (2 actions)
Phase 2/2 [transcode]: Processing... done (1 action, transcoded to HEVC)
```

**File B** (HEVC video):
```
$ vpo process -p policy.yaml /videos/hevc-movie.mkv
Phase 1/2 [normalize]: Processing... done (2 actions)
Phase 2/2 [transcode]: Skipped (video_codec matches [hevc, h265])
```

---

## Scenario 2: Phase Dependencies

**Goal**: Only run verification after transcode completes, cleanup after normalize.

### Policy

```yaml
schema_version: 12

phases:
  - name: normalize
    container:
      target: mkv

  - name: transcode
    skip_when:
      video_codec: [hevc, h265]
    transcode:
      video:
        target_codec: hevc
    depends_on: [normalize]

  - name: verify
    conditional:
      - name: size_check
        when:
          file_size_over: 10GB
        then:
          - log_warning: "Large file detected"
    depends_on: [transcode]

  - name: cleanup
    attachment_filter:
      remove_all: true
    depends_on: [normalize]
```

### Expected Behavior

**File A** (H.264 video, needs transcode):
```
Phase 1/4 [normalize]: Processing... done
Phase 2/4 [transcode]: Processing... done (transcoded)
Phase 3/4 [verify]: Processing... done
Phase 4/4 [cleanup]: Processing... done
```

**File B** (HEVC video, transcode skipped):
```
Phase 1/4 [normalize]: Processing... done
Phase 2/4 [transcode]: Skipped (video_codec matches [hevc, h265])
Phase 3/4 [verify]: Skipped (dependency 'transcode' did not complete)
Phase 4/4 [cleanup]: Processing... done
```

Note: `cleanup` still runs because it depends on `normalize` (which completed), not `transcode`.

---

## Scenario 3: Per-Phase Error Handling

**Goal**: Analysis can fail without stopping; transcode failures must stop immediately.

### Policy

```yaml
schema_version: 12

config:
  on_error: continue  # Default for phases without override

phases:
  - name: analyze
    transcription:
      enabled: true
    on_error: skip  # If Whisper fails, mark as skipped and continue

  - name: normalize
    container:
      target: mkv
    on_error: stop  # Container issues are critical

  - name: transcode
    transcode:
      video:
        target_codec: hevc
    on_error: stop  # Transcode failures mean corrupted output
```

### Expected Behavior

**Whisper API unavailable**:
```
Phase 1/3 [analyze]: Error (Whisper API timeout) - Skipped per on_error policy
Phase 2/3 [normalize]: Processing... done
Phase 3/3 [transcode]: Processing... done
Result: Success (1 phase skipped)
```

**FFmpeg crash during transcode**:
```
Phase 1/3 [analyze]: Processing... done
Phase 2/3 [normalize]: Processing... done
Phase 3/3 [transcode]: Error (FFmpeg returned non-zero exit code)
Result: Failed - processing halted due to on_error: stop
```

---

## Scenario 4: Conditional Execution Based on Modifications

**Goal**: Only verify if transcode actually made changes.

### Policy

```yaml
schema_version: 12

phases:
  - name: transcode
    skip_when:
      video_codec: [hevc, h265]
    transcode:
      video:
        target_codec: hevc

  - name: verify
    run_if:
      phase_modified: transcode
    conditional:
      - name: bitrate_check
        when:
          video_bitrate_over: 20M
        then:
          - log_warning: "High bitrate output"
```

### Expected Behavior

**File A** (transcoded):
```
Phase 1/2 [transcode]: Processing... done (file modified)
Phase 2/2 [verify]: Processing... done
```

**File B** (transcode skipped):
```
Phase 1/2 [transcode]: Skipped (video_codec matches [hevc, h265])
Phase 2/2 [verify]: Skipped ('transcode' made no modifications)
```

---

## Scenario 5: Using --phases with Dependencies

**Goal**: Re-run only transcode phase after fixing an issue.

```
$ vpo process -p policy.yaml --phases transcode /videos/movie.mkv
Warning: Phase 'transcode' depends on 'normalize' which is not selected.
Processing may fail or produce unexpected results.

Phase 1/1 [transcode]: Processing... done
```

The warning helps users understand that they're skipping prerequisite phases.

---

## JSON Output Example

```
$ vpo process -p policy.yaml --json /videos/hevc-movie.mkv
```

```json
{
  "file": "/videos/hevc-movie.mkv",
  "phases": [
    {
      "name": "normalize",
      "outcome": "completed",
      "actions": [...]
    },
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
      }
    },
    {
      "name": "verify",
      "outcome": "skipped",
      "skip_reason": {
        "type": "dependency",
        "dependency": "transcode",
        "dependency_outcome": "skipped",
        "message": "Phase 'verify' skipped: dependency 'transcode' did not complete"
      }
    }
  ],
  "summary": {
    "total_phases": 3,
    "completed": 1,
    "skipped": 2,
    "failed": 0
  }
}
```

---

## Validation Scenarios

### Circular Dependency (Error)

```yaml
phases:
  - name: a
    depends_on: [b]
  - name: b
    depends_on: [a]
```

```
$ vpo process -p policy.yaml /videos/movie.mkv
Error: Policy validation failed
  Circular dependency detected: a → b → a
```

### Missing Dependency (Error)

```yaml
phases:
  - name: finalize
    depends_on: [transcod]  # Typo
```

```
$ vpo process -p policy.yaml /videos/movie.mkv
Error: Policy validation failed
  Phase 'finalize' depends on unknown phase 'transcod'
  Did you mean 'transcode'?
```
