# Implementation Plan: V9 Policy Editor GUI

**Branch**: `036-v9-policy-editor` | **Date**: 2025-11-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/036-v9-policy-editor/spec.md`

## Summary

Extend the existing policy editor GUI to support schema versions 3-10, enabling users to configure track filtering, container conversion, conditional rules, audio synthesis, video/audio transcoding, and workflow settings through a visual form interface with collapsible accordion sections.

## Technical Context

**Language/Version**: Python 3.10+ (backend), JavaScript ES6+ (frontend)
**Primary Dependencies**: aiohttp, Jinja2, ruamel.yaml (existing); pydantic for validation
**Storage**: YAML policy files in `~/.vpo/policies/`
**Testing**: pytest for backend, manual browser testing for frontend
**Target Platform**: Linux and macOS via web browser
**Project Type**: Web application (server-rendered HTML with JavaScript enhancements)
**Performance Goals**: Validation feedback < 500ms, YAML preview updates debounced to 300ms
**Constraints**: Vanilla JavaScript only (no frameworks), must preserve unknown YAML fields and comments
**Scale/Scope**: Support all schema V3-V10 features across 8 collapsible sections

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime handling in policy editor |
| II. Stable Identity | PASS | Policies identified by name, not path |
| III. Portable Paths | PASS | Using pathlib.Path for policy paths |
| IV. Versioned Schemas | PASS | Editor respects schema_version, creates V10 by default |
| V. Idempotent Operations | PASS | Save operation is idempotent (same input = same output) |
| VI. IO Separation | PASS | PolicyRoundTripEditor encapsulates file I/O |
| VII. Explicit Error Handling | PASS | Field-level validation errors returned |
| VIII. Structured Logging | PASS | API handlers use logger |
| IX. Configuration as Data | PASS | Policies are data files, not code |
| X. Policy Stability | PASS | Backward compatible, preserves unknown fields |
| XI. Plugin Isolation | N/A | No plugin interfaces affected |
| XII. Safe Concurrency | PASS | Optimistic locking via last_modified timestamp |
| XIII. Database Design | N/A | No database changes |
| XIV. Test Media Corpus | N/A | No test media needed |
| XV. Stable CLI/API Contracts | PASS | Extending existing API endpoints |
| XVI. Dry-Run Default | PASS | Validate endpoint allows preview before save |
| XVII. Data Privacy | N/A | No external service integration |
| XVIII. Living Documentation | PASS | Update policy-editor.md after implementation |

## Project Structure

### Documentation (this feature)

```text
specs/036-v9-policy-editor/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── server/
│   ├── ui/
│   │   ├── routes.py           # Extend policy_editor_handler, api_policy_* handlers
│   │   ├── models.py           # Extend PolicyEditorContext, PolicyEditorRequest
│   │   └── templates/
│   │       └── sections/
│   │           └── policy_editor.html    # Main editor template (extend)
│   └── static/
│       ├── css/
│       │   └── policy-editor.css         # Accordion styles, section styles
│       └── js/
│           └── policy-editor/
│               ├── policy-editor.js      # Main module (extend)
│               ├── section-transcode.js  # NEW: V6 transcode section
│               ├── section-filters.js    # NEW: V3 filtering section
│               ├── section-synthesis.js  # NEW: V5 synthesis section
│               ├── section-conditional.js# NEW: V4 conditional rules
│               ├── section-container.js  # NEW: V3 container section
│               ├── section-workflow.js   # NEW: V9 workflow section
│               └── accordion.js          # NEW: Accordion component
├── policy/
│   ├── editor.py               # PolicyRoundTripEditor (extend for V3-V10)
│   └── validation.py           # validate_policy_data (existing, no changes)

tests/
├── unit/
│   └── policy/
│       └── test_editor_v6_v10.py  # NEW: Tests for new schema fields
└── integration/
    └── server/
        └── test_policy_editor_api.py  # NEW: API integration tests
```

**Structure Decision**: Extending existing web application structure. New JavaScript modules follow existing pattern in `policy-editor/` directory. Each major schema feature gets its own section module.

## Complexity Tracking

No constitution violations requiring justification.

## Phase Completion Status

| Phase | Status | Output |
|-------|--------|--------|
| Phase 0: Research | COMPLETE | [research.md](./research.md) |
| Phase 1: Design | COMPLETE | [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md) |
| Phase 2: Tasks | COMPLETE | [tasks.md](./tasks.md) |
