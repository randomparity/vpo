# Implementation Plan: Analyze-Language CLI Commands

**Branch**: `042-analyze-language-cli` | **Date**: 2025-12-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/042-analyze-language-cli/spec.md`

## Summary

Implement a dedicated `vpo analyze-language` command group with three subcommands (`run`, `status`, `clear`) for managing language analysis results independently of the scan workflow. This feature builds on the existing `language_analysis` module (from issue #270) and follows established VPO CLI patterns (Click groups, progress reporting, JSON output support).

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: click (CLI), existing `language_analysis` module, existing `db` module
**Storage**: SQLite at `~/.vpo/library.db` - uses existing `language_analysis_results` and `language_segments` tables
**Testing**: pytest with existing test fixtures from `tests/fixtures/audio/`
**Target Platform**: Linux and macOS
**Project Type**: Single project (existing VPO structure)
**Performance Goals**: Per spec - 60s single file analysis, 5s status query, 10s clear operation
**Constraints**: Must integrate with existing CLI patterns (db_conn via ctx.obj, progress bars, JSON output)
**Scale/Scope**: Library-wide operations (10,000+ files supported)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No new datetime handling (uses existing analysis timestamps) |
| II. Stable Identity | PASS | Uses existing track_id foreign keys |
| III. Portable Paths | PASS | Uses pathlib.Path for all file arguments |
| IV. Versioned Schemas | N/A | No schema changes (tables exist) |
| V. Idempotent Operations | PASS | `run` with cache is idempotent; `clear` is idempotent |
| VI. IO Separation | PASS | CLI layer orchestrates existing service functions |
| VII. Explicit Error Handling | PASS | Custom exceptions already defined in service.py |
| VIII. Structured Logging | PASS | Uses existing logging patterns |
| IX. Configuration as Data | N/A | No new configuration |
| X. Policy Stability | N/A | No policy changes |
| XI. Plugin Isolation | PASS | Uses existing TranscriptionPlugin protocol |
| XII. Safe Concurrency | PASS | Sequential file processing with progress |
| XIII. Database Design | PASS | Reuses existing tables and queries |
| XIV. Test Media Corpus | PASS | Test fixtures exist in tests/fixtures/audio/ |
| XV. Stable CLI/API Contracts | PASS | Follows existing flag conventions (--force, --dry-run, --json, --yes) |
| XVI. Dry-Run Default | PASS | `clear --dry-run` supported |
| XVII. Data Privacy | PASS | All processing local; no external services |
| XVIII. Living Documentation | TODO | Update docs/usage/multi-language-detection.md |

## Project Structure

### Documentation (this feature)

```text
specs/042-analyze-language-cli/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── cli-analyze-language.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── language_analysis/           # EXISTING - service layer
│   ├── __init__.py              # EXISTING - public API
│   ├── models.py                # EXISTING - domain models
│   ├── service.py               # EXISTING - analysis functions
│   └── formatters.py            # EXISTING - output formatting
├── db/
│   ├── views.py                 # MODIFY - add analysis status queries
│   └── queries.py               # MODIFY - add analysis deletion queries
└── cli/
    ├── __init__.py              # MODIFY - register analyze_language_group
    └── analyze_language.py      # NEW - CLI command group

tests/
├── fixtures/
│   └── audio/                   # EXISTING - test audio files
├── unit/
│   └── cli/
│       └── test_analyze_language.py  # NEW - CLI unit tests
└── integration/
    └── test_analyze_language_cli.py  # NEW - CLI integration tests
```

**Structure Decision**: Follows existing VPO single-project structure. New CLI module `analyze_language.py` mirrors `stats.py` pattern (Click group with subcommands). Database queries added to existing `views.py` and `queries.py` modules.

## Complexity Tracking

No constitution violations requiring justification. All changes follow existing patterns:
- CLI group follows `stats_group` pattern
- Database queries follow existing `get_*` and `delete_*` patterns
- Progress reporting follows existing `click.progressbar` usage

## Generated Artifacts

- [research.md](./research.md) - Technical research on CLI patterns
- [data-model.md](./data-model.md) - No new entities; documents query interfaces
- [quickstart.md](./quickstart.md) - Implementation guide
- [contracts/cli-analyze-language.md](./contracts/cli-analyze-language.md) - CLI interface specification

## Next Steps

Run `/speckit.tasks` to generate the implementation task list based on this plan.
