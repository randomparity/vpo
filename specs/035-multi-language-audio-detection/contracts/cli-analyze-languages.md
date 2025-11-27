# Contract: CLI Language Analysis Commands

**Feature**: 035-multi-language-audio-detection
**Version**: 1.0.0
**Date**: 2025-11-26

## Overview

CLI interface for triggering and viewing multi-language audio analysis.

---

## Command: `vpo scan --analyze-languages`

### Purpose

Scans library and performs language analysis on audio tracks.

### Syntax

```bash
vpo scan /path/to/videos --analyze-languages [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--analyze-languages` | flag | false | Enable language analysis |
| `--language-model` | string | "base" | Whisper model size |
| `--force-reanalyze` | flag | false | Re-analyze even if cached |

### Examples

```bash
# Scan with language analysis
vpo scan ~/Movies --analyze-languages

# Use smaller model for speed
vpo scan ~/Movies --analyze-languages --language-model tiny

# Force re-analysis of all files
vpo scan ~/Movies --analyze-languages --force-reanalyze
```

### Output

```
Scanning /home/user/Movies...
  Found 42 media files
  Analyzing languages... [=============>        ] 15/42

Scan complete:
  42 files scanned
  15 files analyzed for language
  3 files detected as multi-language
```

---

## Command: `vpo inspect --analyze-languages`

### Purpose

Inspect single file with language analysis.

### Syntax

```bash
vpo inspect /path/to/file.mkv --analyze-languages [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--analyze-languages` | flag | false | Perform language analysis |
| `--language-model` | string | "base" | Whisper model size |
| `--show-segments` | flag | false | Show individual language segments |

### Examples

```bash
# Inspect with language analysis
vpo inspect ~/Movies/movie.mkv --analyze-languages

# Show detailed segment information
vpo inspect ~/Movies/movie.mkv --analyze-languages --show-segments
```

### Output (Standard)

```
File: movie.mkv
Duration: 2:15:30
Container: Matroska

Video Tracks:
  #0: HEVC 1920x1080 @ 23.976fps (default)

Audio Tracks:
  #1: TrueHD 7.1 English (default)
      Language Analysis: MULTI_LANGUAGE
        Primary: English (82%)
        Secondary: French (12%), German (6%)
  #2: AAC 2.0 English (commentary)

Subtitle Tracks:
  #3: PGS English (forced)
  #4: SRT English
  #5: SRT French
```

### Output (With Segments)

```
Audio Track #1 Language Analysis:
  Classification: MULTI_LANGUAGE
  Primary Language: English (82%)
  Secondary Languages:
    - French: 12%
    - German: 6%

  Language Segments:
    00:00:30 - 00:45:00  English (confidence: 0.98)
    00:45:00 - 00:48:30  French (confidence: 0.95)
    00:48:30 - 01:15:00  English (confidence: 0.97)
    01:15:00 - 01:16:30  German (confidence: 0.92)
    01:16:30 - 01:22:00  English (confidence: 0.96)
    01:22:00 - 01:25:00  French (confidence: 0.94)
    01:25:00 - 02:15:00  English (confidence: 0.98)
```

---

## Command: `vpo analyze-language`

### Purpose

Dedicated command for language analysis operations.

### Syntax

```bash
vpo analyze-language [OPTIONS] FILE_OR_PATH
```

### Subcommands

#### `vpo analyze-language run`

Run language analysis on files.

```bash
vpo analyze-language run /path/to/file.mkv
vpo analyze-language run /path/to/directory --recursive
```

#### `vpo analyze-language status`

Show analysis status for files.

```bash
vpo analyze-language status /path/to/file.mkv
vpo analyze-language status /path/to/directory
```

Output:
```
Language Analysis Status:
  Total files: 42
  Analyzed: 38
  Pending: 4
  Multi-language: 3
  Single-language: 35
```

#### `vpo analyze-language clear`

Clear cached analysis results.

```bash
vpo analyze-language clear /path/to/file.mkv
vpo analyze-language clear --all
```

---

## Command: `vpo apply` (Integration)

### Behavior

When applying a policy with `audio_is_multi_language` conditions:

1. **Analysis Available**: Evaluate condition normally
2. **Analysis Missing**:
   - With `--auto-analyze`: Run analysis, then evaluate
   - Without: Warn and skip condition (evaluate as false)

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--auto-analyze` | flag | false | Auto-run language analysis if needed |

### Examples

```bash
# Apply policy (warns if analysis missing)
vpo apply --policy multi-lang.yaml ~/Movies/movie.mkv

# Apply policy with automatic analysis
vpo apply --policy multi-lang.yaml ~/Movies/movie.mkv --auto-analyze

# Dry-run to preview
vpo apply --policy multi-lang.yaml ~/Movies/movie.mkv --dry-run
```

### Dry-Run Output

```
Applying policy: multi-lang.yaml
File: movie.mkv

Conditional Rules:
  Rule "Enable forced subs for multi-language audio":
    Condition: audio_is_multi_language(primary_language=eng, threshold=5%)
    Evaluation: TRUE (track #1 is multi-language: 18% secondary)
    Actions:
      - set_default(subtitle, language=eng, is_forced=true) -> Track #3
      - warn("Enabled forced English subtitles for multi-language content")

Plan:
  - Set subtitle track #3 (PGS English forced) as default

Run without --dry-run to apply changes.
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | No files found |
| 3 | Analysis failed |
| 4 | Plugin not available |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VPO_LANGUAGE_MODEL` | Default Whisper model | "base" |
| `VPO_LANGUAGE_GPU` | Enable GPU acceleration | "true" |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-26 | Initial CLI contract |
