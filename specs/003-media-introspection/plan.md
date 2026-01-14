# Implementation Plan: Media Introspection & Track Modeling

**Branch**: `003-media-introspection` | **Date**: 2025-11-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-media-introspection/spec.md`

## Summary

Implement concrete ffprobe-based media introspection to extract track-level metadata (video, audio, subtitle) from MKV/MP4 containers and persist to SQLite. Extends existing `MediaIntrospector` protocol with real implementation, adds video-specific fields (resolution, frame rate) and audio channels to the track model, and provides a CLI `inspect` command for user-facing track enumeration.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml)
**Primary Dependencies**: click (CLI), subprocess (ffprobe invocation), sqlite3 (stdlib)
**Storage**: SQLite (~/.vpo/library.db) - existing schema from 002-library-scanner
**Testing**: pytest with JSON fixtures (recorded ffprobe output)
**Target Platform**: Linux, macOS, Windows (ffprobe must be installed)
**Project Type**: Single project (CLI tool with library)
**Performance Goals**: Track extraction within 5 seconds per file (SC-001)
**Constraints**: ffprobe required; graceful failure if missing
**Scale/Scope**: Single-user local libraries (thousands of files typical)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution file contains template placeholders only - no specific gates defined.
Proceeding with standard best practices for the project type.

## Project Structure

### Documentation (this feature)

```text
specs/003-media-introspection/
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
├── introspector/
│   ├── __init__.py          # Existing
│   ├── interface.py         # Existing MediaIntrospector protocol
│   ├── stub.py              # Existing stub implementation
│   └── ffprobe.py           # NEW: ffprobe-based implementation
├── db/
│   ├── models.py            # EXTEND: TrackInfo/TrackRecord with new fields
│   └── schema.py            # EXTEND: tracks table schema
└── cli/
    ├── __init__.py          # Existing
    ├── scan.py              # Existing
    └── inspect.py           # NEW: vpo inspect command

tests/
├── fixtures/
│   └── ffprobe/             # NEW: JSON fixtures for ffprobe output
│       ├── simple_single_track.json
│       ├── multi_audio.json
│       └── subtitle_heavy.json
├── unit/
│   └── test_ffprobe_introspector.py  # NEW
└── integration/
    └── test_inspect_command.py       # NEW
```

**Structure Decision**: Extends existing single-project structure from 002-library-scanner. New code integrates into established module hierarchy.

## Complexity Tracking

No constitution violations to justify. Design follows existing patterns established in 002-library-scanner.
