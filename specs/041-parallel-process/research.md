# Research: Parallel File Processing

**Feature**: 041-parallel-process
**Date**: 2025-12-02

## Overview

This document captures research findings for implementing parallel file processing in the `vpo process` command.

## Research Topics

### 1. ThreadPoolExecutor Best Practices for File Processing

**Decision**: Use `concurrent.futures.ThreadPoolExecutor` with `as_completed()` for result handling.

**Rationale**:
- ThreadPoolExecutor is ideal for I/O-bound workloads (waiting for ffmpeg/mkvmerge subprocesses)
- `as_completed()` allows processing results as they finish, enabling early termination on `on_error: fail`
- Futures can be cancelled with `future.cancel()` for pending work when stopping the batch
- Thread overhead is lower than multiprocessing for this use case

**Alternatives Considered**:
- `ProcessPoolExecutor`: Higher overhead, SQLite complications with multiprocessing, unnecessary for I/O-bound work
- `asyncio`: Would require rewriting workflow processor to be async; significant refactoring
- Manual threading: More complex, less robust than executor pattern

**Implementation Pattern**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=workers) as executor:
    futures = {executor.submit(process_file, f): f for f in files}
    for future in as_completed(futures):
        file_path = futures[future]
        try:
            result = future.result()
            # Handle result
        except Exception as e:
            # Handle error based on on_error mode
            if on_error == "fail":
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                break
```

### 2. DaemonConnectionPool Thread Safety

**Decision**: Use existing `DaemonConnectionPool` for all database access in parallel mode.

**Rationale**:
- `DaemonConnectionPool` already implements thread-safe access with internal locking
- Uses `check_same_thread=False` with explicit lock protection
- Provides `execute_read()`, `execute_write()`, and `transaction()` methods
- Already proven in daemon mode with concurrent web UI requests

**Current Usage**:
- CLI `process.py` currently uses `get_connection()` context manager (single-threaded)
- Need to switch to `DaemonConnectionPool` instance for parallel mode

**Implementation Notes**:
- Create pool at start of batch processing
- Pass pool to `V11WorkflowProcessor` instead of connection
- Processor already accepts connection; may need interface update to accept pool

### 3. Progress Display with Multiple Workers

**Decision**: Use in-place terminal updates with carriage return for aggregate progress.

**Rationale**:
- Aggregate line (e.g., "Processing: 3/10 files [2 active]") is clean and informative
- In-place update (`\r`) avoids terminal spam
- Thread-safe output requires serialization via lock or queue

**Implementation Pattern**:
```python
import sys
import threading

class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.active = 0
        self._lock = threading.Lock()

    def start_file(self):
        with self._lock:
            self.active += 1
            self._print()

    def complete_file(self, success: bool):
        with self._lock:
            self.active -= 1
            self.completed += 1
            self._print()

    def _print(self):
        msg = f"\rProcessing: {self.completed}/{self.total} files [{self.active} active]"
        sys.stderr.write(msg)
        sys.stderr.flush()
```

**Considerations**:
- Use stderr for progress to keep stdout clean for JSON output
- Final newline after progress completes
- Disable progress in JSON output mode

### 4. Error Handling with on_error Modes

**Decision**: Implement distinct behavior for `fail` vs `skip` modes.

**Rationale**:
- `on_error: fail` must stop batch ASAP - cancel pending futures, let in-progress complete
- `on_error: skip` continues all workers, collects all results
- Use atomic flag or threading.Event for coordination

**Implementation Pattern**:
```python
import threading

class BatchController:
    def __init__(self, on_error: str):
        self.on_error = on_error
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.results = []
        self.errors = []

    def should_stop(self) -> bool:
        return self._stop_event.is_set()

    def record_error(self, file_path: Path, error: str):
        with self._lock:
            self.errors.append((file_path, error))
            if self.on_error == "fail":
                self._stop_event.set()
```

### 5. Worker Count Calculation

**Decision**: Cap at half CPU cores with minimum of 1.

**Rationale**:
- Half CPU cores balances parallelism with system responsiveness
- External tools (ffmpeg) are CPU-intensive; too many workers exhausts resources
- Minimum of 1 ensures at least sequential processing

**Implementation**:
```python
import os

def get_max_workers() -> int:
    """Calculate maximum worker count (half CPU cores, minimum 1)."""
    cpu_count = os.cpu_count() or 2  # Default to 2 if detection fails
    return max(1, cpu_count // 2)

def resolve_worker_count(requested: int | None, config_default: int) -> int:
    """Resolve effective worker count with capping."""
    max_workers = get_max_workers()
    effective = requested if requested is not None else config_default

    if effective > max_workers:
        logger.warning(
            f"Requested {effective} workers exceeds cap of {max_workers} "
            f"(half of {os.cpu_count()} cores). Using {max_workers}."
        )
        return max_workers

    return max(1, effective)  # Minimum 1
```

### 6. Configuration Integration

**Decision**: Add `ProcessingConfig` dataclass with `workers` field.

**Rationale**:
- Follows existing config pattern (`JobsConfig`, `WorkerConfig`, etc.)
- Loaded from `[processing]` section in config.toml
- CLI flag overrides config value

**Implementation**:
```python
@dataclass
class ProcessingConfig:
    """Configuration for batch processing behavior."""

    workers: int = 2
    """Number of parallel workers for batch processing (1 = sequential)."""

    def __post_init__(self) -> None:
        if self.workers < 1:
            raise ValueError(f"workers must be at least 1, got {self.workers}")
```

**Config File Example**:
```toml
[processing]
workers = 4
```

## Summary of Decisions

| Topic | Decision | Key Reasoning |
|-------|----------|---------------|
| Parallelism | ThreadPoolExecutor | I/O-bound workload, simple API |
| DB Access | DaemonConnectionPool | Already thread-safe, proven |
| Progress | In-place aggregate line | Clean, informative, thread-safe |
| Error Handling | Event-based coordination | Allows early termination |
| Worker Cap | Half CPU cores | Balance parallelism with resources |
| Configuration | ProcessingConfig dataclass | Follows existing patterns |

## Open Questions

None. All technical decisions resolved.
