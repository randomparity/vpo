# Implementation Plan: Reporting & Export CLI

**Branch**: `011-report-export-cli` | **Date**: 2025-01-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-report-export-cli/spec.md`

## Summary

Add a `vpo report` command group that generates text, CSV, or JSON reports for job history, library snapshots, scan operations, transcode operations, and policy applications. Reports are read-only views over existing database tables (jobs, files, tracks, operations) with time-based filtering, format selection, and file output options.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml)
**Primary Dependencies**: click (CLI), sqlite3 (database), csv (stdlib), json (stdlib)
**Storage**: SQLite (~/.vpo/library.db) - read-only access to existing schema v7
**Testing**: pytest
**Target Platform**: Linux, macOS (cross-platform via pathlib)
**Project Type**: Single project - CLI extension to existing VPO
**Performance Goals**: < 2 seconds for reports on databases with up to 10,000 files
**Constraints**: Read-only operations, no database modifications, default 100-row limit
**Scale/Scope**: 5 report subcommands, 3 output formats, shared formatting utilities

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | Timestamps stored as UTC in DB; convert to local time at presentation layer (FR-016) |
| II. Stable Identity | PASS | Reports query by stable IDs (job.id, file.id); no path-based keys |
| III. Portable Paths | PASS | Use pathlib.Path for --output; UTF-8 support (edge case documented) |
| IV. Versioned Schemas | PASS | Read-only; no schema changes required |
| V. Idempotent Operations | PASS | Reports are pure reads; inherently idempotent |
| VI. IO Separation | PASS | Reporting module separate from formatters; database access via existing models |
| VII. Explicit Error Handling | PASS | FR-019 requires non-zero exit on errors; clear error messages per edge cases |
| VIII. Structured Logging | PASS | Report operations should log query parameters and result counts |
| XII. Safe Concurrency | PASS | Single-threaded CLI; read-only DB access |
| XIII. Database Design | PASS | Uses existing DAO pattern in db/models.py; no raw SQL in CLI |
| XV. Stable CLI/API Contracts | PASS | Follow existing CLI patterns (--help, --format); reuse common flags |
| XVI. Dry-Run Default | N/A | Reports are inherently non-destructive |
| XVII. Data Privacy | PASS | Local data only; no external service calls |
| XVIII. Living Documentation | PASS | FR-018 requires help text; SC-008 requires documentation |

**Gate Status**: PASS - All applicable principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/011-report-export-cli/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── cli/
│   ├── __init__.py          # Existing - add report group registration
│   └── report.py            # NEW - report command group and subcommands
├── reports/                 # NEW - reporting backend module
│   ├── __init__.py
│   ├── queries.py           # Database query functions for each report type
│   ├── formatters.py        # Text, CSV, JSON output formatters
│   └── filters.py           # Time filter parsing (relative/absolute)
└── db/
    └── models.py            # Existing - may need minor query extensions

tests/
├── unit/
│   └── reports/             # NEW - unit tests for reporting
│       ├── test_queries.py
│       ├── test_formatters.py
│       └── test_filters.py
└── integration/
    └── test_report_cli.py   # NEW - CLI integration tests
```

**Structure Decision**: Single project extension. New `reports/` module follows existing patterns (see `scanner/`, `executor/`). CLI command in `cli/report.py` follows existing pattern (see `cli/scan.py`, `cli/jobs.py`).

## Complexity Tracking

No constitution violations requiring justification. Implementation follows established patterns.
