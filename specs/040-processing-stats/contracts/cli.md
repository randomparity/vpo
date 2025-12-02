# CLI Contract: vpo stats

## Command Structure

```
vpo stats <subcommand> [options]
```

## Subcommands

### vpo stats summary

Display aggregate processing statistics.

```
vpo stats summary [OPTIONS]
```

**Options:**
- `--since DATE`: Start date (ISO-8601 or YYYY-MM-DD)
- `--until DATE`: End date (ISO-8601 or YYYY-MM-DD)
- `--format FORMAT`: Output format (table, json, csv)

**Output (table format):**
```
Processing Statistics Summary
════════════════════════════════════════════════════════════════

Files Processed:     1,234
  Successful:        1,200 (97.2%)
  Failed:               34 (2.8%)

Space Savings:
  Total Before:      2.45 TB
  Total After:       1.82 TB
  Total Saved:     643.2 GB (26.2%)

Track Removals:
  Audio Tracks:        456
  Subtitles:         1,234
  Attachments:         789

Transcoding:
  Videos Transcoded:   234
  Videos Skipped:      456
  Audio Transcoded:    890

Performance:
  Avg Processing Time: 45.2s
  Total Time:         15h 28m

Time Range: 2024-01-01 to 2025-12-01
```

### vpo stats policy

Display per-policy statistics.

```
vpo stats policy [POLICY_NAME] [OPTIONS]
```

**Arguments:**
- `POLICY_NAME`: (Optional) Show stats for specific policy

**Options:**
- `--since DATE`: Start date
- `--until DATE`: End date
- `--sort FIELD`: Sort by (files, savings, time) [default: files]
- `--format FORMAT`: Output format (table, json, csv)

**Output (table format, all policies):**
```
Policy Statistics
════════════════════════════════════════════════════════════════

Policy              Files    Success   Savings     Avg Time   Last Used
────────────────────────────────────────────────────────────────
default               456      98.2%    245.3 GB      32.1s   2025-12-01
anime-library         234      96.5%    156.7 GB      89.4s   2025-11-30
transcode-hevc        123      94.3%     89.2 GB     234.5s   2025-11-28
```

**Output (table format, specific policy):**
```
Policy: anime-library
════════════════════════════════════════════════════════════════

Files Processed:        234
Success Rate:         96.5%
Total Saved:       156.7 GB
Avg Savings:          28.4%

Track Removals:
  Audio:                123
  Subtitles:            456
  Attachments:          234

Transcoding:
  Videos:               45
  Audio:               123

Avg Processing Time: 89.4s
Last Used: 2025-11-30T14:32:00Z
```

### vpo stats file

Display processing history for a file.

```
vpo stats file <FILE_PATH> [OPTIONS]
```

**Arguments:**
- `FILE_PATH`: Path to the file

**Options:**
- `--limit N`: Maximum entries to show [default: 10]
- `--format FORMAT`: Output format (table, json, csv)

**Output (table format):**
```
Processing History: /media/movies/example.mkv
════════════════════════════════════════════════════════════════

Date                Policy          Before     After     Saved    Status
────────────────────────────────────────────────────────────────
2025-12-01 14:32   anime-library   12.4 GB    9.2 GB   3.2 GB   Success
2025-11-15 09:15   default          8.1 GB    8.1 GB      0 B   Success
2025-10-01 18:45   transcode       15.6 GB   12.4 GB   3.2 GB   Success
```

### vpo stats detail

Display detailed statistics for a specific processing run.

```
vpo stats detail <STATS_ID> [OPTIONS]
```

**Arguments:**
- `STATS_ID`: Processing stats UUID

**Options:**
- `--format FORMAT`: Output format (table, json)
- `--show-actions`: Include per-action details
- `--show-performance`: Include performance metrics

**Output (table format):**
```
Processing Details: a1b2c3d4-e5f6-7890-abcd-ef1234567890
════════════════════════════════════════════════════════════════

File: /media/movies/example.mkv
Policy: anime-library
Processed: 2025-12-01T14:32:00Z
Status: Success

Size Metrics:
  Before:    12.4 GB
  After:      9.2 GB
  Saved:      3.2 GB (25.8%)

Track Changes:
  Audio:     4 → 2  (-2 removed)
  Subtitles: 8 → 3  (-5 removed)
  Attachments: 12 → 0 (-12 removed)

Transcode:
  Video: h264 → hevc
  Audio: 2 transcoded, 0 preserved

Integrity:
  Hash Before: sha256:abc123...
  Hash After:  sha256:def456...

Duration: 89.4s
Phases: 3/3 completed
Changes: 19 total
```

### vpo stats purge

Remove old processing statistics.

```
vpo stats purge [OPTIONS]
```

**Options:**
- `--before DATE`: Delete stats older than this date (required unless --all)
- `--policy NAME`: Delete stats for this policy only
- `--all`: Delete all statistics (requires confirmation)
- `--dry-run`: Show what would be deleted without deleting
- `--yes`: Skip confirmation prompt

**Output:**
```
Purging processing statistics...

Would delete:
  - 456 processing records
  - 2,345 action results
  - 1,234 performance metrics

Proceed? [y/N] y

Deleted 456 processing records.
```

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Invalid arguments
- `64`: File not found
- `65`: No statistics found

## Output Formats

### table (default)
Human-readable tabular output with ANSI formatting.

### json
Machine-readable JSON output, suitable for piping to `jq`.

### csv
Comma-separated values, suitable for spreadsheet import.

## Examples

```bash
# Show overall summary
vpo stats summary

# Show summary for last 30 days
vpo stats summary --since 2025-11-01

# Compare all policies
vpo stats policy

# Show specific policy details
vpo stats policy anime-library

# Show file history
vpo stats file /media/movies/example.mkv

# Show detailed run info
vpo stats detail a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Export policy stats to CSV
vpo stats policy --format csv > policy-stats.csv

# Purge old stats (dry run)
vpo stats purge --before 2024-01-01 --dry-run

# Purge stats for deleted policy
vpo stats purge --policy old-policy --yes
```
