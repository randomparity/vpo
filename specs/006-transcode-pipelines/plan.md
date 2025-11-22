# Implementation Plan: Transcoding & File Movement Pipelines

**Branch**: `006-transcode-pipelines` | **Date**: 2025-11-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-transcode-pipelines/spec.md`

## Summary

Implement a job-based transcoding and file movement system for VPO. The feature adds:
1. **Job queue system** - SQLite-backed job persistence with CLI commands for managing long-running operations
2. **Transcoding policies** - Extend PolicySchema with video codec, quality, and resolution settings
3. **Audio preservation rules** - Policy-driven codec preservation with selective transcoding
4. **Directory organization** - Metadata-based file routing using filename-parsed templates
5. **Safety features** - Backup/restore capabilities and operation logging for rollback

Technical approach: Extend existing policy/executor architecture with new `TranscodeExecutor`, `MoveExecutor`, and `JobWorker` components. Jobs are processed via `vpo jobs start` worker with configurable limits for cron/systemd integration.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml)
**Primary Dependencies**: click (CLI), pydantic (models), PyYAML (config), sqlite3 (jobs DB)
**Storage**: SQLite (~/.vpo/library.db) - extend existing schema with jobs table
**Testing**: pytest (existing test infrastructure)
**Target Platform**: Linux, macOS (per Constitution III - Portable Paths)
**Project Type**: Single CLI application with plugin architecture
**Performance Goals**: Job queue operations < 1 second (SC-008); transcoding performance limited by ffmpeg
**Constraints**: Single job at a time (FR-011); worker limits for resource control (FR-027-030)
**Scale/Scope**: Personal media libraries (thousands of files); jobs persist across CLI invocations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ Pass | All job timestamps UTC ISO-8601 |
| II. Stable Identity | ✅ Pass | Jobs use UUID; files referenced by existing file_id |
| III. Portable Paths | ✅ Pass | pathlib.Path for all filesystem ops |
| IV. Versioned Schemas | ✅ Pass | Schema version bump (4→5) with migration |
| V. Idempotent Operations | ✅ Pass | Job submission idempotent; re-run safe |
| VI. IO Separation | ✅ Pass | TranscodeExecutor/MoveExecutor as adapters |
| VII. Explicit Error Handling | ✅ Pass | Job status tracks failures; custom exceptions |
| VIII. Structured Logging | ✅ Pass | Job ID + file ID in all log entries |
| IX. Configuration as Data | ✅ Pass | Worker limits, retention in config |
| X. Policy Stability | ✅ Pass | Backward-compatible policy extension |
| XI. Plugin Isolation | ✅ Pass | MetadataExtractor hook for future providers |
| XII. Safe Concurrency | ✅ Pass | Single worker; atomic job state transitions |
| XIII. Database Design | ✅ Pass | Jobs table with FK, indexes, constraints |
| XIV. Test Media Corpus | ✅ Pass | Add test fixtures for transcode scenarios |
| XV. Stable CLI/API Contracts | ✅ Pass | New `vpo jobs` subcommand group |
| XVI. Dry-Run Default | ✅ Pass | All operations support --dry-run |
| XVII. Data Privacy | ✅ Pass | No external services; local processing only |
| XVIII. Living Documentation | ✅ Pass | Update docs with transcode/jobs guide |

## Project Structure

### Documentation (this feature)

```text
specs/006-transcode-pipelines/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI interface specs)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── cli/
│   ├── __init__.py          # Add jobs subgroup
│   ├── jobs.py              # NEW: vpo jobs list/status/start/cancel/cleanup
│   └── transcode.py         # NEW: vpo transcode (submit job)
├── db/
│   ├── schema.py            # Extend with jobs table (v5 migration)
│   └── models.py            # Add Job, JobStatus models
├── executor/
│   ├── transcode.py         # NEW: FFmpeg transcoding adapter
│   └── move.py              # NEW: File movement adapter
├── jobs/
│   ├── __init__.py          # NEW: Job system module
│   ├── worker.py            # NEW: Job worker (processes queue)
│   ├── queue.py             # NEW: Job queue operations
│   └── progress.py          # NEW: FFmpeg progress parsing
├── policy/
│   ├── models.py            # Extend PolicySchema with transcode fields
│   └── transcode.py         # NEW: Transcode policy evaluation
├── metadata/
│   ├── __init__.py          # NEW: Metadata extraction module
│   ├── parser.py            # NEW: Filename pattern parser
│   └── templates.py         # NEW: Destination template rendering
└── plugin/
    └── events.py            # Add metadata extraction hook

tests/
├── unit/
│   ├── test_jobs_queue.py   # NEW
│   ├── test_jobs_worker.py  # NEW
│   ├── test_transcode_policy.py  # NEW
│   ├── test_metadata_parser.py   # NEW
│   └── test_destination_template.py  # NEW
├── integration/
│   ├── test_transcode_executor.py  # NEW
│   └── test_job_lifecycle.py       # NEW
└── fixtures/
    └── transcode/           # NEW: Test media for transcoding
```

**Structure Decision**: Extend existing single-project structure. New `jobs/` and `metadata/` modules follow existing patterns (e.g., `executor/`, `introspector/`). CLI commands follow existing `cli/` module organization.

## Complexity Tracking

> No constitution violations requiring justification.
