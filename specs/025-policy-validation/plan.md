# Implementation Plan: Policy Validation and Error Reporting

**Branch**: `025-policy-validation` | **Date**: 2025-11-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/025-policy-validation/spec.md`

## Summary

This feature enhances the policy editor web UI with comprehensive validation feedback. It connects policy saving to backend validation (already implemented via PolicyModel/Pydantic), surfaces field-level errors clearly in the UI, adds a "Test Policy" dry-run capability, and provides diff summaries on successful saves. The technical approach extends the existing PUT /api/policies/{name} endpoint to return structured validation errors and adds a new POST /api/policies/{name}/validate endpoint for testing without saving.

## Technical Context

**Language/Version**: Python 3.10+ (backend), Vanilla JavaScript ES6+ (frontend)
**Primary Dependencies**: aiohttp (async web server), Pydantic (validation), Jinja2 (templates), ruamel.yaml (round-trip YAML)
**Storage**: Filesystem (YAML policy files in ~/.vpo/policies/)
**Testing**: pytest (unit + integration tests)
**Target Platform**: Linux server (local daemon accessed via browser)
**Project Type**: Web application (Python backend + vanilla JS frontend)
**Performance Goals**: <1 second validation response time (FR-010, SC-001)
**Constraints**: No JavaScript frameworks; CSRF protection required for state-changing endpoints
**Scale/Scope**: Single-user local application; ~10 policy files typical

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime handling in this feature |
| II. Stable Identity | PASS | Policies identified by name (filename stem) |
| III. Portable Paths | PASS | Uses pathlib.Path throughout existing code |
| IV. Versioned Schemas | PASS | PolicyModel has schema_version field |
| V. Idempotent Operations | PASS | Validation is read-only; save is idempotent |
| VI. IO Separation | PASS | Validation logic in PolicyModel, IO in editor.py |
| VII. Explicit Error Handling | PASS | PolicyValidationError with field context |
| VIII. Structured Logging | PASS | Existing logging patterns in routes.py |
| IX. Configuration as Data | PASS | Policies stored as YAML config files |
| X. Policy Stability | PASS | No schema changes; enhanced error reporting only |
| XI. Plugin Isolation | N/A | No plugin interfaces affected |
| XII. Safe Concurrency | PASS | Existing optimistic locking with last_modified |
| XIII. Database Design | N/A | No database changes |
| XIV. Test Media Corpus | N/A | No media file handling |
| XV. Stable CLI/API Contracts | PASS | New endpoint; existing PUT enhanced backward-compatibly |
| XVI. Dry-Run Default | PASS | Test Policy feature enables validation without save |
| XVII. Data Privacy | PASS | No external service calls |
| XVIII. Living Documentation | PENDING | Update docs/usage/policy-editor.md after implementation |

**Gate Status**: PASS - All applicable principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/025-policy-validation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.yaml         # OpenAPI spec for new/modified endpoints
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── policy/
│   ├── loader.py           # PolicyModel, PolicyValidationError (existing)
│   ├── editor.py           # PolicyRoundTripEditor (existing)
│   └── validation.py       # NEW: ValidationResult, DiffSummary helpers
├── server/
│   ├── ui/
│   │   ├── routes.py       # MODIFY: Enhanced error responses, new validate endpoint
│   │   └── models.py       # MODIFY: ValidationErrorResponse, DiffSummary models
│   └── static/
│       └── js/
│           └── policy-editor/
│               └── policy-editor.js  # MODIFY: Error display, Test Policy button

tests/
├── unit/
│   └── policy/
│       └── test_validation.py       # NEW: ValidationResult, DiffSummary tests
└── integration/
    └── test_policy_editor_flow.py   # MODIFY: Add validation error test cases
```

**Structure Decision**: Follows existing web application structure with Python backend (aiohttp) and vanilla JS frontend. New validation helpers go in policy/ module; API changes in server/ui/.

## Complexity Tracking

> No violations to justify - implementation follows existing patterns.

| Aspect | Approach | Rationale |
|--------|----------|-----------|
| Error format | Structured JSON with field paths | Matches Pydantic error structure |
| Test endpoint | POST /api/policies/{name}/validate | Separate from PUT to maintain REST semantics |
| Diff summary | Server-side comparison | Keeps UI simple; server has original state |
