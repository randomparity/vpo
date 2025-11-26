# Implementation Plan: Web UI REST API Endpoints

**Branch**: `028-webui-rest-api` | **Date**: 2025-11-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/028-webui-rest-api/spec.md`

## Summary

This feature documents the existing REST API endpoints that power the VPO Web UI. All endpoints (FR-001 through FR-017) are already implemented and functional. The primary deliverable is creating comprehensive API reference documentation at `docs/api-webui.md` (FR-018) that covers all endpoints with request/response schemas and examples.

## Technical Context

**Language/Version**: Python 3.10+, JavaScript ES6+
**Primary Dependencies**: aiohttp (web server), Jinja2 (templates), ruamel.yaml (policy editing)
**Storage**: SQLite database at `~/.vpo/library.db` (existing `jobs`, `files`, `plans`, `policies` tables)
**Testing**: pytest with aiohttp test client
**Target Platform**: Linux server, macOS (local tool with web interface)
**Project Type**: Web application (Python backend + vanilla JS frontend)
**Performance Goals**: List endpoints < 1 second, detail endpoints < 500ms under normal load
**Constraints**: Same-origin frontend (no CORS needed), CSRF protection required for mutations
**Scale/Scope**: Local tool - single user, typical library < 10k files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps in UTC ISO-8601 format |
| II. Stable Identity | PASS | Jobs/Plans use UUIDv4, Files use integer IDs |
| IV. Versioned Schemas | PASS | Response schemas use typed dataclasses |
| V. Idempotent Operations | PASS | GET endpoints idempotent; POST/PUT validate state |
| VI. IO Separation | PASS | Route handlers delegate to db/operations modules |
| VII. Explicit Error Handling | PASS | Structured error responses with codes |
| VIII. Structured Logging | PASS | Request logging middleware logs method, path, status, duration |
| XIII. Database Design | PASS | All queries via typed operations, no raw SQL in routes |
| XV. Stable CLI/API Contracts | PASS | Documentation deliverable ensures API stability |
| XVIII. Living Documentation | PASS | Primary deliverable is API documentation |

**Gate Result**: PASS - No violations. All applicable principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/028-webui-rest-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI spec)
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (existing structure)

```text
src/video_policy_orchestrator/
├── server/
│   ├── app.py           # Application setup, route registration
│   ├── csrf.py          # CSRF middleware
│   └── ui/
│       ├── routes.py    # All API handlers (existing)
│       └── models.py    # Response models (existing)
└── db/
    ├── models.py        # Database models
    └── operations.py    # Database queries

docs/
└── api-webui.md         # NEW: API reference documentation (FR-018)

tests/
├── unit/
│   └── server/          # Existing route tests
└── integration/
    └── server/          # Existing API integration tests
```

**Structure Decision**: No new source structure needed. This feature adds documentation only (`docs/api-webui.md`).

## Complexity Tracking

No constitution violations to justify. This feature documents existing functionality.
