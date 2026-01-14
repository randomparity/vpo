# Implementation Plan: Web UI Authentication

**Branch**: `029-webui-auth` | **Date**: 2025-11-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/029-webui-auth/spec.md`

## Summary

Implement minimal HTTP Basic Authentication for the VPO Web UI and API endpoints. The auth token is configurable via environment variable (`VPO_AUTH_TOKEN`) with precedence over config file (`server.auth_token`). When configured, all endpoints except `/health` require valid credentials. When not configured, the server operates in backward-compatible open access mode with a startup warning.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: aiohttp (existing), secrets (stdlib for constant-time compare)
**Storage**: N/A (token from config/env, no persistence)
**Testing**: pytest with aiohttp test client
**Target Platform**: Linux, macOS (server daemon)
**Project Type**: Single project with web server component
**Performance Goals**: <100ms added latency (negligible for middleware)
**Constraints**: Middleware must not block event loop; constant-time token comparison
**Scale/Scope**: Single shared token; single-user/operator access model

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime handling in this feature |
| II. Stable Identity | N/A | No entity identity changes |
| III. Portable Paths | PASS | No path handling in auth middleware |
| IV. Versioned Schemas | PASS | ServerConfig dataclass extended (backward compatible) |
| V. Idempotent Operations | PASS | Auth check is stateless, safe to repeat |
| VI. IO Separation | PASS | Auth middleware is pure check; config loaded via existing loader |
| VII. Explicit Error Handling | PASS | 401 response with WWW-Authenticate header |
| VIII. Structured Logging | PASS | Warning on no-auth mode at startup |
| IX. Configuration as Data | PASS | Token from env var or config file, never in code |
| X. Policy Stability | N/A | No policy schema changes |
| XI. Plugin Isolation | N/A | No plugin interface changes |
| XII. Safe Concurrency | PASS | Stateless middleware, no shared mutable state |
| XIII. Database Design | N/A | No database changes |
| XIV. Test Media Corpus | N/A | No media processing |
| XV. Stable CLI/API Contracts | PASS | No CLI changes; API behavior unchanged when auth disabled |
| XVI. Dry-Run Default | N/A | No destructive operations |
| XVII. Data Privacy | PASS | Token not logged; standard access logs only |
| XVIII. Living Documentation | PASS | Will document in usage guide |

**Gate Result**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/029-webui-auth/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.md           # Auth-related API contract changes
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── config/
│   ├── models.py        # MODIFY: Add auth_token to ServerConfig
│   └── loader.py        # MODIFY: Add VPO_AUTH_TOKEN env var handling
├── server/
│   ├── app.py           # MODIFY: Add auth middleware
│   └── auth.py          # NEW: Auth middleware and helpers
└── ...

tests/
├── unit/
│   └── server/
│       └── test_auth.py # NEW: Auth middleware unit tests
└── integration/
    └── server/
        └── test_auth_integration.py  # NEW: End-to-end auth tests
```

**Structure Decision**: Extends existing single-project structure. Auth logic isolated in new `server/auth.py` module; configuration extended in existing config modules.

## Complexity Tracking

> No violations requiring justification - feature is minimal and follows existing patterns.
