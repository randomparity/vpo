# Workflows

**Purpose:**
This document describes common end-to-end workflows for using VPO.

---

## Overview

VPO supports a workflow where you first scan your library to build a database of files and tracks, then apply policies to organize and transform your media. Library maintenance commands help you keep the database clean and healthy. This document covers the currently implemented workflows.

---

## Implemented Workflows

### Scan a Video Library

Build a database of all video files in your library:

```bash
# Initial scan of your media directories
vpo scan /media/movies /media/tv

# Output:
# Scanned 2 directories
# Found 500 video files
#   New: 500
#   Updated: 0
#   Skipped: 0
# Elapsed time: 45.23s
```

### Incremental Rescan

Re-scan to pick up new files or changes:

```bash
# Rescan - only new/changed files are processed
vpo scan /media/movies /media/tv

# Output:
# Scanned 2 directories
# Found 510 video files
#   New: 10
#   Updated: 2
#   Skipped: 498
# Elapsed time: 5.12s
```

Files are skipped when their size and modification time haven't changed.

### Preview Scan (Dry Run)

See what would be scanned without database changes:

```bash
vpo scan --dry-run --verbose /media/new-downloads

# Output:
# Scanned 1 directory
# Found 25 video files
#   (dry run - no database changes)
# Elapsed time: 2.34s
#
# Files found:
#   /media/new-downloads/movie1.mkv (4.50 GB)
#   /media/new-downloads/movie2.mkv (2.30 GB)
#   ...
```

### Inspect a Single File

View detailed track information for a specific file:

```bash
vpo inspect /media/movies/movie.mkv

# Output:
# File: /media/movies/movie.mkv
# Container: Matroska
#
# Tracks:
#   Video:
#     #0 [video] hevc 1920x1080 @ 23.976fps (default)
#   Audio:
#     #1 [audio] aac stereo eng "English Stereo" (default)
#     #2 [audio] eac3 5.1 eng "English 5.1"
#   Subtitles:
#     #3 [subtitle] subrip eng "English" (default)
```

### Script Integration with JSON Output

Use JSON output for scripting and automation:

```bash
# Get scan results as JSON
vpo scan --json /media/videos > scan_results.json

# Get file details as JSON
vpo inspect --format json /media/movies/movie.mkv | jq '.tracks[] | select(.type == "audio")'
```

### Library Maintenance

VPO provides several commands for inspecting and maintaining the library database.

#### Check Library Status

View a summary of your library to understand its composition:

```bash
vpo library info

# Output:
# Library Summary
# ========================================
#
# Files: 500
#   OK:      490
#   Missing: 8
#   Error:   2
#   Total size: 1.5 TB
#
# Tracks: 1,800
#   Video:      500
#   Audio:      900
#   Subtitle:   380
#   Attachment: 20
#
# Database
#   Size:    12.0 MB
#   Schema:  v26
```

#### Clean Up Missing Files

After moving or deleting files on disk, scan first to detect missing files, then prune them:

```bash
# Re-scan to detect missing files
vpo scan /media/movies

# See which files are missing
vpo library missing

# Preview what would be removed
vpo library prune --dry-run

# Remove the stale records
vpo library prune --yes
```

#### Find Duplicate Files

If you scanned with `--verify-hash`, you can find files with identical content:

```bash
# Scan with content hashing enabled
vpo scan --verify-hash /media/movies

# Find duplicates
vpo library duplicates
```

#### Database Maintenance

Periodically verify and compact the database:

```bash
# Check database integrity
vpo library verify

# Reclaim unused space
vpo library optimize --yes
```

---

## Planned Workflows

The following workflows will be available once the policy engine is implemented:

### Preview Policy Changes (Dry Run)

```bash
# NOT YET IMPLEMENTED
vpo policy run --dry-run --policy normalize-tracks.yaml /media/movies
```

### Apply Policies to Library

```bash
# NOT YET IMPLEMENTED
vpo policy run --policy normalize-tracks.yaml /media/movies
```

### View and Manage Jobs

```bash
# NOT YET IMPLEMENTED
vpo jobs list
vpo jobs status <job-id>
```

---

## Related docs

- [Documentation Index](../INDEX.md)
- [CLI Usage](cli-usage.md)
- [Configuration](configuration.md)
- [Project Overview](../overview/project-overview.md)
