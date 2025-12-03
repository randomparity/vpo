# Logging and Metrics

**Purpose:**
This document describes VPO's logging configuration, structured log formats, and how to filter logs during parallel processing.

---

## Overview

VPO uses Python's standard logging infrastructure with support for:

- **Text format** (default) - Human-readable logs with timestamps
- **JSON format** - Structured logs for machine processing
- **File rotation** - Automatic log file rotation to manage disk space
- **Worker context** - Automatic tagging of logs during parallel file processing

---

## Configuration

### CLI Options

```bash
# Set log level
vpo --log-level debug process ...

# Log to file
vpo --log-file ~/.vpo/vpo.log process ...

# Use JSON format
vpo --log-json --log-file ~/.vpo/vpo.log process ...
```

### Configuration File

Add to `~/.vpo/config.toml`:

```toml
[logging]
level = "info"           # debug, info, warning, error
file = "~/.vpo/vpo.log"  # Optional log file path
format = "text"          # text or json
include_stderr = false   # Also log to stderr when file is set
max_bytes = 10485760     # 10MB rotation threshold
backup_count = 5         # Number of rotated files to keep
```

---

## Log Formats

### Text Format

```
2025-12-02T10:15:32-0500 - video_policy_orchestrator.workflow - INFO - Processing with 3 phase(s)
```

With worker context (parallel processing):
```
2025-12-02T10:15:32-0500 - [W01:F001] video_policy_orchestrator.workflow - INFO - Processing with 3 phase(s)
```

### JSON Format

```json
{
  "timestamp": "2025-12-02T15:15:32+00:00",
  "level": "INFO",
  "message": "Processing with 3 phase(s)",
  "logger": "video_policy_orchestrator.workflow",
  "context": {
    "worker_id": "01",
    "file_id": "F001",
    "file_path": "/path/to/movie.mkv"
  }
}
```

---

## Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed diagnostic information (tool commands, SQL queries) |
| `INFO` | Normal operation events (phase started, file processed) |
| `WARNING` | Non-fatal issues (missing metadata, retry attempts) |
| `ERROR` | Operation failures (tool errors, database errors) |

---

## Filtering Logs During Parallel Processing

When processing multiple files with `--workers`, each log line includes a worker/file tag like `[W01:F042]`:
- `W01` = Worker thread 01
- `F042` = File 42 in the current batch

The first log line for each file is a mapping line showing the full path:
```
2025-12-02T10:15:32-0500 - [W01:F042] video_policy_orchestrator.cli.process - INFO - === FILE F042: /full/path/to/movie.mkv
```

### Finding the Full Path for a File ID

```bash
grep 'FILE F042:' vpo.log
# Output: ... [W01:F042] ... === FILE F042: /full/path/to/movie.mkv
```

### Filtering by Worker

```bash
# All logs from worker 1
grep '\[W01:' vpo.log

# Errors from worker 2
grep '\[W02:' vpo.log | grep ERROR
```

### Filtering by File

```bash
# All logs for file F042
grep ':F042\]' vpo.log

# Just errors for that file
grep ':F042\]' vpo.log | grep ERROR
```

### JSON Log Filtering (with jq)

```bash
# Filter by worker
jq 'select(.context.worker_id == "01")' vpo.log

# Filter by file ID
jq 'select(.context.file_id == "F042")' vpo.log

# Find errors with file context
jq 'select(.level == "ERROR" and .context.file_id)' vpo.log

# Get all unique file paths that had errors
jq 'select(.level == "ERROR") | .context.file_path' vpo.log | sort -u
```

---

## File ID Numbering

File IDs use dynamic width based on batch size:

| Batch Size | File ID Format | Examples |
|------------|----------------|----------|
| 1-9 files | F1, F2, ... F9 | F1 |
| 10-99 files | F01, F02, ... F99 | F42 |
| 100-999 files | F001, F002, ... F999 | F042 |
| 1000+ files | F0001, F0002, ... | F0042 |

This keeps log lines compact while ensuring consistent grep patterns within a batch.

---

## Implementation Details

Worker context is implemented using Python's `contextvars` module, which provides thread-safe context propagation. The `WorkerContextFilter` logging filter automatically injects context into all log records.

Key modules:
- `video_policy_orchestrator.logging.context` - Context management
- `video_policy_orchestrator.logging.config` - Logging configuration
- `video_policy_orchestrator.logging.handlers` - JSON formatter

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Configuration](../usage/configuration.md)
- [CLI Usage](../usage/cli-usage.md)
- [Error Handling](error-handling.md)
