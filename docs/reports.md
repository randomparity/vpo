# Reports & Export

The `vpo report` command group provides read-only access to VPO database information, allowing you to generate reports about jobs, library files, scans, transcodes, and policy applications.

## Quick Reference

```bash
# Job history
vpo report jobs                          # List recent jobs
vpo report jobs --type scan --status failed  # Failed scan jobs
vpo report jobs --since 7d --format json # Last week as JSON

# Library exports
vpo report library                       # List library files
vpo report library --resolution 4K       # Only 4K files
vpo report library --language jpn        # Files with Japanese audio
vpo report library --has-subtitles       # Files with subtitles

# Scan history
vpo report scans                         # List scan operations
vpo report scans --since 30d             # Scans from last month

# Transcode history
vpo report transcodes                    # List transcodes
vpo report transcodes --codec hevc       # HEVC conversions only

# Policy applications
vpo report policy-apply                  # List policy applications
vpo report policy-apply --verbose        # Per-file details
```

## Common Options

All report commands support these options:

| Option | Description |
|--------|-------------|
| `--format`, `-f` | Output format: `text` (default), `csv`, `json` |
| `--output`, `-o` | Write to file instead of stdout |
| `--force` | Overwrite existing output file |
| `--limit`, `-n` | Maximum rows to return (default: 100) |
| `--no-limit` | Return all rows |

## Commands

### `vpo report jobs`

List job history with filtering.

```bash
vpo report jobs [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--type`, `-t` | Filter by type: `scan`, `apply`, `transcode`, `move`, `all` |
| `--status`, `-s` | Filter by status: `queued`, `running`, `completed`, `failed`, `cancelled`, `all` |
| `--since` | Show jobs since (relative: `7d`, `1w`, `2h` or ISO-8601) |
| `--until` | Show jobs until (relative or ISO-8601) |

**Output columns:** ID, TYPE, STATUS, TARGET, STARTED, COMPLETED, DURATION, ERROR

**Examples:**

```bash
# List failed jobs from last week
vpo report jobs --status failed --since 7d

# Export all transcode jobs to CSV
vpo report jobs --type transcode --no-limit --format csv --output jobs.csv

# JSON output for scripting
vpo report jobs --format json | jq '.[] | select(.status == "failed")'
```

### `vpo report library`

Export library file metadata.

```bash
vpo report library [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--resolution`, `-r` | Filter by resolution: `4K`, `1080p`, `720p`, `480p`, `SD` |
| `--language`, `-l` | Filter by audio language (ISO 639-2 code, e.g., `eng`, `jpn`) |
| `--has-subtitles` | Only files with subtitle tracks |
| `--no-subtitles` | Only files without subtitle tracks |

**Output columns:** PATH, TITLE, CONTAINER, RESOLUTION, AUDIO, SUBTITLES, SCANNED

**Examples:**

```bash
# Export 4K content inventory
vpo report library --resolution 4K --format csv --output 4k-content.csv

# Find files needing subtitles
vpo report library --no-subtitles --format json

# Japanese audio content
vpo report library --language jpn --no-limit
```

### `vpo report scans`

List scan operation history.

```bash
vpo report scans [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--since` | Show scans since (relative or ISO-8601) |
| `--until` | Show scans until (relative or ISO-8601) |

**Output columns:** SCAN_ID, STARTED, COMPLETED, DURATION, TOTAL, NEW, CHANGED, STATUS

**Examples:**

```bash
# Scans from last month
vpo report scans --since 30d

# Export scan history
vpo report scans --no-limit --format json --output scan-history.json
```

### `vpo report transcodes`

List transcode operation history.

```bash
vpo report transcodes [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--codec`, `-c` | Filter by target codec (e.g., `hevc`, `av1`) |
| `--since` | Show transcodes since (relative or ISO-8601) |
| `--until` | Show transcodes until (relative or ISO-8601) |

**Output columns:** JOB_ID, FILE, FROM, TO, STARTED, COMPLETED, DURATION, STATUS, SAVINGS

**Examples:**

```bash
# HEVC conversion report for size savings analysis
vpo report transcodes --codec hevc --format csv --output hevc-report.csv

# Recent transcode activity
vpo report transcodes --since 7d
```

### `vpo report policy-apply`

List policy application history.

```bash
vpo report policy-apply [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--policy`, `-p` | Filter by policy name |
| `--verbose`, `-v` | Show per-file details |
| `--since` | Show applications since (relative or ISO-8601) |
| `--until` | Show applications until (relative or ISO-8601) |

**Output columns (summary):** OP_ID, POLICY, FILES, METADATA, HEAVY, STATUS, STARTED

**Output columns (verbose):** FILE, CHANGES

**Examples:**

```bash
# Policy application summary
vpo report policy-apply

# Detailed report for specific policy
vpo report policy-apply --policy normalize.yaml --verbose

# Export for audit
vpo report policy-apply --since 30d --format json --output policy-audit.json
```

## Time Filters

Time filters accept two formats:

**Relative format:**
- `7d` - 7 days ago
- `2w` - 2 weeks ago
- `24h` - 24 hours ago

**ISO-8601 format:**
- `2025-01-15` - Date only (midnight UTC)
- `2025-01-15T14:30:00` - Full datetime
- `2025-01-15T14:30:00Z` - With UTC indicator
- `2025-01-15T14:30:00+05:00` - With timezone offset

## Output Formats

### Text (default)

Human-readable table format optimized for terminal display. Long values are truncated to fit column widths.

```text
ID         TYPE       STATUS       TARGET
------------------------------------------------------------------------------
690edd68   scan       completed    /home/user/Videos
```

### CSV

Standard CSV with headers, suitable for spreadsheet import or data analysis tools.

```bash
vpo report jobs --format csv --output jobs.csv
```

### JSON

Array of objects with full field values. Useful for scripting and integration.

```bash
# Pipe to jq for filtering
vpo report jobs --format json | jq '.[] | select(.type == "scan")'

# Process with Python
vpo report library --format json | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
```

## File Output

Use `--output` to write reports directly to files:

```bash
# Write to file
vpo report library --format csv --output library.csv

# Overwrite existing file
vpo report jobs --format json --output jobs.json --force
```

Files are created with UTF-8 encoding. Parent directories are created if they don't exist.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (even with empty results) |
| 1 | Error (invalid options, write failure, etc.) |

## Related docs

- [Jobs System](jobs.md) - Background job processing
- [Scanning](scanning.md) - Library scanning operations
- [Policy System](policy.md) - Policy definitions and application
