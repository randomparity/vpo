# Implementation Plan: Audio Transcription & Language Detection

**Branch**: `007-audio-transcription` | **Date**: 2025-11-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-audio-transcription/spec.md`

## Summary

Integrate audio transcription and language detection capabilities into VPO to automatically detect and tag audio track languages, identify commentary tracks, and update metadata via policy-driven workflows. The feature uses a pluggable transcription plugin interface with a Whisper-based reference implementation, persists results to SQLite, and integrates with the existing policy engine.

## Technical Context

**Language/Version**: Python 3.10+ (per pyproject.toml)
**Primary Dependencies**: click (CLI), pydantic (models), PyYAML (config), sqlite3 (database), openai-whisper (reference plugin)
**Storage**: SQLite (~/.vpo/library.db) - extend existing schema with transcription_results table
**Testing**: pytest
**Target Platform**: Linux, macOS (per Constitution III)
**Project Type**: Single project with plugin architecture
**Performance Goals**: <30 seconds per track for language detection (sampling mode)
**Constraints**: Offline-capable by default (Constitution XVII), streaming audio extraction via ffmpeg
**Scale/Scope**: Per-file/per-track processing, batch via policies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps stored as UTC ISO-8601 |
| II. Stable Identity | PASS | TranscriptionResult linked to track_id (existing) |
| III. Portable Paths | PASS | Using pathlib.Path for all file operations |
| IV. Versioned Schemas | PASS | Schema migration v5→v6 with transcription_results table |
| V. Idempotent Operations | PASS | Re-running transcription updates existing results |
| VI. IO Separation | PASS | TranscriptionPlugin interface separates core from backends |
| VII. Explicit Error Handling | PASS | Graceful failure handling per FR-014 |
| VIII. Structured Logging | PASS | Log transcription decisions with track/file IDs |
| IX. Configuration as Data | PASS | Plugin selection and model config in VPO config |
| X. Policy Stability | PASS | New policy options are additive, backward compatible |
| XI. Plugin Isolation | PASS | TranscriptionPlugin follows Protocol pattern |
| XII. Safe Concurrency | PASS | SQLite transactions for result persistence |
| XIII. Database Design | PASS | Foreign key to tracks, proper indexes |
| XIV. Test Media Corpus | PASS | Add test audio files for language detection |
| XV. Stable CLI/API Contracts | PASS | New `vpo transcribe` subcommand follows patterns |
| XVI. Dry-Run Default | PASS | Policy updates respect existing dry-run mode |
| XVII. Data Privacy | PASS | Whisper runs offline; cloud plugins require explicit config |
| XVIII. Living Documentation | PASS | Plugin SDK docs updated per FR-011 |

## Project Structure

### Documentation (this feature)

```text
specs/007-audio-transcription/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vpo/
├── transcription/                    # NEW: Core transcription module
│   ├── __init__.py
│   ├── interface.py                  # TranscriptionPlugin Protocol
│   ├── models.py                     # TranscriptionResult, TranscriptionConfig
│   ├── registry.py                   # Plugin discovery and selection
│   └── audio_extractor.py            # ffmpeg streaming audio extraction
├── plugins/
│   └── whisper_transcriber/          # NEW: Reference Whisper plugin
│       ├── __init__.py
│       └── plugin.py
├── policy/
│   ├── models.py                     # MODIFY: Add transcription policy options
│   └── evaluator.py                  # MODIFY: Handle language updates
├── db/
│   ├── schema.py                     # MODIFY: Add transcription_results table (v6)
│   └── models.py                     # MODIFY: Add TranscriptionResultRecord
├── cli/
│   └── transcribe.py                 # NEW: vpo transcribe subcommand
└── plugin_sdk/
    └── transcription.py              # NEW: SDK helpers for transcription plugins

tests/
├── unit/
│   └── transcription/
│       ├── test_interface.py
│       ├── test_models.py
│       ├── test_registry.py
│       └── test_audio_extractor.py
├── integration/
│   └── test_whisper_plugin.py
└── fixtures/
    └── audio/                        # Test audio files (short clips)
```

**Structure Decision**: Extends existing single-project structure. New `transcription/` module follows the pattern of existing modules (`introspector/`, `executor/`). Whisper plugin lives in `plugins/` alongside existing `policy_engine/` plugin.

## Complexity Tracking

> No constitution violations requiring justification.

| Decision | Rationale |
|----------|-----------|
| Separate `transcription/` module | Follows existing module patterns; keeps transcription logic isolated from introspection |
| Plugin in `plugins/` not external | Reference implementation; users can install external plugins via entry points |
| Stream audio via ffmpeg | Clarified in spec; avoids temp files, consistent with existing ffprobe pattern |
