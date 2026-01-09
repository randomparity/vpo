# Implementation Plan: Conditional Video Transcoding

**Branch**: `034-conditional-video-transcode` | **Date**: 2025-11-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/034-conditional-video-transcode/spec.md`

## Summary

Extend the existing TranscodeExecutor with conditional skip logic and enhanced quality settings. Users can skip transcoding when files already meet codec/resolution/bitrate requirements, configure CRF/bitrate quality modes with presets and tune options, downscale resolution, detect hardware acceleration, and preserve lossless audio during video-only transcoding.

This feature builds on the existing V4 conditional policy framework (Sprint 2/032-conditional-policy) and the TranscodeExecutor infrastructure, adding skip condition evaluation, quality parameter configuration, resolution scaling, and hardware encoder detection.

## Technical Context

**Language/Version**: Python 3.10+ (existing project standard)
**Primary Dependencies**: ffmpeg (transcoding), ffprobe (introspection), click (CLI), pydantic (validation), aiohttp (web UI)
**Storage**: SQLite at ~/.vpo/library.db (existing), temp files for transcode output
**Testing**: pytest with test media fixtures
**Target Platform**: Linux and macOS (per Constitution III)
**Project Type**: Single project (existing VPO structure)
**Performance Goals**: Hardware-accelerated encoding achieves 3x+ speedup; progress estimates within 20% accuracy
**Constraints**: Must preserve lossless audio bit-perfect; must support dry-run preview; temp-then-replace output pattern
**Scale/Scope**: Handles individual files via existing job queue; batch operations via existing scan/apply flow

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| I. Datetime Integrity | PASS | Uses existing UTC datetime patterns from job system |
| II. Stable Identity | PASS | Files identified by UUIDv4 file_id, not paths |
| III. Portable Paths | PASS | Uses pathlib.Path, no hardcoded separators |
| IV. Versioned Schemas | PASS | Extends PolicySchema with version bump if needed |
| V. Idempotent Operations | PASS | Skip conditions ensure compliant files aren't re-encoded |
| VI. IO Separation | PASS | TranscodeExecutor is already an adapter behind Executor protocol |
| VII. Explicit Error Handling | PASS | Spec defines explicit error behaviors for all edge cases |
| VIII. Structured Logging | PASS | Uses existing job logging patterns |
| IX. Configuration as Data | PASS | All settings in YAML policy, no hardcoded values |
| X. Policy Stability | PASS | New fields are additive, backward compatible |
| XI. Plugin Isolation | N/A | No plugin interface changes |
| XII. Safe Concurrency | PASS | Existing job queue handles concurrency |
| XIII. Database Design | PASS | No schema changes needed; progress in existing job fields |
| XIV. Test Media Corpus | PASS | Will add fixtures for skip condition and quality testing |
| XV. Stable CLI/API | PASS | Extends existing apply command; no breaking changes |
| XVI. Dry-Run Default | PASS | FR-006 requires dry-run skip message; dry-run is default |
| XVII. Data Privacy | PASS | No external service calls; all processing local |
| XVIII. Living Documentation | PASS | Will update docs with new policy options |

**Gate Status**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/034-conditional-video-transcode/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (policy schema extensions)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── executor/
│   └── transcode.py          # MODIFY: Add skip evaluation, quality modes, HW accel
├── policy/
│   ├── models.py             # MODIFY: Add skip/quality/scaling/hwaccel dataclasses
│   ├── schema.py             # MODIFY: Parse new transcode policy fields
│   └── transcode.py          # MODIFY: Enhance audio codec planning
├── introspector/
│   └── ffprobe.py            # EXISTING: Already extracts codec/resolution/bitrate
├── tools/
│   └── ffmpeg.py             # MODIFY: Add HW encoder detection
└── jobs/
    └── progress.py           # EXISTING: FFmpegProgress already handles progress

tests/
├── unit/
│   ├── test_skip_conditions.py    # NEW: Skip condition evaluation tests
│   ├── test_quality_settings.py   # NEW: CRF/bitrate/preset validation tests
│   └── test_scaling.py            # NEW: Resolution scaling tests
├── integration/
│   └── test_transcode_executor.py # MODIFY: Add skip/quality/scaling scenarios
└── fixtures/
    └── media/                     # ADD: Test files for skip condition testing
```

**Structure Decision**: Extends existing single-project structure. All changes are modifications to existing modules or new test files. No new top-level directories needed.

## Complexity Tracking

> No Constitution Check violations - table not required.
