# CLI Contract: vpo transcribe

**Version**: 1.0.0
**Feature**: 007-audio-transcription

## Command Overview

The `vpo transcribe` command provides transcription and language detection for audio tracks.

## Commands

### vpo transcribe detect

Detect language for audio tracks in a file.

```
vpo transcribe detect [OPTIONS] FILE_PATH
```

**Arguments**:
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| FILE_PATH | path | Yes | Path to media file |

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --track | -t | int | all audio | Specific track index to analyze |
| --update | -u | flag | False | Update language tags in file |
| --threshold | | float | 0.8 | Minimum confidence for updates |
| --dry-run | -n | flag | False | Show what would change without updating |
| --json | | flag | False | Output results as JSON |

**Exit Codes**:
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | File not found or unreadable |
| 2 | No audio tracks found |
| 3 | Transcription plugin not available |
| 4 | Transcription failed |

**Example Output** (default):
```
Analyzing: /path/to/movie.mkv

Track 1 (audio, aac):
  Current language: und
  Detected language: en (English)
  Confidence: 94.2%
  → Would update to: en

Track 2 (audio, ac3):
  Current language: en
  Detected language: en (English)
  Confidence: 97.1%
  → No change needed

Track 3 (audio, aac):
  Current language: und
  Detected language: fr (French)
  Confidence: 62.3%
  → Confidence below threshold (0.80), skipping
```

**Example Output** (--json):
```json
{
  "file": "/path/to/movie.mkv",
  "tracks": [
    {
      "index": 1,
      "codec": "aac",
      "current_language": "und",
      "detected_language": "en",
      "confidence": 0.942,
      "track_type": "main",
      "action": "update"
    },
    {
      "index": 2,
      "codec": "ac3",
      "current_language": "en",
      "detected_language": "en",
      "confidence": 0.971,
      "track_type": "main",
      "action": "none"
    }
  ]
}
```

### vpo transcribe status

Show transcription status for a file or library.

```
vpo transcribe status [OPTIONS] [FILE_PATH]
```

**Arguments**:
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| FILE_PATH | path | No | Path to specific file (omit for library summary) |

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --json | | flag | False | Output as JSON |

**Example Output** (library):
```
Transcription Status

Total audio tracks: 1,247
  With transcription results: 892 (71.5%)
  Pending transcription: 355 (28.5%)

Language distribution:
  en (English): 623 (69.8%)
  fr (French): 142 (15.9%)
  ja (Japanese): 87 (9.8%)
  und (Unknown): 40 (4.5%)

Track types:
  main: 812 (91.0%)
  commentary: 67 (7.5%)
  alternate: 13 (1.5%)
```

### vpo transcribe clear

Clear transcription results.

```
vpo transcribe clear [OPTIONS] FILE_PATH
```

**Arguments**:
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| FILE_PATH | path | Yes | Path to media file |

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --track | -t | int | all | Specific track index |
| --force | -f | flag | False | Skip confirmation prompt |

**Example**:
```
$ vpo transcribe clear /path/to/movie.mkv
Clear transcription results for 3 audio tracks? [y/N]: y
Cleared 3 transcription results.
```

## Policy Integration

Transcription can also be triggered via policy application:

```yaml
# policy.yaml
audio:
  transcription:
    enabled: true
    update_language_from_transcription: true
    confidence_threshold: 0.8
    detect_commentary: true
    reorder_commentary: true
```

```
$ vpo apply --policy policy.yaml /path/to/movie.mkv
```

## Configuration

Global transcription settings in `~/.vpo/config.yaml`:

```yaml
transcription:
  plugin: whisper-local  # or auto-detect
  model_size: base       # tiny, base, small, medium, large
  sample_duration: 60    # seconds
  gpu_enabled: true
```

## Consistency with Existing CLI

This command follows existing VPO CLI patterns:
- File path as positional argument (like `vpo inspect`, `vpo scan`)
- `--dry-run` / `-n` flag for preview mode (like `vpo apply`)
- `--json` flag for machine-readable output (like `vpo inspect --json`)
- Subcommands for related operations (like `vpo jobs list/cancel/clear`)
