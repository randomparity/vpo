# Implementation Plan: Transcriptions Overview List

**Branch**: `021-transcriptions-list` | **Date**: 2025-11-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-transcriptions-list/spec.md`

## Summary

Implement a Transcriptions page that displays files with transcription results, showing language detection and confidence information. The page defaults to showing only transcribed files with a toggle to show all files. Users can click files to navigate to the existing File Detail view. The implementation follows established patterns from the Library List view (018) and File Detail view (020).

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: aiohttp, Jinja2, aiohttp-jinja2 (existing web stack)
**Storage**: SQLite via existing `db/models.py` and `db/connection.py`
**Testing**: pytest
**Target Platform**: Linux/macOS (web daemon)
**Project Type**: Web application (server-rendered HTML + vanilla JS)
**Performance Goals**: <2s page load for 10,000 files (SC-001)
**Constraints**: Pagination required for large datasets (SC-006)
**Scale/Scope**: Same as Library view - up to 10k files with pagination

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ Pass | Uses existing ISO-8601 UTC patterns |
| II. Stable Identity | ✅ Pass | Uses file_id and track_id as stable identifiers |
| III. Portable Paths | ✅ Pass | Uses pathlib via existing infrastructure |
| IV. Versioned Schemas | ✅ Pass | No schema changes - uses existing tables |
| V. Idempotent Operations | ✅ Pass | Read-only view with no state mutations |
| VI. IO Separation | ✅ Pass | UI queries via db/models.py, no direct SQL in handlers |
| VII. Explicit Error Handling | ✅ Pass | Follows existing error middleware patterns |
| VIII. Structured Logging | ✅ Pass | Uses existing request logging middleware |
| IX. Configuration as Data | ✅ Pass | No new config required |
| X. Policy Stability | N/A | No policy changes |
| XI. Plugin Isolation | N/A | No plugin interfaces affected |
| XII. Safe Concurrency | ✅ Pass | Uses asyncio.to_thread for DB queries |
| XIII. Database Design | ✅ Pass | Uses existing normalized schema |
| XIV. Test Media Corpus | ✅ Pass | Can use existing test fixtures |
| XV. Stable CLI/API Contracts | ✅ Pass | New API endpoint follows existing patterns |
| XVI. Dry-Run Default | N/A | Read-only feature |
| XVII. Data Privacy | ✅ Pass | Local data only, no external services |
| XVIII. Living Documentation | ✅ Pass | Spec-driven development with docs |

**Gate Status**: ✅ PASS - No violations

## Project Structure

### Documentation (this feature)

```text
specs/021-transcriptions-list/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.yaml         # OpenAPI spec for /api/transcriptions
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── db/
│   └── models.py                    # Add get_files_with_transcriptions() query
├── server/
│   ├── ui/
│   │   ├── models.py                # Add TranscriptionsFilterParams, TranscriptionListItem, etc.
│   │   ├── routes.py                # Update transcriptions_handler, add api_transcriptions_handler
│   │   └── templates/
│   │       └── sections/
│   │           └── transcriptions.html  # Replace placeholder with full template
│   └── static/
│       └── js/
│           └── transcriptions.js    # New: Client-side filtering/pagination

tests/
├── unit/
│   └── server/
│       └── test_transcriptions_models.py  # Model unit tests
└── integration/
    └── server/
        └── test_transcriptions_routes.py  # API integration tests
```

**Structure Decision**: Extends existing web application structure following patterns from 018-library-list-view and 020-file-detail-view. No new directories required.

## Complexity Tracking

> No violations to justify - Constitution Check passed.
