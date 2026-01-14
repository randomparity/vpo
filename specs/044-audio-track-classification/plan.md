# Implementation Plan: Audio Track Classification

**Branch**: `044-audio-track-classification` | **Date**: 2025-12-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/044-audio-track-classification/spec.md`

## Summary

Implement audio track classification to identify original vs dubbed tracks and detect commentary tracks via acoustic analysis. Extends the existing policy condition system with `is_original`, `is_dubbed` conditions and enhances `is_commentary` to support acoustic detection. Primary signal for original/dubbed is external metadata (production country/title language); fallback signals include track position and acoustic analysis. Classification results are cached per file hash with 70% default confidence threshold.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: openai-whisper (transcription plugin), pydantic (validation), click (CLI), aiohttp (daemon)
**Storage**: SQLite at `~/.vpo/library.db` - new table for track classification results
**Testing**: pytest with fixtures for audio classification test cases
**Target Platform**: Linux and macOS
**Project Type**: Single project (existing VPO structure)
**Performance Goals**: Classification completes within 30 seconds per audio track using sampling
**Constraints**: Opt-in analysis (not automatic), results cached per file hash, 70% default confidence threshold
**Scale/Scope**: Per-file analysis with caching, integrates with existing policy evaluation and language detection

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps UTC ISO-8601 |
| II. Stable Identity | PASS | Uses track_id (UUIDv4 linked) as foreign key |
| III. Portable Paths | N/A | No direct path operations in this feature |
| IV. Versioned Schemas | PASS | Adds to schema version 19, migration provided |
| V. Idempotent Operations | PASS | Re-analysis produces deterministic results |
| VI. IO Separation | PASS | Acoustic analysis via plugin adapter, pure evaluation functions |
| VII. Explicit Error Handling | PASS | Custom exceptions: InsufficientDataError, ClassificationError |
| VIII. Structured Logging | PASS | Classification decisions logged with track/file context |
| IX. Configuration as Data | PASS | Classification config in policy YAML |
| X. Policy Stability | PASS | New condition types, backward compatible |
| XI. Plugin Isolation | PASS | Extends existing TranscriptionPlugin protocol |
| XII. Safe Concurrency | PASS | Per-track analysis, no shared mutable state |
| XIII. Database Design | PASS | Normalized schema with foreign keys and indexes |
| XIV. Test Media Corpus | TODO | Need audio tracks with known original/dubbed status |
| XVI. Dry-Run Default | PASS | `--dry-run` shows classification plan |
| XVII. Data Privacy | PASS | All analysis runs locally, opt-in only |

## Project Structure

### Documentation (this feature)

```text
specs/044-audio-track-classification/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Technical research and decisions
├── data-model.md        # Entity definitions and schemas
├── quickstart.md        # Implementation guide
├── contracts/           # API contracts
│   ├── classification-service.md
│   ├── policy-conditions.md
│   └── cli-classify-tracks.md
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/vpo/
├── track_classification/        # NEW: Track classification module
│   ├── __init__.py
│   ├── models.py               # TrackClassificationResult, AcousticProfile, enums
│   ├── service.py              # classify_track(), get_original_language()
│   ├── acoustic.py             # Acoustic analysis helpers (speech patterns, voice detection)
│   └── metadata.py             # External metadata integration (production country lookup)
├── transcription/
│   └── interface.py            # MODIFY: Add acoustic_profile() to protocol
├── plugins/
│   └── whisper_transcriber/
│       └── plugin.py           # MODIFY: Implement acoustic_profile()
├── db/
│   ├── schema.py               # MODIFY: Add track_classification_results table (version 19)
│   └── types.py                # MODIFY: Add TrackClassificationRecord, OriginalDubbedStatus enum
├── policy/
│   ├── models.py               # MODIFY: Add IsOriginalCondition, IsDubbedCondition
│   ├── loader.py               # MODIFY: Add condition parsing
│   └── conditions.py           # MODIFY: Add evaluation functions
└── cli/
    ├── inspect.py              # MODIFY: Add --classify-tracks option
    └── classify.py             # NEW: Dedicated classification command

tests/
├── fixtures/
│   └── classification/         # NEW: Classification test fixtures
│       ├── original-japanese.json
│       └── dubbed-english.json
├── unit/
│   ├── track_classification/   # NEW: Unit tests for classification
│   │   ├── test_models.py
│   │   ├── test_service.py
│   │   └── test_acoustic.py
│   └── policy/
│       └── test_conditions.py  # MODIFY: Add original/dubbed condition tests
└── integration/
    └── test_track_classification.py  # NEW: Integration tests
```

**Structure Decision**: Follows existing VPO single-project structure. New `track_classification` module mirrors `language_analysis` module pattern. Policy extensions follow established patterns from Schema V4-V12.

## Complexity Tracking

No constitution violations requiring justification. All changes follow existing patterns:
- New condition types follow `ExistsCondition`/`AudioIsMultiLanguageCondition` pattern
- Plugin extension follows `TranscriptionPlugin` protocol pattern
- Database tables follow `language_analysis_results` pattern
- New CLI command follows existing `analyze-language` pattern

## Generated Artifacts

- [research.md](./research.md) - Technical research and decisions
- [data-model.md](./data-model.md) - Entity definitions and schemas
- [quickstart.md](./quickstart.md) - Implementation guide
- [contracts/classification-service.md](./contracts/classification-service.md) - Service interface
- [contracts/policy-conditions.md](./contracts/policy-conditions.md) - Condition definitions
- [contracts/cli-classify-tracks.md](./contracts/cli-classify-tracks.md) - CLI interface

## Next Steps

Run `/speckit.tasks` to generate the implementation task list based on this plan.
