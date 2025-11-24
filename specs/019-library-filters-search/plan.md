# Implementation Plan: Library Filters and Search

**Branch**: `019-library-filters-search` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-library-filters-search/spec.md`

## Summary

Add metadata filtering and search capabilities to the existing Library view (018-library-list-view). The feature extends the current status filter with: text search (filename/title), resolution filter, audio language filter (multi-select), and subtitle presence filter. All filtering happens via API without full page reload. Filter state is persisted in URL query parameters for shareability.

## Technical Context

**Language/Version**: Python 3.10+ (existing codebase)
**Primary Dependencies**: aiohttp, Jinja2, aiohttp-jinja2 (existing web stack), SQLite
**Storage**: SQLite via existing `db/models.py` and `db/connection.py`
**Testing**: pytest (unit and integration)
**Target Platform**: Linux server (localhost web daemon)
**Project Type**: Web application (Python backend + vanilla JavaScript frontend)
**Performance Goals**: Filter operations complete within 1 second for 1000+ file libraries
**Constraints**: No full page reload on filter changes, debounce search input 300-500ms
**Scale/Scope**: Libraries with 1000-10000+ files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | No new datetime handling; uses existing scanned_at |
| II. Stable Identity | PASS | Filtering by existing file.id; no new identity concerns |
| III. Portable Paths | PASS | No new path handling; uses existing pathlib patterns |
| IV. Versioned Schemas | PASS | No schema changes required; uses existing tracks table |
| V. Idempotent Operations | PASS | Read-only filtering; inherently idempotent |
| VI. IO Separation | PASS | Extends existing API/DB separation pattern |
| VII. Explicit Error Handling | PASS | Will use existing error patterns from 018 |
| VIII. Structured Logging | PASS | Will log filter operations via existing logger |
| XII. Safe Concurrency | PASS | Uses existing thread-safe connection pool |
| XIII. Database Design | PASS | Extends existing query; no new tables needed |
| XV. Stable CLI/API Contracts | PASS | Additive API change (new query params); backward compatible |
| XVII. Data Privacy | PASS | No external service calls; local filtering only |

**Gate Result**: PASS - No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/019-library-filters-search/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
│   └── library-api.yaml # OpenAPI spec for library endpoint
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── db/
│   └── models.py              # Extend get_files_filtered() with new params
├── server/
│   ├── ui/
│   │   ├── models.py          # Extend LibraryFilterParams, LibraryContext
│   │   ├── routes.py          # Extend api_library_handler
│   │   └── templates/
│   │       └── sections/
│   │           └── library.html  # Add filter controls
│   └── static/
│       ├── js/
│       │   └── library.js     # Add filter handlers, debounce, URL sync
│       └── css/
│           └── library.css    # Add filter styling (if needed)

tests/
├── unit/
│   └── server/
│       └── ui/
│           └── test_models.py     # Test LibraryFilterParams parsing
└── integration/
    └── server/
        └── test_library_api.py    # Test filtered queries
```

**Structure Decision**: Web application pattern using existing VPO architecture. Backend extends existing aiohttp routes; frontend uses vanilla JavaScript (no build step).
