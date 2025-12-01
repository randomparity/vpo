# Implementation Plan: User-Defined Processing Phases

**Branch**: `037-user-defined-phases` | **Date**: 2025-11-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/037-user-defined-phases/spec.md`

## Summary

Replace VPO's hardcoded three-phase workflow system (ANALYZE, APPLY, TRANSCODE) with a flexible, user-defined phase system. Users define named phases in V11 policy files and specify which operations run in each phase, enabling single-command processing of complex media normalization workflows.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: Click (CLI), Pydantic (validation), ruamel.yaml (round-trip YAML), aiohttp (web UI)
**Storage**: SQLite (~/.vpo/library.db)
**Testing**: pytest with fixtures for media files
**Target Platform**: Linux, macOS (cross-platform via pathlib)
**Project Type**: Single project with CLI + web UI
**Performance Goals**: < 100ms phase dispatch overhead for 10 phases; < 1s policy validation for 20 phases
**Constraints**: No backward compatibility with V1-V10 flat schema; atomic rollback on mid-phase failure
**Scale/Scope**: Typical policies have 3-6 phases; support up to 20 phases

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ Pass | No new datetime handling required |
| II. Stable Identity | ✅ Pass | Phases identified by name within policy; no new UUIDs needed |
| III. Portable Paths | ✅ Pass | Existing pathlib patterns reused |
| IV. Versioned Schemas | ✅ Pass | Schema version 11 with explicit migration path (no V10 compat) |
| V. Idempotent Operations | ✅ Pass | Phase execution remains idempotent; rollback on failure |
| VI. IO Separation | ✅ Pass | Phases orchestrate executors; pure evaluation logic |
| VII. Explicit Error Handling | ✅ Pass | on_error modes + phase-level rollback defined in spec |
| VIII. Structured Logging | ✅ Pass | FR-008 requires phase/operation logging |
| IX. Configuration as Data | ✅ Pass | Phases defined in YAML policy, not code |
| X. Policy Stability | ⚠️ Note | Breaking change: V11 required. No V10 migration (per spec) |
| XI. Plugin Isolation | ✅ Pass | No plugin interface changes; phases are internal |
| XII. Safe Concurrency | ✅ Pass | Sequential phase execution; no parallel phase support |
| XIII. Database Design | ✅ Pass | No schema changes required |
| XIV. Test Media Corpus | ✅ Pass | Existing fixtures sufficient; add phase-specific tests |
| XV. Stable CLI/API Contracts | ✅ Pass | `vpo process` already exists; add `--phases` filter |
| XVI. Dry-Run Default | ✅ Pass | Existing `--dry-run` flag works with phases |
| XVII. Data Privacy | ✅ Pass | No new external services |
| XVIII. Living Documentation | ✅ Pass | Docs updated with new schema examples |

**Constitution Gate**: ✅ PASSED (Principle X noted but justified by spec requirement FR-011)

## Project Structure

### Documentation (this feature)

```text
specs/037-user-defined-phases/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.md           # API contract for policy schema
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── policy/
│   ├── loader.py        # MODIFY: V11 schema validation, phases array
│   ├── models.py        # MODIFY: Phase, GlobalConfig, V11PolicySchema dataclasses
│   └── editor.py        # MODIFY: Phase GUI support in round-trip editor
├── workflow/
│   ├── processor.py     # MODIFY: Dynamic phase dispatch, rollback logic
│   └── phases/
│       ├── base.py      # NEW: BasePhase protocol/abstract class
│       └── composite.py # NEW: CompositePhase (multiple operations per phase)
├── cli/
│   └── process.py       # MODIFY: --phases filter for named phases
└── server/
    ├── ui/
    │   ├── routes.py    # MODIFY: Phase editor endpoints
    │   └── templates/
    │       └── sections/
    │           └── policy_editor.html  # MODIFY: Phase GUI components
    └── static/
        └── js/
            └── policy-editor/
                └── section-phases.js   # NEW: Phase editor JavaScript

tests/
├── unit/
│   └── policy/
│       ├── test_v11_loader.py    # NEW: V11 schema validation tests
│       └── test_phase_models.py  # NEW: Phase dataclass tests
├── integration/
│   └── workflow/
│       └── test_phase_execution.py  # NEW: Multi-phase workflow tests
└── fixtures/
    └── policies/
        └── v11/                  # NEW: V11 policy fixtures
```

**Structure Decision**: Single project structure maintained. New files added to existing modules following established patterns.

## Complexity Tracking

No constitution violations requiring justification.

## Architecture Decisions

### AD-1: Phase as Operation Container

**Decision**: A Phase is a named container that holds zero or more operations. Operations execute in a predefined order within each phase.

**Rationale**:
- Simpler than a plugin system (no dynamic discovery)
- Reuses existing operation implementations
- Phase names are user-defined; operation types are fixed

**Alternative Rejected**: Phase plugin system with custom code - too complex for V11 scope.

### AD-2: Rollback via Backup Files

**Decision**: Mid-phase rollback uses existing backup mechanism (`.vpo.bak` files). Each phase operates on a backup, committed only on success.

**Rationale**:
- Existing `restore_from_backup()` already implemented
- Atomic: backup → modify → cleanup/restore pattern proven
- No database state to rollback (operations are file-based)

**Alternative Rejected**: Transaction log with undo operations - higher complexity, more failure modes.

### AD-3: Remove ProcessingPhase Enum

**Decision**: Replace `ProcessingPhase` enum with string-based phase names validated against policy.

**Rationale**:
- User-defined names can't be enumerated
- Validation moves to policy loader
- Existing ANALYZE/APPLY/TRANSCODE become example phase names, not special cases

**Alternative Rejected**: Keep enum + registry for custom phases - unnecessary abstraction.
