# Tasks: Parallel File Processing

**Input**: Design documents from `/specs/041-parallel-process/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: Tests are included as this is a concurrency feature where correctness is critical.

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

**Purpose**: No setup tasks required - this feature modifies existing modules only

*No tasks in this phase - all work is modifications to existing code.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core configuration and utilities that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T001 [P] Add ProcessingConfig dataclass with workers field (default=2, validation >=1) in src/video_policy_orchestrator/config/models.py
- [x] T002 [P] Add processing field to VPOConfig dataclass in src/video_policy_orchestrator/config/models.py
- [x] T003 Update ConfigBuilder to handle [processing] section from TOML in src/video_policy_orchestrator/config/builder.py
- [x] T004 Add get_max_workers() utility function (half CPU cores, min 1) in src/video_policy_orchestrator/cli/process.py
- [x] T005 Add resolve_worker_count() function to apply cap and log warning in src/video_policy_orchestrator/cli/process.py
- [x] T006 Add ProgressTracker class with thread-safe start_file/complete_file methods in src/video_policy_orchestrator/cli/process.py
- [x] T007 Add unit tests for ProcessingConfig validation in tests/unit/config/test_models.py
- [x] T008 Add unit tests for get_max_workers and resolve_worker_count in tests/unit/cli/test_process.py

**Checkpoint**: Foundation ready - ProcessingConfig loads from config.toml, worker utilities work, ProgressTracker is thread-safe

---

## Phase 3: User Story 1 - Process Large Video Batches Faster (Priority: P1) MVP

**Goal**: Enable parallel file processing with `--workers` CLI flag using ThreadPoolExecutor

**Independent Test**: Run `vpo process --workers 2 -p policy.yaml /path/to/files/` and observe concurrent processing with reduced batch time

### Implementation for User Story 1

- [ ] T009 [US1] Add --workers/-w CLI option to process_command in src/video_policy_orchestrator/cli/process.py
- [ ] T010 [US1] Create DaemonConnectionPool instance at batch start (replacing get_connection) in src/video_policy_orchestrator/cli/process.py
- [ ] T011 [US1] Implement process_files_parallel() function using ThreadPoolExecutor and as_completed (relies on existing fcntl.flock for file safety) in src/video_policy_orchestrator/cli/process.py
- [ ] T012 [US1] Update V11WorkflowProcessor instantiation to accept DaemonConnectionPool in src/video_policy_orchestrator/cli/process.py
- [ ] T013 [US1] Integrate ProgressTracker to display aggregate progress line on stderr in src/video_policy_orchestrator/cli/process.py
- [ ] T014 [US1] Add batch summary output (success/fail counts, total duration) in src/video_policy_orchestrator/cli/process.py
- [ ] T015 [US1] Add integration test for parallel processing with 2 workers in tests/integration/test_parallel_process.py

**Checkpoint**: User Story 1 complete - parallel processing works with --workers flag, progress displays correctly

---

## Phase 4: User Story 4 - Error Handling with on_error Modes (Priority: P1)

**Goal**: Implement proper error handling that respects on_error policy modes in parallel context

**Independent Test**: Process a batch with a known-failing file and verify on_error=fail stops batch, on_error=skip continues

### Implementation for User Story 4

- [ ] T016 [US4] Add stop_event (threading.Event) for coordinating early termination in src/video_policy_orchestrator/cli/process.py
- [ ] T017 [US4] Implement on_error=fail logic: set stop_event, cancel pending futures, let in-progress complete in src/video_policy_orchestrator/cli/process.py
- [ ] T018 [US4] Implement on_error=skip logic: record failure, continue other workers, collect all results in src/video_policy_orchestrator/cli/process.py
- [ ] T019 [US4] Add stopped_early flag to batch result and include in summary output in src/video_policy_orchestrator/cli/process.py
- [ ] T020 [US4] Add integration test for on_error=fail stopping batch in tests/integration/test_parallel_process.py
- [ ] T021 [US4] Add integration test for on_error=skip continuing batch in tests/integration/test_parallel_process.py

**Checkpoint**: User Story 4 complete - error handling works correctly for both on_error modes

---

## Phase 5: User Story 2 - Configure Default Worker Count (Priority: P2)

**Goal**: Allow users to set default worker count in config.toml [processing] section

**Independent Test**: Set workers=4 in config.toml, run vpo process without --workers, verify 4 workers used

### Implementation for User Story 2

- [ ] T022 [US2] Load processing config from get_config() and use workers value as default in src/video_policy_orchestrator/cli/process.py
- [ ] T023 [US2] Ensure CLI --workers flag overrides config file value in src/video_policy_orchestrator/cli/process.py
- [ ] T024 [US2] Add unit test for config loading with [processing] section in tests/unit/config/test_builder.py
- [ ] T025 [US2] Add integration test for config-based worker count in tests/integration/test_parallel_process.py

**Checkpoint**: User Story 2 complete - default worker count configurable via config.toml

---

## Phase 6: User Story 3 - Force Sequential Processing (Priority: P2)

**Goal**: Allow --workers 1 to force sequential processing for debugging or resource constraints

**Independent Test**: Run `vpo process --workers 1` and verify files process one at a time in order

### Implementation for User Story 3

- [ ] T026 [US3] Ensure --workers 1 uses sequential execution path (ThreadPoolExecutor with max_workers=1) in src/video_policy_orchestrator/cli/process.py
- [ ] T027 [US3] Verify output order matches input order with --workers 1 in src/video_policy_orchestrator/cli/process.py
- [ ] T028 [US3] Add integration test for sequential processing with --workers 1 in tests/integration/test_parallel_process.py

**Checkpoint**: User Story 3 complete - sequential mode works correctly

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, edge cases, and final validation

- [ ] T029 [P] Update CLI help text for --workers option in src/video_policy_orchestrator/cli/process.py
- [ ] T030 [P] Add [processing] section documentation to example config comments
- [ ] T030a [P] Document disk space requirements (2.5x per file × workers) in CLI help text for --workers option
- [ ] T031 Verify JSON output mode still works correctly with parallel processing in src/video_policy_orchestrator/cli/process.py
- [ ] T032 Test verbose mode (-v) output with parallel processing in src/video_policy_orchestrator/cli/process.py
- [ ] T033 Ensure DaemonConnectionPool is properly closed on batch completion/error in src/video_policy_orchestrator/cli/process.py
- [ ] T034 Run full test suite to verify no regressions: `uv run pytest`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies - can start immediately
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 4 (Phase 4)**: Depends on User Story 1 (builds on parallel infrastructure)
- **User Story 2 (Phase 5)**: Depends on Foundational (config loading)
- **User Story 3 (Phase 6)**: Depends on User Story 1 (sequential is special case of parallel)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: FIRST - Core parallel processing infrastructure
- **User Story 4 (P1)**: SECOND - Error handling builds on US1
- **User Story 2 (P2)**: Can start after Foundational - config loading independent
- **User Story 3 (P2)**: Depends on US1 - sequential is special case of parallel

### Parallel Opportunities

- T001, T002 can run in parallel (different classes in same file)
- T007, T008 can run in parallel (different test files)
- T029, T030 can run in parallel (different documentation)
- User Stories 2 and 3 can be developed in parallel after US1 completes

---

## Parallel Example: Foundational Phase

```bash
# Launch parallel config tasks:
Task: "Add ProcessingConfig dataclass in config/models.py"
Task: "Add processing field to VPOConfig in config/models.py"

# Then sequential:
Task: "Update ConfigBuilder to handle [processing] section"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001-T008)
2. Complete Phase 3: User Story 1 (T009-T015)
3. **STOP and VALIDATE**: Test parallel processing independently
4. Users can now process batches in parallel

### Full Feature Delivery

1. Complete Foundational → Config and utilities ready
2. Add User Story 1 → Parallel processing works → Deploy/Demo (MVP!)
3. Add User Story 4 → Error handling correct → Critical for production
4. Add User Story 2 → Config persistence → Power user convenience
5. Add User Story 3 → Sequential mode → Debugging escape hatch
6. Polish → Documentation and edge cases

---

## Summary

| Phase | Tasks | Parallel | Description |
|-------|-------|----------|-------------|
| Foundational | 8 | 4 | Config + utilities |
| US1 (P1) | 7 | 0 | Core parallel processing |
| US4 (P1) | 6 | 0 | Error handling |
| US2 (P2) | 4 | 0 | Config persistence |
| US3 (P2) | 3 | 0 | Sequential mode |
| Polish | 6 | 2 | Documentation |
| **Total** | **34** | **6** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Test parallel execution with small batches first (2-5 files)
- Verify ProgressTracker thread safety with concurrent unit tests
