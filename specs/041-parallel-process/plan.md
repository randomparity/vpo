# Implementation Plan: Parallel File Processing

**Branch**: `041-parallel-process` | **Date**: 2025-12-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/041-parallel-process/spec.md`

## Summary

Add parallel file processing to the `vpo process` command using `ThreadPoolExecutor`. Files will be processed concurrently with configurable worker count (CLI `--workers` flag, config file `[processing].workers`, default 2). Maximum workers capped at half CPU cores. Progress shown via aggregate summary line. Error handling respects `on_error` policy modes.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: click (CLI), concurrent.futures (parallelism), threading (synchronization)
**Storage**: SQLite with WAL mode via existing `DaemonConnectionPool`
**Testing**: pytest with unit and integration tests
**Target Platform**: Linux, macOS
**Project Type**: Single CLI application
**Performance Goals**: Process multiple files concurrently to reduce total batch time
**Constraints**: Worker count capped at half CPU cores; external tools (ffmpeg, mkvmerge) are resource-heavy
**Scale/Scope**: Batches of 100+ files typical use case

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime handling changes |
| II. Stable Identity | N/A | No identity changes |
| III. Portable Paths | PASS | Uses existing pathlib patterns |
| IV. Versioned Schemas | PASS | Adding `[processing]` section to config, no DB schema change |
| V. Idempotent Operations | PASS | Parallel processing doesn't change idempotency |
| VI. IO Separation | PASS | Uses existing adapter patterns |
| VII. Explicit Error Handling | PASS | Error modes explicitly handled per spec |
| VIII. Structured Logging | PASS | Will use existing logger |
| IX. Configuration as Data | PASS | New config section follows existing patterns |
| X. Policy Stability | N/A | No policy schema changes |
| XI. Plugin Isolation | N/A | No plugin changes |
| XII. Safe Concurrency | PASS | Uses ThreadPoolExecutor, DaemonConnectionPool, file locking |
| XIII. Database Design | PASS | Uses existing DaemonConnectionPool for thread safety |
| XIV. Test Media Corpus | PASS | Will add integration tests |
| XV. Stable CLI/API Contracts | PASS | New `--workers` flag extends existing CLI |
| XVI. Dry-Run Default | PASS | Existing dry-run behavior preserved |
| XVII. Data Privacy | N/A | No external service calls |
| XVIII. Living Documentation | PASS | Will update docs |

**All gates pass.** No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/041-parallel-process/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no API changes)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── cli/
│   └── process.py           # MODIFY: Add --workers, parallel execution
├── config/
│   ├── models.py            # MODIFY: Add ProcessingConfig dataclass
│   ├── loader.py            # MODIFY: Load [processing] section
│   └── builder.py           # MODIFY: Handle processing config
└── db/
    └── connection.py        # EXISTS: DaemonConnectionPool (no changes needed)

tests/
├── unit/
│   ├── cli/
│   │   └── test_process.py  # MODIFY: Add parallel processing tests
│   └── config/
│       └── test_models.py   # MODIFY: Add ProcessingConfig tests
└── integration/
    └── test_parallel_process.py  # CREATE: End-to-end parallel tests
```

**Structure Decision**: Single project structure. Changes are additive to existing modules with no new directories required.

## Complexity Tracking

No violations requiring justification.
