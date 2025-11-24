# Implementation Plan: Library List View

**Branch**: `018-library-list-view` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-library-list-view/spec.md`

## Summary

Implement a Library page that displays all scanned video files in a tabular format with columns for filename, title, resolution, audio languages, last scanned time, and policy profile. The page will follow the established Jobs dashboard patterns for pagination, filtering, and styling consistency.

## Technical Context

**Language/Version**: Python 3.10+ (existing codebase)
**Primary Dependencies**: aiohttp, Jinja2, aiohttp-jinja2 (existing web stack)
**Storage**: SQLite via existing `db/models.py` and `db/connection.py`
**Testing**: pytest (existing test infrastructure)
**Target Platform**: Linux server (existing daemon via `vpo serve`)
**Project Type**: Web application (server-rendered HTML + vanilla JavaScript)
**Performance Goals**: Page load within 3 seconds, pagination within 2 seconds for 10,000 files
**Constraints**: Consistent with Jobs dashboard styling; no new frontend framework dependencies
**Scale/Scope**: Support libraries up to 10,000+ files with efficient pagination

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ PASS | Use existing UTC timestamps from `scanned_at` field |
| II. Stable Identity | ✅ PASS | Files use database `id` as primary key, not paths |
| III. Portable Paths | ✅ PASS | Use `pathlib.Path` patterns from existing codebase |
| IV. Versioned Schemas | ✅ PASS | No schema changes needed; uses existing FileRecord/TrackRecord |
| V. Idempotent Operations | ✅ PASS | Read-only display feature; no mutations |
| VI. IO Separation | ✅ PASS | Database queries via existing DAO patterns |
| VII. Explicit Error Handling | ✅ PASS | Handle scan errors via existing `scan_status`/`scan_error` fields |
| VIII. Structured Logging | ✅ PASS | Follow existing route logging patterns |
| IX. Configuration as Data | ✅ PASS | Page size configurable via existing patterns |
| X. Policy Stability | N/A | Display-only feature |
| XI. Plugin Isolation | N/A | No plugin interfaces involved |
| XII. Safe Concurrency | ✅ PASS | Use existing `DaemonConnectionPool` thread-safety patterns |
| XIII. Database Design | ✅ PASS | Use existing indexed tables; add efficient pagination query |
| XIV. Test Media Corpus | ✅ PASS | Write unit tests for new query functions |
| XV. Stable CLI/API Contracts | ✅ PASS | New `/api/library` endpoint follows existing API patterns |
| XVI. Dry-Run Default | N/A | Read-only feature |
| XVII. Data Privacy | ✅ PASS | No external service calls; local data only |
| XVIII. Living Documentation | ✅ PASS | Update docs if needed |

**Result**: All applicable principles satisfied. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/018-library-list-view/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── library-api.yaml # OpenAPI spec for /api/library
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── db/
│   └── models.py              # Add get_files_filtered() query function
├── server/
│   ├── ui/
│   │   ├── models.py          # Add FileListItem, FileListResponse, LibraryFilterParams
│   │   ├── routes.py          # Add library_handler(), library_api_handler()
│   │   └── templates/
│   │       └── sections/
│   │           └── library.html  # Update placeholder template
│   └── static/
│       ├── js/
│       │   └── library.js     # New: Library page JavaScript
│       └── css/
│           └── main.css       # Extend with library-specific styles

tests/
├── unit/
│   └── server/
│       └── ui/
│           └── test_library_models.py  # New: model unit tests
└── integration/
    └── server/
        └── test_library_api.py         # New: API endpoint tests
```

**Structure Decision**: Extends existing web application structure. No new directories needed at top level. All new code integrates into existing modules following established patterns.

## Complexity Tracking

> No violations to justify. Feature follows existing patterns exactly.

| Area | Complexity | Justification |
|------|------------|---------------|
| Database query | Low | Follows `get_jobs_filtered()` pattern exactly |
| UI models | Low | Follows `JobListItem`/`JobListResponse` pattern |
| Template | Low | Follows `jobs.html` structure |
| JavaScript | Medium | New file but follows `jobs.js` patterns |
