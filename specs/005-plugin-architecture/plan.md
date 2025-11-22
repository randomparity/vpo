# Implementation Plan: Plugin Architecture & Extension Model

**Branch**: `005-plugin-architecture` | **Date**: 2025-11-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-plugin-architecture/spec.md`

## Summary

Introduce a plugin system for VPO enabling policies and actions to be developed independently from the core application. The architecture defines two plugin types (AnalyzerPlugin for read-only inspection, MutatorPlugin for modifications), supports dual discovery mechanisms (directory-based and Python entry points), and refactors the existing policy engine as a reference built-in plugin. Plugins self-register for events they want to handle.

## Technical Context

**Language/Version**: Python 3.10+ (matching existing codebase)
**Primary Dependencies**: click (CLI), pydantic (validation), PyYAML (config), importlib.metadata (entry points)
**Storage**: SQLite (~/.vpo/library.db for plugin acknowledgment records)
**Testing**: pytest (existing test infrastructure)
**Target Platform**: Linux, macOS (per Constitution III)
**Project Type**: Single project extension (CLI tool)
**Performance Goals**: Plugin discovery < 1 second for 50 plugins (SC-001)
**Constraints**: No hot-reload (app restart required), no sandboxing, offline operation
**Scale/Scope**: Support ~50 plugins typical, 100+ max

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ PASS | Plugin acknowledgment timestamps stored as UTC |
| II. Stable Identity | ✅ PASS | Plugins identified by name+version, not file path |
| III. Portable Paths | ✅ PASS | Use pathlib.Path for plugin directories |
| IV. Versioned Schemas | ✅ PASS | Plugin API versioned with semver, manifest schema versioned |
| V. Idempotent Operations | ✅ PASS | Plugin discovery is idempotent (same result each run) |
| VI. IO Separation | ✅ PASS | Plugin interfaces are pure protocols; I/O in implementations |
| VII. Explicit Error Handling | ✅ PASS | FR-007/FR-018 require graceful handling without crashes |
| VIII. Structured Logging | ✅ PASS | FR-008 requires logging of discovery/loading/errors |
| IX. Configuration as Data | ✅ PASS | Plugin directories configurable, not hardcoded |
| X. Policy Stability | ✅ PASS | Plugin API version documented, backward compatibility required |
| XI. Plugin Isolation | ✅ PASS | This feature implements plugin isolation principle |
| XII. Safe Concurrency | ✅ PASS | Plugin loading is single-threaded; execution isolation per FR-018 |
| XIII. Database Design | ✅ PASS | Acknowledgment records in normalized table with FK |
| XIV. Test Media Corpus | N/A | Plugin system doesn't directly process media |
| XV. Stable CLI/API Contracts | ✅ PASS | `vpo plugins list` follows existing CLI patterns |
| XVI. Dry-Run Default | N/A | Plugin loading doesn't modify media |
| XVII. Data Privacy | ✅ PASS | No external service calls in plugin system |
| XVIII. Living Documentation | ✅ PASS | FR-016 requires docs/plugins.md |

**Gate Result**: PASS - All applicable principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/005-plugin-architecture/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (plugin interfaces)
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── plugin/                      # NEW: Plugin system core
│   ├── __init__.py             # Public exports
│   ├── interfaces.py           # AnalyzerPlugin, MutatorPlugin protocols
│   ├── registry.py             # PluginRegistry discovery/management
│   ├── loader.py               # Plugin loading and validation
│   ├── events.py               # Event system for plugin registration
│   ├── manifest.py             # PluginManifest model and parsing
│   └── version.py              # API version checking
├── plugin_sdk/                  # NEW: Plugin SDK package
│   ├── __init__.py             # Public SDK exports
│   ├── base.py                 # BaseAnalyzerPlugin, BaseMutatorPlugin
│   ├── helpers.py              # Utility functions for plugin authors
│   └── testing.py              # Test utilities for plugin development
├── plugins/                     # NEW: Built-in plugins
│   └── policy_engine/          # Refactored policy engine as plugin
│       ├── __init__.py
│       └── plugin.py           # PolicyEnginePlugin implementation
├── cli/
│   └── plugins.py              # NEW: `vpo plugins list` command
├── db/
│   └── schema.py               # Extended: plugin_acknowledgments table
└── config/
    └── models.py               # Extended: plugin directory config

examples/plugins/
└── simple_reorder_plugin/      # NEW: Example plugin project
    ├── pyproject.toml
    ├── README.md
    └── src/
        └── simple_reorder/
            └── __init__.py

docs/
└── plugins.md                  # NEW: Plugin development guide

tests/
├── unit/
│   └── plugin/                 # NEW: Plugin system unit tests
│       ├── test_version.py
│       ├── test_registry.py
│       ├── test_loader.py
│       ├── test_sdk.py
│       └── test_policy_plugin.py
├── integration/
│   └── test_plugin_discovery.py  # NEW: E2E plugin discovery tests
└── contract/
    └── test_plugin_contracts.py  # NEW: Plugin interface contract tests
```

**Structure Decision**: Extends existing single-project structure with new `plugin/` and `plugin_sdk/` packages. Built-in plugins live in `plugins/` subdirectory. Example plugins in `examples/plugins/` (outside main package).

## Complexity Tracking

> No Constitution violations requiring justification.

| Component | Complexity | Justification |
|-----------|------------|---------------|
| Dual discovery (dir + entry points) | Medium | Both mechanisms are standard Python patterns; entry points for pip packages, directory for development/testing |
| Event-based registration | Medium | More flexible than fixed hooks; plugins declare capabilities |
| User acknowledgment for directory plugins | Low | Simple SQLite table + CLI prompt; required per FR-008a |
