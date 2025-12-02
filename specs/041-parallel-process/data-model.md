# Data Model: Parallel File Processing

**Feature**: 041-parallel-process
**Date**: 2025-12-02

## Overview

This feature adds configuration and runtime entities for parallel file processing. No database schema changes are required.

## Configuration Entities

### ProcessingConfig

New configuration dataclass for batch processing settings.

**Location**: `src/video_policy_orchestrator/config/models.py`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workers` | `int` | `2` | Number of parallel workers for batch processing |

**Validation Rules**:
- `workers` must be >= 1
- At runtime, capped at half CPU cores

**Config File Representation** (`~/.vpo/config.toml`):
```toml
[processing]
workers = 2
```

### VPOConfig Updates

Add `processing` field to main config container.

| Field | Type | Default |
|-------|------|---------|
| `processing` | `ProcessingConfig` | `ProcessingConfig()` |

## Runtime Entities

### BatchResult

Aggregated result of parallel batch processing.

**Location**: `src/video_policy_orchestrator/cli/process.py` (inline or new module)

| Field | Type | Description |
|-------|------|-------------|
| `total_files` | `int` | Number of files in batch |
| `success_count` | `int` | Files processed successfully |
| `fail_count` | `int` | Files that failed processing |
| `skipped_count` | `int` | Files skipped (e.g., locked) |
| `results` | `list[FileProcessingResult]` | Individual file results |
| `total_duration_seconds` | `float` | Total batch duration |
| `stopped_early` | `bool` | True if batch stopped due to on_error=fail |

### ProgressTracker

Thread-safe progress tracking for console output.

**Location**: `src/video_policy_orchestrator/cli/process.py` (inline)

| Field | Type | Description |
|-------|------|-------------|
| `total` | `int` | Total files to process |
| `completed` | `int` | Files completed (success or fail) |
| `active` | `int` | Files currently being processed |
| `_lock` | `threading.Lock` | Synchronization lock |

**Methods**:
- `start_file()` - Increment active count
- `complete_file(success: bool)` - Decrement active, increment completed
- `print_progress()` - Output current state to stderr

### BatchController

Coordinates parallel execution with error handling.

**Location**: `src/video_policy_orchestrator/cli/process.py` (inline)

| Field | Type | Description |
|-------|------|-------------|
| `on_error` | `str` | Error handling mode ("skip", "fail") |
| `_stop_event` | `threading.Event` | Signal to stop accepting new work |
| `_lock` | `threading.Lock` | Synchronization lock |

**Methods**:
- `should_stop() -> bool` - Check if batch should stop
- `signal_stop()` - Set stop event (for on_error=fail)

## Entity Relationships

```
VPOConfig
└── ProcessingConfig (new)
        └── workers: int

BatchController
├── manages → ThreadPoolExecutor
├── signals → ProgressTracker
└── collects → BatchResult
        └── contains → FileProcessingResult (existing)
```

## State Transitions

### Batch Processing States

```
INITIALIZING
    │
    ▼
PROCESSING (active workers > 0)
    │
    ├─── (all files complete) ──► COMPLETED
    │
    └─── (error + on_error=fail) ──► STOPPING
                                        │
                                        ▼
                                    COMPLETED (with stopped_early=True)
```

### Individual File States (unchanged)

Existing `FileProcessingResult` tracks per-file success/failure.

## Database Impact

**No changes required.**

- Uses existing `DaemonConnectionPool` for thread-safe access
- No new tables or columns
- No schema version bump needed

## Backward Compatibility

- New `[processing]` config section is optional (defaults apply)
- New `--workers` CLI flag is optional (defaults to config or 2)
- Existing single-threaded behavior preserved with `--workers 1`
