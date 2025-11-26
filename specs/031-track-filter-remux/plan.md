# Implementation Plan: Track Filtering & Container Remux

**Branch**: `031-track-filter-remux` | **Date**: 2025-11-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/031-track-filter-remux/spec.md`

## Summary

Implement track-level filtering (audio, subtitle, attachment removal) and lossless container conversion (MKV ↔ MP4) for VPO policies. This extends the policy schema to v3 with backward compatibility, adds track disposition tracking for dry-run output, and introduces new executors for track selection and remuxing.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: click (CLI), pydantic (validation), ruamel.yaml (policy parsing), aiohttp (daemon)
**External Tools**: mkvmerge, mkvpropedit (MKV operations), ffmpeg/ffprobe (general media operations)
**Storage**: SQLite (`~/.vpo/library.db`) - no schema changes required
**Testing**: pytest with test media corpus
**Target Platform**: Linux, macOS
**Project Type**: Single Python package with CLI and daemon
**Performance Goals**: Process track filtering decisions in <100ms; remux at native I/O speed
**Constraints**: Must preserve source quality (lossless stream copy), must never create audio-less files
**Scale/Scope**: Library-scale operations (thousands of files), single-file atomic operations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps use UTC (existing pattern) |
| II. Stable Identity | PASS | Uses file_id (UUID), not paths as keys |
| III. Portable Paths | PASS | Uses pathlib.Path throughout |
| IV. Versioned Schemas | PASS | Introducing schema v3 with explicit migration |
| V. Idempotent Operations | PASS | Track filtering is deterministic and repeatable |
| VI. IO Separation | PASS | Filter logic in evaluator, tool calls in executors |
| VII. Explicit Error Handling | PASS | Custom exceptions: InsufficientTracksError, IncompatibleCodecError |
| VIII. Structured Logging | PASS | Follows existing logging patterns |
| IX. Configuration as Data | PASS | Policy files are data, not code |
| X. Policy Stability | PASS | v2 policies unchanged, v3 additive |
| XI. Plugin Isolation | N/A | No plugin interface changes |
| XII. Safe Concurrency | PASS | Single-file atomic operations with backup |
| XIII. Database Design | PASS | No DB schema changes required |
| XIV. Test Media Corpus | REQUIRED | Need test files with multiple audio/subtitle tracks |
| XV. Stable CLI/API Contracts | PASS | Extends existing --dry-run, adds new policy fields |
| XVI. Dry-Run Default | PASS | Enhanced dry-run with track disposition output |
| XVII. Data Privacy | PASS | No external service integration |
| XVIII. Living Documentation | REQUIRED | Update policy documentation with v3 fields |

**Gate Status**: PASS (with required follow-up for test corpus and documentation)

## Project Structure

### Documentation (this feature)

```text
specs/031-track-filter-remux/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Research findings
├── data-model.md        # Data model definitions
├── quickstart.md        # Implementation guide
├── contracts/           # API contracts
│   ├── policy-schema-v3.yaml
│   └── cli-contract.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── policy/
│   ├── models.py        # Add V3 config models, TrackDisposition
│   ├── loader.py        # Update MAX_SCHEMA_VERSION, add V3 validation
│   ├── evaluator.py     # Add compute_track_dispositions()
│   └── exceptions.py    # Add InsufficientTracksError, IncompatibleCodecError
├── executor/
│   ├── mkvmerge.py      # Extend with track selection args
│   └── ffmpeg_remux.py  # NEW: Container conversion executor
└── cli/
    └── apply.py         # Enhanced dry-run output

tests/
├── unit/
│   └── policy/
│       ├── test_track_filtering.py   # NEW
│       └── test_container_config.py  # NEW
├── integration/
│   └── test_track_filtering.py       # NEW
└── fixtures/
    └── media/
        └── multilang/                 # Test corpus (to be added)
```

**Structure Decision**: Extends existing single-package structure. New code integrates into existing policy/ and executor/ modules. One new executor file for FFmpeg remuxing.

## Complexity Tracking

> No Constitution Check violations requiring justification.

| Decision | Rationale |
|----------|-----------|
| Extend existing executors | Simpler than creating new executor hierarchy |
| V3 fields all optional | Ensures backward compatibility without migration code |
| Track disposition in Plan | Enables rich dry-run without separate data structure |

## Phase Artifacts

| Phase | Artifact | Status |
|-------|----------|--------|
| 0 | research.md | Complete |
| 1 | data-model.md | Complete |
| 1 | contracts/policy-schema-v3.yaml | Complete |
| 1 | contracts/cli-contract.md | Complete |
| 1 | quickstart.md | Complete |
| 2 | tasks.md | Pending (`/speckit.tasks`) |

## Implementation Priorities

Based on spec user story priorities:

1. **P1 - Core Filtering + Dry-Run** (US1, US2)
   - AudioFilterConfig model
   - compute_track_dispositions() in evaluator
   - Enhanced dry-run output in CLI
   - InsufficientTracksError validation

2. **P2 - Container Conversion** (US3, US4)
   - ContainerConfig model
   - FFmpeg remux executor
   - Codec compatibility checking
   - IncompatibleCodecError handling

3. **P3 - Additional Filters** (US5, US6, US7)
   - SubtitleFilterConfig with preserve_forced
   - AttachmentFilterConfig with font warnings
   - LanguageFallbackConfig modes

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Audio-less output | Mandatory minimum=1 validation, error before execution |
| Disk space during remux | Pre-flight check for 2x file size |
| Breaking v2 policies | All v3 fields optional, extensive backward compat tests |
| Large file performance | 30-minute timeout (existing), progress indication |

## Next Steps

Run `/speckit.tasks` to generate detailed implementation tasks from this plan.
