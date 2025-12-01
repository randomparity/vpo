# Tasks: User-Defined Processing Phases

**Input**: Design documents from `/specs/037-user-defined-phases/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api.md

**Tests**: Not explicitly requested in the specification. Test tasks are NOT included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and V11 schema foundation

- [x] T001 Create V11 policy test fixtures directory at tests/fixtures/policies/v11/
- [x] T002 [P] Create basic V11 policy fixture with single phase at tests/fixtures/policies/v11/single-phase.yaml
- [x] T003 [P] Create multi-phase V11 policy fixture at tests/fixtures/policies/v11/multi-phase.yaml
- [x] T004 [P] Create complete V11 policy fixture with all operations at tests/fixtures/policies/v11/complete.yaml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and enums that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Add OperationType enum to src/video_policy_orchestrator/policy/models.py with canonical execution order constant
- [x] T006 [P] Add OnErrorMode enum to src/video_policy_orchestrator/policy/models.py (skip, continue, fail)
- [x] T007 [P] Add GlobalConfig frozen dataclass to src/video_policy_orchestrator/policy/models.py
- [x] T008 [P] Add PhaseDefinition frozen dataclass to src/video_policy_orchestrator/policy/models.py
- [x] T009 Add PolicySchema frozen dataclass (V11) to src/video_policy_orchestrator/policy/models.py with phase_names property and get_phase() method
- [x] T010 [P] Add PhaseExecutionContext mutable dataclass to src/video_policy_orchestrator/policy/models.py
- [x] T011 [P] Add PhaseResult frozen dataclass to src/video_policy_orchestrator/policy/models.py
- [x] T012 [P] Add FileProcessingResult frozen dataclass to src/video_policy_orchestrator/policy/models.py
- [x] T013 [P] Add PhaseExecutionError exception class to src/video_policy_orchestrator/policy/models.py
- [x] T014 Add Pydantic GlobalConfigModel to src/video_policy_orchestrator/policy/loader.py
- [x] T015 Add Pydantic PhaseModel to src/video_policy_orchestrator/policy/loader.py with name pattern validation and reserved word check
- [x] T016 Update PolicyModel in src/video_policy_orchestrator/policy/loader.py to support V11 schema with phases array and unique name validation
- [x] T017 Update MAX_SCHEMA_VERSION constant to 11 in src/video_policy_orchestrator/policy/loader.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Single Command Media Normalization (Priority: P0) MVP

**Goal**: Run `vpo process -p policy.yaml /path/to/video.mkv` and execute all phases in order without additional flags

**Independent Test**: Create a V11 policy with multiple phases, run `vpo process`, verify all phases execute in order and output file reflects all transformations

### Implementation for User Story 1

- [ ] T018 Create workflow/phases/ directory at src/video_policy_orchestrator/workflow/phases/
- [ ] T019 [P] [US1] Create BasePhase protocol/abstract class in src/video_policy_orchestrator/workflow/phases/base.py
- [ ] T020 [US1] Create PhaseExecutor class in src/video_policy_orchestrator/workflow/phases/executor.py implementing execute_phase() and rollback_phase() methods
- [ ] T021 [US1] Add phase-level backup creation in PhaseExecutor.execute_phase() in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T022 [US1] Add canonical operation ordering logic to PhaseExecutor in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T023 [US1] Implement operation dispatch to existing executors in PhaseExecutor in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T024 [US1] Implement rollback_phase() with backup restoration in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T025 [US1] Update WorkflowProcessor in src/video_policy_orchestrator/workflow/processor.py to accept PolicySchema V11
- [ ] T026 [US1] Replace ProcessingPhase enum dispatch with dynamic phase name lookup in src/video_policy_orchestrator/workflow/processor.py
- [ ] T027 [US1] Implement sequential phase execution loop in WorkflowProcessor.process_file() in src/video_policy_orchestrator/workflow/processor.py
- [ ] T028 [US1] Add file_modified tracking and re-introspection between phases in src/video_policy_orchestrator/workflow/processor.py
- [ ] T029 [US1] Implement on_error handling (skip, continue, fail) in WorkflowProcessor in src/video_policy_orchestrator/workflow/processor.py
- [ ] T030 [US1] Update or create vpo process command in src/video_policy_orchestrator/cli/process.py with policy file loading
- [ ] T031 [US1] Add V11 policy validation in vpo process command in src/video_policy_orchestrator/cli/process.py
- [ ] T032 [US1] Implement file processing with WorkflowProcessor in src/video_policy_orchestrator/cli/process.py
- [ ] T033 [US1] Add JSON output format (--json flag) in src/video_policy_orchestrator/cli/process.py per contracts/api.md
- [ ] T034 [US1] Add exit codes per CLI contract (0, 1, 2, 3) in src/video_policy_orchestrator/cli/process.py

**Checkpoint**: `vpo process -p policy.yaml /path/to/file.mkv` executes all phases in order

---

## Phase 4: User Story 2 - Custom Phase Names (Priority: P1)

**Goal**: Users can name phases descriptively (e.g., "cleanup", "enhance", "compress") and names appear in logs/output

**Independent Test**: Create a policy with custom-named phases, verify names appear in logs and error messages

### Implementation for User Story 2

- [ ] T035 [P] [US2] Add phase name pattern validation (^[a-zA-Z][a-zA-Z0-9_-]{0,63}$) to PhaseModel in src/video_policy_orchestrator/policy/loader.py
- [ ] T036 [P] [US2] Add reserved word rejection (config, schema_version, phases) to PhaseModel in src/video_policy_orchestrator/policy/loader.py
- [ ] T037 [US2] Add phase name and index to structured logging in PhaseExecutor in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T038 [US2] Add phase name to console output (Phase 1/4 [cleanup]: ...) in src/video_policy_orchestrator/cli/process.py
- [ ] T039 [US2] Include phase names in JSON output per contracts/api.md in src/video_policy_orchestrator/cli/process.py
- [ ] T040 [US2] Add descriptive error messages with phase name for validation failures in src/video_policy_orchestrator/policy/loader.py

**Checkpoint**: Custom phase names appear correctly in all output and validation errors are descriptive

---

## Phase 5: User Story 3 - Operation Flexibility (Priority: P1)

**Goal**: Any operation can appear in any phase; users control exactly when each operation runs

**Independent Test**: Create policies with operations in non-traditional configurations, verify they execute correctly

### Implementation for User Story 3

- [ ] T041 [P] [US3] Ensure container operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T042 [P] [US3] Ensure audio_filter operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T043 [P] [US3] Ensure subtitle_filter operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T044 [P] [US3] Ensure attachment_filter operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T045 [P] [US3] Ensure track_order operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T046 [P] [US3] Ensure default_flags operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T047 [P] [US3] Ensure conditional operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T048 [P] [US3] Ensure audio_synthesis operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T049 [P] [US3] Ensure transcode operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T050 [P] [US3] Ensure transcription operation is dispatchable from any phase in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T051 [US3] Add multiple operations per phase support in PhaseExecutor in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T052 [US3] Add empty phase handling (skip with warning) in src/video_policy_orchestrator/workflow/phases/executor.py

**Checkpoint**: All operations work in any phase configuration, multiple operations per phase work

---

## Phase 6: User Story 4 - Global Configuration (Priority: P2)

**Goal**: Settings like language preferences defined once in config section, shared across all phases

**Independent Test**: Create policy with global config, verify all phases use those settings without per-phase configuration

### Implementation for User Story 4

- [ ] T053 [P] [US4] Add audio_language_preference to GlobalConfig and GlobalConfigModel in src/video_policy_orchestrator/policy/models.py and loader.py
- [ ] T054 [P] [US4] Add subtitle_language_preference to GlobalConfig and GlobalConfigModel in src/video_policy_orchestrator/policy/models.py and loader.py
- [ ] T055 [P] [US4] Add commentary_patterns to GlobalConfig and GlobalConfigModel in src/video_policy_orchestrator/policy/models.py and loader.py
- [ ] T056 [P] [US4] Add on_error to GlobalConfig and GlobalConfigModel in src/video_policy_orchestrator/policy/models.py and loader.py
- [ ] T057 [US4] Pass global config to PhaseExecutionContext in src/video_policy_orchestrator/workflow/processor.py
- [ ] T058 [US4] Make operations use global config when per-phase config not specified in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T059 [US4] Add validation for required global config when operations need it (FR-009) in src/video_policy_orchestrator/policy/loader.py

**Checkpoint**: Global config works across all phases, operations inherit settings correctly

---

## Phase 7: User Story 5 - Selective Phase Execution (Priority: P2)

**Goal**: Run only specific phases using --phases flag for incremental processing

**Independent Test**: Run `vpo process --phases transcode` and verify only the transcode phase executes

### Implementation for User Story 5

- [ ] T060 [US5] Add --phases CLI option accepting comma-separated names in src/video_policy_orchestrator/cli/process.py
- [ ] T061 [US5] Validate --phases names against policy's phases list in src/video_policy_orchestrator/cli/process.py
- [ ] T062 [US5] Add phase_filter parameter to WorkflowProcessor.__init__() in src/video_policy_orchestrator/workflow/processor.py
- [ ] T063 [US5] Filter phases in process_file() respecting policy-defined order in src/video_policy_orchestrator/workflow/processor.py
- [ ] T064 [US5] Add error exit code 3 for invalid phase names in src/video_policy_orchestrator/cli/process.py
- [ ] T065 [US5] Update JSON output to indicate filtered phases in src/video_policy_orchestrator/cli/process.py

**Checkpoint**: --phases flag works correctly, filters execute in policy order, invalid names error properly

---

## Phase 8: User Story 6 - GUI Phase Editor (Priority: P3)

**Goal**: Add/remove/reorder phases visually in web UI without writing YAML manually

**Independent Test**: Use web UI to create a multi-phase policy, save it, verify YAML output is valid and matches GUI

### Implementation for User Story 6

- [ ] T066 [US6] Update GET /api/policies/{name} to include phases list in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T067 [US6] Update PUT /api/policies/{name} to handle V11 phases in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T068 [US6] Update POST /api/policies/{name}/validate to validate V11 phases in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T069 [US6] Add phase-specific validation errors to API responses in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T070 [US6] Update PolicyRoundTripEditor to preserve V11 phase structure in src/video_policy_orchestrator/policy/editor.py
- [ ] T071 [US6] Create section-phases.js for phase GUI components in src/video_policy_orchestrator/server/static/js/policy-editor/section-phases.js
- [ ] T072 [US6] Add "Add Phase" button handler in section-phases.js
- [ ] T073 [US6] Add phase name input field with validation in section-phases.js
- [ ] T074 [US6] Add operation toggles for each phase in section-phases.js
- [ ] T075 [US6] Add drag-and-drop phase reordering in section-phases.js
- [ ] T076 [US6] Add phase delete functionality in section-phases.js
- [ ] T077 [US6] Add real-time YAML preview updates for phases in section-phases.js
- [ ] T078 [US6] Update policy_editor.html template to include phases section in src/video_policy_orchestrator/server/ui/templates/sections/policy_editor.html
- [ ] T079 [US6] Add CSS styling for phase editor in src/video_policy_orchestrator/server/static/css/

**Checkpoint**: Phase editor GUI fully functional for creating, editing, and reordering phases

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T080 [P] Add V11 schema documentation examples to docs/usage/policy-editor.md
- [ ] T081 [P] Update docs/overview/ with V11 phase system overview
- [ ] T082 [P] Add migration guide from V10 to V11 in docs/usage/
- [ ] T083 Run all quickstart.md scenarios to validate feature completeness
- [ ] T084 Performance validation: verify < 100ms phase dispatch overhead for 10 phases
- [ ] T085 Performance validation: verify < 1s policy validation for 20 phases

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-8)**: All depend on Foundational phase completion
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P0)**: Can start after Foundational (Phase 2) - Core MVP functionality
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Enhances US1 with naming
- **User Story 3 (P1)**: Can start after Foundational (Phase 2) - Extends US1 operation flexibility
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - Adds global config to US1
- **User Story 5 (P2)**: Depends on US1 completion - Adds filtering to existing phase execution
- **User Story 6 (P3)**: Depends on US1-US4 completion - GUI for existing functionality

### Within Each User Story

- Models/dataclasses before services/executors
- Core implementation before CLI integration
- CLI before web UI
- Each story should be independently testable at its checkpoint

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002, T003, T004)
- All Foundational tasks marked [P] can run in parallel (T006, T007, T008, T010, T011, T012, T013)
- US2 tasks T035, T036 can run in parallel
- US3 tasks T041-T050 can run in parallel (all operation dispatchers)
- US4 tasks T053-T056 can run in parallel (all config fields)
- US6 tasks T066-T069 (API updates) can run in parallel with T070-T079 (frontend)

---

## Parallel Example: Foundational Phase

```bash
# Launch all independent dataclass definitions together:
Task: "Add OnErrorMode enum to src/video_policy_orchestrator/policy/models.py"
Task: "Add GlobalConfig frozen dataclass to src/video_policy_orchestrator/policy/models.py"
Task: "Add PhaseDefinition frozen dataclass to src/video_policy_orchestrator/policy/models.py"
Task: "Add PhaseExecutionContext mutable dataclass to src/video_policy_orchestrator/policy/models.py"
Task: "Add PhaseResult frozen dataclass to src/video_policy_orchestrator/policy/models.py"
Task: "Add FileProcessingResult frozen dataclass to src/video_policy_orchestrator/policy/models.py"
Task: "Add PhaseExecutionError exception class to src/video_policy_orchestrator/policy/models.py"
```

---

## Parallel Example: User Story 3 (Operation Flexibility)

```bash
# Launch all operation dispatcher tasks together:
Task: "Ensure container operation is dispatchable from any phase"
Task: "Ensure audio_filter operation is dispatchable from any phase"
Task: "Ensure subtitle_filter operation is dispatchable from any phase"
Task: "Ensure attachment_filter operation is dispatchable from any phase"
Task: "Ensure track_order operation is dispatchable from any phase"
Task: "Ensure default_flags operation is dispatchable from any phase"
Task: "Ensure conditional operation is dispatchable from any phase"
Task: "Ensure audio_synthesis operation is dispatchable from any phase"
Task: "Ensure transcode operation is dispatchable from any phase"
Task: "Ensure transcription operation is dispatchable from any phase"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (fixtures)
2. Complete Phase 2: Foundational (dataclasses, Pydantic models)
3. Complete Phase 3: User Story 1 (core phase execution)
4. **STOP and VALIDATE**: Run `vpo process -p v11-policy.yaml /test/video.mkv`
5. MVP is shippable at this point

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test phase execution -> **MVP Ready**
3. Add User Story 2 -> Test custom naming in logs -> Enhanced logging
4. Add User Story 3 -> Test operation flexibility -> Full operation support
5. Add User Story 4 -> Test global config -> Config usability
6. Add User Story 5 -> Test --phases flag -> Selective execution
7. Add User Story 6 -> Test GUI -> Full web UI support

### Suggested MVP Scope

**MVP = Setup + Foundational + User Story 1 (T001-T034)**

This delivers:
- V11 schema parsing and validation
- Multi-phase execution in order
- Rollback on failure
- Basic CLI with JSON output
- Exit codes per contract

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Tests not included (not requested in spec) - add if needed during implementation
