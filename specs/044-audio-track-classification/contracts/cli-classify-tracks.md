# Contract: CLI - Classify Tracks

**Feature**: 044-audio-track-classification
**Date**: 2025-12-05
**Module**: `cli/classify.py`, `cli/inspect.py`

## Overview

This contract defines the CLI interface for audio track classification.

---

## Commands

### vpo inspect --classify-tracks

Add classification flag to existing inspect command.

**Usage**:

```bash
vpo inspect /path/to/file.mkv --classify-tracks
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--classify-tracks` | flag | False | Run track classification |
| `--show-acoustic` | flag | False | Show acoustic profile details |

**Output Format**:

```
File: /path/to/movie.mkv
Container: matroska
Duration: 2:15:30

Tracks:
  [0] Video: hevc 1920x1080 @ 23.976fps
  [1] Audio: aac eng 5.1 "English DTS-HD MA"
      Classification: DUBBED (confidence: 92%, method: metadata)
  [2] Audio: aac jpn 5.1 "Japanese"
      Classification: ORIGINAL (confidence: 95%, method: metadata)
  [3] Audio: aac eng 2.0 "Director's Commentary"
      Classification: COMMENTARY (confidence: 88%, method: acoustic)
```

---

### vpo scan --classify-tracks

Add classification flag to existing scan command.

**Usage**:

```bash
vpo scan /path/to/videos --classify-tracks
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--classify-tracks` | flag | False | Run track classification during scan |

**Behavior**:
- Runs classification after introspection
- Stores results in database
- Reports classification statistics in summary

---

### vpo classify

Dedicated command group for classification operations.

#### vpo classify run

Run classification on files.

**Usage**:

```bash
vpo classify run /path/to/videos
vpo classify run /path/to/file.mkv
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--force` | flag | False | Re-classify even if cached results exist |
| `--no-acoustic` | flag | False | Skip acoustic analysis |
| `--recursive` | flag | True | Process directories recursively |

**Output**:

```
Classifying tracks...
  [1/3] movie1.mkv: 2 audio tracks classified
  [2/3] movie2.mkv: 3 audio tracks classified
  [3/3] movie3.mkv: 1 audio track classified (from cache)

Summary:
  Files processed: 3
  Tracks classified: 6 (5 new, 1 cached)
  Original: 3, Dubbed: 2, Unknown: 1
  Commentary detected: 1
```

---

#### vpo classify status

Show classification status for files.

**Usage**:

```bash
vpo classify status /path/to/file.mkv
vpo classify status /path/to/videos
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--format` | choice | `table` | Output format: `table`, `json`, `brief` |

**Output (table)**:

```
Classification Status: /path/to/videos

File                  Track  Type   Status     Confidence  Method
--------------------  -----  -----  ---------  ----------  --------
movie1.mkv            1      audio  original   95%         metadata
movie1.mkv            2      audio  dubbed     92%         metadata
movie2.mkv            1      audio  unknown    45%         position
movie2.mkv            2      audio  commentary 88%         acoustic
```

**Output (json)**:

```json
{
  "files": [
    {
      "path": "/path/to/videos/movie1.mkv",
      "classifications": [
        {
          "track_index": 1,
          "original_dubbed_status": "original",
          "commentary_status": "main",
          "confidence": 0.95,
          "detection_method": "metadata"
        }
      ]
    }
  ]
}
```

---

#### vpo classify clear

Clear cached classification results.

**Usage**:

```bash
vpo classify clear /path/to/file.mkv
vpo classify clear /path/to/videos --all
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--all` | flag | False | Clear all classifications in directory |
| `--yes` | flag | False | Skip confirmation prompt |

**Output**:

```
Clearing classification cache...

This will remove classification results for:
  - movie1.mkv (2 tracks)
  - movie2.mkv (3 tracks)

Continue? [y/N]: y

Cleared 5 classification results.
```

---

## Error Handling

### File Not Found

```
Error: File not found: /path/to/missing.mkv
```

### No Audio Tracks

```
Warning: /path/to/video.mkv has no audio tracks to classify
```

### Classification Failed

```
Error: Failed to classify /path/to/file.mkv
  Reason: Insufficient data for reliable classification
  Hint: Try running with Radarr/Sonarr metadata plugin enabled
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | File not found |
| 3 | No audio tracks |
| 4 | Classification failed |

---

## Integration with Apply

When `--classify-tracks` is used with policies containing `is_original` or `is_dubbed` conditions:

```bash
# Auto-classify if policy requires it
vpo apply --policy original-audio.yaml /path/to/videos

# Policy requires is_original condition - triggers auto-classification
# Classification runs before policy evaluation
```

**Behavior**:
- If policy uses `is_original` or `is_dubbed` conditions
- AND file doesn't have cached classification
- THEN classification runs automatically before evaluation

---

## Help Text

```
Usage: vpo classify [OPTIONS] COMMAND [ARGS]...

  Audio track classification commands.

  Classify audio tracks as original/dubbed and detect commentary
  tracks via acoustic analysis.

Options:
  --help  Show this message and exit.

Commands:
  run     Run classification on files
  status  Show classification status
  clear   Clear cached classification results
```
