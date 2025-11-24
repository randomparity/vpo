# Tasks: Policies List View

**Input**: Design documents from `/specs/023-policies-list-view/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Tests are included as this follows the existing VPO test patterns.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- Source: `src/video_policy_orchestrator/`
- Tests: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test fixtures and project structure verification

- [ ] T001 [P] Create test policy fixtures directory at tests/fixtures/policies/
- [ ] T002 [P] Create valid-basic.yaml test fixture in tests/fixtures/policies/
- [ ] T003 [P] Create valid-full.yaml test fixture with transcode and transcription in tests/fixtures/policies/
- [ ] T004 [P] Create invalid-syntax.yaml test fixture in tests/fixtures/policies/
- [ ] T005 [P] Create invalid-format.yaml test fixture (list not mapping) in tests/fixtures/policies/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core policy discovery module that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create PolicySummary dataclass in src/video_policy_orchestrator/policy/discovery.py
- [ ] T007 Implement _parse_policy_file() helper in src/video_policy_orchestrator/policy/discovery.py
- [ ] T008 Implement _is_default_policy() helper in src/video_policy_orchestrator/policy/discovery.py
- [ ] T009 Implement discover_policies() main function in src/video_policy_orchestrator/policy/discovery.py
- [ ] T010 Add __init__.py exports for discovery module in src/video_policy_orchestrator/policy/__init__.py
- [ ] T011 [P] Create unit tests for _parse_policy_file() in tests/unit/policy/test_discovery.py
- [ ] T012 [P] Create unit tests for discover_policies() in tests/unit/policy/test_discovery.py

**Checkpoint**: Foundation ready - policy discovery module is complete and tested

---

## Phase 3: User Story 1 - View All Policies (Priority: P1) MVP

**Goal**: Display a list of all policy files from ~/.vpo/policies/ with names and basic info

**Independent Test**: Navigate to /policies and verify policy files are displayed with names; verify empty state when no policies exist

### Implementation for User Story 1

- [ ] T013 [US1] Add format_language_preferences() helper in src/video_policy_orchestrator/server/ui/models.py
- [ ] T014 [US1] Add PolicyListItem dataclass in src/video_policy_orchestrator/server/ui/models.py
- [ ] T015 [US1] Add PolicyListResponse dataclass in src/video_policy_orchestrator/server/ui/models.py
- [ ] T016 [US1] Add PoliciesContext dataclass in src/video_policy_orchestrator/server/ui/models.py
- [ ] T017 [US1] Implement policies_handler() route in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T018 [US1] Implement policies_api_handler() route in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T019 [US1] Register /policies and /api/policies routes in setup_ui_routes() in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T020 [US1] Create policies.html template with basic list structure in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T021 [US1] Add empty state message to policies.html template in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T022 [US1] Add directory-missing state message to policies.html template in src/video_policy_orchestrator/server/ui/templates/sections/policies.html

**Checkpoint**: User Story 1 complete - Users can view list of policies with names, see empty states

---

## Phase 4: User Story 2 - View Policy Metadata (Priority: P2)

**Goal**: Display metadata for each policy (last modified, schema version, language preferences)

**Independent Test**: Verify policy rows show last modified timestamp, schema version, and language preferences summary

### Implementation for User Story 2

- [ ] T023 [US2] Add last_modified column to policies table in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T024 [US2] Add schema_version column to policies table in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T025 [US2] Add audio/subtitle language columns to policies table in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T026 [US2] Add CSS styling for metadata columns in src/video_policy_orchestrator/server/static/css/main.css

**Checkpoint**: User Story 2 complete - Users can see detailed metadata for each policy

---

## Phase 5: User Story 3 - Identify Active Policy (Priority: P2)

**Goal**: Clearly indicate which policy is the default for the current profile

**Independent Test**: Configure default_policy in profile and verify "Default" badge appears on correct policy; verify warning when default is missing

### Implementation for User Story 3

- [ ] T027 [US3] Add is_default badge rendering to policies table in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T028 [US3] Add CSS for .badge-default styling in src/video_policy_orchestrator/server/static/css/main.css
- [ ] T029 [US3] Add default_policy_missing warning banner to policies.html in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T029a [US3] Add "no default configured" info message to policies.html in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T030 [US3] Add CSS for .policies-warning and .policies-info styling in src/video_policy_orchestrator/server/static/css/main.css

**Checkpoint**: User Story 3 complete - Users can identify the default policy at a glance

---

## Phase 6: User Story 4 - Policy Scope Indication (Priority: P3)

**Goal**: Show feature indicators (transcode, transcription badges) for each policy

**Independent Test**: Verify policies with transcode settings show transcode badge; verify policies with transcription.enabled show transcription badge

### Implementation for User Story 4

- [ ] T031 [US4] Add has_transcode badge to policies table in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T032 [US4] Add has_transcription badge to policies table in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T033 [US4] Add parse_error badge for invalid policies in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T034 [US4] Add CSS for .badge-transcode, .badge-transcription, .badge-error in src/video_policy_orchestrator/server/static/css/main.css

**Checkpoint**: User Story 4 complete - Users can see feature indicators for each policy

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final testing, validation, and cleanup

- [ ] T035 [P] Create integration test for /api/policies endpoint in tests/integration/server/test_policies_api.py
- [ ] T036 [P] Create integration test for /policies HTML page in tests/integration/server/test_policies_page.py
- [ ] T037 Run all tests and verify passing (uv run pytest tests/unit/policy/test_discovery.py tests/integration/server/test_policies*)
- [ ] T038 Run linter and fix any issues (uv run ruff check src/video_policy_orchestrator/policy/discovery.py src/video_policy_orchestrator/server/ui/)
- [ ] T039 Manual test: verify page loads with sample policies
- [ ] T040 Manual test: verify empty state displays correctly
- [ ] T041 Manual test: verify invalid policy shows error badge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in priority order (P1 → P2 → P2 → P3)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 template structure (T020)
- **User Story 3 (P2)**: Depends on US1 template structure (T020)
- **User Story 4 (P3)**: Depends on US1 template structure (T020)

### Within Each User Story

- Models/helpers before routes
- Routes before templates
- Core implementation before styling

### Parallel Opportunities

**Phase 1 (Setup)**:
- T001-T005 can ALL run in parallel (different fixture files)

**Phase 2 (Foundational)**:
- T011-T012 can run in parallel (test files)
- T006-T010 should run sequentially (same file, building on each other)

**Phase 3 (US1)**:
- T013-T016 can run in parallel (model additions)
- T017-T019 should run sequentially (route dependencies)
- T020-T022 should run sequentially (same template file)

**Phase 4-6 (US2-US4)**:
- Can run in parallel with different developers (different concerns)
- Within each phase: template then CSS

**Phase 7 (Polish)**:
- T035-T036 can run in parallel (different test files)

---

## Parallel Example: Phase 1 Setup

```bash
# Launch all fixture creation tasks together:
Task: "Create test policy fixtures directory at tests/fixtures/policies/"
Task: "Create valid-basic.yaml test fixture in tests/fixtures/policies/"
Task: "Create valid-full.yaml test fixture with transcode and transcription in tests/fixtures/policies/"
Task: "Create invalid-syntax.yaml test fixture in tests/fixtures/policies/"
Task: "Create invalid-format.yaml test fixture (list not mapping) in tests/fixtures/policies/"
```

## Parallel Example: Phase 3 Models

```bash
# Launch all model additions together:
Task: "Add format_language_preferences() helper in src/video_policy_orchestrator/server/ui/models.py"
Task: "Add PolicyListItem dataclass in src/video_policy_orchestrator/server/ui/models.py"
Task: "Add PolicyListResponse dataclass in src/video_policy_orchestrator/server/ui/models.py"
Task: "Add PoliciesContext dataclass in src/video_policy_orchestrator/server/ui/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (test fixtures)
2. Complete Phase 2: Foundational (discovery module)
3. Complete Phase 3: User Story 1 (basic list view)
4. **STOP and VALIDATE**: Test US1 independently - page loads, shows policies, empty state works
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Now shows metadata
4. Add User Story 3 → Test independently → Now shows default badge
5. Add User Story 4 → Test independently → Now shows feature badges
6. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The discovery module (Phase 2) is the critical path - all UI depends on it
