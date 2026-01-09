# Implementation Plan: File Detail View

**Branch**: `020-file-detail-view` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-file-detail-view/spec.md`

## Summary

Add a file detail view accessible from the Library that displays comprehensive file metadata including all tracks grouped by type (video/audio/subtitle), file properties (path, size, container format), linked scan/apply jobs, and transcription results when available. Follows existing patterns from job detail view (016-job-detail-view) and library list view (018-library-list-view).

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: aiohttp, Jinja2, aiohttp-jinja2 (existing web stack)
**Storage**: SQLite via existing `db/models.py` and `db/connection.py`
**Testing**: pytest (unit and integration tests)
**Target Platform**: Linux server (local daemon, accessed via browser)
**Project Type**: Web application (server-rendered HTML with JavaScript enhancements)
**Performance Goals**: Page load < 2 seconds for files with up to 50 tracks
**Constraints**: Single-page detail view, collapsible track sections for 5+ tracks
**Scale/Scope**: Single file detail page, follows existing UI patterns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | Timestamps from DB are already UTC ISO-8601, display uses existing patterns |
| II. Stable Identity | PASS | Files identified by integer DB primary key (file_id), not path |
| III. Portable Paths | PASS | Using pathlib patterns already established in codebase |
| IV. Versioned Schemas | PASS | No schema changes required, using existing tables |
| V. Idempotent Operations | PASS | Read-only view, no modifications |
| VI. IO Separation | PASS | DB access via existing models.py functions |
| VII. Explicit Error Handling | PASS | 404/400/503 error responses specified in FR-010/FR-011 |
| VIII. Structured Logging | PASS | Follow existing request_logging_middleware pattern |
| IX. Configuration as Data | PASS | No new configuration needed |
| X. Policy Stability | N/A | Not modifying policy system |
| XI. Plugin Isolation | N/A | Not modifying plugin system |
| XII. Safe Concurrency | PASS | Using existing connection pool with transaction() |
| XIII. Database Design | PASS | Read-only queries using existing get_* functions |
| XIV. Test Media Corpus | PASS | Can use existing test fixtures |
| XV. Stable CLI/API Contracts | PASS | New API endpoint follows existing /api/library patterns |
| XVI. Dry-Run Default | N/A | Read-only feature |
| XVII. Data Privacy | PASS | No external service calls |
| XVIII. Living Documentation | PASS | Will update docs as needed |

**Gate Status**: PASS - No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/020-file-detail-view/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.yaml         # OpenAPI spec for /api/library/{file_id}
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/vpo/
├── db/
│   └── models.py              # Add: get_file_by_id(), get_transcriptions_for_tracks()
└── server/
    └── ui/
        ├── models.py          # Add: FileDetailItem, FileDetailResponse, TrackItem
        ├── routes.py          # Add: file_detail_handler, api_file_detail_handler
        └── templates/
            └── sections/
                └── file_detail.html  # New template

tests/
├── unit/
│   └── test_file_detail_models.py    # Unit tests for new models
└── integration/
    └── test_file_detail_api.py       # API endpoint tests
```

**Structure Decision**: Follows existing web application structure. New code integrates into existing `server/ui/` module following patterns from `016-job-detail-view`.

## Complexity Tracking

> **No violations - table not needed**

No constitution violations requiring justification. Feature follows all existing patterns.
