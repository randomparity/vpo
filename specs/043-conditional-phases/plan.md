# Implementation Plan: Conditional Phase Execution

**Branch**: `043-conditional-phases` | **Date**: 2025-12-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/043-conditional-phases/spec.md`

## Summary

Extend VPO's V12 phase system with conditional execution (`skip_when`), per-phase error handling (`on_error` override), phase dependencies (`depends_on`), and modification-based conditions (`run_if`). These additions enable intelligent workflow optimization where phases adapt to file characteristics and previous phase outcomes.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: Click (CLI), Pydantic (validation), ruamel.yaml (round-trip YAML)
**Storage**: SQLite (~/.vpo/library.db) - no schema changes required
**Testing**: pytest with existing fixtures
**Target Platform**: Linux, macOS (cross-platform via pathlib)
**Project Type**: Single project with CLI + web UI
**Performance Goals**: < 10ms skip condition evaluation per phase; < 1ms dependency resolution for 20 phases
**Constraints**: Circular dependency detection at policy load time; no disk I/O for skipped phases
**Scale/Scope**: Typical policies have 3-6 phases; support up to 20 phases with dependencies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ Pass | No new datetime handling required |
| II. Stable Identity | ✅ Pass | Phases identified by name within policy; no new UUIDs needed |
| III. Portable Paths | ✅ Pass | Existing pathlib patterns reused |
| IV. Versioned Schemas | ✅ Pass | Additive changes to V12 schema; no version bump required |
| V. Idempotent Operations | ✅ Pass | Skip conditions are deterministic; same input = same skip decision |
| VI. IO Separation | ✅ Pass | Skip evaluation is pure (no I/O); existing executor adapters unchanged |
| VII. Explicit Error Handling | ✅ Pass | per-phase on_error provides explicit error handling control |
| VIII. Structured Logging | ✅ Pass | FR-004, FR-013, FR-023 require logging skip reasons |
| IX. Configuration as Data | ✅ Pass | skip_when, depends_on, run_if defined in YAML policy |
| X. Policy Stability | ✅ Pass | Additive fields; existing policies continue to work unchanged |
| XI. Plugin Isolation | ✅ Pass | No plugin interface changes |
| XII. Safe Concurrency | ✅ Pass | Sequential phase execution; no parallel phase support |
| XIII. Database Design | ✅ Pass | No schema changes required |
| XIV. Test Media Corpus | ✅ Pass | Existing fixtures sufficient; add skip condition tests |
| XV. Stable CLI/API Contracts | ✅ Pass | Existing --phases flag enhanced with dependency warnings |
| XVI. Dry-Run Default | ✅ Pass | Existing --dry-run works with conditional phases |
| XVII. Data Privacy | ✅ Pass | No external services |
| XVIII. Living Documentation | ✅ Pass | Docs updated with new schema fields |

**Constitution Gate**: ✅ PASSED

## Project Structure

### Documentation (this feature)

```text
specs/043-conditional-phases/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.md           # Policy schema contract for new fields
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/vpo/
├── policy/
│   ├── loader.py        # MODIFY: Add skip_when, depends_on, run_if, on_error to PhaseModel
│   ├── models.py        # MODIFY: Add SkipCondition, PhaseOutcome, extend PhaseDefinition
│   └── skip_conditions.py    # NEW: Skip condition evaluation logic
├── workflow/
│   ├── v11_processor.py # MODIFY: Add dependency resolution, skip evaluation, outcome tracking
│   ├── dependency.py    # NEW: DependencyGraph for validation and resolution
│   └── phases/
│       └── executor.py  # MODIFY: Track phase outcomes, support per-phase on_error
├── cli/
│   └── process.py       # MODIFY: Add dependency warnings to --phases validation

tests/
├── unit/
│   ├── policy/
│   │   ├── test_skip_conditions.py    # NEW: Skip condition evaluation tests
│   │   └── test_dependency_graph.py   # NEW: Dependency validation tests
│   └── workflow/
│       └── test_conditional_phases.py # NEW: Integration tests for skip/depend
└── fixtures/
    └── policies/
        └── v12/
            └── conditional-phases/    # NEW: Test policy fixtures
```

**Structure Decision**: Single project structure maintained. New files added to existing modules following established patterns from 037-user-defined-phases.

## Complexity Tracking

No constitution violations requiring justification.

## Architecture Decisions

### AD-1: SkipCondition as Separate Dataclass

**Decision**: Create a dedicated `SkipCondition` dataclass to represent skip_when predicates, separate from existing condition evaluation.

**Rationale**:
- Skip conditions evaluate against file metadata before phase execution
- Existing conditional rules evaluate during phase execution with different context
- Separation prevents coupling and enables independent optimization

**Alternative Rejected**: Reuse existing condition evaluation system - different timing and context requirements.

### AD-2: PhaseOutcome Enum for Dependency Resolution

**Decision**: Track phase outcomes as an enum (`completed`, `failed`, `skipped`) stored in processor state during execution.

**Rationale**:
- Simple state machine: each phase transitions to one outcome
- Dependency resolution checks outcome of referenced phase
- No database persistence needed (runtime state only)

**Alternative Rejected**: Persist outcomes to database - unnecessary complexity for single-run state.

### AD-3: DependencyGraph for Validation

**Decision**: Build a directed graph at policy load time for circular dependency detection using standard topological sort.

**Rationale**:
- O(V+E) validation at load time (< 1ms for 20 phases)
- Clear error messages identifying the cycle
- Reusable for --phases filter validation

**Alternative Rejected**: Runtime dependency checking - too late, wastes processing time.

### AD-4: Skip Condition OR Semantics

**Decision**: Multiple conditions in `skip_when` combine with OR logic (any match causes skip).

**Rationale**:
- More intuitive: "skip if video is HEVC OR file is small"
- Users can express AND by using single conditions with arrays: `video_codec: [hevc, h265]`
- Consistent with existing filter behavior

**Alternative Rejected**: AND semantics - less useful, harder to express "skip if any of these is true".
