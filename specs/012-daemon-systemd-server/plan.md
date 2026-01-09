# Implementation Plan: Daemon Mode & Systemd-Friendly Server

**Branch**: `012-daemon-systemd-server` | **Date**: 2025-11-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-daemon-systemd-server/spec.md`

## Summary

Add a `vpo serve` daemon mode command that runs VPO as a long-lived background service suitable for systemd management. The daemon will provide a health-check HTTP endpoint, use the existing centralized logging system (with JSON format support), handle graceful shutdown on SIGTERM/SIGINT, and load configuration from the existing `~/.vpo/config.toml` file with CLI flag overrides.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml requires-python = ">=3.10")
**Primary Dependencies**: click (>=8.0, existing), pydantic (>=2.10, existing), aiohttp (new - lightweight async HTTP server)
**Storage**: SQLite (~/.vpo/library.db, existing schema v7)
**Testing**: pytest (>=9.0.1, existing)
**Target Platform**: Linux (systemd), macOS (launchd compatible but not primary target)
**Project Type**: Single project (existing CLI application)
**Performance Goals**: Health endpoint <100ms response time (per FR-030)
**Constraints**: Graceful shutdown within 30 seconds (configurable), no interactive prompts in daemon mode
**Scale/Scope**: Single-instance daemon per host, suitable for personal/small-team media library management

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | Timestamps in logs use ISO-8601 UTC (existing pattern) |
| II. Stable Identity | PASS | No new identity requirements; uses existing file/track IDs |
| III. Portable Paths | PASS | Uses pathlib.Path throughout (existing pattern) |
| IV. Versioned Schemas | PASS | No schema changes required; uses existing schema v7 |
| V. Idempotent Operations | PASS | Daemon startup/shutdown are idempotent |
| VI. IO Separation | PASS | Server logic isolated in new `server/` module |
| VII. Explicit Error Handling | PASS | Startup failures logged and exit with non-zero code |
| VIII. Structured Logging | PASS | Extends existing logging/ module with daemon context |
| IX. Configuration as Data | PASS | Extends existing config.toml with server section |
| X. Policy Stability | N/A | No policy format changes |
| XI. Plugin Isolation | N/A | No plugin interface changes |
| XII. Safe Concurrency | PASS | Uses asyncio event loop; explicit shutdown coordination |
| XIII. Database Design | PASS | Uses existing connection patterns; read-only health check |
| XIV. Test Media Corpus | N/A | No media processing changes |
| XV. Stable CLI/API Contracts | PASS | New `vpo serve` command follows existing CLI patterns |
| XVI. Dry-Run Default | N/A | Daemon is non-destructive (observes, doesn't modify) |
| XVII. Data Privacy | PASS | No external service calls; localhost-only by default |
| XVIII. Living Documentation | PASS | Includes systemd unit file and daemon-mode.md docs |

**Gate Result**: PASS - All applicable principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/012-daemon-systemd-server/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI spec for health endpoint)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── cli/
│   ├── __init__.py      # Add serve command registration
│   └── serve.py         # NEW: vpo serve command implementation
├── config/
│   ├── models.py        # Extend with ServerConfig dataclass
│   └── loader.py        # Add server config loading
├── logging/
│   └── config.py        # Minor: ensure daemon-friendly defaults
├── server/              # NEW: Daemon server module
│   ├── __init__.py
│   ├── app.py           # HTTP application (health endpoint)
│   ├── lifecycle.py     # Startup/shutdown coordination
│   └── signals.py       # Signal handler registration
└── db/
    └── connection.py    # Minor: add health check query helper

tests/
├── unit/
│   └── server/          # NEW: Unit tests for server module
│       ├── test_lifecycle.py
│       └── test_signals.py
└── integration/
    └── test_serve_command.py  # NEW: Integration tests for daemon

docs/
├── systemd/
│   └── vpo.service      # NEW: Example systemd unit file
└── daemon-mode.md       # NEW: Daemon mode documentation
```

**Structure Decision**: Extends existing single-project structure with new `server/` module. Follows existing patterns for CLI commands (`cli/serve.py`) and configuration extension (`config/models.py`).

## Complexity Tracking

> No violations requiring justification. Design follows existing patterns.

| Area | Decision | Rationale |
|------|----------|-----------|
| HTTP Framework | aiohttp | Lightweight, async-native, no heavy framework overhead |
| Event Loop | asyncio | Standard library, matches aiohttp, good signal handling |
| Config Extension | Add ServerConfig to existing models.py | Follows existing pattern, single config source |

## Post-Design Constitution Re-Check

*Re-evaluation after Phase 1 design artifacts completed.*

| Principle | Status | Design Artifact Reference |
|-----------|--------|---------------------------|
| I. Datetime Integrity | PASS | `ShutdownState.initiated` uses `datetime` with UTC (data-model.md) |
| VI. IO Separation | PASS | `server/` module isolates HTTP/async from core logic |
| VIII. Structured Logging | PASS | JSON logging supported via existing handlers (research.md) |
| XII. Safe Concurrency | PASS | `asyncio.Event` for shutdown coordination (research.md) |
| XIII. Database Design | PASS | Read-only `SELECT 1` for health check (research.md) |
| XV. Stable CLI/API Contracts | PASS | OpenAPI spec defines health endpoint contract (contracts/openapi.yaml) |
| XVIII. Living Documentation | PASS | quickstart.md, daemon-mode.md planned |

**Post-Design Gate Result**: PASS - Design artifacts comply with constitution.

## Generated Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Research | `specs/012-daemon-systemd-server/research.md` | Technology decisions and patterns |
| Data Model | `specs/012-daemon-systemd-server/data-model.md` | Configuration and runtime state models |
| API Contract | `specs/012-daemon-systemd-server/contracts/openapi.yaml` | Health endpoint OpenAPI spec |
| Quickstart | `specs/012-daemon-systemd-server/quickstart.md` | Implementation guide |

## Next Steps

Run `/speckit.tasks` to generate the implementation task list.
