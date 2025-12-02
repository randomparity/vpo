# Implementation Plan: Processing Statistics and Metrics Tracking

**Branch**: `040-processing-stats` | **Date**: 2025-12-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/040-processing-stats/spec.md`

## Summary

Add comprehensive processing statistics and metrics tracking to VPO. This includes persisting file size before/after, track counts, transcode details, per-action results, and performance metrics. Statistics are exposed via both CLI (`vpo stats`) and Web UI dashboard. Data is retained indefinitely with manual purge capability.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: SQLite (via stdlib sqlite3), Click (CLI), aiohttp (Web UI), Pydantic (validation)
**Storage**: SQLite at `~/.vpo/library.db` - current schema version 17, will bump to 18
**Testing**: pytest with fixtures in `tests/`
**Target Platform**: Linux/macOS (cross-platform)
**Project Type**: Single Python package with CLI and web server
**Performance Goals**: Aggregate statistics query within 2 seconds (SC-001)
**Constraints**: Must not impact processing performance significantly; statistics capture should be lightweight
**Scale/Scope**: Designed for libraries with 10k+ files and years of historical data

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Check (Phase 0)

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps will use UTC ISO-8601 |
| II. Stable Identity | PASS | ProcessingStats uses UUIDv4, links to file_id |
| III. Portable Paths | PASS | Using pathlib.Path throughout |
| IV. Versioned Schemas | PASS | Schema bump 17→18 with migration |
| V. Idempotent Operations | PASS | Statistics recording is append-only, safe to repeat |
| VI. IO Separation | PASS | Statistics capture in workflow layer, storage in db layer |
| VII. Explicit Error Handling | PASS | Partial stats recorded on failure with error details |
| VIII. Structured Logging | PASS | Statistics inherently provide audit trail |
| IX. Configuration as Data | N/A | No new configuration required |
| X. Policy Stability | N/A | No policy schema changes |
| XI. Plugin Isolation | N/A | No plugin interface changes |
| XII. Safe Concurrency | PASS | Using existing DaemonConnectionPool patterns |
| XIII. Database Design | PASS | Normalized tables with proper FKs and indexes |
| XIV. Test Media Corpus | PASS | Will add fixtures for statistics tests |
| XV. Stable CLI/API Contracts | PASS | New `vpo stats` command follows existing patterns |
| XVI. Dry-Run Default | N/A | Statistics capture is read-only observation |
| XVII. Data Privacy | PASS | Statistics contain only metadata, no media content |
| XVIII. Living Documentation | PASS | Will update architecture docs |

### Post-Design Check (Phase 1)

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | `processed_at` uses ISO-8601 UTC per data-model.md |
| II. Stable Identity | PASS | `processing_stats.id` is UUIDv4, FKs to files.id |
| III. Portable Paths | PASS | No path operations in statistics layer |
| IV. Versioned Schemas | PASS | Migration `migrate_v17_to_v18()` documented |
| V. Idempotent Operations | PASS | Append-only design; purge is explicit user action |
| VI. IO Separation | PASS | Pure dataclasses in types.py, queries in queries.py |
| VII. Explicit Error Handling | PASS | `success` boolean + `error_message` field per record |
| VIII. Structured Logging | PASS | Statistics tables serve as structured audit log |
| XII. Safe Concurrency | PASS | Uses existing connection patterns; FK CASCADE for cleanup |
| XIII. Database Design | PASS | 3NF normalized; proper indexes per data-model.md |
| XV. Stable CLI/API Contracts | PASS | CLI contract in contracts/cli.md; OpenAPI in contracts/api.yaml |
| XVII. Data Privacy | PASS | Only metadata stored; no file content or paths in hashes |
| XVIII. Living Documentation | PASS | quickstart.md provides implementation guide |

**Post-Design Verdict**: All applicable principles PASS. Ready for task generation.

## Project Structure

### Documentation (this feature)

```text
specs/040-processing-stats/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── db/
│   ├── schema.py        # Add processing_stats, action_results, performance_metrics tables
│   ├── types.py         # Add ProcessingStatsRecord, ActionResultRecord, PerformanceMetricsRecord
│   ├── queries.py       # Add CRUD for new tables
│   └── views.py         # Add aggregate statistics queries
├── workflow/
│   ├── v11_processor.py # Capture and persist statistics during processing
│   └── stats_capture.py # Helper functions: compute_partial_hash(), count_tracks_by_type()
├── executor/
│   └── interface.py     # Extend ExecutorResult with metrics fields
├── cli/
│   └── stats.py         # New: vpo stats command
└── server/
    ├── routes.py        # Add /api/stats endpoints
    └── ui/
        └── templates/
            └── stats.html  # Statistics dashboard template

tests/
├── unit/
│   └── test_stats_*.py  # Unit tests for statistics logic
└── integration/
    └── test_stats_*.py  # Integration tests for CLI and API
```

**Structure Decision**: Extends existing single-package structure. New files are minimal - primarily `cli/stats.py` and a web template. Most changes extend existing modules.

## Complexity Tracking

No violations requiring justification. Implementation follows established patterns.
