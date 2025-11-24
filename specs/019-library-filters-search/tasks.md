# Tasks: Library Filters and Search

**Input**: Design documents from `/specs/019-library-filters-search/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in spec - test tasks omitted.

**Organization**: Tasks grouped by user story. US2 and US3 are both P2 priority but independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US6)
- Exact file paths included in descriptions

## Path Conventions

- **Backend**: `src/video_policy_orchestrator/` (existing structure)
- **Frontend**: `src/video_policy_orchestrator/server/static/` and `server/ui/templates/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend existing models with new filter parameters - shared by all user stories

- [ ] T001 Extend LibraryFilterParams with search field in src/video_policy_orchestrator/server/ui/models.py
- [ ] T002 Extend LibraryFilterParams with resolution field in src/video_policy_orchestrator/server/ui/models.py
- [ ] T003 Extend LibraryFilterParams with audio_lang field (list) in src/video_policy_orchestrator/server/ui/models.py
- [ ] T004 Extend LibraryFilterParams with subtitles field in src/video_policy_orchestrator/server/ui/models.py
- [ ] T005 Add resolution_options and subtitles_options to LibraryContext.default() in src/video_policy_orchestrator/server/ui/models.py
- [ ] T006 Update has_filters logic in api_library_handler to include all new filter params in src/video_policy_orchestrator/server/ui/routes.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core backend query changes that ALL filters depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 Add search parameter (filename/title LIKE) to get_files_filtered() in src/video_policy_orchestrator/db/models.py
- [ ] T008 Add resolution parameter (height range) to get_files_filtered() in src/video_policy_orchestrator/db/models.py
- [ ] T009 Add audio_lang parameter (IN clause with OR logic) to get_files_filtered() in src/video_policy_orchestrator/db/models.py
- [ ] T010 Add subtitles parameter (EXISTS/NOT EXISTS subquery) to get_files_filtered() in src/video_policy_orchestrator/db/models.py
- [ ] T011 Wire new filter params from api_library_handler to get_files_filtered() in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T012 Add get_distinct_audio_languages() function in src/video_policy_orchestrator/db/models.py
- [ ] T013 Add /api/library/languages endpoint handler in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T014 Register /api/library/languages route in src/video_policy_orchestrator/server/ui/routes.py

**Checkpoint**: Backend API fully supports all filter parameters

---

## Phase 3: User Story 1 - Text Search for Files (Priority: P1) MVP

**Goal**: Users can search files by typing filename or title fragments

**Independent Test**: Type "avatar" in search box, verify only matching files appear

### Implementation for User Story 1

- [ ] T015 [US1] Add search input HTML element to filter bar in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [ ] T016 [US1] Implement debounce utility function (300ms) in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T017 [US1] Add search input event handler with debounce in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T018 [US1] Update buildQueryString() to include search param in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T019 [US1] Update currentFilters state object with search field in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T020 [US1] Initialize search input from URL params on page load in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T021 [US1] Update empty state message for filtered results in src/video_policy_orchestrator/server/static/js/library.js

**Checkpoint**: Text search fully functional - US1 complete

---

## Phase 4: User Story 2 - Filter by Resolution (Priority: P2)

**Goal**: Users can filter files by resolution category (4K, 1080p, etc.)

**Independent Test**: Select "1080p" from dropdown, verify only 1080p files appear

### Implementation for User Story 2

- [ ] T022 [US2] Add resolution dropdown HTML element to filter bar in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [ ] T023 [US2] Add resolution filter event handler in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T024 [US2] Update buildQueryString() to include resolution param in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T025 [US2] Update currentFilters state object with resolution field in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T026 [US2] Initialize resolution dropdown from URL params on page load in src/video_policy_orchestrator/server/static/js/library.js

**Checkpoint**: Resolution filter functional - US2 complete

---

## Phase 5: User Story 3 - Filter by Audio Language (Priority: P2)

**Goal**: Users can filter by audio language with multi-select OR logic

**Independent Test**: Select "jpn" language, verify only files with Japanese audio appear

### Implementation for User Story 3

- [ ] T027 [US3] Add audio language multi-select dropdown HTML element to filter bar in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [ ] T028 [US3] Fetch /api/library/languages on page load and populate dropdown in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T029 [US3] Add audio language filter event handler (multi-select) in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T030 [US3] Update buildQueryString() to include audio_lang params (multiple values) in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T031 [US3] Update currentFilters state object with audio_lang array in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T032 [US3] Initialize audio language selection from URL params on page load in src/video_policy_orchestrator/server/static/js/library.js

**Checkpoint**: Audio language filter functional - US3 complete

---

## Phase 6: User Story 4 - Filter by Subtitle Presence (Priority: P3)

**Goal**: Users can filter files by whether they have subtitles

**Independent Test**: Select "Has subtitles", verify only files with subtitle tracks appear

### Implementation for User Story 4

- [ ] T033 [US4] Add subtitles dropdown HTML element to filter bar in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [ ] T034 [US4] Add subtitles filter event handler in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T035 [US4] Update buildQueryString() to include subtitles param in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T036 [US4] Update currentFilters state object with subtitles field in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T037 [US4] Initialize subtitles dropdown from URL params on page load in src/video_policy_orchestrator/server/static/js/library.js

**Checkpoint**: Subtitle presence filter functional - US4 complete

---

## Phase 7: User Story 5 - Clear All Filters (Priority: P3)

**Goal**: Users can reset all filters with one action

**Independent Test**: Apply multiple filters, click "Clear filters", verify all reset

### Implementation for User Story 5

- [ ] T038 [US5] Add "Clear filters" button HTML element to filter bar in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [ ] T039 [US5] Implement clearAllFilters() function in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T040 [US5] Add click handler for Clear filters button in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T041 [US5] Show/hide Clear filters button based on hasActiveFilters() in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T042 [US5] Implement hasActiveFilters() helper function in src/video_policy_orchestrator/server/static/js/library.js

**Checkpoint**: Clear filters button functional - US5 complete

---

## Phase 8: User Story 6 - Active Filter Visibility (Priority: P3)

**Goal**: Users can see at a glance which filters are active

**Independent Test**: Apply filters, verify visual indicators show active state

### Implementation for User Story 6

- [ ] T043 [US6] Add CSS class for active filter state in src/video_policy_orchestrator/server/static/css/library.css
- [ ] T044 [US6] Update filter dropdowns to show active state visually in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T045 [US6] Update search input to show active state when has text in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T046 [US6] Implement updateFilterVisuals() function called after any filter change in src/video_policy_orchestrator/server/static/js/library.js

**Checkpoint**: Active filter indicators working - US6 complete

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: URL sync, pagination reset, and integration testing

- [ ] T047 Implement updateUrl() using history.replaceState in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T048 Call updateUrl() after every filter change in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T049 Ensure pagination resets to offset=0 on any filter change in src/video_policy_orchestrator/server/static/js/library.js
- [ ] T050 Add structured logging for filter API requests in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T051 Run quickstart.md validation checklist manually
- [ ] T052 Verify combined filters work correctly (search + resolution + audio + subtitles)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - extends existing models
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phases 3-8 (User Stories)**: All depend on Phase 2 completion
  - US1 (P1): Can proceed first (MVP)
  - US2, US3 (P2): Can proceed in parallel after US1
  - US4, US5, US6 (P3): Can proceed in parallel after US2/US3
- **Phase 9 (Polish)**: Depends on all user stories

### User Story Dependencies

- **US1 (Text Search)**: Independent after Phase 2
- **US2 (Resolution)**: Independent after Phase 2 - can parallelize with US3
- **US3 (Audio Language)**: Independent after Phase 2 - can parallelize with US2
- **US4 (Subtitles)**: Independent after Phase 2
- **US5 (Clear Filters)**: Depends on US1-US4 being implemented (needs filters to clear)
- **US6 (Active Visibility)**: Depends on US1-US4 being implemented (needs filters to visualize)

### Within Each User Story

- HTML template changes before JavaScript handlers
- State management before event handlers
- URL param initialization before filter logic

### Parallel Opportunities

- T001-T006 (Setup) can be done in single file session
- T007-T010 (DB query extensions) can be parallelized
- T012-T014 (languages endpoint) can parallelize with T007-T011
- US2 and US3 can be implemented in parallel by different developers
- US4, US5, US6 can be implemented in parallel once US1-US3 are complete

---

## Parallel Example: Foundational Phase

```bash
# These can run in parallel (different query conditions):
Task: "Add search parameter to get_files_filtered()"
Task: "Add resolution parameter to get_files_filtered()"
Task: "Add audio_lang parameter to get_files_filtered()"
Task: "Add subtitles parameter to get_files_filtered()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T014)
3. Complete Phase 3: User Story 1 - Text Search (T015-T021)
4. **STOP and VALIDATE**: Test search independently
5. Deploy/demo text search feature

### Incremental Delivery

1. Setup + Foundational → Backend ready for all filters
2. Add US1 (Text Search) → Test → Deploy (MVP!)
3. Add US2 (Resolution) → Test → Deploy
4. Add US3 (Audio Language) → Test → Deploy
5. Add US4 (Subtitles) → Test → Deploy
6. Add US5 (Clear Filters) → Test → Deploy
7. Add US6 (Active Visibility) → Test → Deploy
8. Polish phase → Final validation

### Parallel Team Strategy

With 2 developers after Phase 2:
- Developer A: US1 → US4 → US5
- Developer B: US2 → US3 → US6
- Merge and validate combined functionality

---

## Notes

- All filter changes use existing fetchLibrary() pattern from 018
- Debounce only applies to text search (300ms)
- Dropdown changes trigger immediate fetch
- URL sync uses replaceState to avoid history pollution
- Empty state message already exists - just update text for filtered results
