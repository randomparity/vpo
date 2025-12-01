# Tasks: Plugin Metadata Access in Policies

**Input**: Design documents from `/specs/039-plugin-metadata-policy/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Schema versioning and configuration updates

- [ ] T001 Update MAX_SCHEMA_VERSION to 12 in src/video_policy_orchestrator/policy/loader.py
- [ ] T002 [P] Update CLAUDE.md with feature context in section markers

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Add `plugin_metadata TEXT` column migration (v16→v17) in src/video_policy_orchestrator/db/schema.py
- [ ] T004 [P] Add `plugin_metadata` field to FileRecord dataclass in src/video_policy_orchestrator/db/types.py
- [ ] T005 [P] Add `plugin_metadata` field to FileInfo dataclass in src/video_policy_orchestrator/db/types.py
- [ ] T006 Update upsert_file() to include plugin_metadata in src/video_policy_orchestrator/db/queries.py
- [ ] T007 Update get_file_by_* queries to include plugin_metadata in src/video_policy_orchestrator/db/queries.py
- [ ] T008 Create PluginMetadataOperator enum in src/video_policy_orchestrator/policy/plugin_metadata.py
- [ ] T009 Create PluginMetadataCondition dataclass in src/video_policy_orchestrator/policy/plugin_metadata.py
- [ ] T010 Add PluginMetadataCondition to Condition type union in src/video_policy_orchestrator/policy/models.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Condition on Plugin-Provided Original Language (Priority: P1) 🎯 MVP

**Goal**: Enable policy conditions to check plugin metadata like `radarr:original_language`

**Independent Test**: Create a policy with `plugin_metadata` condition and verify it evaluates correctly against files with plugin enrichment data

### Implementation for User Story 1

- [ ] T011 [US1] Implement evaluate_plugin_metadata_condition() in src/video_policy_orchestrator/policy/plugin_metadata.py
- [ ] T012 [US1] Create PluginMetadataConditionModel Pydantic model in src/video_policy_orchestrator/policy/loader.py
- [ ] T013 [US1] Add plugin_metadata condition parsing to convert_condition() in src/video_policy_orchestrator/policy/loader.py
- [ ] T014 [US1] Update evaluate_condition() to handle PluginMetadataCondition in src/video_policy_orchestrator/policy/conditions.py
- [ ] T015 [US1] Thread plugin_metadata through evaluate_conditions() signature in src/video_policy_orchestrator/policy/evaluator.py
- [ ] T016 [US1] Update Plan.evaluate() to pass plugin_metadata from FileInfo in src/video_policy_orchestrator/policy/evaluator.py

**Checkpoint**: User Story 1 complete - plugin metadata conditions evaluate correctly

---

## Phase 4: User Story 2 - Filter Audio Tracks by Content Language (Priority: P1)

**Goal**: Enable track filtering decisions based on plugin-provided original language

**Independent Test**: Process a file with `original_language: jpn` through a policy that conditionally filters tracks

### Implementation for User Story 2

- [ ] T017 [US2] Update scanner orchestrator to collect and store plugin enrichment in src/video_policy_orchestrator/scanner/orchestrator.py
- [ ] T018 [US2] Verify conditional rule evaluation passes plugin_metadata in src/video_policy_orchestrator/policy/evaluator.py
- [ ] T019 [US2] Add unit test for track filtering with plugin metadata condition in tests/unit/policy/test_plugin_metadata.py

**Checkpoint**: User Story 2 complete - track filtering works with plugin metadata

---

## Phase 5: User Story 3 - Conditional Rules Based on External IDs (Priority: P2)

**Goal**: Support conditions on tmdb_id, series_title, and other external identifiers

**Independent Test**: Create conditional rules checking `radarr:tmdb_id` and `sonarr:series_title`

### Implementation for User Story 3

- [ ] T020 [US3] Add integer and NEQ comparison support to evaluate_plugin_metadata_condition() in src/video_policy_orchestrator/policy/plugin_metadata.py
- [ ] T021 [US3] Add CONTAINS operator evaluation for string substring matching in src/video_policy_orchestrator/policy/plugin_metadata.py
- [ ] T022 [US3] Add unit tests for integer, NEQ, and CONTAINS operators in tests/unit/policy/test_plugin_metadata.py

**Checkpoint**: User Story 3 complete - all operator types work correctly

---

## Phase 6: User Story 4 - Policy Validation with Plugin References (Priority: P2)

**Goal**: Provide clear validation warnings for unknown plugins or fields

**Independent Test**: Load policies with invalid plugin references and verify warning messages

### Implementation for User Story 4

- [ ] T023 [US4] Create KNOWN_PLUGIN_FIELDS registry in src/video_policy_orchestrator/policy/plugin_metadata.py
- [ ] T024 [US4] Implement validate_plugin_reference() in src/video_policy_orchestrator/policy/plugin_metadata.py
- [ ] T025 [US4] Add validation call to PluginMetadataConditionModel in src/video_policy_orchestrator/policy/loader.py
- [ ] T026 [US4] Add validation warning tests in tests/unit/policy/test_plugin_metadata.py

**Checkpoint**: User Story 4 complete - validation warnings work for unknown plugins/fields

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration testing and documentation

- [ ] T027 [P] Create integration test for end-to-end policy evaluation in tests/integration/test_plugin_metadata_policy.py
- [ ] T028 [P] Update policy schema documentation in docs/
- [ ] T029 Run quickstart.md validation scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Core condition evaluation
- **User Story 2 (P1)**: Depends on US1 completion - Uses conditions in track filtering context
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Extends operators (parallel with US1/US2)
- **User Story 4 (P2)**: Can start after T009 (PluginMetadataCondition exists) - Adds validation layer

### Within Each User Story

- Models before evaluation logic
- Pydantic models before condition parsing
- Core implementation before integration
- Unit tests alongside implementation

### Parallel Opportunities

- T002 can run in parallel with T001
- T004, T005 can run in parallel (different dataclasses)
- T027, T028 can run in parallel (different concerns)
- US3 and US4 can run in parallel after US1/US2

---

## Parallel Example: Foundational Phase

```bash
# After T003 migration completes, these can run in parallel:
Task: "Add plugin_metadata field to FileRecord in db/types.py" (T004)
Task: "Add plugin_metadata field to FileInfo in db/types.py" (T005)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test basic plugin metadata condition evaluation
5. Can deploy - core feature works

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test condition evaluation → MVP!
3. Add User Story 2 → Test track filtering integration
4. Add User Story 3 → Test all operator types
5. Add User Story 4 → Test validation warnings
6. Polish phase → Documentation and integration tests

### Key Files Summary

| File | Changes |
|------|---------|
| `policy/plugin_metadata.py` | NEW: All plugin metadata abstractions |
| `policy/models.py` | UPDATE: Add to Condition union |
| `policy/loader.py` | UPDATE: Pydantic model, parsing, MAX_SCHEMA_VERSION |
| `policy/conditions.py` | UPDATE: Add evaluation case |
| `policy/evaluator.py` | UPDATE: Thread plugin_metadata |
| `db/schema.py` | UPDATE: Migration v16→v17 |
| `db/types.py` | UPDATE: FileRecord, FileInfo fields |
| `db/queries.py` | UPDATE: upsert/select queries |
| `scanner/orchestrator.py` | UPDATE: Store plugin enrichment |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Missing plugin data → condition evaluates to false (no errors)
