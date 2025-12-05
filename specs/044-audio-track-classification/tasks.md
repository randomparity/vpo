# Tasks: Audio Track Classification

**Input**: Design documents from `/specs/044-audio-track-classification/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create module structure and package initialization

- [X] T001 Create track_classification module directory at src/video_policy_orchestrator/track_classification/
- [X] T002 [P] Create __init__.py skeleton (empty or minimal) in src/video_policy_orchestrator/track_classification/__init__.py
- [X] T003 [P] Create test directory at tests/unit/track_classification/
- [X] T004 [P] Create test fixtures directory at tests/fixtures/classification/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Add OriginalDubbedStatus enum to src/video_policy_orchestrator/db/types.py
- [X] T006 [P] Add CommentaryStatus enum to src/video_policy_orchestrator/db/types.py
- [X] T007 [P] Add DetectionMethod enum to src/video_policy_orchestrator/db/types.py
- [X] T008 Add TrackClassificationRecord dataclass to src/video_policy_orchestrator/db/types.py
- [X] T009 Create AcousticProfile dataclass in src/video_policy_orchestrator/track_classification/models.py
- [X] T010 [P] Create TrackClassificationResult dataclass in src/video_policy_orchestrator/track_classification/models.py
- [X] T011 Bump SCHEMA_VERSION to 19 and add track_classification_results table in src/video_policy_orchestrator/db/schema.py
- [X] T012 Add migration logic for version 18→19 in src/video_policy_orchestrator/db/schema.py
- [X] T013 Add upsert_track_classification() function in src/video_policy_orchestrator/db/queries.py
- [X] T014 [P] Add get_track_classification() function in src/video_policy_orchestrator/db/queries.py
- [X] T015 [P] Add delete_track_classification() function in src/video_policy_orchestrator/db/queries.py
- [X] T016 [P] Add get_classifications_for_file() function in src/video_policy_orchestrator/db/queries.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Identify Dubbed vs Original Audio Track (Priority: P1)

**Goal**: Identify which audio tracks are original theatrical audio versus dubbed versions using external metadata as primary signal

**Independent Test**: Analyze a video file with Japanese (original) and English (dubbed) audio tracks and verify correct classification

### Implementation for User Story 1

- [X] T017 [US1] Create get_original_language_from_metadata() in src/video_policy_orchestrator/track_classification/metadata.py
- [X] T018 [US1] Create determine_original_track() applying detection priority (metadata > position > acoustic) in src/video_policy_orchestrator/track_classification/metadata.py
- [X] T019 [US1] Create classify_track() main classification function (integrating with language_analysis results per FR-008) in src/video_policy_orchestrator/track_classification/service.py
- [X] T020 [US1] Create classify_file_tracks() for batch classification in src/video_policy_orchestrator/track_classification/service.py
- [X] T021 [US1] Add cache checking logic (file hash validation) in src/video_policy_orchestrator/track_classification/service.py
- [X] T022 [US1] Add result persistence to database in src/video_policy_orchestrator/track_classification/service.py
- [X] T023 [US1] Handle edge case: single audio track defaults to "original" with low confidence in src/video_policy_orchestrator/track_classification/service.py
- [X] T024 [US1] Handle edge case: identical tracks (theatrical vs extended) both marked "original" in src/video_policy_orchestrator/track_classification/service.py
- [ ] T025 [US1] Add --classify-tracks option to inspect command in src/video_policy_orchestrator/cli/inspect.py
- [ ] T026 [US1] Add classification output formatting showing original/dubbed status in src/video_policy_orchestrator/cli/inspect.py
- [X] T027 [US1] Create test fixture for Japanese anime with original/dubbed tracks at tests/fixtures/classification/original-japanese.json
- [X] T028 [US1] Create test fixture for English original with dubbed tracks at tests/fixtures/classification/dubbed-english.json

**Checkpoint**: User Story 1 complete - original/dubbed detection works independently

---

## Phase 4: User Story 2 - Detect Commentary Tracks by Audio Characteristics (Priority: P2)

**Goal**: Identify commentary tracks based on acoustic analysis (speech density, dynamic range, voice count) when metadata is absent

**Independent Test**: Analyze an unlabeled commentary track and verify acoustic detection identifies it as commentary

### Implementation for User Story 2

- [X] T029 [US2] Create extract_acoustic_profile() analyzing speech density and dynamic range in src/video_policy_orchestrator/track_classification/acoustic.py
- [X] T030 [US2] Create is_commentary_by_acoustic() evaluating profile for commentary indicators in src/video_policy_orchestrator/track_classification/acoustic.py
- [X] T031 [US2] Add get_acoustic_profile() method signature to TranscriptionPlugin protocol in src/video_policy_orchestrator/transcription/interface.py
- [X] T032 [US2] Add "acoustic_analysis" feature flag to TranscriptionPlugin in src/video_policy_orchestrator/transcription/interface.py
- [ ] T033 [US2] Implement get_acoustic_profile() in Whisper plugin in src/video_policy_orchestrator/plugins/whisper_transcriber/plugin.py
- [X] T034 [US2] Integrate acoustic analysis into classify_track() for commentary detection in src/video_policy_orchestrator/track_classification/service.py
- [X] T035 [US2] Handle edge case: acoustic analysis fallback when metadata absent in src/video_policy_orchestrator/track_classification/service.py
- [X] T036 [US2] Handle edge case: mixed content (commentary over movie audio) in src/video_policy_orchestrator/track_classification/service.py
- [X] T037 [US2] Handle edge case: analysis failure fallback to metadata-only in src/video_policy_orchestrator/track_classification/service.py
- [ ] T038 [US2] Add --show-acoustic option to display acoustic profile details in src/video_policy_orchestrator/cli/inspect.py
- [X] T039 [US2] Create test fixture for commentary acoustic profile at tests/fixtures/classification/commentary-profile.json

**Checkpoint**: User Story 2 complete - commentary detection via acoustics works independently

---

## Phase 5: User Story 3 - Use Track Classification in Policies (Priority: P3)

**Goal**: Add is_original and is_dubbed policy conditions to enable automated track organization based on classification results

**Independent Test**: Create a policy with `is_original: true` condition and verify it matches only tracks classified as original

**Note**: This story depends on US1 and US2 for classification data, but the policy conditions themselves are independently testable with mocked classification results

### Implementation for User Story 3

- [ ] T040 [US3] Add IsOriginalCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [ ] T041 [P] [US3] Add IsDubbedCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [ ] T042 [US3] Update Condition union type to include new conditions in src/video_policy_orchestrator/policy/models.py
- [ ] T043 [US3] Add IsOriginalModel Pydantic validation model in src/video_policy_orchestrator/policy/loader.py
- [ ] T044 [P] [US3] Add IsDubbedModel Pydantic validation model in src/video_policy_orchestrator/policy/loader.py
- [ ] T045 [US3] Update ConditionModel to include is_original and is_dubbed in src/video_policy_orchestrator/policy/loader.py
- [ ] T046 [US3] Add _convert_is_original() conversion function in src/video_policy_orchestrator/policy/loader.py
- [ ] T047 [P] [US3] Add _convert_is_dubbed() conversion function in src/video_policy_orchestrator/policy/loader.py
- [ ] T048 [US3] Add evaluate_is_original() function in src/video_policy_orchestrator/policy/conditions.py
- [ ] T049 [P] [US3] Add evaluate_is_dubbed() function in src/video_policy_orchestrator/policy/conditions.py
- [ ] T050 [US3] Update evaluate_condition() to handle IsOriginalCondition and IsDubbedCondition in src/video_policy_orchestrator/policy/conditions.py
- [ ] T051 [US3] Update policy evaluator to fetch classification results when needed in src/video_policy_orchestrator/policy/evaluator.py
- [ ] T052 [US3] Pass classification_results to condition evaluation chain in src/video_policy_orchestrator/policy/evaluator.py
- [ ] T053 [US3] Implement 70% default confidence threshold per clarification in src/video_policy_orchestrator/policy/conditions.py
- [ ] T054 [US3] Add is_original/is_dubbed to audio order and default filter support in src/video_policy_orchestrator/policy/evaluator.py

**Checkpoint**: User Story 3 complete - policy conditions evaluate correctly

---

## Phase 6: CLI Integration & Commands

**Purpose**: Dedicated classify command and scan integration

- [ ] T055 Create classify command group skeleton in src/video_policy_orchestrator/cli/classify.py
- [ ] T056 Implement `vpo classify run` subcommand in src/video_policy_orchestrator/cli/classify.py
- [ ] T057 Implement `vpo classify status` subcommand in src/video_policy_orchestrator/cli/classify.py
- [ ] T058 Implement `vpo classify clear` subcommand in src/video_policy_orchestrator/cli/classify.py
- [ ] T059 Add --classify-tracks option to scan command in src/video_policy_orchestrator/cli/scan.py
- [ ] T060 Register classify command group in src/video_policy_orchestrator/cli/__init__.py
- [ ] T061 Add exit codes (0=success, 2=not found, 3=no tracks, 4=failed) in src/video_policy_orchestrator/cli/classify.py

**Checkpoint**: Full CLI support available

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and refinements

- [ ] T062 [P] Add structured logging for classification decisions in src/video_policy_orchestrator/track_classification/service.py
- [ ] T063 [P] Add ClassificationError and InsufficientDataError exceptions in src/video_policy_orchestrator/track_classification/models.py
- [ ] T064 Update db/__init__.py to export new types in src/video_policy_orchestrator/db/__init__.py
- [ ] T065 Update track_classification/__init__.py with public API exports in src/video_policy_orchestrator/track_classification/__init__.py
- [ ] T066 [P] Run quickstart.md validation (manual verification of documented commands)
- [ ] T067 Verify schema migration works on existing databases

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 can start after Foundational
  - US2 can start after Foundational (independent of US1)
  - US3 technically depends on US1/US2 data but conditions can be tested with mocks
- **CLI Integration (Phase 6)**: Depends on US1, US2 core service being complete
- **Polish (Phase 7)**: Can start after user stories are complete

### User Story Dependencies

- **User Story 1 (P1)**: Requires Foundational - No dependencies on other stories
- **User Story 2 (P2)**: Requires Foundational - Extends service.py but independent test path
- **User Story 3 (P3)**: Requires US1/US2 for real data, but policy conditions testable with mocked classification

### Within Each User Story

- Models before services (T009-T010 before T019)
- Service layer before CLI integration (T019-T024 before T025-T026)
- Core implementation before edge cases

### Parallel Opportunities

**Setup Phase**:
- T002, T003, T004 all [P]

**Foundational Phase**:
- T006, T007 can run in parallel with T005
- T014, T015, T016 can run in parallel after T013

**User Story 3**:
- T040, T041 in parallel
- T043, T044 in parallel
- T046, T047 in parallel
- T048, T049 in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch enum definitions together:
Task: "Add OriginalDubbedStatus enum to src/video_policy_orchestrator/db/types.py"
Task: "Add CommentaryStatus enum to src/video_policy_orchestrator/db/types.py"
Task: "Add DetectionMethod enum to src/video_policy_orchestrator/db/types.py"

# After enums, launch models together:
Task: "Create AcousticProfile dataclass in src/video_policy_orchestrator/track_classification/models.py"
Task: "Create TrackClassificationResult dataclass in src/video_policy_orchestrator/track_classification/models.py"
```

---

## Parallel Example: User Story 3 Policy Conditions

```bash
# Launch condition dataclasses together:
Task: "Add IsOriginalCondition dataclass to src/video_policy_orchestrator/policy/models.py"
Task: "Add IsDubbedCondition dataclass to src/video_policy_orchestrator/policy/models.py"

# Launch Pydantic models together:
Task: "Add IsOriginalModel Pydantic validation model in src/video_policy_orchestrator/policy/loader.py"
Task: "Add IsDubbedModel Pydantic validation model in src/video_policy_orchestrator/policy/loader.py"

# Launch evaluation functions together:
Task: "Add evaluate_is_original() function in src/video_policy_orchestrator/policy/conditions.py"
Task: "Add evaluate_is_dubbed() function in src/video_policy_orchestrator/policy/conditions.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test with `vpo inspect --classify-tracks`
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy (original/dubbed detection MVP!)
3. Add User Story 2 → Test independently → Deploy (adds commentary acoustic detection)
4. Add User Story 3 → Test independently → Deploy (policy integration)
5. Add Phase 6 → Full CLI support
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (original/dubbed detection)
   - Developer B: User Story 2 (commentary acoustic analysis)
   - Developer C: User Story 3 (policy conditions) - can use mocked data
3. Stories complete and integrate

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Tests are not included (not explicitly requested in spec)
- Total tasks: 67
  - Setup: 4 tasks
  - Foundational: 12 tasks
  - User Story 1: 12 tasks
  - User Story 2: 11 tasks
  - User Story 3: 15 tasks
  - CLI Integration: 7 tasks
  - Polish: 6 tasks
