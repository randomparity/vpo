# Tasks: Conditional Phase Execution

**Input**: Design documents from `/specs/043-conditional-phases/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included as this feature modifies core workflow logic and requires validation of edge cases.

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

**Purpose**: Project initialization and test fixtures

- [ ] T001 Create test policy fixtures directory at tests/fixtures/policies/v12/conditional-phases/
- [ ] T002 [P] Create skip condition test policy at tests/fixtures/policies/v12/conditional-phases/skip-when-basic.yaml
- [ ] T003 [P] Create dependency test policy at tests/fixtures/policies/v12/conditional-phases/depends-on-basic.yaml
- [ ] T004 [P] Create error handling test policy at tests/fixtures/policies/v12/conditional-phases/on-error-override.yaml
- [ ] T005 [P] Create run_if test policy at tests/fixtures/policies/v12/conditional-phases/run-if-modified.yaml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and enums that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Add PhaseOutcome enum (PENDING, COMPLETED, FAILED, SKIPPED) to src/video_policy_orchestrator/policy/models.py
- [ ] T007 Add SkipReasonType enum (CONDITION, DEPENDENCY, ERROR_MODE, RUN_IF) to src/video_policy_orchestrator/policy/models.py
- [ ] T008 Add SkipReason dataclass to src/video_policy_orchestrator/policy/models.py
- [ ] T009 Extend PhaseResult dataclass with outcome and skip_reason fields in src/video_policy_orchestrator/policy/models.py
- [ ] T010 Add unit tests for PhaseOutcome and SkipReason in tests/unit/policy/test_phase_outcome.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Skip Expensive Phases (Priority: P0) 🎯 MVP

**Goal**: Skip phases based on file characteristics using `skip_when` conditions

**Independent Test**: Create a policy with `skip_when: { video_codec: [hevc] }`, process an HEVC file, verify phase skips with log message

### Tests for User Story 1

- [ ] T011 [P] [US1] Unit tests for SkipCondition dataclass in tests/unit/policy/test_skip_conditions.py
- [ ] T012 [P] [US1] Unit tests for skip condition evaluation in tests/unit/policy/test_skip_conditions.py (include timing assertion < 10ms per NFR-001; include edge case: missing track metadata returns None with warning)
- [ ] T013 [P] [US1] Integration test for skip_when workflow in tests/unit/workflow/test_conditional_phases.py

### Implementation for User Story 1

- [ ] T014 [P] [US1] Add SkipCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [ ] T015 [P] [US1] Add SkipConditionModel Pydantic model to src/video_policy_orchestrator/policy/loader.py
- [ ] T016 [US1] Add skip_when field to PhaseModel in src/video_policy_orchestrator/policy/loader.py
- [ ] T017 [US1] Add skip_when field to PhaseDefinition dataclass in src/video_policy_orchestrator/policy/models.py
- [ ] T018 [US1] Update convert_phase() to parse skip_when in src/video_policy_orchestrator/policy/loader.py
- [ ] T019 [US1] Create skip condition evaluation module at src/video_policy_orchestrator/policy/skip_conditions.py
- [ ] T020 [US1] Implement evaluate_skip_condition() for video_codec check in src/video_policy_orchestrator/policy/skip_conditions.py
- [ ] T021 [US1] Implement evaluate_skip_condition() for audio_codec_exists check in src/video_policy_orchestrator/policy/skip_conditions.py
- [ ] T022 [US1] Implement evaluate_skip_condition() for file_size_under/over checks in src/video_policy_orchestrator/policy/skip_conditions.py
- [ ] T023 [US1] Implement evaluate_skip_condition() for duration_under/over checks in src/video_policy_orchestrator/policy/skip_conditions.py
- [ ] T024 [US1] Implement evaluate_skip_condition() for resolution/resolution_under checks in src/video_policy_orchestrator/policy/skip_conditions.py
- [ ] T025 [US1] Implement evaluate_skip_condition() for container check in src/video_policy_orchestrator/policy/skip_conditions.py
- [ ] T026 [US1] Implement evaluate_skip_condition() for subtitle_language_exists check in src/video_policy_orchestrator/policy/skip_conditions.py
- [ ] T027 [US1] Integrate skip condition evaluation into V11WorkflowProcessor._process_phase() in src/video_policy_orchestrator/workflow/v11_processor.py
- [ ] T028 [US1] Add skip logging with reason in V11WorkflowProcessor in src/video_policy_orchestrator/workflow/v11_processor.py
- [ ] T029 [US1] Update JSON output to include skip_reason in PhaseResult serialization in src/video_policy_orchestrator/workflow/v11_processor.py

**Checkpoint**: User Story 1 complete - phases can be skipped based on file characteristics

---

## Phase 4: User Story 2 - Per-Phase Error Recovery (Priority: P1)

**Goal**: Override global `on_error` at the phase level

**Independent Test**: Create policy with phase `on_error: continue`, trigger failure, verify processing continues

### Tests for User Story 2

- [ ] T030 [P] [US2] Unit tests for phase-level on_error parsing in tests/unit/policy/test_loader.py
- [ ] T031 [P] [US2] Integration test for on_error override behavior in tests/unit/workflow/test_conditional_phases.py

### Implementation for User Story 2

- [ ] T032 [P] [US2] Add on_error field to PhaseModel in src/video_policy_orchestrator/policy/loader.py
- [ ] T033 [US2] Add on_error field to PhaseDefinition dataclass in src/video_policy_orchestrator/policy/models.py
- [ ] T034 [US2] Update convert_phase() to parse on_error in src/video_policy_orchestrator/policy/loader.py
- [ ] T035 [US2] Implement phase-level on_error resolution in V11PhaseExecutor in src/video_policy_orchestrator/workflow/phases/executor.py
- [ ] T036 [US2] Update V11WorkflowProcessor to use phase-level on_error when specified in src/video_policy_orchestrator/workflow/v11_processor.py
- [ ] T037 [US2] Implement on_error: skip behavior (mark as skipped, log warning, continue) in src/video_policy_orchestrator/workflow/v11_processor.py

**Checkpoint**: User Story 2 complete - phases can have individual error handling

---

## Phase 5: User Story 3 - Phase Dependencies (Priority: P2)

**Goal**: Skip phases when their dependencies fail or are skipped

**Independent Test**: Create policy where phase B depends on A, skip A via --phases, verify B also skips

### Tests for User Story 3

- [ ] T038 [P] [US3] Unit tests for DependencyGraph in tests/unit/policy/test_dependency_graph.py (include timing assertion < 1ms for 20 phases per NFR-002)
- [ ] T039 [P] [US3] Unit tests for circular dependency detection in tests/unit/policy/test_dependency_graph.py
- [ ] T040 [P] [US3] Integration test for depends_on workflow in tests/unit/workflow/test_conditional_phases.py

### Implementation for User Story 3

- [ ] T041 [P] [US3] Create DependencyGraph class at src/video_policy_orchestrator/workflow/dependency.py
- [ ] T042 [US3] Implement add_phase() and add_dependency() methods in src/video_policy_orchestrator/workflow/dependency.py
- [ ] T043 [US3] Implement detect_cycle() using DFS with coloring in src/video_policy_orchestrator/workflow/dependency.py
- [ ] T044 [US3] Implement get_dependencies() and get_dependents() methods in src/video_policy_orchestrator/workflow/dependency.py
- [ ] T045 [US3] Implement validate_order() for --phases filter validation in src/video_policy_orchestrator/workflow/dependency.py
- [ ] T046 [P] [US3] Add depends_on field to PhaseModel in src/video_policy_orchestrator/policy/loader.py
- [ ] T047 [US3] Add depends_on field to PhaseDefinition dataclass in src/video_policy_orchestrator/policy/models.py
- [ ] T048 [US3] Update convert_phase() to parse depends_on in src/video_policy_orchestrator/policy/loader.py
- [ ] T049 [US3] Add dependency validation to policy loading (circular detection, missing references) in src/video_policy_orchestrator/policy/loader.py
- [ ] T050 [US3] Integrate dependency graph building into V11WorkflowProcessor.__init__() in src/video_policy_orchestrator/workflow/v11_processor.py
- [ ] T051 [US3] Track phase outcomes during processing in V11WorkflowProcessor in src/video_policy_orchestrator/workflow/v11_processor.py
- [ ] T052 [US3] Implement dependency check before phase execution in V11WorkflowProcessor._process_phase() in src/video_policy_orchestrator/workflow/v11_processor.py
- [ ] T053 [US3] Add dependency warning to --phases filter validation in src/video_policy_orchestrator/cli/process.py
- [ ] T054 [US3] Update JSON output to include dependency resolution status in src/video_policy_orchestrator/workflow/v11_processor.py

**Checkpoint**: User Story 3 complete - phases respect dependencies

---

## Phase 6: User Story 4 - Conditional Phase Based on Modifications (Priority: P2)

**Goal**: Skip phases when referenced phase made no changes using `run_if: { phase_modified: ... }`

**Independent Test**: Create policy where phase B runs only if A modified file, process where A makes no changes, verify B skips

### Tests for User Story 4

- [ ] T055 [P] [US4] Unit tests for RunIfCondition parsing in tests/unit/policy/test_loader.py
- [ ] T056 [P] [US4] Integration test for run_if workflow in tests/unit/workflow/test_conditional_phases.py

### Implementation for User Story 4

- [ ] T057 [P] [US4] Add RunIfCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [ ] T058 [P] [US4] Add RunIfConditionModel Pydantic model to src/video_policy_orchestrator/policy/loader.py
- [ ] T059 [US4] Add run_if field to PhaseModel in src/video_policy_orchestrator/policy/loader.py
- [ ] T060 [US4] Add run_if field to PhaseDefinition dataclass in src/video_policy_orchestrator/policy/models.py
- [ ] T061 [US4] Update convert_phase() to parse run_if in src/video_policy_orchestrator/policy/loader.py
- [ ] T062 [US4] Add run_if validation (referenced phase must exist and appear earlier) in src/video_policy_orchestrator/policy/loader.py
- [ ] T063 [US4] Implement run_if evaluation using PhaseResult.file_modified in src/video_policy_orchestrator/workflow/v11_processor.py
- [ ] T064 [US4] Ensure skip_when is evaluated before run_if in V11WorkflowProcessor._process_phase() in src/video_policy_orchestrator/workflow/v11_processor.py

**Checkpoint**: User Story 4 complete - phases can conditionally run based on previous phase modifications

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and cleanup

- [ ] T065 [P] Update policy schema documentation with new fields in docs/
- [ ] T066 [P] Add conditional phases example to docs/examples/ or existing policy examples
- [ ] T067 Run all tests and verify all acceptance scenarios pass
- [ ] T068 Run quickstart.md validation scenarios manually
- [ ] T069 Update CLAUDE.md if any new patterns or conventions were introduced

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - Core skip_when functionality
- **User Story 2 (Phase 4)**: Depends on Foundational - Can run in parallel with US1
- **User Story 3 (Phase 5)**: Depends on Foundational - Can run in parallel with US1, US2
- **User Story 4 (Phase 6)**: Depends on US3 (needs outcome tracking) - Sequential after US3
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P0)**: Independent after Foundational - MVP target
- **US2 (P1)**: Independent after Foundational - Can parallel with US1
- **US3 (P2)**: Independent after Foundational - Can parallel with US1, US2
- **US4 (P2)**: Depends on US3 (needs phase outcome tracking infrastructure)

### Within Each User Story

- Tests written first (if included)
- Dataclasses/models before parsing logic
- Parsing logic before workflow integration
- Workflow integration before CLI updates
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
```
T002, T003, T004, T005 can run in parallel
```

**Phase 3 (US1) - Models**:
```
T014, T015 can run in parallel
```

**Phase 3 (US1) - Tests**:
```
T011, T012, T013 can run in parallel
```

**Phase 5 (US3) - Initial**:
```
T038, T039, T040, T041, T046 can run in parallel
```

**Phase 6 (US4) - Initial**:
```
T055, T056, T057, T058 can run in parallel
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (fixtures)
2. Complete Phase 2: Foundational (PhaseOutcome, SkipReason)
3. Complete Phase 3: User Story 1 (skip_when)
4. **STOP and VALIDATE**: Test skip_when independently
5. Deploy/demo if ready - users can skip phases based on file characteristics

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (skip_when) → Test → Deploy (MVP!)
3. Add US2 (on_error override) → Test → Deploy
4. Add US3 (depends_on) → Test → Deploy
5. Add US4 (run_if) → Test → Deploy
6. Each story adds value without breaking previous stories

### Suggested Order

Given US4 depends on US3 infrastructure:
1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: US1 (skip_when) - **MVP**
4. Phase 4: US2 (on_error) - parallel with US1 if desired
5. Phase 5: US3 (depends_on)
6. Phase 6: US4 (run_if) - must follow US3
7. Phase 7: Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US4 requires US3's outcome tracking infrastructure - not fully independent
