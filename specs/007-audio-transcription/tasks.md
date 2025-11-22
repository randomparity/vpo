# Tasks: Audio Transcription & Language Detection

**Input**: Design documents from `/specs/007-audio-transcription/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Unit tests included as requested for core functionality.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Commits**: Per user request, commit code changes after completing each phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/video_policy_orchestrator/`, `tests/` at repository root
- Paths follow existing VPO module structure per plan.md

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create module structure and foundational files

- [X] T001 Create transcription module directory structure at `src/video_policy_orchestrator/transcription/`
- [X] T002 [P] Create `src/video_policy_orchestrator/transcription/__init__.py` with module exports
- [X] T003 [P] Create `src/video_policy_orchestrator/plugins/whisper_transcriber/__init__.py` with plugin exports
- [X] T004 [P] Create `tests/unit/transcription/` directory structure
- [X] T005 Commit Phase 1 changes: "feat(transcription): create module structure"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Add TrackClassification enum to `src/video_policy_orchestrator/db/models.py`
- [X] T007 Add TranscriptionResultRecord dataclass to `src/video_policy_orchestrator/db/models.py`
- [X] T008 Add TranscriptionResult domain model to `src/video_policy_orchestrator/transcription/models.py`
- [X] T009 Add TranscriptionConfig dataclass to `src/video_policy_orchestrator/transcription/models.py`
- [X] T010 Add transcription_results table schema (v5→v6 migration) in `src/video_policy_orchestrator/db/schema.py`
- [X] T011 Add CRUD operations for transcription_results in `src/video_policy_orchestrator/db/models.py`: upsert_transcription_result, get_transcription_result, delete_transcription_results_for_file
- [X] T012 [P] Add unit tests for TranscriptionResult model in `tests/unit/transcription/test_models.py`
- [X] T013 [P] Add unit tests for database operations in `tests/unit/db/test_transcription_operations.py`
- [X] T014 Commit Phase 2 changes: "feat(transcription): add data models and schema migration"

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Automatic Language Detection (Priority: P1) MVP

**Goal**: Detect spoken language in audio tracks and report with confidence scores

**Independent Test**: Run `vpo transcribe detect /path/to/file.mkv` and verify language detection output

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create TranscriptionPlugin Protocol in `src/video_policy_orchestrator/transcription/interface.py`
- [ ] T016 [P] [US1] Create TranscriptionError exception class in `src/video_policy_orchestrator/transcription/interface.py`
- [ ] T017 [US1] Implement audio_extractor module with ffmpeg streaming in `src/video_policy_orchestrator/transcription/audio_extractor.py`
- [ ] T018 [US1] Implement plugin registry with discovery/selection in `src/video_policy_orchestrator/transcription/registry.py`
- [ ] T019 [US1] Add `vpo transcribe detect` CLI command with `--force` flag to re-run even if results exist in `src/video_policy_orchestrator/cli/transcribe.py`
- [ ] T020 [US1] Register transcribe command in `src/video_policy_orchestrator/cli/__init__.py`
- [ ] T021 [P] [US1] Add unit tests for audio_extractor in `tests/unit/transcription/test_audio_extractor.py`
- [ ] T022 [P] [US1] Add unit tests for plugin registry in `tests/unit/transcription/test_registry.py`
- [ ] T023 [P] [US1] Add unit tests for interface protocol in `tests/unit/transcription/test_interface.py`
- [ ] T024 Commit Phase 3 changes: "feat(transcription): implement language detection core (US1)"

**Checkpoint**: User Story 1 complete - language detection works via CLI

---

## Phase 4: User Story 2 - Pluggable Transcription Engine (Priority: P2)

**Goal**: Enable multiple transcription backends through a stable plugin interface

**Independent Test**: Configure different plugins in config and verify each produces results through same interface

### Implementation for User Story 2

- [ ] T025 [US2] Add transcription plugin configuration to `src/video_policy_orchestrator/config/models.py`
- [ ] T026 [US2] Implement plugin loading from configuration in `src/video_policy_orchestrator/transcription/registry.py`
- [ ] T027 [US2] Add plugin availability check to `vpo doctor` in `src/video_policy_orchestrator/cli/doctor.py`
- [ ] T028 [US2] Create plugin SDK helpers in `src/video_policy_orchestrator/plugin_sdk/transcription.py`
- [ ] T029 [P] [US2] Add unit tests for plugin configuration loading in `tests/unit/config/test_transcription_config.py`
- [ ] T030 Commit Phase 4 changes: "feat(transcription): pluggable engine architecture (US2)"

**Checkpoint**: User Story 2 complete - plugin system allows swappable backends

---

## Phase 5: User Story 3 - Whisper-Based Local Transcription (Priority: P3)

**Goal**: Provide offline Whisper-based transcription as reference implementation

**Independent Test**: Install Whisper, run detection on test file, verify no network calls and correct language output

### Implementation for User Story 3

- [ ] T031 [US3] Implement WhisperTranscriptionPlugin class in `src/video_policy_orchestrator/plugins/whisper_transcriber/plugin.py`
- [ ] T032 [US3] Add model size configuration (tiny/base/small/medium/large) to Whisper plugin
- [ ] T033 [US3] Add GPU detection and configuration support to Whisper plugin
- [ ] T034 [US3] Implement audio sampling for long tracks (default 60s) in Whisper plugin
- [ ] T035 [US3] Register Whisper plugin in `src/video_policy_orchestrator/plugins/whisper_transcriber/__init__.py`
- [ ] T036 [P] [US3] Add integration tests for Whisper plugin in `tests/integration/test_whisper_plugin.py`
- [ ] T037 Commit Phase 5 changes: "feat(transcription): whisper reference plugin (US3)"

**Checkpoint**: User Story 3 complete - offline transcription works with Whisper

---

## Phase 6: User Story 4 - Policy-Driven Language Updates (Priority: P4)

**Goal**: Enable policy-based automatic language tag updates with confidence thresholds

**Independent Test**: Create policy with `update_language_from_transcription: true`, apply to file, verify language tag updated

### Implementation for User Story 4

- [ ] T038 [US4] Add TranscriptionPolicyOptions to `src/video_policy_orchestrator/policy/models.py`
- [ ] T039 [US4] Extend policy loader to parse transcription options in `src/video_policy_orchestrator/policy/loader.py`
- [ ] T040 [US4] Implement language update logic in policy evaluator `src/video_policy_orchestrator/policy/evaluator.py`
- [ ] T041 [US4] Add confidence threshold check before language updates
- [ ] T042 [US4] Add `--update` flag to `vpo transcribe detect` to apply updates directly
- [ ] T043 [P] [US4] Add unit tests for policy transcription options in `tests/unit/policy/test_transcription_policy.py`
- [ ] T044 Commit Phase 6 changes: "feat(transcription): policy-driven language updates (US4)"

**Checkpoint**: User Story 4 complete - policies can auto-update language tags

---

## Phase 7: User Story 5 - Commentary Track Detection (Priority: P5)

**Goal**: Identify commentary tracks via metadata keywords and optional transcript analysis

**Independent Test**: Process file with commentary track, verify it's flagged and optionally reordered

### Implementation for User Story 5

- [ ] T045 [US5] Add commentary keyword detection (metadata-based) in `src/video_policy_orchestrator/transcription/models.py`
- [ ] T046 [US5] Add transcript-based commentary pattern detection in Whisper plugin
- [ ] T047 [US5] Implement track reordering logic for commentary in `src/video_policy_orchestrator/policy/evaluator.py`
- [ ] T048 [US5] Add `detect_commentary` and `reorder_commentary` policy options handling
- [ ] T049 [P] [US5] Add unit tests for commentary detection in `tests/unit/transcription/test_commentary_detection.py`
- [ ] T050 Commit Phase 7 changes: "feat(transcription): commentary track detection (US5)"

**Checkpoint**: User Story 5 complete - commentary tracks identified and reordered

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: CLI completion, documentation, and final integration

- [ ] T051 [P] Implement `vpo transcribe status` subcommand in `src/video_policy_orchestrator/cli/transcribe.py`
- [ ] T052 [P] Implement `vpo transcribe clear` subcommand in `src/video_policy_orchestrator/cli/transcribe.py`
- [ ] T053 [P] Add `--json` output format to all transcribe subcommands
- [ ] T054 [P] Add `--dry-run` support to transcribe detect --update
- [ ] T055 Add structured logging for transcription operations (Constitution VIII)
- [ ] T056 [P] Update plugin SDK documentation for TranscriptionPlugin in `docs/`
- [ ] T057 [P] Add sample transcription policy to `examples/` directory
- [ ] T058 Run `uv run pytest` to verify all tests pass
- [ ] T059 Run `uv run ruff check .` and `uv run ruff format .` for code quality
- [ ] T060 Commit Phase 8 changes: "feat(transcription): CLI polish and documentation"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3-7 (User Stories)**: All depend on Phase 2 completion
  - User stories can proceed sequentially in priority order (P1 → P2 → P3 → P4 → P5)
  - Or in parallel if team capacity allows
- **Phase 8 (Polish)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundational only - core language detection
- **User Story 2 (P2)**: Foundational only - plugin architecture (parallel with US1)
- **User Story 3 (P3)**: Depends on US1 and US2 - Whisper implementation
- **User Story 4 (P4)**: Depends on US1 - policy integration
- **User Story 5 (P5)**: Depends on US1 and US3 - commentary detection

### Within Each Phase

- Tasks marked [P] can run in parallel
- Models/data before services
- Services before CLI
- Core implementation before tests

### Parallel Opportunities

Within Phase 2 (Foundational):
```
T006, T007, T008, T009 → T010 → T011 → [T012, T013]
```

Within Phase 3 (US1):
```
[T015, T016] → T017 → T018 → T019 → T020 → [T021, T022, T023]
```

---

## Parallel Example: Phase 2

```bash
# These can run in parallel (different files):
T012: Unit tests for TranscriptionResult model
T013: Unit tests for database operations
```

## Parallel Example: Phase 3 (US1)

```bash
# These can run in parallel:
T015: TranscriptionPlugin Protocol
T016: TranscriptionError exception

# After T017-T020 complete, these can run in parallel:
T021: Unit tests for audio_extractor
T022: Unit tests for plugin registry
T023: Unit tests for interface protocol
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1 (Language Detection)
4. **STOP and VALIDATE**: Test with `vpo transcribe detect`
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Language Detection) → Test → Commit → MVP!
3. Add US2 (Plugin Architecture) → Test → Commit
4. Add US3 (Whisper Plugin) → Test → Commit
5. Add US4 (Policy Updates) → Test → Commit
6. Add US5 (Commentary) → Test → Commit
7. Polish phase → Final commit

### Commit Strategy (Per User Request)

After each phase completion:
```bash
git add -A
git commit -m "<commit message from task>"
```

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label maps task to specific user story
- Each user story is independently testable after completion
- Commit after each phase as requested
- Stop at any checkpoint to validate story independently
- Whisper is optional dependency - tests should mock when not installed
