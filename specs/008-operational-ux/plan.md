# Implementation Plan: Operational UX - Incremental Scans, Job History & Profiles

**Branch**: `008-operational-ux` | **Date**: 2025-11-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-operational-ux/spec.md`

## Summary

Enable VPO for periodic maintenance workflows with: (1) incremental scanning that skips unchanged files using mtime/size change detection, (2) expanded job history tracking all operations with `vpo jobs list/show` commands, (3) configuration profiles stored in `~/.vpo/profiles/` for library-specific settings, and (4) structured logging with configurable levels and JSON format support.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml)
**Primary Dependencies**: click (CLI), pydantic (models), PyYAML (config), sqlite3 (database)
**Storage**: SQLite (~/.vpo/library.db) - extend existing schema v6
**Testing**: pytest (tests/ directory)
**Target Platform**: Linux, macOS (per Constitution Principle III)
**Project Type**: Single CLI application with Rust extension for parallel discovery
**Performance Goals**: Incremental scan of 1000-file library with 10 changes completes in <10% of full scan time (SC-001)
**Constraints**: Backward-compatible CLI (new flags only), schema migration required
**Scale/Scope**: Home media libraries (1k-100k files), single-user local operation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps UTC ISO-8601, converted at presentation layer |
| II. Stable Identity | PASS | Jobs use UUIDv4, files identified by path with id PK |
| III. Portable Paths | PASS | Using pathlib.Path, UTF-8 encoding |
| IV. Versioned Schemas | PASS | Schema v6→v7 migration required for job_type expansion |
| V. Idempotent Operations | PASS | Incremental scan is idempotent by design |
| VI. IO Separation | PASS | Profile/logging config loaded via existing config layer |
| VII. Explicit Error Handling | PASS | Profile validation at startup, clear error messages |
| VIII. Structured Logging | PASS | This feature implements structured logging per constitution |
| IX. Configuration as Data | PASS | Profiles stored as YAML files, not code |
| X. Policy Stability | N/A | No policy schema changes |
| XI. Plugin Isolation | N/A | No plugin interface changes |
| XII. Safe Concurrency | PASS | Incremental detection uses per-file atomic checks |
| XIII. Database Design | PASS | Expanding jobs table, adding indexes |
| XIV. Test Media Corpus | PASS | Unit tests for incremental detection logic |
| XV. Stable CLI/API Contracts | PASS | New flags additive (`--full`, `--profile`), no breaking changes |
| XVI. Dry-Run Default | N/A | Scan is non-destructive |
| XVII. Data Privacy | PASS | No external service integration |
| XVIII. Living Documentation | PASS | CLI help text updated, docs in /docs/ |

**Gate Status**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/008-operational-ux/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── cli/
│   ├── __init__.py
│   ├── scan.py          # MODIFY: add --full flag, incremental summary
│   ├── jobs.py          # CREATE: vpo jobs list/show commands
│   └── profiles.py      # CREATE: vpo profiles list/show commands
├── config/
│   ├── models.py        # MODIFY: add LoggingConfig, ProfileConfig
│   ├── loader.py        # MODIFY: add profile loading
│   └── profiles.py      # CREATE: profile resolution logic
├── db/
│   ├── schema.py        # MODIFY: expand job_type constraint, add scan job type
│   └── models.py        # MODIFY: add JobType.SCAN, JobType.APPLY
├── scanner/
│   └── orchestrator.py  # MODIFY: incremental detection logic
├── logging/             # CREATE: new module
│   ├── __init__.py
│   ├── config.py        # Logging configuration
│   └── handlers.py      # JSON handler, rotation
└── jobs/
    └── tracking.py      # CREATE: scan/apply job recording

tests/
├── unit/
│   ├── test_incremental_scan.py
│   ├── test_profiles.py
│   └── test_logging_config.py
├── integration/
│   └── test_jobs_cli.py
└── fixtures/
    └── profiles/        # Sample profile YAML files
```

**Structure Decision**: Extending existing single-project structure. New `logging/` module for structured logging, new CLI subcommands in `cli/`, profile logic in `config/`.

## Complexity Tracking

> No violations requiring justification.

| Component | Complexity | Rationale |
|-----------|------------|-----------|
| Incremental scan | Low | Leverage existing mtime/size in files table |
| Job expansion | Low | Extend existing jobs table with new job types |
| Profiles | Medium | New config layer, YAML loading, precedence rules |
| Logging | Medium | New module with rotation, JSON format support |
