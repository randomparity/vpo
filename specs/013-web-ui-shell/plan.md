# Implementation Plan: Web UI Shell with Global Navigation

**Branch**: `013-web-ui-shell` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-web-ui-shell/spec.md`

## Summary

Implement a Web UI shell with persistent navigation that allows operators to navigate between Jobs, Library, Transcriptions, Policies, and Approvals sections. The UI will be a server-rendered HTML application served by the existing aiohttp daemon server from feature 012, with client-side navigation enhancement for a responsive user experience. Each section will initially display placeholder content that will be replaced by full implementations in future features.

## Technical Context

**Language/Version**: Python 3.10+ (server), HTML5/CSS3/JavaScript (client)
**Primary Dependencies**: aiohttp (existing server), Jinja2 (templating)
**Storage**: N/A (no new storage required for shell - static UI served via daemon)
**Testing**: pytest + aiohttp test client, browser testing for responsive behavior
**Target Platform**: Linux server (daemon), modern browsers (Chrome, Firefox, Safari, Edge)
**Project Type**: Web application (extending existing daemon server)
**Performance Goals**: <1 second page load, instant navigation response
**Constraints**: 768px minimum viewport width, no JavaScript frameworks (minimal vanilla JS)
**Scale/Scope**: 5 navigation sections, single operator concurrent use

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime handling in UI shell |
| II. Stable Identity | N/A | No data entities in UI shell |
| III. Portable Paths | ✅ Pass | Using pathlib for static file serving |
| IV. Versioned Schemas | N/A | No schema changes required |
| V. Idempotent Operations | ✅ Pass | UI rendering is stateless/idempotent |
| VI. IO Separation | ✅ Pass | UI layer is presentation-only |
| VII. Explicit Error Handling | ✅ Pass | 404 handling for unknown routes |
| VIII. Structured Logging | ✅ Pass | Use existing logging framework for requests |
| IX. Configuration as Data | ✅ Pass | No hardcoded paths; serve from config |
| X. Policy Stability | N/A | No policy changes |
| XI. Plugin Isolation | N/A | No plugin interfaces |
| XII. Safe Concurrency | ✅ Pass | aiohttp handles concurrency |
| XIII. Database Design | N/A | No database changes |
| XIV. Test Media Corpus | N/A | No media processing |
| XV. Stable CLI/API Contracts | ✅ Pass | Extends existing server routes |
| XVI. Dry-Run Default | N/A | Read-only UI |
| XVII. Data Privacy | ✅ Pass | No external service calls |
| XVIII. Living Documentation | ✅ Pass | Update docs with UI usage |

**Gate Result**: PASS - No constitution violations

## Project Structure

### Documentation (this feature)

```text
specs/013-web-ui-shell/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (routes)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/vpo/
├── server/
│   ├── app.py           # [MODIFY] Add UI routes
│   ├── ui/              # [NEW] UI module
│   │   ├── __init__.py
│   │   ├── routes.py    # UI route handlers
│   │   └── templates/   # Jinja2 templates
│   │       ├── base.html        # Base layout with nav
│   │       ├── sections/        # Section templates
│   │       │   ├── jobs.html
│   │       │   ├── library.html
│   │       │   ├── transcriptions.html
│   │       │   ├── policies.html
│   │       │   └── approvals.html
│   │       └── errors/
│   │           └── 404.html
│   └── static/          # [NEW] Static assets
│       ├── css/
│       │   └── main.css
│       └── js/
│           └── nav.js   # Navigation enhancement

tests/
├── unit/
│   └── server/
│       └── test_ui_routes.py
└── integration/
    └── test_web_ui.py
```

**Structure Decision**: Extending the existing daemon server structure with a new `ui` submodule under `server/`. Static assets and templates are co-located with the UI code for cohesion.

## Complexity Tracking

> No constitution violations - table not required.
