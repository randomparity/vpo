# Quickstart: Reporting & Export CLI

**Feature**: 011-report-export-cli
**Date**: 2025-01-22

## Overview

The `vpo report` command group generates reports from your VPO database in text, CSV, or JSON format. All reports are read-only views of existing data.

## Prerequisites

- VPO installed and configured
- Database initialized (run `vpo scan` at least once)

## Basic Usage

### View Job History

```bash
# List recent jobs (default: last 100)
vpo report jobs

# Filter by status
vpo report jobs --status failed

# Filter by type and time range
vpo report jobs --type scan --since 7d
```

### Export Library Metadata

```bash
# List library files
vpo report library

# Filter by resolution
vpo report library --resolution 4K

# Filter by language
vpo report library --language jpn

# Find files with subtitles
vpo report library --has-subtitles
```

### View Scan History

```bash
# Recent scans
vpo report scans

# Scans from last month
vpo report scans --since 30d
```

### View Transcode History

```bash
# All transcodes
vpo report transcodes

# HEVC conversions only
vpo report transcodes --codec hevc
```

### View Policy Applications

```bash
# Summary view
vpo report policy-apply

# Detailed per-file changes
vpo report policy-apply --verbose
```

## Output Formats

### Text (Default)

Human-readable table format for terminal viewing:

```bash
vpo report jobs --format text
# or simply
vpo report jobs
```

### CSV

For spreadsheet import and data analysis:

```bash
vpo report library --format csv
```

### JSON

For programmatic processing:

```bash
vpo report jobs --format json
```

## File Output

Write reports to files instead of stdout:

```bash
# Write to file
vpo report library --format csv --output library.csv

# Overwrite existing file
vpo report library --format csv --output library.csv --force
```

## Result Limits

```bash
# Default: 100 rows
vpo report jobs

# Custom limit
vpo report jobs --limit 50

# No limit (all results)
vpo report jobs --no-limit
```

## Time Filters

### Relative Time

- `Nd` - N days ago (e.g., `7d`)
- `Nw` - N weeks ago (e.g., `2w`)
- `Nh` - N hours ago (e.g., `24h`)

```bash
vpo report jobs --since 7d
vpo report scans --since 1w --until 1d
```

### Absolute Time (ISO-8601)

```bash
vpo report jobs --since 2025-01-01
vpo report jobs --since 2025-01-01T00:00:00
```

## Common Workflows

### Weekly Audit Report

```bash
# Export last week's jobs to JSON
vpo report jobs --since 7d --format json --output weekly-jobs.json

# Include scan statistics
vpo report scans --since 7d --format json --output weekly-scans.json
```

### Storage Savings Analysis

```bash
# Export all HEVC transcodes to CSV
vpo report transcodes --codec hevc --no-limit --format csv --output hevc-savings.csv
```

### 4K Content Inventory

```bash
# List all 4K files
vpo report library --resolution 4K --no-limit --format csv --output 4k-inventory.csv
```

### Policy Impact Review

```bash
# See what a policy changed
vpo report policy-apply --policy normalize.yaml --verbose
```

## Getting Help

```bash
# Command group help
vpo report --help

# Subcommand help
vpo report jobs --help
vpo report library --help
```

## Troubleshooting

### "No records found"

The database may be empty or filters too restrictive. Try:
- Running `vpo scan` to populate the database
- Removing filters to see all records
- Checking the time range with `--since`

### Large Result Sets

If output is too long:
- Use `--limit N` to restrict rows
- Export to file with `--output`
- Use `--format csv` or `--format json` for processing

### Unicode Display Issues

Ensure your terminal supports UTF-8. Reports fully support Unicode in file paths and titles.
