# Implementation Plan: Jobs Dashboard List View

**Branch**: `015-jobs-dashboard` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-jobs-dashboard/spec.md`

## Summary

Implement a Jobs dashboard page in the existing VPO web UI that displays all recent jobs with filtering by status, type, and time range. The implementation leverages the existing aiohttp server architecture, jobs database table, and Jinja2 template system.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml)
**Primary Dependencies**: aiohttp (existing), aiohttp_jinja2 (existing), Jinja2 (existing)
**Storage**: SQLite (~/.vpo/library.db) - existing jobs table with schema v7
**Testing**: pytest (existing test infrastructure)
**Target Platform**: Linux server (web browser client)
**Project Type**: Web application (server-rendered HTML with client-side JS enhancements)
**Performance Goals**: Page load under 3 seconds, filter response under 1 second
**Constraints**: Server-side rendering primary, minimal JavaScript, no external dependencies
**Scale/Scope**: Support displaying up to 1000+ jobs with pagination (50 per page default)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps from jobs table are UTC; display conversion at template layer |
| II. Stable Identity | PASS | Jobs use UUID primary keys; no path-based identity |
| III. Portable Paths | PASS | Using pathlib.Path for file paths in target display |
| IV. Versioned Schemas | PASS | Jobs table part of schema v7; no schema changes needed |
| V. Idempotent Operations | PASS | Read-only operations; no data modification |
| VI. IO Separation | PASS | Database queries encapsulated in existing db/operations module |
| VII. Explicit Error Handling | PASS | Using existing error middleware patterns |
| VIII. Structured Logging | PASS | Using existing request logging middleware |
| IX. Configuration as Data | PASS | No new configuration needed |
| XII. Safe Concurrency | PASS | Using existing DaemonConnectionPool for thread-safe DB access |
| XIII. Database Design | PASS | Using existing DAO pattern via db/operations module |
| XV. Stable CLI/API Contracts | PASS | New API endpoint follows existing /api/* pattern |

## Project Structure

### Documentation (this feature)

```text
specs/015-jobs-dashboard/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── jobs-api.yaml    # OpenAPI spec for /api/jobs
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── server/
│   ├── app.py                    # Add /api/jobs route registration
│   ├── ui/
│   │   ├── routes.py             # Add jobs_handler with data, api_jobs_handler
│   │   ├── models.py             # Add JobListContext, JobFilterParams models
│   │   └── templates/
│   │       └── sections/
│   │           └── jobs.html     # Replace placeholder with full implementation
│   └── static/
│       ├── css/
│       │   └── main.css          # Add jobs table styles
│       └── js/
│           └── jobs.js           # New: job filtering and pagination

tests/
├── unit/
│   └── server/
│       └── ui/
│           └── test_jobs_routes.py    # Deferred: unit tests (add if tests requested later)
└── integration/
    └── server/
        └── test_jobs_api.py           # Deferred: integration tests (add if tests requested later)
```

**Structure Decision**: Web application pattern - extends existing server/ui structure with new handlers, templates, and static assets. No new directories needed at top level.

## Complexity Tracking

No constitution violations requiring justification.
