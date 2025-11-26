# Tasks: VPO Init Command

**Input**: Design documents from `/specs/030-init-command/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md

**Tests**: Not explicitly requested in specification. Tests will be added in Polish phase for completeness.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/video_policy_orchestrator/`, `tests/` at repository root
- Paths based on existing VPO project structure from plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new files and module structure for init command

- [ ] T001 [P] Create config templates module at src/video_policy_orchestrator/config/templates.py
- [ ] T002 [P] Create init CLI module at src/video_policy_orchestrator/cli/init.py
- [ ] T003 Register init command in src/video_policy_orchestrator/cli/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures and template content that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Define InitializationState dataclass in src/video_policy_orchestrator/config/templates.py
- [ ] T005 Define InitResult dataclass in src/video_policy_orchestrator/config/templates.py
- [ ] T006 Implement config.toml template string with all VPOConfig sections in src/video_policy_orchestrator/config/templates.py
- [ ] T007 Implement default policy YAML template in src/video_policy_orchestrator/config/templates.py

**Checkpoint**: Foundation ready - templates and data structures defined

---

## Phase 3: User Story 1 - First-Time Setup (Priority: P1) 🎯 MVP

**Goal**: New users can run `vpo init` to create all necessary directories, config file, and default policy

**Independent Test**: Run `vpo init` on a system with no `~/.vpo/` directory and verify all files are created with valid content

### Implementation for User Story 1

- [ ] T008 [US1] Implement check_initialization_state() function in src/video_policy_orchestrator/config/templates.py
- [ ] T009 [US1] Implement create_data_directory() function in src/video_policy_orchestrator/config/templates.py
- [ ] T010 [US1] Implement write_config_file() function in src/video_policy_orchestrator/config/templates.py
- [ ] T011 [US1] Implement write_default_policy() function in src/video_policy_orchestrator/config/templates.py
- [ ] T012 [US1] Implement run_init() orchestration function in src/video_policy_orchestrator/config/templates.py
- [ ] T013 [US1] Implement init_command Click command with basic options in src/video_policy_orchestrator/cli/init.py
- [ ] T014 [US1] Implement success message with next steps in src/video_policy_orchestrator/cli/init.py
- [ ] T015 [US1] Add structured logging for init operations in src/video_policy_orchestrator/cli/init.py

**Checkpoint**: User Story 1 complete - `vpo init` creates all files for new users

---

## Phase 4: User Story 2 - Safe Re-initialization (Priority: P2)

**Goal**: Protect existing configurations; require --force to overwrite; report existing state

**Independent Test**: Create a VPO directory with custom config, run `vpo init`, verify config is preserved; then run `vpo init --force` and verify it overwrites

### Implementation for User Story 2

- [ ] T016 [US2] Add --force flag to init_command in src/video_policy_orchestrator/cli/init.py
- [ ] T017 [US2] Implement already-initialized detection and error message in src/video_policy_orchestrator/cli/init.py
- [ ] T018 [US2] Implement partial state detection (directory exists but incomplete; handles interrupt recovery) in src/video_policy_orchestrator/config/templates.py
- [ ] T019 [US2] Implement force overwrite logic with warning in src/video_policy_orchestrator/cli/init.py
- [ ] T020 [US2] Display existing files report when already initialized in src/video_policy_orchestrator/cli/init.py

**Checkpoint**: User Story 2 complete - existing configs are protected

---

## Phase 5: User Story 3 - Custom Data Directory (Priority: P3)

**Goal**: Users can specify `--data-dir` to use a non-default location

**Independent Test**: Run `vpo init --data-dir /tmp/custom-vpo` and verify all files are created in the specified location

### Implementation for User Story 3

- [ ] T021 [US3] Add --data-dir option to init_command in src/video_policy_orchestrator/cli/init.py
- [ ] T022 [US3] Implement path validation (writable, not a file; handles OS errors for disk space) in src/video_policy_orchestrator/config/templates.py
- [ ] T023 [US3] Implement parent directory creation in src/video_policy_orchestrator/config/templates.py
- [ ] T024 [US3] Implement error handling for invalid/inaccessible paths in src/video_policy_orchestrator/cli/init.py
- [ ] T025 [US3] Support VPO_DATA_DIR environment variable as fallback in src/video_policy_orchestrator/cli/init.py

**Checkpoint**: User Story 3 complete - custom data directories supported

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T026 [P] Add --dry-run flag showing what would be created in src/video_policy_orchestrator/cli/init.py
- [ ] T027 [P] Create unit tests for templates module in tests/unit/config/test_templates.py
- [ ] T028 [P] Create unit tests for init command in tests/unit/cli/test_init.py
- [ ] T029 [P] Create integration test for full init workflow in tests/integration/test_init_integration.py
- [ ] T030 Update docs/usage/ with init command documentation
- [ ] T031 Run quickstart.md validation (verify documented commands work)
- [ ] T032 Verify `vpo doctor` passes after `vpo init`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can proceed sequentially in priority order (P1 → P2 → P3)
  - Or in parallel if staffed appropriately
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Uses same functions as US1 but adds --force logic
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Uses same functions but with custom paths

### Within Each User Story

- Core functions before CLI integration
- Basic implementation before error handling
- Story complete before moving to next priority

### Parallel Opportunities

- T001 and T002 can run in parallel (different files)
- T004, T005, T006, T007 are sequential within templates.py (created by T001); no [P] marker needed
- All unit test tasks (T027, T028, T029) can run in parallel
- T026 (dry-run) and tests can run in parallel

---

## Parallel Example: Setup Phase

```bash
# Launch both file creations together:
Task: "Create config templates module at src/video_policy_orchestrator/config/templates.py"
Task: "Create init CLI module at src/video_policy_orchestrator/cli/init.py"
```

## Parallel Example: Polish Phase

```bash
# Launch all tests and dry-run together:
Task: "Add --dry-run flag showing what would be created in src/video_policy_orchestrator/cli/init.py"
Task: "Create unit tests for templates module in tests/unit/config/test_templates.py"
Task: "Create unit tests for init command in tests/unit/cli/test_init.py"
Task: "Create integration test for full init workflow in tests/integration/test_init_integration.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (create files)
2. Complete Phase 2: Foundational (templates and data structures)
3. Complete Phase 3: User Story 1 (basic `vpo init`)
4. **STOP and VALIDATE**: Test `vpo init` on clean system
5. Can deploy/demo - users can initialize VPO!

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → MVP Ready!
3. Add User Story 2 → Existing configs protected
4. Add User Story 3 → Custom directories supported
5. Add Polish → Tests, docs, --dry-run

### Task Summary

| Phase | Task Count | Description |
|-------|------------|-------------|
| Phase 1: Setup | 3 | Create new files |
| Phase 2: Foundational | 4 | Templates and data structures |
| Phase 3: US1 (P1) | 8 | First-time setup |
| Phase 4: US2 (P2) | 5 | Safe re-initialization |
| Phase 5: US3 (P3) | 5 | Custom data directory |
| Phase 6: Polish | 7 | Tests, docs, dry-run |
| **Total** | **32** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All paths use `pathlib.Path` per Constitution III
- Error messages should suggest next steps per Constitution VII
