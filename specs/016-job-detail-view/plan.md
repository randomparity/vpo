# Implementation Plan: Job Detail View with Logs

**Branch**: `016-job-detail-view` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-job-detail-view/spec.md`

## Summary

Add a job detail view accessible from the Jobs dashboard that displays full job metadata, human-readable summaries, and log output. The detail view is implemented as a separate page route (`/jobs/{job_id}`) for URL sharing and deep-linking. Job logs are stored in files on disk with a `log_path` field reference in the jobs table.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml requires-python = ">=3.10")
**Primary Dependencies**: aiohttp (>=3.9, existing), aiohttp-jinja2 (>=1.6, existing), Jinja2 (>=3.1, existing)
**Storage**: SQLite (~/.vpo/library.db) - existing schema v7, file-based logs (~/.vpo/logs/{job_id}.log)
**Testing**: pytest (>=9.0.1)
**Target Platform**: Linux, macOS (cross-platform per Constitution III)
**Project Type**: Web application (server-rendered HTML with JavaScript enhancement)
**Performance Goals**: Page load within 2 seconds (SC-001), log viewing supports 10,000+ lines (SC-004)
**Constraints**: File-based log storage to avoid database bloat, lazy loading for large logs
**Scale/Scope**: Single-user desktop application, logs up to 10,000+ lines per job

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ PASS | All timestamps stored as UTC ISO-8601, displayed with relative time at presentation layer |
| II. Stable Identity | ✅ PASS | Jobs identified by UUID, not file paths |
| III. Portable Paths | ✅ PASS | Using pathlib.Path for log file operations |
| IV. Versioned Schemas | ✅ PASS | New `log_path` field requires schema v8 migration |
| V. Idempotent Operations | ✅ PASS | Read-only view operations are inherently idempotent |
| VI. IO Separation | ✅ PASS | Log file reading encapsulated in dedicated module |
| VII. Explicit Error Handling | ✅ PASS | Missing logs, invalid IDs handled with clear error states |
| VIII. Structured Logging | ✅ PASS | Job logs stored per-job, structured by job ID |
| IX. Configuration as Data | ✅ PASS | Log directory path from VPO_DATA_DIR config |
| X. Policy Stability | N/A | No policy changes |
| XI. Plugin Isolation | N/A | No plugin interface changes |
| XII. Safe Concurrency | ✅ PASS | Read-only operations, existing connection pool handles concurrency |
| XIII. Database Design | ✅ PASS | Adding indexed `log_path` field, DAO encapsulation maintained |
| XIV. Test Media Corpus | N/A | No media processing changes |
| XV. Stable CLI/API Contracts | ✅ PASS | New API endpoint follows existing patterns |
| XVI. Dry-Run Default | N/A | Read-only feature |
| XVII. Data Privacy | ✅ PASS | Logs displayed only to local user, no external transmission |
| XVIII. Living Documentation | ✅ PASS | Feature documented in spec, implementation details in plan |

**Gate Result**: ✅ PASS - All applicable principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/016-job-detail-view/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── db/
│   ├── models.py              # Add log_path field to Job dataclass
│   └── schema.py              # Schema v8 migration for log_path column
├── server/
│   └── ui/
│       ├── models.py          # Add JobDetailItem, JobDetailResponse models
│       ├── routes.py          # Add job_detail_handler, api_job_detail_handler, api_job_logs_handler
│       └── templates/
│           └── sections/
│               └── job_detail.html  # New template for detail view
├── jobs/
│   └── logs.py                # New: Log file reading utilities (get_log_path, read_log_tail, etc.)
└── static/
    └── js/
        └── job_detail.js      # New: Client-side JavaScript for detail view

tests/
├── unit/
│   ├── server/ui/
│   │   └── test_job_detail_routes.py  # Unit tests for new routes
│   └── jobs/
│       └── test_logs.py               # Unit tests for log utilities
└── integration/
    └── test_job_detail_api.py         # Integration tests for API endpoints
```

**Structure Decision**: Extends existing web application structure. New code follows established patterns from 015-jobs-dashboard implementation.

## Complexity Tracking

> No Constitution violations requiring justification.

| Item | Decision | Rationale |
|------|----------|-----------|
| Schema migration v7→v8 | Add `log_path` column | Minimal change, follows existing migration pattern |
| Separate logs API endpoint | `/api/jobs/{id}/logs` | Enables lazy loading, avoids bloating main job response |
| File-based log storage | `~/.vpo/logs/{job_id}.log` | Avoids SQLite bloat, supports streaming large logs |
