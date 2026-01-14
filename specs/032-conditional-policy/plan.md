# Implementation Plan: Conditional Policy Logic

**Branch**: `032-conditional-policy` | **Date**: 2025-11-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/032-conditional-policy/spec.md`

## Summary

This feature adds conditional if/then/else rules to VPO policies, enabling smart decisions based on file track analysis. Users can apply different actions based on track existence, count, codec, resolution, and other properties. The implementation extends the existing policy schema (v3→v4) with a new `conditional` section containing rules that are evaluated before non-conditional policy sections.

**Key Technical Approach:**
- Extend PolicySchema with `conditional_rules: tuple[ConditionalRule, ...]`
- Implement recursive condition evaluator supporting `exists`, `count`, `and`, `or`, `not`, and comparison operators
- Integrate conditional evaluation into Plan generation, executed before track filtering
- Add skip flags, warn, and fail actions with placeholder substitution

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: Pydantic (validation), dataclasses (domain models), PyYAML (policy loading)
**Storage**: N/A (extends in-memory policy evaluation)
**Testing**: pytest with existing test infrastructure
**Target Platform**: Linux, macOS (CLI tool)
**Project Type**: Single Python package with Rust extension
**Performance Goals**: Policy load+validate <1 second, condition evaluation <10ms per file
**Constraints**: Max 3 levels boolean nesting, first-match-wins semantics
**Scale/Scope**: Policies with up to 20 conditional rules, files with up to 50 tracks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime handling in this feature |
| II. Stable Identity | PASS | Conditions reference track indices/properties, not paths |
| III. Portable Paths | PASS | Only processes in-memory track data |
| IV. Versioned Schemas | PASS | Incrementing schema to v4, Pydantic validation extended |
| V. Idempotent Operations | PASS | Condition evaluation is pure; same input = same output |
| VI. IO Separation | PASS | Conditions evaluated in pure functions on in-memory models |
| VII. Explicit Error Handling | PASS | PolicyValidationError for invalid syntax, fail action for runtime errors |
| VIII. Structured Logging | PASS | Dry-run output shows rule matching with reasons |
| IX. Configuration as Data | PASS | Conditional rules are policy data, not code |
| X. Policy Stability | PASS | New section is additive; existing policies work unchanged |
| XI. Plugin Isolation | N/A | No plugin interfaces affected |
| XII. Safe Concurrency | PASS | Evaluation is pure function, no shared state |
| XIII. Database Design | N/A | No database changes |
| XIV. Test Media Corpus | PASS | Will add test policies with conditional rules |
| XV. Stable CLI/API Contracts | PASS | No CLI changes; extends existing --dry-run output |
| XVI. Dry-Run Default | PASS | Conditional evaluation fully visible in dry-run |
| XVII. Data Privacy | PASS | No external service calls |
| XVIII. Living Documentation | PASS | Policy schema docs updated with v4 conditional section |

**Gate Status**: PASS - All applicable principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/032-conditional-policy/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (internal contracts)
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
src/vpo/
├── policy/
│   ├── models.py           # MODIFY: Add ConditionalRule, Condition types
│   ├── loader.py           # MODIFY: Update MAX_SCHEMA_VERSION to 4
│   ├── validation.py       # MODIFY: Add Pydantic models for conditional syntax
│   ├── evaluator.py        # MODIFY: Add evaluate_conditions() before track filtering
│   ├── conditions.py       # NEW: Condition evaluation logic (exists, count, operators)
│   └── actions.py          # NEW: Conditional action handlers (skip, warn, fail)
├── executor/
│   └── interface.py        # MODIFY: Handle skip flags from Plan

tests/
├── unit/
│   └── policy/
│       ├── test_conditions.py      # NEW: Unit tests for condition evaluation
│       ├── test_conditional_rules.py # NEW: Unit tests for rule matching
│       └── test_conditional_actions.py # NEW: Unit tests for warn/fail/skip
├── integration/
│   └── test_conditional_policy.py  # NEW: End-to-end conditional policy tests

docs/
├── usage/
│   └── conditional-policies.md     # NEW: User guide for conditional rules
└── decisions/
    └── ADR-0005-conditional-policy-schema.md  # NEW: Schema v4 design decision
```

**Structure Decision**: Single project structure, extending existing `policy/` module with new submodules for conditions and actions. Maintains separation between validation (Pydantic), domain models (dataclasses), and evaluation (pure functions).

## Complexity Tracking

No constitution violations to justify. Design follows existing patterns.

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design completion.*

| Principle | Post-Design Status | Design Artifact |
|-----------|-------------------|-----------------|
| IV. Versioned Schemas | PASS | `data-model.md` defines v3→v4 migration, backward compatible |
| V. Idempotent Operations | PASS | `contracts/condition-evaluator.md` specifies pure functions |
| VI. IO Separation | PASS | `contracts/` define clear interfaces, no I/O in condition evaluation |
| VII. Explicit Error Handling | PASS | `ConditionalFailError`, `PolicyValidationError` defined |
| X. Policy Stability | PASS | Existing v3 policies unchanged, new section additive |

**Post-Design Gate Status**: PASS - Design artifacts align with constitution principles.

## Generated Artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Research | `specs/032-conditional-policy/research.md` | Complete |
| Data Model | `specs/032-conditional-policy/data-model.md` | Complete |
| Quickstart | `specs/032-conditional-policy/quickstart.md` | Complete |
| Contract: Condition Evaluator | `specs/032-conditional-policy/contracts/condition-evaluator.md` | Complete |
| Contract: Conditional Actions | `specs/032-conditional-policy/contracts/conditional-actions.md` | Complete |
| Contract: Rule Evaluator | `specs/032-conditional-policy/contracts/rule-evaluator.md` | Complete |

## Next Steps

Run `/speckit.tasks` to generate implementation tasks from this plan.
