# Logging and Metrics

**Purpose:**
This document describes VPO's logging strategy, structured log format, and metrics for monitoring.

> **Status:** This feature is planned but not yet implemented. This document captures the intended design.

---

## Overview

VPO will use structured logging to provide observability for batch operations, debugging, and monitoring. Logs will include contextual fields to enable filtering and correlation.

---

## Planned Log Format

### Structured Fields

Each log entry should include:

| Field | Description | Example |
|-------|-------------|---------|
| `timestamp` | ISO 8601 UTC timestamp | `2024-01-15T10:30:00Z` |
| `level` | Log level | `INFO`, `WARNING`, `ERROR` |
| `message` | Human-readable message | `File scanned successfully` |
| `run_id` | Unique ID for the current operation | `scan-abc123` |
| `file_path` | Path to media file (when applicable) | `/media/movies/movie.mkv` |
| `duration_ms` | Operation duration in milliseconds | `1234` |

### Example Log Output

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "File scanned successfully",
  "run_id": "scan-abc123",
  "file_path": "/media/movies/movie.mkv",
  "duration_ms": 45
}
```

---

## Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed diagnostic information for developers |
| `INFO` | Normal operation events (file processed, scan started) |
| `WARNING` | Non-fatal issues (duplicate tracks, missing metadata) |
| `ERROR` | Operation failures (file couldn't be parsed, database error) |

---

## Planned Metrics

### Scan Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `vpo_scan_files_total` | Counter | Total files scanned |
| `vpo_scan_files_new` | Counter | New files added to database |
| `vpo_scan_files_updated` | Counter | Files updated in database |
| `vpo_scan_errors_total` | Counter | Total scan errors |
| `vpo_scan_duration_seconds` | Histogram | Scan duration per file |

### Database Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `vpo_db_files_total` | Gauge | Total files in database |
| `vpo_db_tracks_total` | Gauge | Total tracks in database |

---

## Current Implementation

VPO currently uses simple CLI output instead of structured logging:

```python
# Progress callback for verbose mode
def progress_callback(processed: int, total: int) -> None:
    if verbose and not json_output:
        click.echo(f"  Progress: {processed}/{total} files processed...")
```

Future versions will add proper logging infrastructure.

---

## Configuration (Planned)

Logging configuration options:

```yaml
# ~/.vpo/config.yaml (planned)
logging:
  level: INFO
  format: json  # or "text"
  file: ~/.vpo/vpo.log  # optional file output
```

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Design Docs Index](../design/DESIGN_INDEX.md)
- [Error Handling](error-handling.md)
- [Configuration](../usage/configuration.md)
