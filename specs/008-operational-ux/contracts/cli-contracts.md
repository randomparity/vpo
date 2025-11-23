# CLI Contracts: Operational UX

**Feature**: 008-operational-ux
**Date**: 2025-11-22

This document defines the CLI interface contracts for new and modified commands.

---

## Modified Commands

### `vpo scan`

**Current Signature**:
```
vpo scan [OPTIONS] DIRECTORY
```

**New Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--full` | flag | false | Force full scan, bypass incremental detection |
| `--prune` | flag | false | Delete database records for missing files |
| `--verify-hash` | flag | false | Use content hash for change detection (slower) |
| `--profile` | string | None | Use named configuration profile |

**Behavior Changes**:
- Default behavior is now incremental when prior scan data exists
- Summary output includes incremental statistics

**Output Format** (incremental mode):
```
Scanning /media/movies...
  Discovered: 1,234 files
  Skipped (unchanged): 1,220
  Scanned (changed): 10
  Added (new): 4
  Removed (missing): 0

Scan complete in 12.3s (job: abc12345)
```

**Exit Codes**:
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Partial success (some files had errors) |
| 2 | Fatal error (database, permission, etc.) |

---

## New Commands

### `vpo jobs list`

**Signature**:
```
vpo jobs list [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--status` | choice | all | Filter by status: queued, running, completed, failed, cancelled |
| `--type` | choice | all | Filter by type: scan, apply, transcode, move |
| `--since` | string | None | Show jobs since date (ISO-8601 or relative: "1d", "1w") |
| `--limit` | int | 20 | Maximum number of jobs to show |
| `--json` | flag | false | Output as JSON array |

**Output Format** (table):
```
ID        TYPE       STATUS     STARTED              DURATION  PATH
abc12345  scan       completed  2025-11-22 10:30:00  12.3s     /media/movies
def67890  apply      failed     2025-11-22 10:45:00  2.1s      /media/movies/file.mkv
```

**Output Format** (JSON):
```json
[
  {
    "id": "abc12345-...",
    "type": "scan",
    "status": "completed",
    "started_at": "2025-11-22T10:30:00Z",
    "completed_at": "2025-11-22T10:30:12Z",
    "file_path": "/media/movies"
  }
]
```

---

### `vpo jobs show`

**Signature**:
```
vpo jobs show JOB_ID
```

**Arguments**:

| Argument | Type | Description |
|----------|------|-------------|
| `JOB_ID` | string | Full UUID or unique prefix (minimum 4 characters) |

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--json` | flag | false | Output as JSON object |

**Output Format** (text):
```
Job: abc12345-6789-...
Type: scan
Status: completed
Path: /media/movies

Timing:
  Started: 2025-11-22 10:30:00
  Completed: 2025-11-22 10:30:12
  Duration: 12.3s

Summary:
  Discovered: 1,234
  Scanned: 10
  Skipped: 1,220
  Added: 4
  Removed: 0
```

**Error Handling**:
- If prefix matches multiple jobs: "Multiple jobs match 'abc1'. Use more characters."
- If no match: "No job found with ID 'xyz'"

---

### `vpo profiles list`

**Signature**:
```
vpo profiles list [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--json` | flag | false | Output as JSON array |

**Output Format** (table):
```
NAME      DESCRIPTION                    POLICY
movies    Settings for movie library     ~/policies/movies.yaml
tv        TV show processing rules       ~/policies/tv.yaml
kids      Kid-safe content settings      -
```

---

### `vpo profiles show`

**Signature**:
```
vpo profiles show PROFILE_NAME
```

**Arguments**:

| Argument | Type | Description |
|----------|------|-------------|
| `PROFILE_NAME` | string | Profile name (without .yaml extension) |

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--json` | flag | false | Output as JSON object |

**Output Format** (text):
```
Profile: movies
Description: Settings for movie library
Location: ~/.vpo/profiles/movies.yaml

Default Policy: ~/policies/movies.yaml

Behavior:
  warn_on_missing_features: false
  show_upgrade_suggestions: true

Logging:
  level: info
  file: ~/.vpo/logs/movies.log
```

---

## Global Options (All Commands)

### New Global Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--profile` | string | None | Use named configuration profile |
| `--log-level` | choice | info | Override log level: debug, info, warning, error |
| `--log-file` | path | None | Override log file path |
| `--log-json` | flag | false | Use JSON log format |

**Precedence**: CLI flags > profile settings > config file > defaults

---

## Error Contract

All commands return structured errors:

**Text Format**:
```
Error: Profile 'nonexistent' not found.

Available profiles:
  - movies
  - tv
  - kids
```

**JSON Format** (with `--json`):
```json
{
  "error": true,
  "code": "PROFILE_NOT_FOUND",
  "message": "Profile 'nonexistent' not found.",
  "details": {
    "requested": "nonexistent",
    "available": ["movies", "tv", "kids"]
  }
}
```

---

## Shell Completion

All new commands and options support shell completion:

```bash
# Setup (add to ~/.bashrc or ~/.zshrc)
eval "$(_VPO_COMPLETE=bash_source vpo)"  # bash
eval "$(_VPO_COMPLETE=zsh_source vpo)"   # zsh

# Completions work for:
vpo jobs list --status <TAB>     # queued, running, completed, failed, cancelled
vpo jobs show <TAB>              # recent job IDs
vpo --profile <TAB>              # available profile names
```
