# Implementation Plan: Policy Engine & Reordering (Dry-Run & Metadata-Only)

**Branch**: `004-policy-engine` | **Date**: 2025-11-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-policy-engine/spec.md`

## Summary

Implement a policy engine that evaluates user-defined YAML policies against media track metadata and produces execution plans for metadata-only operations (track reordering, default flag changes, title updates). The engine follows a pure-function evaluation architecture with dry-run preview capability. MKV containers support full track reordering via mkvpropedit; non-MKV formats support only flag/title modifications via ffmpeg. All operations are logged to SQLite for audit purposes with configurable backup retention.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml)
**Primary Dependencies**: click (CLI), PyYAML (policy parsing), subprocess (mkvpropedit/ffmpeg invocation), sqlite3 (stdlib)
**Storage**: SQLite (~/.vpo/library.db) - existing schema extended for operation records
**Testing**: pytest with YAML policy fixtures and mock track data
**Target Platform**: Linux, macOS (mkvpropedit/ffmpeg must be installed)
**Project Type**: Single project (CLI tool with library)
**Performance Goals**: Dry-run preview within 2 seconds (SC-001); metadata operations within 5 seconds for files up to 50GB (SC-002)
**Constraints**: mkvpropedit required for MKV track reordering; ffmpeg for non-MKV metadata; graceful degradation if tools missing
**Scale/Scope**: Single-file operations; single-user local libraries

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | OperationRecord timestamps stored as UTC ISO-8601 |
| II. Stable Identity | PASS | Tracks/files referenced by existing UUID/hash IDs from 003 |
| III. Portable Paths | PASS | Use pathlib.Path; backup suffix `.vpo-backup` is cross-platform |
| IV. Versioned Schemas | PASS | Policy schema versioned; migration path required for changes |
| V. Idempotent Operations | PASS | Core requirement (FR-008); same policy twice = same result |
| VI. IO Separation | PASS | Pure evaluation function (FR-007) separate from mkvpropedit/ffmpeg adapters |
| VII. Explicit Error Handling | PASS | Backup/restore on failure (FR-013); clear error types |
| VIII. Structured Logging | PASS | Operation records include media ID, policy ID, actions (FR-012) |
| IX. Configuration as Data | PASS | Policies are YAML data files, not code |
| X. Policy Stability | PASS | Policy schema versioned; backward compatibility required |
| XI. Plugin Isolation | N/A | No plugins in this feature |
| XII. Safe Concurrency | PASS | File locking during modification (FR-015) |
| XIII. Database Design | PASS | OperationRecord via repository pattern; no inline SQL |
| XIV. Test Media Corpus | PASS | Will use fixtures from 003; add policy-specific test cases |
| XV. Stable CLI/API Contracts | PASS | Uses standard flags: `--policy`, `--dry-run` |
| XVI. Dry-Run Default | PASS | Explicit `--dry-run` flag; non-destructive preview available |
| XVII. Data Privacy | PASS | No external services; local-only operations |
| XVIII. Living Documentation | PASS | quickstart.md and policy examples included |

**Gate Result**: PASS - All applicable principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/004-policy-engine/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI interface spec, policy schema)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── policy/                      # NEW: Policy engine module
│   ├── __init__.py
│   ├── loader.py                # Policy file loading and validation
│   ├── models.py                # Policy, Plan, PlannedAction dataclasses
│   ├── evaluator.py             # Pure evaluation function
│   └── matchers.py              # Commentary pattern matching (regex)
├── executor/                    # NEW: Execution layer module
│   ├── __init__.py
│   ├── interface.py             # Executor protocol
│   ├── mkvpropedit.py           # MKV metadata/reorder adapter
│   ├── ffmpeg_metadata.py       # Non-MKV metadata adapter
│   └── backup.py                # Backup/restore utilities
├── db/
│   ├── models.py                # EXTEND: OperationRecord dataclass
│   └── schema.py                # EXTEND: operations table
└── cli/
    ├── __init__.py              # EXTEND: register apply command
    └── apply.py                 # NEW: vpo apply command

tests/
├── fixtures/
│   └── policies/                # NEW: Sample policy YAML files
│       ├── track_order_basic.yaml
│       ├── audio_preference.yaml
│       └── commentary_detection.yaml
├── unit/
│   ├── test_policy_loader.py    # NEW
│   ├── test_evaluator.py        # NEW
│   └── test_matchers.py         # NEW
└── integration/
    └── test_apply_command.py    # NEW
```

**Structure Decision**: Extends existing single-project structure. Adds `policy/` module for evaluation logic (pure functions) and `executor/` module for IO operations (tool adapters). Follows IO Separation principle (VI).

## Complexity Tracking

No constitution violations to justify. Design follows established patterns from prior features.
