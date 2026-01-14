# Implementation Plan: Settings/About Panel for Web UI

**Branch**: `014-settings-about-panel` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-settings-about-panel/spec.md`

## Summary

Add an "About" page to the VPO Web UI that displays read-only application configuration including: API base URL, current profile (if any), application version/git hash, and documentation links. Integrates with the existing Web UI shell navigation from feature 013.

## Technical Context

**Language/Version**: Python 3.10+ (existing)
**Primary Dependencies**: aiohttp (existing), Jinja2 (existing), aiohttp_jinja2 (existing)
**Storage**: N/A (read-only display of runtime configuration)
**Testing**: pytest with aiohttp test client (existing patterns)
**Target Platform**: Linux/macOS (existing server)
**Project Type**: Web application (extends existing daemon server)
**Performance Goals**: Page load < 1 second (standard web performance)
**Constraints**: Read-only panel only; no editable settings for this version
**Scale/Scope**: Single new navigation item and page

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime storage |
| II. Stable Identity | N/A | No new entities with IDs |
| III. Portable Paths | PASS | Uses pathlib for any path operations |
| IV. Versioned Schemas | N/A | No schema changes |
| V. Idempotent Operations | PASS | Read-only display, inherently idempotent |
| VI. IO Separation | PASS | UI routes follow existing patterns |
| VII. Explicit Error Handling | PASS | Fallback values for missing data |
| VIII. Structured Logging | PASS | Uses existing request logging middleware |
| IX. Configuration as Data | PASS | Reads config, doesn't hardcode values |
| X. Policy Stability | N/A | No policy changes |
| XI. Plugin Isolation | N/A | No plugin interfaces |
| XII. Safe Concurrency | PASS | Read-only operations |
| XIII. Database Design | N/A | No database changes |
| XIV. Test Media Corpus | N/A | No media processing |
| XV. Stable CLI/API Contracts | PASS | New route follows existing patterns |
| XVI. Dry-Run Default | N/A | No destructive operations |
| XVII. Data Privacy | PASS | No external service calls |
| XVIII. Living Documentation | PASS | Linked docs from UI |

**Gate Result**: PASS - No violations, all applicable principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/014-settings-about-panel/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contract)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/vpo/
├── server/
│   ├── app.py           # Add /api/about endpoint
│   └── ui/
│       ├── models.py    # Add "About" to NAVIGATION_ITEMS
│       ├── routes.py    # Add about_handler route
│       └── templates/
│           └── sections/
│               └── about.html  # New template
```

```text
tests/
└── unit/
    └── server/
        └── ui/
            └── test_about_routes.py  # New tests
```

**Structure Decision**: Extends existing Web UI module structure. No new directories needed beyond the about.html template.

## Complexity Tracking

> No constitution violations to justify.

(Table intentionally empty - no complexity justifications needed)
