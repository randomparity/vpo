# Implementation Plan: Multi-Language Audio Detection

**Branch**: `035-multi-language-audio-detection` | **Date**: 2025-11-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/035-multi-language-audio-detection/spec.md`

## Summary

Implement multi-language audio detection to identify when audio tracks contain multiple spoken languages and automatically enable forced subtitles for mixed-language content. The feature extends the existing conditional policy system with a new `audio_is_multi_language` condition type and adds `set_forced`/`set_default` actions for subtitle manipulation. Language detection uses sampling-based analysis via the existing Whisper transcription plugin infrastructure.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: openai-whisper (transcription plugin), pydantic (validation), click (CLI), aiohttp (daemon)
**Storage**: SQLite at `~/.vpo/library.db` - new tables for language analysis results
**Testing**: pytest with fixtures for multi-language audio samples
**Target Platform**: Linux and macOS
**Project Type**: Single project (existing VPO structure)
**Performance Goals**: Language analysis <60 seconds for 2-hour film using 10-minute sampling intervals
**Constraints**: Opt-in analysis (not automatic), results cached per file hash
**Scale/Scope**: Per-file analysis with caching, integrates with existing policy evaluation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps UTC ISO-8601 |
| II. Stable Identity | PASS | Uses track_id (UUIDv4 linked) as foreign key |
| III. Portable Paths | N/A | No direct path operations in this feature |
| IV. Versioned Schemas | PASS | Bumps to schema version 7 |
| V. Idempotent Operations | PASS | Re-analysis produces deterministic results |
| VI. IO Separation | PASS | Plugin adapter for Whisper, pure evaluation functions |
| VII. Explicit Error Handling | PASS | Custom exceptions: InsufficientSpeechError, etc. |
| VIII. Structured Logging | PASS | Analysis decisions logged with track/file context |
| IX. Configuration as Data | PASS | Analysis config in policy YAML |
| X. Policy Stability | PASS | New condition type, backward compatible |
| XI. Plugin Isolation | PASS | Extends existing TranscriptionPlugin protocol |
| XII. Safe Concurrency | PASS | Per-track analysis, no shared mutable state |
| XIII. Database Design | PASS | Normalized schema with foreign keys and indexes |
| XIV. Test Media Corpus | TODO | Need multi-language test fixtures |
| XVI. Dry-Run Default | PASS | `--dry-run` shows analysis plan |
| XVII. Data Privacy | PASS | Whisper runs locally, opt-in only |

## Project Structure

### Documentation (this feature)

```text
specs/035-multi-language-audio-detection/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Technical research and decisions
├── data-model.md        # Entity definitions and schemas
├── quickstart.md        # Implementation guide
├── contracts/           # API contracts
│   ├── language-analysis-plugin.md
│   ├── policy-schema-v7.md
│   └── cli-analyze-languages.md
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/vpo/
├── language_analysis/           # NEW: Language analysis module
│   ├── __init__.py
│   ├── models.py               # LanguageSegment, LanguageAnalysisResult
│   └── service.py              # analyze_track_languages()
├── transcription/
│   └── interface.py            # MODIFY: Add detect_multi_language() to protocol
├── plugins/
│   └── whisper_transcriber/
│       └── plugin.py           # MODIFY: Implement detect_multi_language()
├── db/
│   ├── schema.py               # MODIFY: Add language_analysis tables
│   └── models.py               # MODIFY: Add LanguageAnalysisResultRecord
├── policy/
│   ├── models.py               # MODIFY: Add AudioIsMultiLanguageCondition, actions
│   ├── loader.py               # MODIFY: Add V7 parsing, validation
│   ├── conditions.py           # MODIFY: Add evaluation function
│   └── actions.py              # MODIFY: Add set_forced, set_default execution
└── cli/
    ├── scan.py                 # MODIFY: Add --analyze-languages
    ├── inspect.py              # MODIFY: Add --analyze-languages, --show-segments
    ├── apply.py                # MODIFY: Add --auto-analyze
    └── analyze_language.py     # NEW: Dedicated analysis command

tests/
├── fixtures/
│   └── audio/                  # NEW: Multi-language audio fixtures
│       ├── single-language-en.wav
│       └── multi-language-en-fr.wav
├── unit/
│   ├── language_analysis/      # NEW: Unit tests for models
│   │   └── test_models.py
│   └── policy/
│       ├── test_conditions.py  # MODIFY: Add multi-language tests
│       └── test_actions.py     # MODIFY: Add set_forced/set_default tests
└── integration/
    └── test_language_analysis.py  # NEW: Integration tests
```

**Structure Decision**: Follows existing VPO single-project structure. New `language_analysis` module mirrors `transcription` module pattern. Policy extensions follow established patterns from Schema V4-V6.

## Complexity Tracking

No constitution violations requiring justification. All changes follow existing patterns:
- New condition type follows `ExistsCondition`/`CountCondition` pattern
- New actions follow `SkipAction`/`WarnAction` pattern
- Plugin extension follows `TranscriptionPlugin` protocol pattern
- Database tables follow `transcription_results` pattern

## Generated Artifacts

- [research.md](./research.md) - Technical research and decisions
- [data-model.md](./data-model.md) - Entity definitions and schemas
- [quickstart.md](./quickstart.md) - Implementation guide
- [contracts/language-analysis-plugin.md](./contracts/language-analysis-plugin.md) - Plugin protocol extension
- [contracts/policy-schema-v7.md](./contracts/policy-schema-v7.md) - V7 schema definition
- [contracts/cli-analyze-languages.md](./contracts/cli-analyze-languages.md) - CLI interface

## Next Steps

Run `/speckit.tasks` to generate the implementation task list based on this plan.
