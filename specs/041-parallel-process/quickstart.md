# Quickstart: Parallel File Processing

**Feature**: 041-parallel-process
**Date**: 2025-12-02

## Overview

This guide covers implementation of parallel file processing for the `vpo process` command.

## Prerequisites

- Python 3.10+
- Existing VPO development environment (`uv pip install -e ".[dev]"`)
- Understanding of `cli/process.py` and `config/models.py`

## Implementation Order

### Phase 1: Configuration (Foundation)

1. **Add ProcessingConfig dataclass** (`config/models.py`)
   ```python
   @dataclass
   class ProcessingConfig:
       workers: int = 2

       def __post_init__(self) -> None:
           if self.workers < 1:
               raise ValueError(f"workers must be at least 1, got {self.workers}")
   ```

2. **Add to VPOConfig** (`config/models.py`)
   ```python
   @dataclass
   class VPOConfig:
       # ... existing fields ...
       processing: ProcessingConfig = field(default_factory=ProcessingConfig)
   ```

3. **Update config loader** (`config/loader.py` and `config/builder.py`)
   - Parse `[processing]` section from TOML
   - Apply to ConfigBuilder

4. **Unit tests** (`tests/unit/config/test_models.py`)
   - Test ProcessingConfig validation
   - Test config loading with processing section

### Phase 2: Worker Count Resolution

1. **Add worker count utilities** (`cli/process.py`)
   ```python
   def get_max_workers() -> int:
       cpu_count = os.cpu_count() or 2
       return max(1, cpu_count // 2)

   def resolve_worker_count(requested: int | None, config_default: int) -> int:
       max_workers = get_max_workers()
       effective = requested if requested is not None else config_default
       if effective > max_workers:
           logger.warning(f"Capping workers to {max_workers}")
           return max_workers
       return max(1, effective)
   ```

2. **Add --workers CLI option**
   ```python
   @click.option(
       "--workers",
       "-w",
       type=int,
       default=None,
       help="Number of parallel workers (default: 2, max: half CPU cores)",
   )
   ```

### Phase 3: Progress Tracking

1. **Implement ProgressTracker class**
   ```python
   class ProgressTracker:
       def __init__(self, total: int, enabled: bool = True):
           self.total = total
           self.completed = 0
           self.active = 0
           self.enabled = enabled
           self._lock = threading.Lock()

       def start_file(self) -> None:
           with self._lock:
               self.active += 1
               self._update()

       def complete_file(self) -> None:
           with self._lock:
               self.active -= 1
               self.completed += 1
               self._update()

       def _update(self) -> None:
           if self.enabled:
               msg = f"\rProcessing: {self.completed}/{self.total} [{self.active} active]"
               sys.stderr.write(msg)
               sys.stderr.flush()

       def finish(self) -> None:
           if self.enabled:
               sys.stderr.write("\n")
   ```

### Phase 4: Parallel Execution

1. **Refactor file processing loop**
   ```python
   from concurrent.futures import ThreadPoolExecutor, as_completed

   def process_files_parallel(
       files: list[Path],
       processor: V11WorkflowProcessor,
       workers: int,
       on_error: str,
       progress: ProgressTracker,
   ) -> list[FileProcessingResult]:
       results = []
       stop_event = threading.Event()

       with ThreadPoolExecutor(max_workers=workers) as executor:
           futures = {}
           for f in files:
               if stop_event.is_set():
                   break
               future = executor.submit(process_single_file, f, processor, progress)
               futures[future] = f

           for future in as_completed(futures):
               file_path = futures[future]
               try:
                   result = future.result()
                   results.append(result)
                   if not result.success and on_error == "fail":
                       stop_event.set()
                       # Cancel pending futures
                       for f in futures:
                           f.cancel()
               except Exception as e:
                   # Handle unexpected errors
                   pass

       return results
   ```

2. **Switch to DaemonConnectionPool**
   ```python
   from video_policy_orchestrator.db.connection import DaemonConnectionPool

   pool = DaemonConnectionPool(db_path)
   try:
       # Use pool for all DB access
   finally:
       pool.close()
   ```

### Phase 5: Error Handling

1. **Handle on_error modes**
   - `fail`: Set stop event, cancel pending, report failure
   - `skip`: Continue processing, collect all results

2. **Aggregate results**
   ```python
   success_count = sum(1 for r in results if r.success)
   fail_count = len(results) - success_count
   ```

### Phase 6: Testing

1. **Unit tests**
   - ProgressTracker thread safety
   - Worker count resolution
   - Error handling modes

2. **Integration tests**
   - Parallel processing with mock files
   - on_error=fail stops batch
   - on_error=skip continues

## Key Files to Modify

| File | Changes |
|------|---------|
| `config/models.py` | Add `ProcessingConfig`, update `VPOConfig` |
| `config/builder.py` | Handle `[processing]` section |
| `cli/process.py` | Add `--workers`, parallel execution, progress |
| `tests/unit/config/test_models.py` | ProcessingConfig tests |
| `tests/unit/cli/test_process.py` | Parallel processing unit tests |
| `tests/integration/test_parallel_process.py` | End-to-end tests |

## Testing Commands

```bash
# Run all tests
uv run pytest

# Run specific tests
uv run pytest tests/unit/config/test_models.py -v
uv run pytest tests/unit/cli/test_process.py -v
uv run pytest tests/integration/test_parallel_process.py -v

# Manual testing
uv run vpo process --workers 2 -p policy.yaml /path/to/files/
uv run vpo process --workers 1 -p policy.yaml /path/to/files/  # Sequential
```

## Common Pitfalls

1. **Thread safety**: Always use locks when updating shared state
2. **Future cancellation**: `cancel()` only prevents pending futures from running
3. **Progress output**: Use stderr, not stdout (preserves JSON output)
4. **DB access**: Use DaemonConnectionPool, not get_connection()
5. **Worker cap**: Always apply max worker limit based on CPU cores
