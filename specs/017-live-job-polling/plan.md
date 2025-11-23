# Implementation Plan: Live Job Status Updates (Polling)

**Branch**: `017-live-job-polling` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-live-job-polling/spec.md`

## Summary

Add automatic polling to the Jobs dashboard and Job detail view to display real-time job status updates without manual page refresh. This is a client-side JavaScript enhancement that leverages existing API endpoints (`/api/jobs`, `/api/jobs/{job_id}`, `/api/jobs/{job_id}/logs`) with configurable polling intervals, visibility-aware behavior, and graceful error handling with exponential backoff.

## Technical Context

**Language/Version**: Python 3.10+ (server), JavaScript ES6+ (client)
**Primary Dependencies**: aiohttp (existing), Jinja2 (existing), vanilla JavaScript (no new dependencies)
**Storage**: SQLite (~/.vpo/library.db) - existing schema v7, read-only access
**Testing**: pytest (server-side), manual browser testing (client-side)
**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge - all support Page Visibility API)
**Project Type**: Web application (server-rendered HTML with JavaScript enhancements)
**Performance Goals**: Poll updates within configured interval (default 5s), UI render <100ms
**Constraints**: No WebSocket/SSE (polling only per spec), minimal JavaScript (no framework dependencies)
**Scale/Scope**: Single concurrent user expected (local tool), ~100 jobs typical view

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ Pass | All timestamps from API are ISO-8601 UTC; client converts for display |
| II. Stable Identity | ✅ Pass | Jobs identified by UUIDv4; no path-based identity |
| III. Portable Paths | ✅ Pass | Client-side JavaScript; no filesystem operations |
| IV. Versioned Schemas | ✅ Pass | No schema changes; uses existing API contracts |
| V. Idempotent Operations | ✅ Pass | Read-only polling; no state mutations |
| VI. IO Separation | ✅ Pass | Client-side fetch to existing API endpoints |
| VII. Explicit Error Handling | ✅ Pass | Defined backoff strategy (10s initial, 2min max) |
| VIII. Structured Logging | ✅ Pass | Console logging for client errors; server logging unchanged |
| IX. Configuration as Data | ✅ Pass | Polling interval configurable via daemon config |
| X. Policy Stability | N/A | No policy changes |
| XI. Plugin Isolation | N/A | No plugin interfaces affected |
| XII. Safe Concurrency | ✅ Pass | Single-threaded JavaScript; API already thread-safe |
| XIII. Database Design | ✅ Pass | No database changes; read-only queries |
| XIV. Test Media Corpus | N/A | No media processing |
| XV. Stable CLI/API Contracts | ✅ Pass | No API changes; uses existing endpoints |
| XVI. Dry-Run Default | N/A | No destructive operations |
| XVII. Data Privacy | ✅ Pass | No external service calls; local polling only |
| XVIII. Living Documentation | ✅ Pass | Will update relevant docs with polling behavior |

**Gate Result**: ✅ PASSED - All applicable principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/017-live-job-polling/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research findings
├── data-model.md        # Phase 1 data model (client-side state)
├── quickstart.md        # Phase 1 development quickstart
├── contracts/           # Phase 1 API contracts (existing endpoints)
└── tasks.md             # Phase 2 implementation tasks
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── server/
│   ├── static/
│   │   └── js/
│   │       ├── jobs.js           # MODIFY: Add polling to dashboard
│   │       ├── job_detail.js     # MODIFY: Add polling to detail view
│   │       └── polling.js        # NEW: Shared polling utilities
│   ├── ui/
│   │   ├── routes.py             # MODIFY: Add polling config endpoint
│   │   └── models.py             # MODIFY: Add PollingConfig model
│   └── config.py                 # MODIFY: Add polling settings (if needed)

tests/
├── unit/
│   └── server/
│       └── test_polling_config.py  # NEW: Test polling config endpoint
└── integration/
    └── server/
        └── test_polling_api.py     # NEW: Test polling behavior
```

**Structure Decision**: Extends existing web application structure. New `polling.js` module provides shared utilities for visibility-aware polling with backoff. Modifications to existing `jobs.js` and `job_detail.js` integrate polling behavior.

## Complexity Tracking

> No constitution violations requiring justification.

N/A - Design adheres to all applicable constitution principles.
