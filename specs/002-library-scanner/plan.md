# Implementation Plan: Library Scanner

**Branch**: `002-library-scanner` | **Date**: 2025-11-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-library-scanner/spec.md`

## Summary

Implement a read-only library scanner that recursively discovers video files in user-specified directories, extracts basic metadata, and persists results to a SQLite database. The scanner provides a CLI command (`vpo scan`), a `MediaIntrospector` abstraction layer for future ffprobe/mkvmerge integration, and a normalized database schema for files and tracks.

## Technical Context

**Language/Version**: Python 3.10+ with Rust 1.70+ native extension
**Primary Dependencies**: click (CLI), sqlite3 (stdlib), vpo-core (Rust: rayon, walkdir, xxhash-rust)
**Build System**: maturin (Python-Rust bridge via PyO3)
**Storage**: SQLite (~/.vpo/library.db)
**Testing**: pytest (Python), cargo test (Rust)
**Target Platform**: Linux, macOS, Windows (cross-platform CLI)
**Project Type**: Hybrid Python/Rust package with CLI entry point
**Performance Goals**: Scan 10,000 files in under 1 minute on SSD; support terabyte-scale libraries
**Constraints**: Read-only operations; no file modifications; graceful error handling
**Scale/Scope**: Single-user CLI tool; local filesystem; parallel scanning

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: Project constitution is not yet customized (template only). Applying standard best practices:

| Principle | Status | Notes |
|-----------|--------|-------|
| Library-First | PASS | Scanner logic in separate module from CLI |
| CLI Interface | PASS | `vpo scan` command with text output |
| Test-First | PASS | Will implement with TDD approach |
| Simplicity | PASS | Minimal dependencies; stdlib where possible |

No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/002-library-scanner/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI interface contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Rust native extension (performance-critical code)
crates/
└── vpo-core/
    ├── Cargo.toml           # Rust package manifest
    └── src/
        ├── lib.rs           # PyO3 module exports
        ├── discovery.rs     # Parallel directory traversal (walkdir + rayon)
        └── hasher.rs        # Parallel file hashing (xxhash-rust + rayon)

# Python package (CLI, orchestration, database)
src/video_policy_orchestrator/
├── __init__.py              # Package init
├── _core.pyi                # Type stubs for Rust extension
├── cli/
│   ├── __init__.py
│   └── scan.py              # vpo scan command
├── db/
│   ├── __init__.py
│   ├── connection.py        # Database connection management
│   ├── models.py            # Dataclasses for File, Track
│   └── schema.py            # Schema creation and migrations
├── scanner/
│   ├── __init__.py
│   └── orchestrator.py      # Coordinates Rust core + DB writes
└── introspector/
    ├── __init__.py
    ├── interface.py         # MediaIntrospector protocol
    └── stub.py              # Stub implementation returning mock data

# Tests
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_core.py         # Tests for Rust extension via Python
│   ├── test_models.py
│   └── test_introspector.py
├── integration/
│   ├── test_scan_command.py
│   └── test_database.py
└── fixtures/
    └── sample_videos/       # Test video file stubs
```

**Structure Decision**: Hybrid Python/Rust layout. Rust crate in `crates/vpo-core/` compiled via maturin into `video_policy_orchestrator._core`. Python handles CLI, database, and orchestration. Rust handles parallel discovery and hashing.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|-------------------------------------|
| Rust extension (vpo-core) | Terabyte-scale libraries require true parallelism; Python GIL blocks multi-threaded hashing | Python multiprocessing has significant IPC overhead; single-threaded is too slow for 10,000+ files |
| maturin build system | Required for Python-Rust interop | No alternative for PyO3 bindings |

Design still follows simplicity principles:
- Standard library `sqlite3` instead of ORM framework
- `click` for CLI (idiomatic Python)
- Rust code is minimal and focused (discovery + hashing only)
- Python remains primary for all orchestration logic
