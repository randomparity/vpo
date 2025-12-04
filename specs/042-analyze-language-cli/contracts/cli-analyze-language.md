# CLI Contract: vpo analyze-language

**Feature**: 042-analyze-language-cli
**Date**: 2025-12-04

## Command Group

```
vpo analyze-language [SUBCOMMAND]
```

Manage multi-language audio detection results.

## Subcommands

### analyze-language run

Run language analysis on files.

```
vpo analyze-language run [OPTIONS] PATHS...
```

**Arguments**:
- `PATHS`: One or more file or directory paths (required)

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--force` | `-f` | flag | false | Re-analyze even if cached results exist |
| `--recursive` | `-R` | flag | false | Process directories recursively |
| `--json` | | flag | false | Output results as JSON |

**Exit Codes**:
- 0: Success (all files analyzed)
- 1: Partial failure (some files failed)
- 2: Complete failure (no files analyzed)

**Output (human)**:
```
Analyzing 5 files...
  movie1.mkv: 2 tracks analyzed (1 multi-language)
  movie2.mkv: 1 track analyzed
  movie3.mkv: cached (use --force to re-analyze)
  movie4.mkv: error - no audio tracks
  movie5.mkv: 3 tracks analyzed

Summary: 4 files processed, 6 tracks analyzed, 1 cached, 1 failed
```

**Output (JSON)**:
```json
{
  "total_files": 5,
  "successful": 4,
  "failed": 1,
  "cached": 1,
  "tracks_analyzed": 6,
  "duration_ms": 45230,
  "results": [
    {
      "path": "/media/movie1.mkv",
      "success": true,
      "tracks": 2,
      "analyzed": 2,
      "cached": 0,
      "multi_language": 1
    }
  ],
  "errors": [
    {
      "path": "/media/movie4.mkv",
      "error": "No audio tracks found"
    }
  ]
}
```

---

### analyze-language status

View language analysis status.

```
vpo analyze-language status [OPTIONS] [PATH]
```

**Arguments**:
- `PATH`: Optional file or directory path (default: entire library)

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--filter` | | choice | all | Filter by classification: `all`, `multi-language`, `single-language`, `pending` |
| `--json` | | flag | false | Output as JSON |
| `--limit` | `-n` | int | 50 | Maximum files to show |

**Exit Codes**:
- 0: Success

**Output - Summary (no path)**:
```
Language Analysis Status

Library Summary:
  Total files:      1,234
  Total tracks:     2,456
  Analyzed:         1,890 (77%)
  Pending:            566 (23%)

Classification:
  Multi-language:     145 tracks (7.7%)
  Single-language:  1,745 tracks (92.3%)
```

**Output - File Detail (with path)**:
```
Language Analysis: /media/movies/movie.mkv

Track 1 (Audio - English):
  Classification: MULTI_LANGUAGE
  Primary: eng (82.3%)
  Secondary: fra (12.1%), deu (5.6%)
  Analyzed: 2025-12-04T10:30:00Z

Track 2 (Audio - Commentary):
  Classification: SINGLE_LANGUAGE
  Primary: eng (98.7%)
  Analyzed: 2025-12-04T10:30:15Z
```

**Output - File List (with filter)**:
```
Multi-language files (--filter multi-language):

  /media/movies/foreign_film.mkv     2 tracks, 1 multi-language
  /media/movies/dubbed_anime.mkv     3 tracks, 2 multi-language
  /media/movies/documentary.mkv      1 track,  1 multi-language

Showing 3 of 145 files (use --limit to show more)
```

**Output (JSON)**:
```json
{
  "summary": {
    "total_files": 1234,
    "total_tracks": 2456,
    "analyzed_tracks": 1890,
    "pending_tracks": 566,
    "multi_language_count": 145,
    "single_language_count": 1745
  },
  "files": [
    {
      "path": "/media/movies/movie.mkv",
      "tracks": [
        {
          "index": 1,
          "type": "audio",
          "language": "eng",
          "classification": "MULTI_LANGUAGE",
          "primary_language": "eng",
          "primary_percentage": 82.3,
          "secondary_languages": [
            {"language": "fra", "percentage": 12.1},
            {"language": "deu", "percentage": 5.6}
          ],
          "analyzed_at": "2025-12-04T10:30:00Z"
        }
      ]
    }
  ]
}
```

---

### analyze-language clear

Clear cached analysis results.

```
vpo analyze-language clear [OPTIONS] [PATH]
```

**Arguments**:
- `PATH`: Optional file or directory path

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--all` | | flag | false | Clear all results (required if no PATH) |
| `--recursive` | `-R` | flag | false | Include subdirectories |
| `--yes` | `-y` | flag | false | Skip confirmation prompt |
| `--dry-run` | `-n` | flag | false | Show what would be deleted |
| `--json` | | flag | false | Output as JSON |

**Exit Codes**:
- 0: Success
- 1: Nothing to clear
- 2: User cancelled

**Output (dry-run)**:
```
Would clear analysis results:
  Files affected: 42
  Tracks affected: 87

Use without --dry-run to proceed.
```

**Output (with confirmation)**:
```
This will clear language analysis results for:
  Files: 42
  Tracks: 87

Continue? [y/N]: y

Cleared 87 analysis results from 42 files.
```

**Output (JSON)**:
```json
{
  "dry_run": false,
  "files_affected": 42,
  "tracks_cleared": 87,
  "success": true
}
```

---

## Error Messages

| Scenario | Message | Exit Code |
|----------|---------|-----------|
| Plugin not installed | `Error: Whisper transcription plugin not installed.\nInstall with: pip install vpo-whisper-transcriber` | 1 |
| File not in database | `Error: File not found in database: {path}\nRun 'vpo scan {path}' first.` | 1 |
| No audio tracks | `Warning: No audio tracks found in {path}` | 0 (continues) |
| Clear without path or --all | `Error: Specify a PATH or use --all to clear all results.` | 2 |

---

## Integration with Existing Commands

The `analyze-language` commands complement existing language analysis integration:

| Existing Command | Behavior |
|------------------|----------|
| `vpo scan --analyze-languages` | Runs full scan + analysis |
| `vpo inspect --analyze-languages` | Single file analysis + display |
| `vpo analyze-language run` | Analysis only, no rescan |
| `vpo analyze-language status` | View analysis state |
| `vpo analyze-language clear` | Cache management |
