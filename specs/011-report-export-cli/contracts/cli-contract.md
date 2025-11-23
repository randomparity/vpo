# CLI Contract: vpo report

**Feature**: 011-report-export-cli
**Date**: 2025-01-22

## Command Group

```
vpo report [OPTIONS] COMMAND [ARGS]...
```

### Group Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--help` | flag | - | Show help message |

---

## Subcommand: jobs

```
vpo report jobs [OPTIONS]
```

List job history with filtering.

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--type`, `-t` | choice | all | Filter by job type: `scan`, `apply`, `transcode`, `move`, `all` |
| `--status`, `-s` | choice | all | Filter by status: `queued`, `running`, `completed`, `failed`, `cancelled`, `all` |
| `--since` | string | - | Show jobs since (relative: `7d`, `1w`, `2h` or ISO-8601) |
| `--until` | string | - | Show jobs until (relative or ISO-8601) |
| `--format`, `-f` | choice | text | Output format: `text`, `csv`, `json` |
| `--output`, `-o` | path | - | Write to file instead of stdout |
| `--force` | flag | false | Overwrite existing output file |
| `--limit`, `-n` | int | 100 | Maximum rows to return |
| `--no-limit` | flag | false | Return all rows |
| `--help` | flag | - | Show help message |

### Output Columns

| Column | JSON Key | CSV Header | Description |
|--------|----------|------------|-------------|
| ID | `job_id` | `job_id` | 8-char UUID prefix |
| TYPE | `type` | `type` | Job type |
| STATUS | `status` | `status` | Current status |
| TARGET | `target` | `target` | File path (truncated in text) |
| STARTED | `started_at` | `started_at` | Start time (local) |
| COMPLETED | `completed_at` | `completed_at` | End time or empty |
| DURATION | `duration` | `duration` | Elapsed time |
| ERROR | `error` | `error` | Error message (failed only) |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (even if no results) |
| 1 | Error (invalid options, write failure, etc.) |

### Examples

```bash
# List all jobs (default: last 100)
vpo report jobs

# List failed jobs from last week as JSON
vpo report jobs --status failed --since 7d --format json

# Export all transcode jobs to CSV
vpo report jobs --type transcode --no-limit --format csv --output transcodes.csv
```

---

## Subcommand: library

```
vpo report library [OPTIONS]
```

Export library file metadata.

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--resolution`, `-r` | choice | - | Filter by resolution: `4K`, `1080p`, `720p`, `480p`, `SD` |
| `--language`, `-l` | string | - | Filter by audio language (ISO 639-2, e.g., `eng`) |
| `--has-subtitles` | flag | - | Only files with subtitle tracks |
| `--no-subtitles` | flag | - | Only files without subtitle tracks |
| `--format`, `-f` | choice | text | Output format: `text`, `csv`, `json` |
| `--output`, `-o` | path | - | Write to file instead of stdout |
| `--force` | flag | false | Overwrite existing output file |
| `--limit`, `-n` | int | 100 | Maximum rows to return |
| `--no-limit` | flag | false | Return all rows |
| `--help` | flag | - | Show help message |

### Output Columns

| Column | JSON Key | CSV Header | Description |
|--------|----------|------------|-------------|
| PATH | `path` | `path` | Full file path |
| TITLE | `title` | `title` | Display title |
| CONTAINER | `container` | `container` | Container format |
| RESOLUTION | `resolution` | `resolution` | Video resolution category |
| AUDIO | `audio_languages` | `audio_languages` | Audio languages |
| SUBTITLES | `has_subtitles` | `has_subtitles` | Yes/No (text), true/false (JSON) |
| SCANNED | `scanned_at` | `scanned_at` | Last scan time |

### Examples

```bash
# List all library files
vpo report library

# Export 4K files to CSV
vpo report library --resolution 4K --format csv --output 4k-files.csv

# Find files with Japanese audio
vpo report library --language jpn --no-limit
```

---

## Subcommand: scans

```
vpo report scans [OPTIONS]
```

List scan operation history.

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--since` | string | - | Show scans since (relative or ISO-8601) |
| `--until` | string | - | Show scans until (relative or ISO-8601) |
| `--format`, `-f` | choice | text | Output format: `text`, `csv`, `json` |
| `--output`, `-o` | path | - | Write to file instead of stdout |
| `--force` | flag | false | Overwrite existing output file |
| `--limit`, `-n` | int | 100 | Maximum rows to return |
| `--no-limit` | flag | false | Return all rows |
| `--help` | flag | - | Show help message |

### Output Columns

| Column | JSON Key | CSV Header | Description |
|--------|----------|------------|-------------|
| SCAN_ID | `scan_id` | `scan_id` | 8-char UUID prefix |
| STARTED | `started_at` | `started_at` | Start time |
| COMPLETED | `completed_at` | `completed_at` | End time |
| DURATION | `duration` | `duration` | Elapsed time |
| TOTAL | `files_scanned` | `files_scanned` | Total files |
| NEW | `files_new` | `files_new` | New files |
| CHANGED | `files_changed` | `files_changed` | Changed files |
| STATUS | `status` | `status` | Scan status |

### Examples

```bash
# List recent scans
vpo report scans

# Scans from last month
vpo report scans --since 30d --format json
```

---

## Subcommand: transcodes

```
vpo report transcodes [OPTIONS]
```

List transcode operation history.

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--codec`, `-c` | string | - | Filter by target codec (e.g., `hevc`, `av1`) |
| `--since` | string | - | Show transcodes since (relative or ISO-8601) |
| `--until` | string | - | Show transcodes until (relative or ISO-8601) |
| `--format`, `-f` | choice | text | Output format: `text`, `csv`, `json` |
| `--output`, `-o` | path | - | Write to file instead of stdout |
| `--force` | flag | false | Overwrite existing output file |
| `--limit`, `-n` | int | 100 | Maximum rows to return |
| `--no-limit` | flag | false | Return all rows |
| `--help` | flag | - | Show help message |

### Output Columns

| Column | JSON Key | CSV Header | Description |
|--------|----------|------------|-------------|
| JOB_ID | `job_id` | `job_id` | 8-char UUID prefix |
| FILE | `file_path` | `file_path` | Source file |
| FROM | `source_codec` | `source_codec` | Original codec |
| TO | `target_codec` | `target_codec` | Target codec |
| STARTED | `started_at` | `started_at` | Start time |
| COMPLETED | `completed_at` | `completed_at` | End time |
| DURATION | `duration` | `duration` | Elapsed time |
| STATUS | `status` | `status` | Job status |
| SAVINGS | `size_change` | `size_change` | Size change % |

### Examples

```bash
# List all transcodes
vpo report transcodes

# HEVC conversions for size analysis
vpo report transcodes --codec hevc --format csv --output hevc-savings.csv
```

---

## Subcommand: policy-apply

```
vpo report policy-apply [OPTIONS]
```

List policy application history.

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--policy`, `-p` | string | - | Filter by policy name |
| `--since` | string | - | Show applications since (relative or ISO-8601) |
| `--until` | string | - | Show applications until (relative or ISO-8601) |
| `--verbose`, `-v` | flag | false | Show per-file details |
| `--format`, `-f` | choice | text | Output format: `text`, `csv`, `json` |
| `--output`, `-o` | path | - | Write to file instead of stdout |
| `--force` | flag | false | Overwrite existing output file |
| `--limit`, `-n` | int | 100 | Maximum rows to return |
| `--no-limit` | flag | false | Return all rows |
| `--help` | flag | - | Show help message |

### Output Columns (Summary Mode)

| Column | JSON Key | CSV Header | Description |
|--------|----------|------------|-------------|
| OP_ID | `operation_id` | `operation_id` | 8-char UUID prefix |
| POLICY | `policy_name` | `policy_name` | Policy name |
| FILES | `files_affected` | `files_affected` | Files changed |
| METADATA | `metadata_changes` | `metadata_changes` | Metadata ops |
| HEAVY | `heavy_changes` | `heavy_changes` | Heavy ops |
| STATUS | `status` | `status` | Operation status |
| STARTED | `started_at` | `started_at` | Start time |

### Output Columns (Verbose Mode)

| Column | JSON Key | CSV Header | Description |
|--------|----------|------------|-------------|
| FILE | `file_path` | `file_path` | File path |
| CHANGES | `changes` | `changes` | Change summary |

### Examples

```bash
# List policy applications
vpo report policy-apply

# Verbose output for specific policy
vpo report policy-apply --policy normalize.yaml --verbose

# Export to JSON for analysis
vpo report policy-apply --since 7d --format json --output policy-report.json
```

---

## Common Behaviors

### Empty Results

All subcommands display a message and exit 0:
```
No records found.
```

Or with filters:
```
No records match the specified filters.
```

### Invalid Format

Exit 1 with message:
```
Error: Invalid value for '--format': 'xml' is not one of 'text', 'csv', 'json'.
```

### File Exists

Exit 1 with message:
```
Error: File exists: /path/to/file.csv. Use --force to overwrite.
```

### Invalid Time Format

Exit 1 with message:
```
Error: Invalid time format '2025-13-45'. Use ISO-8601 (YYYY-MM-DD) or relative (7d, 1w, 2h).
```
