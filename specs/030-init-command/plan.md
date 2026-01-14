# Implementation Plan: VPO Init Command

**Branch**: `030-init-command` | **Date**: 2025-11-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/030-init-command/spec.md`

## Summary

Add a `vpo init` CLI command that creates the VPO data directory (`~/.vpo` by default), generates a well-documented `config.toml` with all available settings, creates `policies/` and `plugins/` subdirectories, and installs a default policy file (`policies/default.yaml`). The command protects existing configurations (requires `--force` to overwrite), supports custom data directories (`--data-dir`), and provides `--dry-run` preview functionality.

## Technical Context

**Language/Version**: Python 3.10+ (existing codebase)
**Primary Dependencies**: Click (CLI framework), PyYAML (policy files), tomllib/tomli (TOML parsing - read only, use string templates for writing)
**Storage**: Filesystem only (no database interaction for init)
**Testing**: pytest (existing test infrastructure)
**Target Platform**: Linux and macOS (per constitution III)
**Project Type**: Single project - extends existing CLI
**Performance Goals**: <30 seconds initialization (per SC-001), <2 seconds for already-initialized check (per SC-004)
**Constraints**: Must not require external tools (ffmpeg, mkvmerge) to be installed
**Scale/Scope**: Single-user CLI command; creates ~5 files/directories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applicable | Compliance | Notes |
|-----------|------------|------------|-------|
| I. Datetime Integrity | No | N/A | No datetime storage in init |
| II. Stable Identity | No | N/A | No entity IDs created |
| III. Portable Paths | **Yes** | COMPLIANT | Use `pathlib.Path`, support Linux/macOS |
| IV. Versioned Schemas | **Yes** | COMPLIANT | config.toml structure follows existing VPOConfig model |
| V. Idempotent Operations | **Yes** | COMPLIANT | Safe to re-run (detects existing, requires --force) |
| VI. IO Separation | **Yes** | COMPLIANT | Pure init logic separate from filesystem operations |
| VII. Explicit Error Handling | **Yes** | COMPLIANT | Clear errors for permission, disk space, conflicts |
| VIII. Structured Logging | **Yes** | COMPLIANT | Log init operations for auditability |
| IX. Configuration as Data | **Yes** | COMPLIANT | Generated config is data, not hardcoded |
| X. Policy Stability | **Yes** | COMPLIANT | Default policy uses existing schema_version: 1 |
| XI. Plugin Isolation | No | N/A | No plugin interface changes |
| XII. Safe Concurrency | No | N/A | Single-threaded CLI operation |
| XIII. Database Design | No | N/A | No database interaction |
| XIV. Test Media Corpus | No | N/A | No media processing |
| XV. Stable CLI/API Contracts | **Yes** | COMPLIANT | New command, consistent flag naming (--dry-run, --force) |
| XVI. Dry-Run Default | **Yes** | COMPLIANT | Supports --dry-run flag per spec |
| XVII. Data Privacy | No | N/A | No external service calls |
| XVIII. Living Documentation | **Yes** | COMPLIANT | Will update docs with init usage |

**Gate Status**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/030-init-command/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no API)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── cli/
│   ├── __init__.py      # Register init_command
│   └── init.py          # NEW: Init command implementation
├── config/
│   ├── models.py        # Existing VPOConfig (reference for template)
│   ├── loader.py        # Existing loader (reference for defaults)
│   └── templates.py     # NEW: Config/policy template generation
└── ...

tests/
├── unit/
│   ├── cli/
│   │   └── test_init.py # NEW: Unit tests for init command
│   └── config/
│       └── test_templates.py # NEW: Unit tests for templates module
└── integration/
    └── test_init_integration.py  # NEW: Integration tests
```

**Structure Decision**: Extends existing single-project structure. New CLI command in `cli/init.py`, template generation logic in `config/templates.py` to keep config-related code together.

## Complexity Tracking

> No violations requiring justification - all constitution checks pass.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
