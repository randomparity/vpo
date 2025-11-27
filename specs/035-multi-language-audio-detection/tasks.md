# Tasks: Multi-Language Audio Detection

**Input**: Design documents from `/specs/035-multi-language-audio-detection/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included as specified in the Constitution (Principle XIV - Test Media Corpus) and quickstart.md testing strategy.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/video_policy_orchestrator/`, `tests/` at repository root
- Paths follow existing VPO structure per plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and module structure

- [X] T001 Create language_analysis module directory at src/video_policy_orchestrator/language_analysis/__init__.py
- [X] T002 [P] Create test directory structure at tests/unit/language_analysis/__init__.py
- [X] T003 [P] Create test fixtures directory at tests/fixtures/audio/ (empty, for test audio files)
- [X] T003a [P] Create single-language English test audio file (5-10 seconds of clear speech) at tests/fixtures/audio/single-language-en.wav
- [X] T003b [P] Create multi-language test audio file (English primary with French segment) at tests/fixtures/audio/multi-language-en-fr.wav
- [X] T003c [P] Create no-speech test audio file (music/effects only) at tests/fixtures/audio/no-speech.wav

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model and storage that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Database Schema & Models

- [X] T004 Add language_analysis_results table to src/video_policy_orchestrator/db/schema.py
- [X] T005 Add language_segments table to src/video_policy_orchestrator/db/schema.py
- [X] T006 Add LanguageAnalysisResultRecord dataclass to src/video_policy_orchestrator/db/models.py
- [X] T007 [P] Add LanguageSegmentRecord dataclass to src/video_policy_orchestrator/db/models.py

### Domain Models

- [X] T008 [P] Create LanguageClassification enum in src/video_policy_orchestrator/language_analysis/models.py
- [X] T009 [P] Create LanguageSegment dataclass with validation in src/video_policy_orchestrator/language_analysis/models.py
- [X] T010 [P] Create LanguagePercentage dataclass in src/video_policy_orchestrator/language_analysis/models.py
- [X] T011 [P] Create AnalysisMetadata dataclass in src/video_policy_orchestrator/language_analysis/models.py
- [X] T012 Create LanguageAnalysisResult dataclass with from_segments() method in src/video_policy_orchestrator/language_analysis/models.py

### Database Operations

- [X] T013 Add upsert_language_analysis_result() function to src/video_policy_orchestrator/db/models.py
- [X] T014 [P] Add get_language_analysis_result() function to src/video_policy_orchestrator/db/models.py
- [X] T015 [P] Add delete_language_analysis_result() function to src/video_policy_orchestrator/db/models.py
- [X] T016 Add upsert_language_segments() function to src/video_policy_orchestrator/db/models.py
- [X] T017 [P] Add get_language_segments() function to src/video_policy_orchestrator/db/models.py

### Unit Tests for Foundational Models

- [X] T018 [P] Add tests for LanguageSegment validation in tests/unit/language_analysis/test_models.py
- [X] T019 [P] Add tests for LanguageAnalysisResult.from_segments() in tests/unit/language_analysis/test_models.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Detect Multi-Language Audio (Priority: P1) MVP

**Goal**: Analyze audio tracks to detect language segments, identify primary/secondary languages, and classify tracks as SINGLE_LANGUAGE or MULTI_LANGUAGE.

**Independent Test**: Analyze a known multi-language audio file and verify the system correctly identifies each language segment with percentages.

### Plugin Protocol Extension

- [X] T020 [US1] Add detect_multi_language() method signature to TranscriptionPlugin protocol in src/video_policy_orchestrator/transcription/interface.py
- [X] T021 [US1] Add MultiLanguageDetectionResult dataclass to src/video_policy_orchestrator/transcription/interface.py
- [X] T022 [US1] Add "multi_language_detection" feature flag support in src/video_policy_orchestrator/transcription/interface.py

### Whisper Plugin Implementation

- [X] T023 [US1] Add calculate_sample_positions() helper function in src/video_policy_orchestrator/plugins/whisper_transcriber/plugin.py
- [X] T024 [US1] Implement detect_multi_language() in WhisperTranscriptionPlugin in src/video_policy_orchestrator/plugins/whisper_transcriber/plugin.py
- [X] T025 [US1] Add _extract_sample() helper for extracting audio at positions in src/video_policy_orchestrator/plugins/whisper_transcriber/plugin.py
- [X] T026 [US1] Add _aggregate_segments() to convert samples to LanguageAnalysisResult in src/video_policy_orchestrator/plugins/whisper_transcriber/plugin.py

### Service Layer

- [X] T027 [US1] Create analyze_track_languages() function in src/video_policy_orchestrator/language_analysis/service.py
- [X] T028 [US1] Add caching logic (check file hash before analysis) in src/video_policy_orchestrator/language_analysis/service.py
- [X] T029 [US1] Add result persistence (store to database) in src/video_policy_orchestrator/language_analysis/service.py

### CLI: Inspect Command

- [X] T030 [US1] Add --analyze-languages option to inspect command in src/video_policy_orchestrator/cli/inspect.py
- [X] T031 [US1] Add --show-segments option to display detailed segments in src/video_policy_orchestrator/cli/inspect.py
- [X] T032 [US1] Add language analysis output formatting in src/video_policy_orchestrator/cli/inspect.py

### CLI: Scan Command

- [ ] T033 [US1] Add --analyze-languages option to scan command in src/video_policy_orchestrator/cli/scan.py
- [ ] T034 [US1] Integrate language analysis service with scan workflow in src/video_policy_orchestrator/cli/scan.py
- [ ] T035 [US1] Add progress reporting for language analysis during scan in src/video_policy_orchestrator/cli/scan.py

### Unit Tests for User Story 1

- [X] T036 [P] [US1] Add tests for calculate_sample_positions() in tests/unit/plugins/test_whisper_transcriber.py
- [X] T037 [P] [US1] Add tests for detect_multi_language() with mock audio in tests/unit/plugins/test_whisper_transcriber.py
- [X] T038 [P] [US1] Add tests for analyze_track_languages() in tests/unit/language_analysis/test_service.py

**Checkpoint**: Language detection is functional via CLI. Can analyze files and see multi-language classification.

---

## Phase 4: User Story 2 - New Condition Type for Multi-Language Policies (Priority: P2)

**Goal**: Add `audio_is_multi_language` condition type to the conditional policy system, supporting boolean shorthand, thresholds, and primary language constraints.

**Independent Test**: Create a conditional policy with `audio_is_multi_language` conditions and verify it evaluates correctly against files with known language characteristics.

### Policy Condition Dataclass

- [ ] T039 [US2] Add AudioIsMultiLanguageCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [ ] T040 [US2] Update Condition union type to include AudioIsMultiLanguageCondition in src/video_policy_orchestrator/policy/models.py

### Policy Loader (Pydantic Validation)

- [ ] T041 [US2] Add AudioIsMultiLanguageModel Pydantic class in src/video_policy_orchestrator/policy/loader.py
- [ ] T042 [US2] Update ConditionModel to include audio_is_multi_language field in src/video_policy_orchestrator/policy/loader.py
- [ ] T043 [US2] Add _convert_audio_is_multi_language() conversion function in src/video_policy_orchestrator/policy/loader.py
- [ ] T044 [US2] Update _convert_condition() to handle audio_is_multi_language in src/video_policy_orchestrator/policy/loader.py

### Condition Evaluation

- [ ] T045 [US2] Add evaluate_audio_is_multi_language() function in src/video_policy_orchestrator/policy/conditions.py
- [ ] T046 [US2] Update evaluate_condition() to call evaluate_audio_is_multi_language() in src/video_policy_orchestrator/policy/conditions.py
- [ ] T047 [US2] Update condition evaluation to pass language_results parameter in src/video_policy_orchestrator/policy/conditions.py

### Policy Evaluator Integration

- [ ] T048 [US2] Update evaluate_conditional_rules() to fetch language analysis results in src/video_policy_orchestrator/policy/evaluator.py
- [ ] T049 [US2] Pass language_results to condition evaluation chain in src/video_policy_orchestrator/policy/evaluator.py

### Unit Tests for User Story 2

- [ ] T050 [P] [US2] Add tests for AudioIsMultiLanguageCondition parsing in tests/unit/policy/test_loader.py
- [ ] T051 [P] [US2] Add tests for evaluate_audio_is_multi_language() true case in tests/unit/policy/test_conditions.py
- [ ] T052 [P] [US2] Add tests for evaluate_audio_is_multi_language() false cases (threshold, primary language) in tests/unit/policy/test_conditions.py
- [ ] T053 [P] [US2] Add tests for audio_is_multi_language with boolean operators (and/or/not) in tests/unit/policy/test_conditions.py

**Checkpoint**: Policies with `audio_is_multi_language` conditions evaluate correctly. Can dry-run policies to see condition results.

---

## Phase 5: User Story 3 - Auto-Enable Forced Subtitles (Priority: P3)

**Goal**: Add `set_forced` and `set_default` policy actions to manipulate subtitle track flags based on multi-language conditions.

**Independent Test**: Apply a policy to a multi-language file that has a forced English subtitle track and verify the subtitle is set as default.

### Policy Action Dataclasses

- [ ] T054 [US3] Add SetForcedAction dataclass to src/video_policy_orchestrator/policy/models.py
- [ ] T055 [US3] Add SetDefaultAction dataclass to src/video_policy_orchestrator/policy/models.py
- [ ] T056 [US3] Update Action union type to include SetForcedAction and SetDefaultAction in src/video_policy_orchestrator/policy/models.py

### Policy Loader (Action Parsing)

- [ ] T057 [US3] Add SetForcedActionModel Pydantic class in src/video_policy_orchestrator/policy/loader.py
- [ ] T058 [US3] Add SetDefaultActionModel Pydantic class in src/video_policy_orchestrator/policy/loader.py
- [ ] T059 [US3] Update ActionModel to include set_forced and set_default fields in src/video_policy_orchestrator/policy/loader.py
- [ ] T060 [US3] Add _convert_set_forced_action() conversion function in src/video_policy_orchestrator/policy/loader.py
- [ ] T061 [US3] Add _convert_set_default_action() conversion function in src/video_policy_orchestrator/policy/loader.py
- [ ] T062 [US3] Update _convert_action() to handle set_forced and set_default in src/video_policy_orchestrator/policy/loader.py

### Action Execution

- [ ] T063 [US3] Add execute_set_forced_action() function in src/video_policy_orchestrator/policy/actions.py
- [ ] T064 [US3] Add execute_set_default_action() function in src/video_policy_orchestrator/policy/actions.py
- [ ] T065 [US3] Update execute_actions() dispatcher to handle set_forced and set_default in src/video_policy_orchestrator/policy/actions.py
- [ ] T066 [US3] Add warning when no matching track found for set_forced/set_default in src/video_policy_orchestrator/policy/actions.py

### CLI: Apply Command

- [ ] T067 [US3] Add --auto-analyze option to apply command in src/video_policy_orchestrator/cli/apply.py
- [ ] T068 [US3] Integrate auto-analysis with policy application in src/video_policy_orchestrator/cli/apply.py
- [ ] T069 [US3] Update dry-run output to show set_forced/set_default actions in src/video_policy_orchestrator/cli/apply.py

### Unit Tests for User Story 3

- [ ] T070 [P] [US3] Add tests for SetForcedAction parsing in tests/unit/policy/test_loader.py
- [ ] T071 [P] [US3] Add tests for SetDefaultAction parsing in tests/unit/policy/test_loader.py
- [ ] T072 [P] [US3] Add tests for execute_set_forced_action() in tests/unit/policy/test_actions.py
- [ ] T073 [P] [US3] Add tests for execute_set_default_action() in tests/unit/policy/test_actions.py
- [ ] T074 [P] [US3] Add tests for missing track warning in tests/unit/policy/test_actions.py

**Checkpoint**: Full policy pipeline works. Can apply policies that detect multi-language audio and enable forced subtitles.

---

## Phase 6: User Story 4 - Language Detection Integration with Transcription Plugin (Priority: P4)

**Goal**: Optimize language detection by reusing existing transcription results and implementing robust caching.

**Independent Test**: Run language detection on a file that already has transcription results and verify cached results are reused.

### Transcription Integration

- [ ] T075 [US4] Add check for existing transcription results in analyze_track_languages() in src/video_policy_orchestrator/language_analysis/service.py
- [ ] T076 [US4] Extract language from transcription_results when available in src/video_policy_orchestrator/language_analysis/service.py
- [ ] T077 [US4] Add logic to upgrade single-sample transcription to full analysis when needed in src/video_policy_orchestrator/language_analysis/service.py

### Cache Validation

- [ ] T078 [US4] Add file hash comparison for cache validation in src/video_policy_orchestrator/language_analysis/service.py
- [ ] T079 [US4] Add stale result detection and re-analysis trigger in src/video_policy_orchestrator/language_analysis/service.py

### CLI: Dedicated Analyze-Language Command

- [ ] T080 [US4] Create analyze_language.py CLI module in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T081 [US4] Add `run` subcommand for running language analysis in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T082 [US4] Add `status` subcommand for showing analysis status in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T083 [US4] Add `clear` subcommand for clearing cached results in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T084 [US4] Register analyze-language command group in src/video_policy_orchestrator/cli/__init__.py

### Unit Tests for User Story 4

- [ ] T085 [P] [US4] Add tests for transcription result reuse in tests/unit/language_analysis/test_service.py
- [ ] T086 [P] [US4] Add tests for cache validation logic in tests/unit/language_analysis/test_service.py
- [ ] T087 [P] [US4] Add tests for stale result detection in tests/unit/language_analysis/test_service.py

**Checkpoint**: Optimized analysis with caching. Transcription results are reused when available.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Schema version bump, documentation, and integration testing

### Schema Version

- [ ] T088 Update CURRENT_SCHEMA_VERSION to 7 in src/video_policy_orchestrator/policy/loader.py
- [ ] T089 Add V7 schema version validation for new features in src/video_policy_orchestrator/policy/loader.py
- [ ] T090 Ensure V6 policies continue to work (backward compatibility) in src/video_policy_orchestrator/policy/loader.py

### Integration Tests

- [ ] T091 [P] Create integration test for full scan with language analysis in tests/integration/test_language_analysis.py
- [ ] T092 [P] Create integration test for policy evaluation with audio_is_multi_language in tests/integration/test_language_analysis.py
- [ ] T093 Create integration test for end-to-end forced subtitle enablement in tests/integration/test_language_analysis.py

### Documentation

- [ ] T094 [P] Create example policy file at policies/examples/multi-language.yaml
- [ ] T095 [P] Update CLI help text for all new options in src/video_policy_orchestrator/cli/*.py
- [ ] T096 Add user documentation for multi-language detection in docs/usage/multi-language-detection.md

### Edge Case Handling

- [ ] T097 Add handling for audio with no speech (InsufficientSpeechError) in src/video_policy_orchestrator/language_analysis/service.py
- [ ] T098 Add handling for very short audio tracks (<30s) in src/video_policy_orchestrator/language_analysis/service.py
- [ ] T099 Add handling for Whisper model unavailable in src/video_policy_orchestrator/language_analysis/service.py
- [ ] T100 Add handling for multiple audio tracks (analyze each separately) in src/video_policy_orchestrator/language_analysis/service.py

**Edge Case Coverage Note**: The edge case "code-switching within sentences" (spec.md:89) is handled by T026 (`_aggregate_segments()`) which uses per-sample dominant language detection. Whisper naturally handles mixed-language samples by returning the dominant language for each 5-second sample.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (P1): Can start after Foundational
  - US2 (P2): Depends on US1 (needs language results to evaluate conditions)
  - US3 (P3): Depends on US2 (needs conditions to trigger actions)
  - US4 (P4): Can start after US1 (caching/optimization layer)
- **Polish (Phase 7)**: Depends on US1-US3 completion (US4 optional)

### User Story Dependencies

```
Phase 1: Setup
    │
    ▼
Phase 2: Foundational (BLOCKS ALL)
    │
    ├───────────────────────────────┐
    │                               │
    ▼                               ▼
Phase 3: US1 (Detection)        Phase 6: US4 (Caching)
    │                               │
    ▼                               │
Phase 4: US2 (Condition)            │
    │                               │
    ▼                               │
Phase 5: US3 (Actions)              │
    │                               │
    ├───────────────────────────────┘
    │
    ▼
Phase 7: Polish
```

### Within Each User Story

- Tests written first (TDD approach per constitution)
- Plugin/protocol changes before implementations
- Models before services
- Services before CLI integration
- Core implementation before optimization

### Parallel Opportunities

**Setup (Phase 1)**:
- T002, T003 can run in parallel

**Foundational (Phase 2)**:
- T006, T007 (database records) can run in parallel
- T008, T009, T010, T011 (domain models) can run in parallel
- T014, T015 (get/delete operations) can run in parallel after T013
- T018, T019 (tests) can run in parallel

**User Story 1 (Phase 3)**:
- T036, T037, T038 (tests) can run in parallel

**User Story 2 (Phase 4)**:
- T050, T051, T052, T053 (tests) can run in parallel

**User Story 3 (Phase 5)**:
- T070, T071, T072, T073, T074 (tests) can run in parallel

**User Story 4 (Phase 6)**:
- T085, T086, T087 (tests) can run in parallel

**Polish (Phase 7)**:
- T091, T092 (integration tests) can run in parallel
- T094, T095 (documentation) can run in parallel

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests for User Story 1 together:
Task: "Add tests for calculate_sample_positions() in tests/unit/plugins/test_whisper_transcriber.py"
Task: "Add tests for detect_multi_language() with mock audio in tests/unit/plugins/test_whisper_transcriber.py"
Task: "Add tests for analyze_track_languages() in tests/unit/language_analysis/test_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 - Detection
4. **STOP and VALIDATE**: Test language detection via `vpo inspect --analyze-languages`
5. Can demo language detection capability

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test detection → Demo (MVP!)
3. Add User Story 2 → Test conditions → Demo (policy evaluation)
4. Add User Story 3 → Test actions → Demo (full workflow)
5. Add User Story 4 → Test caching → Performance optimization
6. Polish → Production ready

### Suggested MVP Scope

**Minimum for Value**: User Stories 1 + 2 + 3
- US1 provides detection capability
- US2 enables policy conditions
- US3 delivers end-user value (automatic forced subtitles)
- US4 is optimization (nice-to-have)

---

## Summary

| Phase | Tasks | Parallel Tasks | Description |
|-------|-------|----------------|-------------|
| Setup | 6 | 5 | Module structure + test fixtures |
| Foundational | 16 | 10 | Database + domain models |
| US1 (Detection) | 19 | 3 | Language detection core |
| US2 (Condition) | 15 | 4 | Policy condition type |
| US3 (Actions) | 21 | 5 | Policy actions |
| US4 (Caching) | 13 | 3 | Optimization layer |
| Polish | 13 | 5 | Schema, docs, edge cases |
| **Total** | **103** | **35** | |

**Independent Test Criteria**:
- US1: Run `vpo inspect --analyze-languages` on multi-language file
- US2: Create policy with `audio_is_multi_language` condition, verify evaluation
- US3: Apply policy to set forced subtitles, verify track flags change
- US4: Analyze file twice, verify second analysis uses cache
