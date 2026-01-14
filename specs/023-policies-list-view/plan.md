# Implementation Plan: Policies List View

**Branch**: `023-policies-list-view` | **Date**: 2025-11-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/023-policies-list-view/spec.md`

## Summary

Implement a Policies page that displays all policy files from `~/.vpo/policies/` with their metadata (name, description, schema version, language preferences, transcode/transcription indicators). The page will show the default policy prominently, handle invalid YAML gracefully, and provide a GET /api/policies endpoint for programmatic access.

## Technical Context

**Language/Version**: Python 3.10+ (existing codebase)
**Primary Dependencies**: aiohttp, Jinja2, aiohttp-jinja2, PyYAML (existing web stack + policy loader)
**Storage**: Filesystem (YAML files in ~/.vpo/policies/); no database changes
**Testing**: pytest (existing test infrastructure)
**Target Platform**: Linux server (existing daemon via `vpo serve`)
**Project Type**: Web application (server-rendered HTML + vanilla JavaScript)
**Performance Goals**: Page load within 2 seconds for up to 50 policy files
**Constraints**: Consistent with existing dashboard styling; no new frontend framework dependencies
**Scale/Scope**: Support up to 50 policy files without pagination

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ PASS | File modification times converted to UTC ISO-8601 |
| II. Stable Identity | ✅ PASS | Use filename as identifier (policies are file-based, not DB entities) |
| III. Portable Paths | ✅ PASS | Use `pathlib.Path` for all filesystem operations; `~` expansion handled |
| IV. Versioned Schemas | ✅ PASS | Reuse existing PolicySchema; display schema_version from each file |
| V. Idempotent Operations | ✅ PASS | Read-only display feature; no mutations |
| VI. IO Separation | ✅ PASS | Filesystem access encapsulated in policy discovery module |
| VII. Explicit Error Handling | ✅ PASS | Invalid YAML gracefully caught; parse_error field exposed |
| VIII. Structured Logging | ✅ PASS | Follow existing route logging patterns |
| IX. Configuration as Data | ✅ PASS | Policies directory is config; default_policy from profile config |
| X. Policy Stability | N/A | Display-only feature; does not modify policy format |
| XI. Plugin Isolation | N/A | No plugin interfaces involved |
| XII. Safe Concurrency | ✅ PASS | File reads are safe; no concurrent writes expected |
| XIII. Database Design | N/A | No database changes |
| XIV. Test Media Corpus | ✅ PASS | Create test fixtures with valid/invalid policy files |
| XV. Stable CLI/API Contracts | ✅ PASS | New `/api/policies` endpoint follows existing API patterns |
| XVI. Dry-Run Default | N/A | Read-only feature |
| XVII. Data Privacy | ✅ PASS | No external service calls; local data only |
| XVIII. Living Documentation | ✅ PASS | Update docs if needed |

**Result**: All applicable principles satisfied. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/023-policies-list-view/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── policies-api.yaml # OpenAPI spec for /api/policies
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/vpo/
├── policy/
│   └── discovery.py          # NEW: Policy file discovery and summary extraction
├── server/
│   ├── ui/
│   │   ├── models.py         # Add PolicyListItem, PolicyListResponse
│   │   ├── routes.py         # Add policies_handler(), policies_api_handler()
│   │   └── templates/
│   │       └── sections/
│   │           └── policies.html  # Update placeholder template
│   └── static/
│       └── css/
│           └── main.css      # Minor updates if needed for policy badges

tests/
├── unit/
│   └── policy/
│       └── test_discovery.py # NEW: Tests for policy discovery module
└── fixtures/
    └── policies/             # NEW: Test policy files (valid, invalid, various configs)
```

**Structure Decision**: Single project structure following existing VPO patterns. New code integrates into existing `policy/` and `server/ui/` modules.
