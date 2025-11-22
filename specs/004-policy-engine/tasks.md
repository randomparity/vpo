# Tasks: Policy Engine & Reordering

**Input**: Design documents from `/specs/004-policy-engine/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Dependencies & Project Structure)

**Purpose**: Add new dependencies and create module structure

- [X] T001 Add PyYAML and pydantic dependencies to pyproject.toml
- [X] T002 [P] Create policy module structure: `src/video_policy_orchestrator/policy/__init__.py`
- [X] T003 [P] Create executor module structure: `src/video_policy_orchestrator/executor/__init__.py`
- [X] T004 [P] Create policy test fixtures directory: `tests/fixtures/policies/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Extend db/models.py with OperationRecord dataclass and OperationStatus enum
- [X] T006 Extend db/schema.py with operations table (CREATE TABLE, indexes) and migration logic
- [X] T007 [P] Create policy/models.py with ActionType enum, PlannedAction, Plan dataclasses per contracts/evaluator-api.md
- [X] T008 [P] Create policy/models.py additions: TrackType enum, DefaultFlagsConfig, PolicySchema per contracts/policy-schema.yaml
- [X] T009 [P] Create executor/interface.py with Executor protocol and tool availability check function
- [X] T010 [P] Create executor/backup.py with backup creation, restoration, and cleanup utilities

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1+2 - Policy Definition & Dry-Run Preview (Priority: P1) MVP

**Goal**: Users can define policies in YAML and preview changes without modifying files

**Independent Test**: Run `vpo apply --policy policy.yaml --dry-run movie.mkv` and verify output shows proposed changes without file modification

### Implementation

- [X] T011 [P] [US1] Create policy/matchers.py with CommentaryMatcher class implementing regex pattern matching per research.md
- [X] T012 [US1] Create policy/loader.py with load_policy() function, YAML parsing, Pydantic validation, error transformation per contracts/policy-schema.yaml
- [X] T013 [P] [US1] Create sample policy fixtures: `tests/fixtures/policies/track_order_basic.yaml`
- [X] T014 [P] [US1] Create sample policy fixtures: `tests/fixtures/policies/audio_preference.yaml`
- [X] T015 [P] [US1] Create sample policy fixtures: `tests/fixtures/policies/commentary_detection.yaml`
- [X] T016 [US1] Create policy/evaluator.py with classify_track(), compute_desired_order(), compute_default_flags() functions per contracts/evaluator-api.md
- [X] T017 [US1] Implement evaluate_policy() pure function in policy/evaluator.py per contracts/evaluator-api.md
- [X] T018 [US1] Create cli/apply.py with `vpo apply` command skeleton, --policy and --dry-run options per contracts/cli-apply.md
- [X] T019 [US1] Implement dry-run output formatting (human-readable before/after diff) in cli/apply.py
- [X] T020 [US1] Implement JSON output format (--json flag) in cli/apply.py
- [X] T021 [US1] Register apply command in cli/__init__.py

**Checkpoint**: User Story 1+2 complete - users can define policies and preview changes via dry-run

---

## Phase 4: User Story 5 - Policy Evaluation Engine (Priority: P2)

**Goal**: Pure-function evaluation engine with deterministic, testable behavior

**Independent Test**: Call evaluate_policy() with mock track data and verify identical plans for identical inputs

### Implementation

- [X] T022 [US5] Add EvaluationError, NoTracksError, UnsupportedContainerError exceptions to policy/evaluator.py
- [X] T023 [US5] Implement edge case handling in evaluator: missing language fallback, all-commentary default, no-audio-tracks skip
- [X] T024 [US5] Add Plan.summary property for human-readable change description
- [X] T025 [US5] Add PlannedAction.description property for individual action descriptions

**Checkpoint**: User Story 5 complete - evaluation engine is deterministic and handles edge cases

---

## Phase 5: User Story 3 - Metadata Application (Priority: P2)

**Goal**: Apply metadata changes (flags, titles) to files with backup/restore safety

**Independent Test**: Run `vpo apply --policy policy.yaml movie.mkv` and verify metadata changed, operation logged to DB

### Implementation

- [X] T026 [P] [US3] Create executor/mkvpropedit.py with MkvpropeditExecutor class for MKV metadata changes (flags, titles, language)
- [X] T027 [P] [US3] Create executor/ffmpeg_metadata.py with FfmpegMetadataExecutor class for non-MKV metadata changes
- [X] T028 [US3] Implement file locking mechanism in executor/backup.py to prevent concurrent modifications (FR-015)
- [X] T029 [US3] Create db/operations.py repository with create_operation(), update_operation_status(), get_pending_operations()
- [X] T030 [US3] Implement apply mode (non-dry-run) in cli/apply.py: backup creation, executor dispatch, DB logging
- [X] T031 [US3] Implement error handling and rollback in cli/apply.py: restore from backup on failure
- [X] T032 [US3] Implement --keep-backup / --no-keep-backup options in cli/apply.py

**Checkpoint**: User Story 3 complete - metadata changes applied safely with audit logging

---

## Phase 6: User Story 4 - Track Reordering (Priority: P2)

**Goal**: Reorder tracks in MKV containers using mkvmerge remux

**Independent Test**: Run apply on MKV with reorder policy, verify tracks physically reordered (not just header IDs)

### Implementation

- [X] T033 [US4] Create executor/mkvmerge.py with MkvmergeExecutor class for track reordering via --track-order
- [X] T034 [US4] Implement atomic file replacement in mkvmerge executor: write to temp, rename to original
- [X] T035 [US4] Update cli/apply.py to detect requires_remux in plan and dispatch to mkvmerge executor
- [X] T036 [US4] Add container format detection and appropriate executor selection in cli/apply.py

**Checkpoint**: User Story 4 complete - MKV track reordering works without re-encoding

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Error messages, documentation, and final validation

- [X] T037 [P] Implement user-friendly error messages for all exit codes per contracts/cli-apply.md
- [X] T038 [P] Add --verbose flag implementation for detailed operation logging
- [X] T039 Validate quickstart.md examples work end-to-end
- [X] T040 [P] Create example policy file at `docs/examples/default-policy.yaml` based on quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1+2 (Phase 3) can start after Foundational
  - US5 (Phase 4) can start after Phase 3
  - US3 (Phase 5) can start after Phase 3
  - US4 (Phase 6) can start after Phase 5 (needs executor infrastructure)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 2 (Foundational)
        │
        ▼
Phase 3 (US1+2: Policy Definition & Dry-Run) ◄─── MVP DELIVERABLE
        │
        ├────────────┬────────────┐
        ▼            ▼            ▼
Phase 4 (US5)   Phase 5 (US3)   (parallel)
                     │
                     ▼
               Phase 6 (US4)
                     │
                     ▼
               Phase 7 (Polish)
```

### Parallel Opportunities

**Phase 1 (all can run in parallel)**:
- T002, T003, T004

**Phase 2**:
- T007, T008, T009, T010 can run in parallel after T005, T006

**Phase 3 (within US1+2)**:
- T011, T013, T014, T015 can run in parallel
- T016 depends on T011 (matchers)
- T017 depends on T016
- T018-T021 depend on T017

**Phase 5 (within US3)**:
- T026, T027 can run in parallel

---

## Implementation Strategy

### MVP First (Phase 1-3 Only)

1. Complete Phase 1: Setup (dependencies, module structure)
2. Complete Phase 2: Foundational (data models, schema)
3. Complete Phase 3: User Story 1+2 (policy definition + dry-run)
4. **STOP and VALIDATE**: Test dry-run independently
5. Deploy/demo if ready - users can preview policy effects!

### Incremental Delivery

1. **MVP**: Setup + Foundational + US1+2 → Dry-run preview works
2. **+Evaluation**: Add US5 → Robust edge case handling
3. **+Metadata**: Add US3 → Can apply flag/title changes
4. **+Reordering**: Add US4 → Full MKV track reordering
5. **+Polish**: Add Phase 7 → Production-ready error handling

---

## Task Count Summary

| Phase | Tasks | Parallelizable |
|-------|-------|----------------|
| Setup | 4 | 3 |
| Foundational | 6 | 4 |
| US1+2 (P1 MVP) | 11 | 5 |
| US5 (P2) | 4 | 0 |
| US3 (P2) | 7 | 2 |
| US4 (P2) | 4 | 0 |
| Polish | 4 | 3 |
| **Total** | **40** | **17** |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- US1 and US2 combined as they share Policy loader and are both P1 priority
- Each user story is independently testable after Phase 2 completion
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
