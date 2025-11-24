# Tasks: Library List View

**Input**: Design documents from `/specs/018-library-list-view/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are NOT explicitly requested in this feature specification. Test tasks are omitted per template guidelines.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md, this extends the existing VPO project structure:

```text
src/video_policy_orchestrator/
├── db/models.py                    # Database query functions
├── server/ui/models.py             # View models
├── server/ui/routes.py             # Route handlers
├── server/ui/templates/sections/   # HTML templates
└── server/static/                  # CSS and JavaScript
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No setup tasks needed - this feature extends existing infrastructure

This feature builds on existing VPO web infrastructure (aiohttp, Jinja2, SQLite). No new project setup required.

**Checkpoint**: Existing infrastructure is ready. Proceed to foundational tasks.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T001 [P] Add `get_resolution_label()` helper function in src/video_policy_orchestrator/server/ui/models.py
- [X] T002 [P] Add `format_audio_languages()` helper function in src/video_policy_orchestrator/server/ui/models.py
- [X] T003 Add `LibraryFilterParams` dataclass in src/video_policy_orchestrator/server/ui/models.py
- [X] T004 Add `FileListItem` dataclass in src/video_policy_orchestrator/server/ui/models.py
- [X] T005 Add `FileListResponse` dataclass in src/video_policy_orchestrator/server/ui/models.py
- [X] T006 Add `LibraryContext` dataclass in src/video_policy_orchestrator/server/ui/models.py
- [X] T007 Add `get_files_filtered()` query function in src/video_policy_orchestrator/db/models.py

**Checkpoint**: Foundation ready - all view models and database query exist. User story implementation can now begin.

---

## Phase 3: User Story 1 - Browse Scanned Library (Priority: P1) 🎯 MVP

**Goal**: Users can browse scanned video files in a table with filename, title, resolution, audio languages, last scanned, and policy profile columns.

**Independent Test**: Navigate to `/library` and verify scanned files display in table with all required columns, sorted by most recently scanned first.

### Implementation for User Story 1

- [X] T008 [US1] Add `library_api_handler()` API endpoint in src/video_policy_orchestrator/server/ui/routes.py
- [X] T009 [US1] Register `/api/library` route in `setup_ui_routes()` in src/video_policy_orchestrator/server/ui/routes.py
- [X] T010 [US1] Add `library_handler()` HTML page handler in src/video_policy_orchestrator/server/ui/routes.py
- [X] T011 [US1] Register `/library` route in `setup_ui_routes()` in src/video_policy_orchestrator/server/ui/routes.py
- [X] T012 [US1] Create library table HTML structure in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [X] T013 [US1] Create library.js with `fetchLibrary()` and `renderLibraryTable()` in src/video_policy_orchestrator/server/static/js/library.js
- [X] T014 [US1] Add `formatRelativeTime()` function in library.js for timestamp display
- [X] T015 [US1] Add library table CSS styles in src/video_policy_orchestrator/server/static/css/main.css
- [X] T016 [US1] Add status filter dropdown to library.html template
- [X] T017 [US1] Add filter change handler in library.js

**Checkpoint**: At this point, User Story 1 should be fully functional - users can view scanned files in a table with all columns.

---

## Phase 4: User Story 2 - Handle Empty Library State (Priority: P2)

**Goal**: Users see a helpful empty state message when no files have been scanned.

**Independent Test**: View `/library` with an empty database and verify helpful empty state message appears with guidance on how to scan files.

### Implementation for User Story 2

- [X] T018 [US2] Add empty state HTML section to library.html in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [X] T019 [US2] Add `renderEmptyState()` function in src/video_policy_orchestrator/server/static/js/library.js
- [X] T020 [US2] Add empty state CSS styles (`.library-empty`) in src/video_policy_orchestrator/server/static/css/main.css
- [X] T021 [US2] Update `renderLibraryTable()` to show/hide empty state based on file count

**Checkpoint**: At this point, User Story 2 should be functional - empty library shows helpful guidance message.

---

## Phase 5: User Story 3 - Navigate Large Libraries with Pagination (Priority: P3)

**Goal**: Users can navigate through large file collections using pagination controls.

**Independent Test**: Populate library with 100+ files and verify pagination controls appear, Previous/Next work correctly, and disabled states are correct at boundaries.

### Implementation for User Story 3

- [X] T022 [US3] Add pagination HTML section to library.html in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [X] T023 [US3] Add pagination state variables (currentOffset, pageSize, totalFiles) in src/video_policy_orchestrator/server/static/js/library.js
- [X] T024 [US3] Add `updatePagination()` function in src/video_policy_orchestrator/server/static/js/library.js
- [X] T025 [US3] Add `handlePrevPage()` and `handleNextPage()` handlers in src/video_policy_orchestrator/server/static/js/library.js
- [X] T026 [US3] Add pagination CSS styles (`.library-pagination`) in src/video_policy_orchestrator/server/static/css/main.css
- [X] T027 [US3] Update `fetchLibrary()` to include offset parameter for pagination

**Checkpoint**: All user stories should now be independently functional - full library browsing with empty state and pagination.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T028 Add loading state spinner while fetching library data in library.html and library.js
- [X] T029 Add error state handling for API failures in library.js
- [X] T030 [P] Add scan error visual indicator (warning icon) for files with scan_status="error" in library.js
- [X] T031 [P] Add tooltip for full file path on hover in library.js
- [X] T032 Run manual validation against quickstart.md test scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No setup needed - existing infrastructure
- **Foundational (Phase 2)**: No dependencies - can start immediately
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories should proceed sequentially (P1 → P2 → P3) as they share files
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after US1 - Extends library.html and library.js from US1
- **User Story 3 (P3)**: Can start after US2 - Extends library.html and library.js from US1/US2

### Within Each User Story

- Models before routes (Phase 2)
- API handler before HTML handler
- HTML template before JavaScript
- JavaScript before CSS (styling adjustments)

### Parallel Opportunities

- Within Phase 2: T001 and T002 can run in parallel (different functions)
- Within Phase 6: T030 and T031 can run in parallel (different features)
- Note: User stories share library.html and library.js files, so cannot be parallelized across stories

---

## Parallel Example: Foundational Phase

```bash
# Launch helper functions in parallel:
Task: "Add get_resolution_label() helper function in src/video_policy_orchestrator/server/ui/models.py"
Task: "Add format_audio_languages() helper function in src/video_policy_orchestrator/server/ui/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (view models + database query)
2. Complete Phase 3: User Story 1 (table display)
3. **STOP and VALIDATE**: Verify Library page shows files with all columns
4. Deploy/demo if ready

### Incremental Delivery

1. Complete Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test empty state → Deploy/Demo
4. Add User Story 3 → Test pagination → Deploy/Demo
5. Complete Polish phase → Final release

### File Change Summary

| File | Phase | Changes |
|------|-------|---------|
| `server/ui/models.py` | 2 | Add 6 new classes/functions |
| `db/models.py` | 2 | Add `get_files_filtered()` |
| `server/ui/routes.py` | 3 | Add 2 handlers, register 2 routes |
| `templates/sections/library.html` | 3-5 | Replace placeholder with full template |
| `static/js/library.js` | 3-5 | New file with all Library page logic |
| `static/css/main.css` | 3-6 | Add library-specific CSS classes |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- User stories share library.html and library.js, so implement sequentially
- Verify each user story checkpoint before proceeding
- Commit after each task or logical group
- Reference jobs.html and jobs.js patterns throughout implementation
