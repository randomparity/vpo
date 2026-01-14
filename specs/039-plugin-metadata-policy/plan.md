# Implementation Plan: Plugin Metadata Access in Policies

**Branch**: `039-plugin-metadata-policy` | **Date**: 2025-12-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/039-plugin-metadata-policy/spec.md`

## Summary

Enable policy conditions to reference plugin-provided metadata using `plugin_name:field_name` syntax. This allows policies to make decisions based on external data (like original language from Radarr/Sonarr) that isn't available from media file introspection alone. Plugin metadata is stored in a new JSON column on the files table and accessed via a new `PluginMetadataCondition` type in conditional rules.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: Pydantic (validation), ruamel.yaml (policy parsing), SQLite (storage)
**Storage**: SQLite - new `plugin_metadata TEXT` column on `files` table (JSON)
**Testing**: pytest (unit, integration)
**Target Platform**: Linux and macOS (per constitution III)
**Project Type**: Single project with existing structure
**Performance Goals**: No significant impact on policy evaluation (per SC-003)
**Constraints**: Backward compatible with V11 and earlier schemas (per FR-007)
**Scale/Scope**: Extends existing policy condition system with one new condition type

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime handling in this feature |
| II. Stable Identity | PASS | Plugin metadata keyed by plugin name, file identity unchanged |
| III. Portable Paths | N/A | No path handling changes |
| IV. Versioned Schemas | PASS | Schema V12 for policy, DB migration v16→v17 |
| V. Idempotent Operations | PASS | Condition evaluation is pure/deterministic |
| VI. IO Separation | PASS | New condition type is pure function, DB access via existing queries module |
| VII. Explicit Error Handling | PASS | Missing data → condition evaluates to false (documented graceful degradation) |
| VIII. Structured Logging | PASS | Condition results include reason strings for dry-run output |
| IX. Configuration as Data | PASS | Plugin metadata stored in DB, not code |
| X. Policy Stability | PASS | New V12 features, V11 policies unchanged |
| XI. Plugin Isolation | PASS | Uses existing plugin interfaces, no changes to plugin contracts |
| XII. Safe Concurrency | N/A | No new concurrency introduced |
| XIII. Database Design | PASS | JSON column with clear schema, accessed via queries module |
| XIV. Test Media Corpus | PASS | Will add unit tests for condition evaluation |
| XV. Stable CLI/API Contracts | PASS | CLI unchanged, policy schema extended backward-compatibly |
| XVI. Dry-Run Default | PASS | Condition evaluation produces reason strings for preview |
| XVII. Data Privacy | PASS | Plugin metadata is user-configured, no external services |
| XVIII. Living Documentation | PASS | Will update policy schema docs |

**Gate Status**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/039-plugin-metadata-policy/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no new API endpoints)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── policy/
│   ├── plugin_metadata.py   # NEW: PluginMetadataCondition, evaluation, validation
│   ├── models.py            # UPDATE: Add PluginMetadataCondition to Condition union
│   ├── loader.py            # UPDATE: Pydantic model, conversion, MAX_SCHEMA_VERSION=12
│   ├── conditions.py        # UPDATE: Add evaluation case, update signature
│   └── evaluator.py         # UPDATE: Thread plugin_metadata through evaluation
├── db/
│   ├── schema.py            # UPDATE: Migration v16→v17, add column
│   ├── types.py             # UPDATE: Add field to FileRecord, FileInfo
│   └── queries.py           # UPDATE: Include plugin_metadata in upsert/select
└── scanner/
    └── orchestrator.py      # UPDATE: Collect and store plugin enrichment results

tests/
├── unit/
│   └── policy/
│       └── test_plugin_metadata.py  # NEW: Condition evaluation tests
└── integration/
    └── test_plugin_metadata_policy.py  # NEW: End-to-end policy tests
```

**Structure Decision**: Extends existing single-project structure. New module `policy/plugin_metadata.py` encapsulates plugin metadata abstractions to maintain clean separation from existing condition types.

## Complexity Tracking

> No violations requiring justification.
