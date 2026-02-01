# CLI Usage

**Purpose:**
This document describes the VPO command-line interface, including available commands, options, and usage examples.

---

## Overview

VPO provides a command-line tool `vpo` with subcommands for scanning, inspecting, and managing video files. The CLI outputs human-readable text by default, with JSON output available for scripting.

```bash
vpo [OPTIONS] COMMAND [ARGS]...
```

### Global Options

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--help` | Show help message and exit |

---

## Commands

### `vpo scan`

Recursively scan directories for video files, compute content hashes, and store results in the database.

```bash
vpo scan [OPTIONS] DIRECTORIES...
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `DIRECTORIES` | One or more directories to scan (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--extensions` | `-e` | Comma-separated list of extensions to scan. Default: `mkv,mp4,avi,webm,m4v,mov` |
| `--db` | | Custom database path. Default: `~/.vpo/library.db` |
| `--full` | | Force full scan, bypass incremental detection |
| `--verify-hash` | | Use content hash for change detection (slower) |
| `--profile` | | Use named configuration profile from `~/.vpo/profiles/` |
| `--dry-run` | | Scan without writing to database |
| `--verbose` | `-v` | Show detailed output including file list |
| `--json` | | Output results in JSON format |
| `--analyze-languages` | | Analyze audio tracks for multi-language detection |

> **Deprecated:** The `--prune` flag is deprecated. Use `vpo library prune` instead.

#### Examples

```bash
# Scan a single directory
vpo scan /media/videos

# Scan multiple directories with specific extensions
vpo scan --extensions mkv,mp4 /media/movies /media/tv

# Preview scan without database changes
vpo scan --dry-run --verbose /media/videos

# Get JSON output for scripting
vpo scan --json /media/videos

# Use a custom database location
vpo scan --db /tmp/test.db /media/videos
```

#### Output

**Human-readable (default):**
```text
Scanned 2 directories
Found 150 video files
  New: 45
  Updated: 10
  Skipped: 95
Elapsed time: 12.34s
```

**JSON output (`--json`):**
```json
{
  "files_found": 150,
  "elapsed_seconds": 12.34,
  "directories_scanned": ["/media/movies", "/media/tv"],
  "dry_run": false,
  "files_new": 45,
  "files_updated": 10,
  "files_skipped": 95
}
```

#### Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success (files found or partial success with errors) |
| `1` | Complete failure (errors and no files found) |
| `130` | Scan interrupted by Ctrl+C (partial results saved) |

---

### `vpo inspect`

Inspect a single media file and display detailed track information.

```bash
vpo inspect [OPTIONS] FILE
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `FILE` | Path to the media file to inspect (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `human` (default) or `json` |

#### Examples

```bash
# Inspect a file with human-readable output
vpo inspect /media/movies/movie.mkv

# Get JSON output
vpo inspect --format json /media/movies/movie.mkv
```

#### Output

**Human-readable (default):**
```text
File: /media/movies/movie.mkv
Container: Matroska

Tracks:
  Video:
    #0 [video] hevc 1920x1080 @ 23.976fps (default)
  Audio:
    #1 [audio] aac stereo eng "English" (default)
    #2 [audio] aac stereo jpn "Japanese"
  Subtitles:
    #3 [subtitle] subrip eng "English" (default)
    #4 [subtitle] subrip jpn "Japanese"
```

**JSON output (`--format json`):**
```json
{
  "file": "/media/movies/movie.mkv",
  "container": "matroska,webm",
  "tracks": [
    {
      "index": 0,
      "type": "video",
      "codec": "hevc",
      "language": "und",
      "title": null,
      "is_default": true,
      "is_forced": false,
      "width": 1920,
      "height": 1080,
      "frame_rate": "24000/1001"
    },
    {
      "index": 1,
      "type": "audio",
      "codec": "aac",
      "language": "eng",
      "title": "English",
      "is_default": true,
      "is_forced": false,
      "channels": 2,
      "channel_layout": "stereo"
    }
  ],
  "warnings": []
}
```

#### Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | File not found |
| `2` | ffprobe not installed or not in PATH |
| `3` | Failed to parse media file |

---

### `vpo library`

Manage the video library database. Subcommands for viewing library status, finding problems, and performing maintenance.

```bash
vpo library COMMAND [OPTIONS]
```

#### Subcommands

##### `vpo library info`

Show a summary of the library: file counts by status, track counts by type, database size, and schema version.

```bash
vpo library info [--json]
```

**Example output:**
```text
Library Summary
========================================

Files: 1,250
  OK:      1,200
  Missing: 45
  Error:   5
  Total size: 3.8 TB

Tracks: 4,800
  Video:      1,250
  Audio:      2,400
  Subtitle:   1,100
  Attachment: 50

Database
  Size:    48.0 MB
  Schema:  v26
  Free:    2.0 MB (reclaimable)
```

##### `vpo library missing`

List files that were previously scanned but are no longer on disk (`scan_status='missing'`).

```bash
vpo library missing [--json] [--limit N]
```

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--limit` | Maximum files to return (default: 100) |

##### `vpo library prune`

Remove database records for files with `scan_status='missing'`. This is the replacement for the deprecated `vpo scan --prune` flag.

```bash
vpo library prune [--dry-run] [--yes] [--json]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--dry-run` | | Show what would be pruned without making changes |
| `--yes` | `-y` | Skip confirmation prompt |
| `--json` | | Output as JSON |

```bash
# Preview what would be pruned
vpo library prune --dry-run

# Prune without confirmation (for scripts/cron)
vpo library prune --yes

# JSON output for automation
vpo library prune --yes --json
```

##### `vpo library verify`

Run SQLite integrity and foreign key checks on the database. Exits with code 1 if errors are found.

```bash
vpo library verify [--json]
```

```bash
# Quick health check
vpo library verify

# Machine-readable check
vpo library verify --json
```

##### `vpo library optimize`

Compact the database with VACUUM and update query planner statistics with ANALYZE. Requires exclusive database access (no other VPO instances running).

```bash
vpo library optimize [--dry-run] [--yes] [--json]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--dry-run` | | Show estimated savings without making changes |
| `--yes` | `-y` | Skip confirmation prompt |
| `--json` | | Output as JSON |

```bash
# Check how much space can be reclaimed
vpo library optimize --dry-run

# Optimize without confirmation
vpo library optimize --yes
```

##### `vpo library duplicates`

Find files that share the same content hash. Only files scanned with `--verify-hash` are included (files without a content hash are excluded).

```bash
vpo library duplicates [--limit N] [--json]
```

| Option | Description |
|--------|-------------|
| `--limit` | Maximum duplicate groups to show (default: 50) |
| `--json` | Output as JSON |

```bash
# Find all duplicate groups
vpo library duplicates

# JSON output with limited results
vpo library duplicates --limit 10 --json
```

---

## Environment Variables

VPO does not currently use environment variables for configuration. All options are specified via command-line flags.

---

## Database Location

By default, VPO stores its database at:

```text
~/.vpo/library.db
```

The directory is created automatically if it doesn't exist. Use `--db` to specify an alternative location.

---

## Dependencies

The `inspect` command requires `ffprobe` to be installed and available in PATH. Install via:

- **Ubuntu/Debian:** `sudo apt install ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Windows:** Download from https://ffmpeg.org/download.html

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Configuration](configuration.md)
- [Workflows](workflows.md)
- [Architecture Overview](../overview/architecture.md)
