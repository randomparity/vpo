# Tasks: Settings/About Panel for Web UI

**Input**: Design documents from `/specs/014-settings-about-panel/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - test tasks included for route coverage per existing project patterns.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Project type**: Web application (extends existing daemon server)
- Paths follow existing structure from feature 013-web-ui-shell

---

## Phase 1: Setup

**Purpose**: Project initialization - no setup tasks needed as this extends existing infrastructure

*No setup tasks required - feature extends existing Web UI from 013-web-ui-shell*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T001 Add AboutInfo dataclass to `src/video_policy_orchestrator/server/ui/models.py`
- [X] T002 Add "About" NavigationItem to NAVIGATION_ITEMS list in `src/video_policy_orchestrator/server/ui/models.py`
- [X] T003 Create about.html template in `src/video_policy_orchestrator/server/ui/templates/sections/about.html`

**Checkpoint**: Foundation ready - user story implementation can now begin

**Phase 2 Commit**: Commit foundational changes to branch after completing this phase

---

## Phase 3: User Story 1 - View Application Configuration (Priority: P1) MVP

**Goal**: Display API URL, version, and git hash on About page - core configuration visibility

**Independent Test**: Navigate to /about and verify version, API URL, and read-only indicator are displayed

### Implementation for User Story 1

- [X] T004 [US1] Implement `get_about_info()` helper function in `src/video_policy_orchestrator/server/ui/routes.py`
- [X] T005 [US1] Implement `about_handler()` route handler in `src/video_policy_orchestrator/server/ui/routes.py`
- [X] T006 [US1] Register /about route in `setup_ui_routes()` in `src/video_policy_orchestrator/server/ui/routes.py`
- [X] T007 [US1] Update about.html template to display version, API URL, git hash, and read-only notice in `src/video_policy_orchestrator/server/ui/templates/sections/about.html`
- [X] T008 [P] [US1] Add unit tests for about_handler (including edge cases: version unavailable fallback, git_hash None) in `tests/unit/server/ui/test_about_routes.py`

**Checkpoint**: User Story 1 complete - About page shows version and API URL

**Phase 3 Commit**: Commit US1 implementation to branch after completing this phase

---

## Phase 4: User Story 2 - View Current Profile Information (Priority: P2)

**Goal**: Display current profile name or "Default" fallback

**Independent Test**: Start daemon with --profile flag and verify profile name appears; without flag, verify "Default" appears

### Implementation for User Story 2

- [X] T009 [US2] Store profile_name in app context during daemon startup in `src/video_policy_orchestrator/cli/serve.py`
- [X] T010 [US2] Update `get_about_info()` to read profile from app context in `src/video_policy_orchestrator/server/ui/routes.py`
- [X] T011 [US2] Update about.html template to display profile name in `src/video_policy_orchestrator/server/ui/templates/sections/about.html`
- [X] T012 [P] [US2] Add unit tests for profile display (with/without profile) in `tests/unit/server/ui/test_about_routes.py`

**Checkpoint**: User Story 2 complete - Profile information visible on About page

**Phase 4 Commit**: Commit US2 implementation to branch after completing this phase

---

## Phase 5: User Story 3 - Access Documentation Links (Priority: P3)

**Goal**: Provide working links to documentation resources

**Independent Test**: Click documentation link and verify it navigates to GitHub docs

### Implementation for User Story 3

- [X] T013 [US3] Update about.html template with documentation links section in `src/video_policy_orchestrator/server/ui/templates/sections/about.html`
- [X] T014 [P] [US3] Add test verifying docs_url is present in response in `tests/unit/server/ui/test_about_routes.py`

**Checkpoint**: User Story 3 complete - Documentation links accessible from About page

**Phase 5 Commit**: Commit US3 implementation to branch after completing this phase

---

## Phase 6: API Endpoint (Optional Enhancement)

**Purpose**: JSON API endpoint for programmatic access to about info

- [X] T015 [P] Implement `/api/about` JSON endpoint in `src/video_policy_orchestrator/server/app.py`
- [X] T016 [P] Add unit tests for /api/about endpoint in `tests/unit/server/ui/test_about_routes.py`

**Phase 6 Commit**: Commit API endpoint to branch after completing this phase

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T017 Run all tests with `uv run pytest tests/unit/server/`
- [X] T018 Run linting with `uv run ruff check .`
- [ ] T019 Manual validation using quickstart.md checklist
- [ ] T020 Verify all navigation items highlight correctly when switching pages

**Final Commit**: Commit any polish changes and prepare branch for PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Skipped - using existing infrastructure
- **Foundational (Phase 2)**: No dependencies - can start immediately
- **User Stories (Phase 3-5)**: All depend on Foundational phase (T001-T003) completion
- **API Endpoint (Phase 6)**: Can proceed after Foundational, parallel to User Stories
- **Polish (Phase 7)**: Depends on all previous phases

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Foundational (T001-T003)
- **User Story 2 (P2)**: Depends on US1 (T004-T006 for route structure)
- **User Story 3 (P3)**: Depends on US1 (template exists from T007)

### Within Each User Story

- Route handler before template updates
- Template updates before tests
- Tests validate completed functionality

### Parallel Opportunities

- T008 (US1 tests) can run parallel with T009-T011 (US2 implementation)
- T012 (US2 tests) can run parallel with T013 (US3 implementation)
- T014 (US3 tests) can run parallel with T015-T016 (API endpoint)
- All test tasks marked [P] can run in parallel within their phases

---

## Parallel Example: Foundational Phase

```bash
# T001 and T002 are in the same file (models.py) - run sequentially
# T003 (about.html) is a separate file but logically depends on T002
# for consistent nav item naming - can run after T002 completes
```

## Parallel Example: Post-US1

```bash
# After US1 is complete, can run in parallel:
# Developer A: T009-T011 (US2 implementation)
# Developer B: T015-T016 (API endpoint)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001-T003)
2. Complete Phase 3: User Story 1 (T004-T008)
3. **STOP and VALIDATE**: Test About page with version and API URL
4. Commit and optionally PR for early review

### Incremental Delivery

1. Foundational → Navigation item appears, template exists
2. User Story 1 → Core config displayed (MVP!)
3. User Story 2 → Profile info added
4. User Story 3 → Docs links added
5. API Endpoint → Programmatic access
6. Each phase adds value without breaking previous functionality

### Recommended Order (Single Developer)

1. T001-T003 (Foundational) - Commit
2. T004-T008 (US1 + tests) - Commit
3. T009-T012 (US2 + tests) - Commit
4. T013-T014 (US3 + tests) - Commit
5. T015-T016 (API endpoint) - Commit
6. T017-T020 (Polish) - Final commit

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each phase as requested by user
- Stop at any checkpoint to validate story independently
- Template updates accumulate - each US adds to existing about.html
