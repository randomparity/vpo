# Tasks: Transcriptions Overview List

**Input**: Design documents from `/specs/021-transcriptions-list/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.yaml

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/video_policy_orchestrator/`
- **Tests**: `tests/unit/`, `tests/integration/`
- Follows existing VPO web application structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project setup required - extending existing VPO web stack

> This phase is empty because we are extending an existing codebase with established infrastructure.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data access and model infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T001 Add `get_confidence_level()` helper function in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T002 Add `format_detected_languages()` helper function in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T003 Add `get_files_with_transcriptions()` query function in `src/video_policy_orchestrator/db/models.py`
- [ ] T004 [P] Add `TranscriptionFilterParams` dataclass in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T005 [P] Add `TranscriptionListItem` dataclass in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T006 [P] Add `TranscriptionListResponse` dataclass in `src/video_policy_orchestrator/server/ui/models.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - View Files with Transcription Data (Priority: P1) 🎯 MVP

**Goal**: Display a table of files with transcription data showing filename, transcription indicator, detected languages, and confidence levels

**Independent Test**: Navigate to `/transcriptions` and verify files with transcription data appear in a table with relevant columns. Verify empty state shows when no transcriptions exist.

### Implementation for User Story 1

- [ ] T007 [US1] Update `transcriptions_handler()` to return proper template context in `src/video_policy_orchestrator/server/ui/routes.py`
- [ ] T008 [US1] Implement `api_transcriptions_handler()` endpoint in `src/video_policy_orchestrator/server/ui/routes.py`
- [ ] T009 [US1] Register `/api/transcriptions` route in `setup_ui_routes()` in `src/video_policy_orchestrator/server/ui/routes.py`
- [ ] T010 [US1] Create transcriptions table template in `src/video_policy_orchestrator/server/ui/templates/sections/transcriptions.html`
- [ ] T011 [US1] Add confidence badge CSS styles in `src/video_policy_orchestrator/server/static/css/main.css`
- [ ] T012 [US1] Create `transcriptions.js` with API fetch and table rendering (including "Not analyzed" indicator for files without transcription data) in `src/video_policy_orchestrator/server/static/js/transcriptions.js`
- [ ] T013 [US1] Implement loading state in `transcriptions.js`
- [ ] T014 [US1] Implement empty state handling (no transcriptions) in `transcriptions.js`
- [ ] T015 [US1] Implement pagination controls in `transcriptions.js`

**Checkpoint**: User Story 1 complete - Transcriptions page displays files with transcription data, languages, and confidence levels

---

## Phase 4: User Story 2 - Toggle Filter to Show All Files (Priority: P2)

**Goal**: Add a toggle that allows users to view all files including those without transcription data

**Independent Test**: Click "Show all files" toggle and verify non-transcribed files appear. Toggle off and verify only transcribed files show.

### Implementation for User Story 2

- [ ] T016 [US2] Add "Show all files" toggle HTML to `src/video_policy_orchestrator/server/ui/templates/sections/transcriptions.html`
- [ ] T017 [US2] Add toggle CSS styling in `src/video_policy_orchestrator/server/static/css/main.css`
- [ ] T018 [US2] Implement toggle state management in `transcriptions.js`
- [ ] T019 [US2] Update API calls to include `show_all` parameter in `transcriptions.js`
- [ ] T020 [US2] Update empty state message based on filter in `transcriptions.js`

**Checkpoint**: User Story 2 complete - Toggle switches between transcribed-only and all-files views

---

## Phase 5: User Story 3 - Navigate to File Detail (Priority: P3)

**Goal**: Enable clicking a file row to navigate to the existing File Detail view

**Independent Test**: Click any file row and verify navigation to `/library/{file_id}`. Use browser back to return to Transcriptions page.

### Implementation for User Story 3

- [ ] T021 [US3] Make table rows clickable links to `/library/{file_id}` in `src/video_policy_orchestrator/server/ui/templates/sections/transcriptions.html`
- [ ] T022 [US3] Add row hover styles for clickable indication in `src/video_policy_orchestrator/server/static/css/main.css`
- [ ] T023 [US3] Preserve filter state in URL for back navigation in `transcriptions.js`

**Checkpoint**: User Story 3 complete - File rows navigate to detail view with back navigation preserved

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and code quality improvements

- [ ] T024 Verify all edge cases: error status files (including files no longer accessible showing error indicator), boundary confidence values (0.0, 1.0), files with multiple languages
- [ ] T025 Test pagination with varying data sizes
- [ ] T026 Run `uv run ruff check .` and fix any linting issues
- [ ] T027 Run `uv run ruff format .` to ensure consistent formatting
- [ ] T028 Manual testing: Follow quickstart.md verification checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Empty - using existing infrastructure
- **Foundational (Phase 2)**: No dependencies - can start immediately
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can proceed sequentially in priority order (P1 → P2 → P3)
  - US2 and US3 modify files created in US1, so sequential execution recommended
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Foundational (Phase 2) - Core functionality
- **User Story 2 (P2)**: Depends on US1 (extends template and JS created in US1)
- **User Story 3 (P3)**: Depends on US1 (extends template and JS created in US1)

### Within Each User Story

- Route handlers before templates
- Templates before JavaScript
- Core functionality before enhancements

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T004, T005, T006 can run in parallel (separate dataclass definitions)
- T001, T002 should complete before T003 (T003 may use helpers)

**Within User Stories**:
- Limited parallelism due to file dependencies (template → JS → CSS)

---

## Parallel Example: Foundational Phase

```bash
# Launch parallel model creation:
Task: "T004 [P] Add TranscriptionFilterParams dataclass in models.py"
Task: "T005 [P] Add TranscriptionListItem dataclass in models.py"
Task: "T006 [P] Add TranscriptionListResponse dataclass in models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001-T006)
2. Complete Phase 3: User Story 1 (T007-T015)
3. **STOP and VALIDATE**: Test Transcriptions page independently
4. Deploy/demo if ready

### Incremental Delivery

1. Complete Foundational → Foundation ready
2. Add User Story 1 → Test independently → MVP ready!
3. Add User Story 2 → Test filter toggle → Enhanced filtering
4. Add User Story 3 → Test navigation → Full feature complete
5. Polish phase → Production ready

### Sequential Recommendation

Due to file overlap between user stories, sequential implementation is recommended:
- Single developer: P1 → P2 → P3
- The same files (transcriptions.html, transcriptions.js, main.css) are modified across stories

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in same phase
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable once completed
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Follow existing patterns from Library view (018) and File Detail view (020)
