# Tasks: Jobs Dashboard List View

**Input**: Design documents from `/specs/015-jobs-dashboard/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/jobs-api.yaml

**Tests**: Not explicitly requested in specification. Test tasks omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**User Request**: Commit code changes to the branch after completing each phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Project structure**: `src/video_policy_orchestrator/` at repository root
- **Templates**: `src/video_policy_orchestrator/server/ui/templates/`
- **Static files**: `src/video_policy_orchestrator/server/static/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project verification and baseline validation

- [X] T001 Verify existing project structure matches plan.md expectations
- [X] T002 Verify jobs table schema exists in src/video_policy_orchestrator/db/schema.py
- [X] T003 Verify existing daemon server runs: `uv run vpo serve --help`

**Commit after Phase 1**: N/A (no code changes - verification only)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and API endpoint that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Add JobFilterParams dataclass in src/video_policy_orchestrator/server/ui/models.py
- [X] T005 [P] Add JobListItem dataclass in src/video_policy_orchestrator/server/ui/models.py
- [X] T006 [P] Add JobListResponse dataclass in src/video_policy_orchestrator/server/ui/models.py
- [X] T007 [P] Add JobListContext dataclass in src/video_policy_orchestrator/server/ui/models.py
- [X] T008 Implement api_jobs_handler function in src/video_policy_orchestrator/server/ui/routes.py
- [X] T009 Register /api/jobs route in src/video_policy_orchestrator/server/app.py
- [X] T010 Add jobs table CSS styles in src/video_policy_orchestrator/server/static/css/main.css

**Checkpoint**: API endpoint `/api/jobs` returns JSON data. Foundation ready for UI implementation.

**Commit after Phase 2**: `git commit -m "feat(015): Add /api/jobs endpoint and foundational models"`

---

## Phase 3: User Story 1 - View Recent Jobs (Priority: P1) MVP

**Goal**: Display all recent jobs in a table with columns: Job ID, Type, Status, Start time, End time/duration, Target. Sorted by start time descending.

**Independent Test**: Navigate to /jobs, verify jobs table displays with all columns and correct data sorted by most recent first.

### Implementation for User Story 1

- [X] T011 [US1] Replace placeholder in src/video_policy_orchestrator/server/ui/templates/sections/jobs.html with jobs table structure
- [X] T012 [US1] Create src/video_policy_orchestrator/server/static/js/jobs.js with fetchJobs() function
- [X] T013 [US1] Implement renderJobsTable() in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T014 [US1] Implement formatDuration() helper for elapsed time display in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T015 [US1] Update jobs_handler in src/video_policy_orchestrator/server/ui/routes.py to pass JobListContext
- [X] T016 [US1] Add script tag for jobs.js in src/video_policy_orchestrator/server/ui/templates/sections/jobs.html

**Checkpoint**: Jobs page displays all jobs in a table with correct columns and sorting.

**Commit after Phase 3**: `git commit -m "feat(015): Implement jobs table display (US1 - View Recent Jobs)"`

---

## Phase 4: User Story 2 - Filter Jobs by Status (Priority: P2)

**Goal**: Allow filtering jobs by status (queued, running, completed, failed, cancelled) via dropdown filter.

**Independent Test**: Select "failed" status filter, verify only failed jobs displayed. Clear filter, verify all jobs shown.

### Implementation for User Story 2

- [X] T017 [US2] Add status filter dropdown to src/video_policy_orchestrator/server/ui/templates/sections/jobs.html
- [X] T018 [US2] Implement handleStatusFilter() in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T019 [US2] Update fetchJobs() to include status query parameter in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T020 [US2] Add status filter styles in src/video_policy_orchestrator/server/static/css/main.css

**Checkpoint**: Status filter dropdown works, filters jobs correctly, clear filter restores all jobs.

**Commit after Phase 4**: `git commit -m "feat(015): Add status filter (US2 - Filter by Status)"`

---

## Phase 5: User Story 3 - Filter Jobs by Type (Priority: P3)

**Goal**: Allow filtering jobs by type (scan, apply, transcode, move) via dropdown filter.

**Independent Test**: Select "transcode" type filter, verify only transcode jobs displayed. Combine with status filter, verify both filters apply.

### Implementation for User Story 3

- [X] T021 [US3] Add type filter dropdown to src/video_policy_orchestrator/server/ui/templates/sections/jobs.html
- [X] T022 [US3] Implement handleTypeFilter() in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T023 [US3] Update fetchJobs() to include type query parameter in src/video_policy_orchestrator/server/static/js/jobs.js

**Checkpoint**: Type filter dropdown works, combines correctly with status filter (verifies FR-009 AND logic).

**Commit after Phase 5**: `git commit -m "feat(015): Add type filter (US3 - Filter by Type)"`

---

## Phase 6: User Story 4 - Filter Jobs by Time Range (Priority: P4)

**Goal**: Allow filtering jobs by time range (last 24 hours, last 7 days, all time) via dropdown filter.

**Independent Test**: Select "last 24 hours", verify only recent jobs displayed. Combine with other filters.

### Implementation for User Story 4

- [X] T024 [US4] Add time range filter dropdown to src/video_policy_orchestrator/server/ui/templates/sections/jobs.html
- [X] T025 [US4] Implement handleTimeFilter() in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T026 [US4] Update fetchJobs() to include since query parameter in src/video_policy_orchestrator/server/static/js/jobs.js

**Checkpoint**: Time range filter works, combines correctly with status and type filters.

**Commit after Phase 6**: `git commit -m "feat(015): Add time range filter (US4 - Filter by Time)"`

---

## Phase 7: User Story 5 - Empty State Handling (Priority: P5)

**Goal**: Display helpful empty state messages when no jobs exist or no jobs match filters.

**Independent Test**: View jobs page with no jobs in DB, verify empty state message. Apply filter with no matches, verify "no matching jobs" message.

### Implementation for User Story 5

- [X] T027 [US5] Add empty state HTML structure in src/video_policy_orchestrator/server/ui/templates/sections/jobs.html
- [X] T028 [US5] Implement renderEmptyState() in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T029 [US5] Add empty state styles in src/video_policy_orchestrator/server/static/css/main.css
- [X] T030 [US5] Update renderJobsTable() to handle has_filters flag in src/video_policy_orchestrator/server/static/js/jobs.js

**Checkpoint**: Empty states display appropriate messages for no jobs and no matching jobs scenarios.

**Commit after Phase 7**: `git commit -m "feat(015): Add empty state handling (US5 - Empty States)"`

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T031 [P] Add pagination controls to src/video_policy_orchestrator/server/ui/templates/sections/jobs.html
- [X] T032 [P] Implement pagination handling in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T033 [P] Add path truncation with tooltip for long file paths in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T034 [P] Add status color indicators (visual badges) in src/video_policy_orchestrator/server/static/css/main.css
- [X] T035 [P] Add loading state while fetching jobs in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T036 [P] Handle unknown/invalid job status gracefully in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T037 Run quickstart.md validation: verify all API endpoints and UI interactions work

**Commit after Phase 8**: `git commit -m "feat(015): Add pagination, polish, and visual improvements"`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verification only
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phases 3-7)**: All depend on Foundational phase completion
  - User stories should be completed in priority order (P1 → P2 → P3 → P4 → P5)
  - Each builds incrementally on the previous
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Creates base table structure
- **User Story 2 (P2)**: Depends on US1 - Adds status filter to existing table
- **User Story 3 (P3)**: Depends on US2 - Adds type filter alongside status filter
- **User Story 4 (P4)**: Depends on US3 - Adds time filter alongside other filters
- **User Story 5 (P5)**: Depends on US1 - Can be done in parallel with US2-4, but logically completes last

### Within Each User Story

- Templates before JavaScript
- JavaScript logic before styles (where both needed)
- Handler updates before template if template depends on context

### Parallel Opportunities

- All Foundational tasks T004-T007 (dataclasses) can run in parallel
- T010 (CSS) can run in parallel with T008-T009 (routes)
- All Polish tasks T031-T035 marked [P] can run in parallel

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all dataclass tasks together:
Task: "Add JobFilterParams dataclass in src/video_policy_orchestrator/server/ui/models.py"
Task: "Add JobListItem dataclass in src/video_policy_orchestrator/server/ui/models.py"
Task: "Add JobListResponse dataclass in src/video_policy_orchestrator/server/ui/models.py"
Task: "Add JobListContext dataclass in src/video_policy_orchestrator/server/ui/models.py"

# Then handler and route (sequential):
Task: "Implement api_jobs_handler function in src/video_policy_orchestrator/server/ui/routes.py"
Task: "Register /api/jobs route in src/video_policy_orchestrator/server/app.py"

# CSS can run in parallel with handler:
Task: "Add jobs table CSS styles in src/video_policy_orchestrator/server/static/css/main.css"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verification)
2. Complete Phase 2: Foundational (API endpoint + models)
3. Complete Phase 3: User Story 1 (jobs table display)
4. **STOP and VALIDATE**: Test jobs page independently
5. Deploy/demo if ready - users can view jobs!

### Incremental Delivery

1. Complete Setup + Foundational → API ready
2. Add User Story 1 → Test table display → Deploy (MVP!)
3. Add User Story 2 → Test status filter → Deploy
4. Add User Story 3 → Test type filter → Deploy
5. Add User Story 4 → Test time filter → Deploy
6. Add User Story 5 → Test empty states → Deploy
7. Complete Polish → Full feature done

### Commit Strategy

Per user request, commit after each phase:
- Phase 2: Foundation models and API
- Phase 3: US1 - View jobs
- Phase 4: US2 - Status filter
- Phase 5: US3 - Type filter
- Phase 6: US4 - Time filter
- Phase 7: US5 - Empty states
- Phase 8: Polish and pagination

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story builds on previous but adds independent value
- No tests explicitly requested in spec - test tasks omitted
- Commit messages follow conventional commit format with feature number
- Stop at any checkpoint to validate incrementally
