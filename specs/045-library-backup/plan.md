# Implementation Plan: Library Backup and Restore

**Branch**: `045-library-backup` | **Date**: 2026-02-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/045-library-backup/spec.md`

## Summary

Extend the `vpo library` command to support backup and restore of the library database. Users can create compressed `.tar.gz` archives containing the SQLite database with metadata, restore from backups, and list available backups. This provides disaster recovery and migration capabilities for VPO users.

## Technical Context

**Language/Version**: Python 3.10-3.13
**Primary Dependencies**: click (CLI), tarfile (stdlib), json (stdlib), shutil (stdlib)
**Storage**: SQLite database at `~/.vpo/library.db`, backups at `~/.vpo/backups/`
**Testing**: pytest with unit and integration tests
**Target Platform**: Linux and macOS
**Project Type**: Single project (extends existing CLI module)
**Performance Goals**: Backup/restore under 30s for 100MB databases; 50%+ compression ratio
**Constraints**: Must handle daemon lock detection; schema version compatibility
**Scale/Scope**: Typical database sizes 10MB-500MB

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ Pass | Backup timestamps use UTC ISO-8601 format |
| II. Stable Identity | ✅ Pass | Backups identified by timestamp; database IDs preserved |
| III. Portable Paths | ✅ Pass | Using pathlib.Path; supports Linux/macOS |
| IV. Versioned Schemas | ✅ Pass | Schema version included in backup metadata |
| V. Idempotent Operations | ✅ Pass | Backup creates new file; restore is atomic replacement |
| VI. IO Separation | ✅ Pass | Core backup/restore logic separate from CLI layer |
| VII. Explicit Error Handling | ✅ Pass | Custom exceptions for backup errors |
| VIII. Structured Logging | ✅ Pass | Log backup/restore operations with metadata |
| IX. Configuration as Data | ✅ Pass | Default paths in config, not hardcoded |
| X. Policy Stability | N/A | No policy schema changes |
| XI. Plugin Isolation | N/A | No plugin interfaces affected |
| XII. Safe Concurrency | ✅ Pass | Lock detection prevents concurrent access |
| XIII. Database Design | ✅ Pass | No schema changes; read/copy operations only |
| XIV. Test Media Corpus | N/A | No media files involved |
| XV. Stable CLI/API Contracts | ✅ Pass | Follows existing CLI patterns (--dry-run, --json, --yes) |
| XVI. Dry-Run Default | ✅ Pass | --dry-run supported for both backup and restore |
| XVII. Data Privacy | ✅ Pass | No external services; local-only operations |
| XVIII. Living Documentation | ✅ Pass | CLI help updated; docs as needed |

## Project Structure

### Documentation (this feature)

```text
specs/045-library-backup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI interface spec)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── cli/
│   └── library.py       # Extended with backup, restore, backups commands
├── db/
│   └── backup.py        # NEW: Backup/restore core logic
└── core/
    └── __init__.py      # Existing utilities (format_file_size, etc.)

tests/
├── unit/
│   └── db/
│       └── test_backup.py  # NEW: Unit tests for backup module
└── integration/
    └── cli/
        └── test_library_backup.py  # NEW: Integration tests
```

**Structure Decision**: Extends existing single-project structure. Core backup logic in `db/backup.py` (follows DAO pattern from constitution). CLI commands in `cli/library.py` (extends existing library command group).

## Complexity Tracking

> No violations requiring justification. Design follows existing patterns.
