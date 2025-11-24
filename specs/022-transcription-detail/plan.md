# Implementation Plan: Transcription Detail View

**Branch**: `022-transcription-detail` | **Date**: 2025-11-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/022-transcription-detail/spec.md`

## Summary

Implement a detailed transcription view for individual audio tracks, displaying language detection results, confidence scores, classification reasoning, and the transcription text. This extends the existing transcriptions infrastructure (021-transcriptions-list) by adding a track-level detail page accessible from both File Detail and Transcriptions List views.

## Technical Context

**Language/Version**: Python 3.10+ (existing codebase)
**Primary Dependencies**: aiohttp, Jinja2, aiohttp-jinja2 (existing web stack)
**Storage**: SQLite via existing `db/models.py` and `db/connection.py`
**Testing**: pytest with existing test infrastructure
**Target Platform**: Linux/macOS (local daemon with web UI)
**Project Type**: Web application (server-rendered HTML with vanilla JS enhancements)
**Performance Goals**: Page load < 2 seconds (per SC-002)
**Constraints**: No external service calls; read-only view of existing data
**Scale/Scope**: Single transcription per audio track; supports long text content (> 10,000 chars)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | Uses existing UTC ISO-8601 timestamps from transcription_results |
| II. Stable Identity | PASS | Uses transcription_results.id as stable identifier |
| III. Portable Paths | PASS | Uses pathlib.Path for templates; no path handling in this feature |
| IV. Versioned Schemas | PASS | No schema changes required; uses existing transcription_results table |
| V. Idempotent Operations | PASS | Read-only view; no data modifications |
| VI. IO Separation | PASS | Uses existing db/models.py repository pattern |
| VII. Explicit Error Handling | PASS | Explicit 404/400 handling per FR-010 |
| VIII. Structured Logging | PASS | Uses existing request_logging_middleware |
| IX. Configuration as Data | PASS | No new configuration required |
| X. Policy Stability | N/A | No policy changes |
| XI. Plugin Isolation | PASS | Displays plugin_name but no plugin API changes |
| XII. Safe Concurrency | PASS | Uses existing connection_pool.transaction() pattern |
| XIII. Database Design | PASS | Uses existing indexes; no new queries require optimization |
| XIV. Test Media Corpus | PASS | Can test with existing transcription fixtures |
| XV. Stable CLI/API Contracts | PASS | Adds new API endpoint /api/transcriptions/{id}; consistent with existing patterns |
| XVI. Dry-Run Default | N/A | Read-only feature |
| XVII. Data Privacy | PASS | Displays user's own transcription data; no external calls |
| XVIII. Living Documentation | PASS | Will update INDEX.md if docs created |

**Gate Status**: PASS - No violations

## Project Structure

### Documentation (this feature)

```text
specs/022-transcription-detail/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── server/
│   ├── ui/
│   │   ├── models.py           # + TranscriptionDetailItem, TranscriptionDetailContext
│   │   ├── routes.py           # + transcription_detail_handler, api_transcription_detail_handler
│   │   └── templates/
│   │       └── sections/
│   │           └── transcription_detail.html  # NEW
│   └── static/
│       ├── css/
│       │   └── main.css        # + transcription detail styles (if needed)
│       └── js/
│           └── transcription-detail.js  # NEW (optional - for show more/highlight)
└── db/
    └── models.py               # + get_transcription_detail() query function

tests/
├── unit/
│   └── server/
│       └── ui/
│           └── test_transcription_detail_models.py  # NEW
└── integration/
    └── server/
        └── test_transcription_detail_routes.py  # NEW
```

**Structure Decision**: Follows existing web application pattern established by 016-job-detail-view and 020-file-detail-view. New route handlers and models in ui/, new template in templates/sections/, database query in db/models.py.

## Complexity Tracking

> No violations - table not required
