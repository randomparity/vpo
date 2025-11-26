# Implementation Plan: Audio Track Synthesis

**Branch**: `033-audio-synthesis` | **Date**: 2025-11-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/033-audio-synthesis/spec.md`

## Summary

Enable creation of new audio tracks by transcoding from existing sources. Users define synthesis tracks in policy YAML with target codec (EAC3, AAC, AC3, Opus, FLAC), channels, and bitrate. The system evaluates `create_if` conditions, selects source tracks based on preference criteria (language, non-commentary, channel count), and adds synthesized tracks alongside originals using FFmpeg. Supports multiple synthesis definitions per policy, configurable track positioning, and dry-run preview.

## Technical Context

**Language/Version**: Python 3.10+ (consistent with existing VPO)
**Primary Dependencies**: FFmpeg (transcoding), existing policy/executor framework
**Storage**: SQLite via existing `db/` module (track metadata storage)
**Testing**: pytest (unit + integration), test fixtures with audio tracks
**Target Platform**: Linux, macOS (consistent with VPO)
**Project Type**: Single project - extends existing `src/video_policy_orchestrator/`
**Performance Goals**: Transcoding speed limited by FFmpeg; no additional overhead
**Constraints**: User-cancellable (Ctrl+C), no automatic timeouts, clean partial file handling
**Scale/Scope**: Batch processing of media libraries (thousands of files)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | N/A | No datetime-specific operations |
| II. Stable Identity | PASS | Synthesized tracks get new UUIDs, source track referenced by ID |
| III. Portable Paths | PASS | Use `pathlib.Path` for temp files and output |
| IV. Versioned Schemas | PASS | Policy schema version bump for `audio_synthesis` section |
| V. Idempotent Operations | PASS | `create_if` conditions prevent duplicate synthesis |
| VI. IO Separation | PASS | FFmpeg calls via adapter (new `synthesis/` executor) |
| VII. Explicit Error Handling | PASS | Custom exceptions: `SynthesisError`, `EncoderUnavailableError` |
| VIII. Structured Logging | PASS | Log synthesis decisions, source selection, skip reasons |
| IX. Configuration as Data | PASS | Synthesis defined in policy YAML, not code |
| X. Policy Stability | PASS | New optional section, backward compatible |
| XI. Plugin Isolation | N/A | No plugin interface changes |
| XII. Safe Concurrency | PASS | Single-file synthesis, atomic operations |
| XIII. Database Design | PASS | Use existing TrackInfo schema |
| XIV. Test Media Corpus | PASS | Add fixtures with multi-track audio |
| XV. Stable CLI/API Contracts | PASS | Extends existing `apply` command, no breaking changes |
| XVI. Dry-Run Default | PASS | Synthesis plan shown in dry-run output |
| XVII. Data Privacy | PASS | No external services, local FFmpeg only |
| XVIII. Living Documentation | PASS | Update docs with synthesis policy examples |

**Gate Status**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/033-audio-synthesis/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (policy schema)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── policy/
│   ├── models.py           # Extend: SynthesisTrackDef, SynthesisPlan
│   ├── schema.py           # Extend: audio_synthesis section
│   ├── evaluator.py        # Extend: synthesis condition evaluation
│   └── synthesis/          # NEW: synthesis planning module
│       ├── __init__.py
│       ├── models.py       # SynthesisTrackDefinition, SourceSelection
│       ├── source_selector.py  # Source track selection algorithm
│       └── planner.py      # Build SynthesisPlan from policy + file
├── executor/
│   ├── interface.py        # Existing Executor protocol
│   └── ffmpeg_synthesis.py # NEW: FFmpeg audio synthesis executor
└── cli/
    └── apply.py            # Extend: synthesis output in dry-run

tests/
├── unit/
│   └── policy/
│       └── synthesis/      # NEW: source selection, planning tests
├── integration/
│   └── executor/
│       └── test_ffmpeg_synthesis.py  # NEW: FFmpeg synthesis tests
└── fixtures/
    └── audio/              # NEW: multi-track audio test files
```

**Structure Decision**: Extend existing single-project structure. New synthesis logic in `policy/synthesis/` submodule for source selection and planning. New executor `executor/ffmpeg_synthesis.py` follows established executor pattern.

## Complexity Tracking

> No violations to justify - all constitution checks pass.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
