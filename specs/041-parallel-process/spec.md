# Feature Specification: Parallel File Processing

**Feature Branch**: `041-parallel-process`
**Created**: 2025-12-02
**Status**: Draft
**Input**: User description: "Add parallel file processing to vpo process command (GitHub issue #224)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Process Large Video Batches Faster (Priority: P1)

A video library administrator runs `vpo process` on a batch of 100+ video files. Currently, files are processed strictly sequentially, meaning each file must complete before the next begins. With parallel processing, multiple files can be processed simultaneously, utilizing system resources more efficiently and completing the batch faster.

**Why this priority**: This is the core value proposition of the feature. Users with large libraries will see immediate time savings when processing batches.

**Independent Test**: Can be tested by processing a batch of files with `--workers 2` and observing that two files are processed concurrently, with reduced total processing time compared to sequential processing.

**Acceptance Scenarios**:

1. **Given** a batch of 10 video files and `--workers 2`, **When** `vpo process` runs, **Then** two files are processed concurrently and the batch completes faster than sequential processing.
2. **Given** default configuration without `--workers` flag, **When** `vpo process` runs, **Then** the system uses the configured default worker count (2 by default).
3. **Given** a batch of 5 files and `--workers 10`, **When** `vpo process` runs, **Then** all 5 files process concurrently (workers limited by available work).

---

### User Story 2 - Configure Default Worker Count (Priority: P2)

A user wants to set their preferred parallelism level in the configuration file so they don't need to specify `--workers` on every command. They add a `[processing]` section to their `config.toml` with a `workers` setting.

**Why this priority**: Configuration persistence reduces friction for power users who have determined their optimal worker count.

**Independent Test**: Can be tested by setting `workers = 4` in config.toml, running `vpo process` without the `--workers` flag, and observing four concurrent file operations.

**Acceptance Scenarios**:

1. **Given** `workers = 4` in config.toml, **When** `vpo process` runs without `--workers` flag, **Then** 4 workers are used.
2. **Given** `workers = 4` in config.toml, **When** `vpo process --workers 1` runs, **Then** CLI flag overrides config and 1 worker is used.
3. **Given** no `[processing]` section in config.toml, **When** `vpo process` runs, **Then** the system uses the default of 2 workers.

---

### User Story 3 - Force Sequential Processing (Priority: P2)

A user with limited system resources or debugging a specific issue wants to force sequential file processing by specifying `--workers 1`, ensuring predictable ordering and minimal resource usage.

**Why this priority**: Provides an escape hatch for users who need deterministic processing order or have resource constraints.

**Independent Test**: Can be tested by running `vpo process --workers 1` and observing that files process one at a time in sequence.

**Acceptance Scenarios**:

1. **Given** `--workers 1`, **When** `vpo process` runs, **Then** files process strictly sequentially, one at a time.
2. **Given** `--workers 1`, **When** processing multiple files, **Then** output shows files processed in the order they were queued.

---

### User Story 4 - Error Handling with on_error Modes (Priority: P1)

When processing files in parallel, the error handling behavior must respect the policy's `on_error` setting. With `on_error: fail`, the batch should stop immediately on first error. With `on_error: skip`, other workers should continue and all results should be collected.

**Why this priority**: Error handling is critical for predictable behavior and matches existing sequential behavior expectations.

**Independent Test**: Can be tested by including a file that will fail processing in a batch and observing the correct behavior based on `on_error` setting.

**Acceptance Scenarios**:

1. **Given** `on_error: fail` and 10 files queued with 2 workers, **When** file 3 fails, **Then** pending work is cancelled, in-progress work completes, and the batch stops with an error.
2. **Given** `on_error: skip` and 10 files queued with 2 workers, **When** file 3 fails, **Then** the failure is recorded, other workers continue, and all results are reported at the end.
3. **Given** `on_error: fail`, **When** a file fails, **Then** no new files are started and the user sees a clear error message.

---

### Edge Cases

- What happens when disk space is limited? Each file needs approximately 2.5x its size during processing (original + backup + temp output). Parallel processing multiplies this requirement.
- How does the system handle the same file appearing multiple times in a batch? Existing file locking prevents concurrent modification of the same file.
- What happens if one worker is much slower than others (e.g., processing a very large file)? Other workers continue processing their files independently.
- How is progress reported when multiple files are being processed? Progress output must be serialized or aggregated to avoid interleaved/garbled output.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `--workers` CLI option for the `vpo process` command to specify the number of parallel workers.
- **FR-002**: System MUST support a `[processing]` configuration section with a `workers` setting in config.toml.
- **FR-003**: CLI `--workers` flag MUST override the configuration file setting.
- **FR-004**: Default worker count MUST be 2 when not specified in configuration or CLI.
- **FR-005**: System MUST accept `--workers 1` to force sequential processing.
- **FR-006**: System MUST use thread-based parallelization via `ThreadPoolExecutor`.
- **FR-007**: System MUST use the existing `DaemonConnectionPool` for thread-safe database access.
- **FR-008**: System MUST respect existing file locking to prevent concurrent modification of the same file.
- **FR-009**: With `on_error: fail`, system MUST cancel pending futures and stop the batch when any file fails.
- **FR-010**: With `on_error: skip`, system MUST continue processing other files and collect all results.
- **FR-011**: System MUST display an aggregate summary line updated in-place during parallel processing (e.g., "Processing: 3/10 files [2 active]") to prevent garbled output and provide clear progress visibility.
- **FR-012**: System MUST report summary results showing successful files, failed files, and total processing time.
- **FR-013**: System MUST cap the maximum worker count at half the CPU core count (e.g., 4 workers on an 8-core system). If the user requests more workers than the cap, the system uses the capped value and logs a warning.

### Key Entities

- **Worker**: A thread that processes files concurrently. Each worker handles one file at a time.
- **Processing Configuration**: Settings related to batch processing behavior, stored in config.toml under `[processing]` section.
- **Batch Result**: Aggregated outcome of processing multiple files, including success count, failure count, and individual file results.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Processing a batch of 10 comparable video files with 2 workers completes in less time than sequential processing of the same files.
- **SC-002**: Users can configure the default worker count without modifying their workflow commands.
- **SC-003**: Error behavior is predictable and consistent with the configured `on_error` policy setting.
- **SC-004**: Console output remains readable during parallel processing (no interleaved or garbled text).
- **SC-005**: Existing single-file processing behavior is unchanged when `--workers 1` is specified.

## Clarifications

### Session 2025-12-02

- Q: What is the maximum worker limit? → A: Dynamic limit, capped at half the CPU core count (≤ 0.5x cores)
- Q: How should progress be displayed during parallel processing? → A: Aggregate summary line updated in-place (e.g., "Processing: 3/10 files [2 active]")

## Assumptions

- The existing `V11WorkflowProcessor` is stateless per-file, making it safe for concurrent use.
- SQLite in WAL mode supports concurrent reads as required for parallel workers.
- The existing file locking mechanism via `fcntl.flock()` is sufficient to prevent race conditions.
- External tools (ffmpeg, mkvmerge) are resource-heavy; the default of 2 workers balances throughput with resource usage.
- Most processing work is I/O-bound (waiting for external subprocess completion), making threads an appropriate choice over processes.

## Dependencies

- Existing `DaemonConnectionPool` for thread-safe database access.
- Existing file locking mechanism.
- `concurrent.futures.ThreadPoolExecutor` from the Python standard library.
