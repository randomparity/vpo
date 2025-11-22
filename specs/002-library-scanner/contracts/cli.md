# CLI Contract: vpo scan

**Feature**: 002-library-scanner
**Date**: 2025-11-21

## Command Signature

```
vpo scan [OPTIONS] DIRECTORIES...
```

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| DIRECTORIES | Path(s) | Yes | One or more directory paths to scan |

## Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--extensions` | `-e` | String | mkv,mp4,avi,webm,m4v,mov | Comma-separated list of file extensions to include |
| `--db` | `-d` | Path | ~/.vpo/library.db | Database file path |
| `--dry-run` | `-n` | Flag | False | Show what would be scanned without writing to DB |
| `--verbose` | `-v` | Flag | False | Show detailed progress and errors |
| `--json` | `-j` | Flag | False | Output summary as JSON |
| `--help` | `-h` | Flag | - | Show help and exit |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (scan completed, may have file-level errors) |
| 1 | Fatal error (invalid arguments, DB inaccessible) |
| 2 | Partial failure (all directories inaccessible) |

## Output Formats

### Human-Readable (default)

```
Scanning 3 directories...
  /media/movies: 1,234 files found
  /media/tv: 5,678 files found
  /media/docs: 0 video files found

Scan complete in 2m 34s
  Files scanned: 6,912
  New files: 1,523
  Updated files: 5,389
  Errors: 12 (use --verbose for details)
  Tracks indexed: 34,560
```

### Verbose Mode (--verbose)

```
Scanning 3 directories...
  /media/movies: 1,234 files found
    [ERROR] /media/movies/broken.mkv: Permission denied
    [ERROR] /media/movies/corrupt.mp4: Unable to read file
  /media/tv: 5,678 files found
  /media/docs: 0 video files found

Scan complete in 2m 34s
  Files scanned: 6,912
  New files: 1,523
  Updated files: 5,389
  Errors: 12
  Tracks indexed: 34,560

Errors:
  1. /media/movies/broken.mkv: Permission denied
  2. /media/movies/corrupt.mp4: Unable to read file
  ...
```

### JSON Mode (--json)

```json
{
  "status": "success",
  "duration_seconds": 154.2,
  "directories": [
    {
      "path": "/media/movies",
      "files_found": 1234,
      "errors": 2
    },
    {
      "path": "/media/tv",
      "files_found": 5678,
      "errors": 0
    },
    {
      "path": "/media/docs",
      "files_found": 0,
      "errors": 0
    }
  ],
  "summary": {
    "total_files": 6912,
    "new_files": 1523,
    "updated_files": 5389,
    "skipped_files": 0,
    "error_count": 12,
    "tracks_indexed": 34560
  },
  "errors": [
    {
      "path": "/media/movies/broken.mkv",
      "error": "Permission denied"
    },
    {
      "path": "/media/movies/corrupt.mp4",
      "error": "Unable to read file"
    }
  ]
}
```

### Dry-Run Mode (--dry-run)

```
[DRY RUN] Would scan 3 directories...
  /media/movies: 1,234 video files
  /media/tv: 5,678 video files
  /media/docs: 0 video files

Total: 6,912 files would be scanned
No changes made to database.
```

## Error Messages

| Scenario | Message | Exit Code |
|----------|---------|-----------|
| No directories provided | `Error: Missing argument 'DIRECTORIES...'` | 1 |
| Directory not found | `Error: Directory not found: /invalid/path` | 2 |
| Permission denied (directory) | `Error: Cannot access directory: /protected` | 2 |
| Invalid extension format | `Error: Invalid extension format: '.mkv'` | 1 |
| Database locked | `Error: Database is locked: ~/.vpo/library.db` | 1 |
| All directories invalid | `Error: No valid directories to scan` | 2 |

## Usage Examples

```bash
# Basic scan of one directory
vpo scan /media/videos

# Scan multiple directories
vpo scan /media/movies /media/tv /media/documentaries

# Scan only MKV files
vpo scan --extensions mkv /media/videos

# Scan multiple formats
vpo scan -e mkv,mp4,avi /media/videos

# Preview what would be scanned
vpo scan --dry-run /media/videos

# Detailed output with errors
vpo scan --verbose /media/videos

# JSON output for scripting
vpo scan --json /media/videos | jq '.summary.total_files'

# Custom database location
vpo scan --db /tmp/test.db /media/videos

# Combine options
vpo scan -v -e mkv,mp4 --db ~/my-library.db /media/movies /media/tv
```

## Behavioral Notes

1. **Duplicate Handling**: If a file path appears in multiple specified directories (via symlinks), it is scanned once.

2. **Relative Paths**: Relative directory paths are resolved to absolute paths before scanning.

3. **Extension Case**: Extensions are case-insensitive (`.MKV` matches `--extensions mkv`).

4. **Progress**: Long scans show progress every 100 files in non-verbose mode.

5. **Interruption**: Ctrl+C gracefully stops the scan and commits completed work to the database.

6. **Re-scanning**: Files with unchanged `modified_at` timestamps are skipped unless `--force` is added (future option).
