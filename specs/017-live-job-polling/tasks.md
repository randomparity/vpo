# Tasks: Live Job Status Updates (Polling)

**Input**: Design documents from `/specs/017-live-job-polling/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - test tasks omitted per specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Project type**: Web application (server + client-side JavaScript)
- **Server code**: `src/video_policy_orchestrator/server/`
- **JavaScript**: `src/video_policy_orchestrator/server/static/js/`
- **Templates**: `src/video_policy_orchestrator/server/ui/templates/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and shared polling infrastructure

- [X] T001 Create polling.js module with core utilities in src/video_policy_orchestrator/server/static/js/polling.js
- [X] T002 Add polling configuration constants (interval, backoff params) in src/video_policy_orchestrator/server/static/js/polling.js
- [X] T003 [P] Add connection status CSS styles in src/video_policy_orchestrator/server/static/css/main.css

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core polling infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Implement PollingState class with start/stop/cleanup methods in src/video_policy_orchestrator/server/static/js/polling.js
- [X] T005 Implement BackoffState with exponential backoff logic (10s initial, 2min max, 3 failures trigger) in src/video_policy_orchestrator/server/static/js/polling.js
- [X] T006 [P] Add Page Visibility API integration (visibilitychange event handler) in src/video_policy_orchestrator/server/static/js/polling.js
- [X] T007 [P] Add connection status indicator element to base template in src/video_policy_orchestrator/server/ui/templates/base.html
- [X] T008 Add polling config data attributes to body element in src/video_policy_orchestrator/server/ui/templates/base.html
- [X] T009 Add polling config to template context in src/video_policy_orchestrator/server/ui/routes.py
- [X] T010 [P] Export VPOPolling namespace for use by page-specific scripts in src/video_policy_orchestrator/server/static/js/polling.js

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Automatic Status Updates on Jobs Dashboard (Priority: P1) MVP

**Goal**: Jobs dashboard automatically refreshes job list without manual page reload

**Independent Test**: Start a job, open Jobs dashboard, observe status change from running to completed without refreshing

### Implementation for User Story 1

- [X] T011 [US1] Create fetchJobsForPolling() function that preserves filter state in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T012 [US1] Implement updateJobsTable() for targeted DOM updates (update changed rows only) in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T013 [US1] Add job data comparison logic to detect changes in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T014 [US1] Integrate VPOPolling.start() on page load in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T015 [US1] Add updateJobRow() function to update individual job cells without re-rendering in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T016 [US1] Add appendJobRow() function to add new jobs to table in src/video_policy_orchestrator/server/static/js/jobs.js
- [X] T017 [US1] Wire up polling start/stop with visibility change events (pause/resume) in src/video_policy_orchestrator/server/static/js/jobs.js

**Checkpoint**: User Story 1 complete - Jobs dashboard updates automatically

---

## Phase 4: User Story 2 - Automatic Status Updates on Job Detail View (Priority: P2)

**Goal**: Job detail view automatically refreshes job status, progress, and logs

**Independent Test**: Open a running job's detail view, observe progress percentage and status update without refreshing

### Implementation for User Story 2

- [ ] T018 [US2] Create fetchJobDetailForPolling() function in src/video_policy_orchestrator/server/static/js/job_detail.js
- [ ] T019 [US2] Implement updateJobDetailFields() for targeted field updates in src/video_policy_orchestrator/server/static/js/job_detail.js
- [ ] T020 [US2] Add terminal state detection (completed/failed/cancelled) to stop polling in src/video_policy_orchestrator/server/static/js/job_detail.js
- [ ] T021 [US2] Integrate VPOPolling.start() on page load in src/video_policy_orchestrator/server/static/js/job_detail.js
- [ ] T022 [US2] Implement log polling with 15s interval (separate from job status polling) in src/video_policy_orchestrator/server/static/js/job_detail.js
- [ ] T023 [US2] Add appendNewLogLines() function for incremental log updates in src/video_policy_orchestrator/server/static/js/job_detail.js
- [ ] T024 [US2] Handle 404 response gracefully (job deleted while viewing) in src/video_policy_orchestrator/server/static/js/job_detail.js

**Checkpoint**: User Story 2 complete - Job detail view updates automatically

---

## Phase 5: User Story 3 - Progress Information for Running Jobs (Priority: P3)

**Goal**: Display detailed progress information (percentage, file counts) for running jobs

**Independent Test**: Start a scan job on a directory with multiple files, verify progress percentage and file count update

### Implementation for User Story 3

- [ ] T025 [US3] Add progress bar/percentage display element to jobs table rows in src/video_policy_orchestrator/server/static/js/jobs.js
- [ ] T026 [US3] Update renderJobRow() to include progress percentage for running jobs in src/video_policy_orchestrator/server/static/js/jobs.js
- [ ] T027 [P] [US3] Add progress bar CSS styles in src/video_policy_orchestrator/server/static/css/styles.css
- [ ] T028 [US3] Add indeterminate progress indicator for jobs without progress data in src/video_policy_orchestrator/server/static/js/jobs.js
- [ ] T029 [US3] Display processed file count (e.g., "25 of 100 files") in job detail view in src/video_policy_orchestrator/server/static/js/job_detail.js
- [ ] T030 [US3] Parse summary_raw for file count information in src/video_policy_orchestrator/server/static/js/job_detail.js

**Checkpoint**: User Story 3 complete - Progress information displays correctly

---

## Phase 6: User Story 4 - Polling Efficiency and Tab Visibility (Priority: P4)

**Goal**: Polling pauses when tab is hidden, resumes when visible

**Independent Test**: Open Jobs dashboard, switch tabs, verify no network requests; return to tab, verify polling resumes

### Implementation for User Story 4

- [ ] T031 [US4] Implement pausePolling() function in src/video_policy_orchestrator/server/static/js/polling.js
- [ ] T032 [US4] Implement resumePolling() with immediate data fetch in src/video_policy_orchestrator/server/static/js/polling.js
- [ ] T033 [US4] Add beforeunload handler to cleanup timers in src/video_policy_orchestrator/server/static/js/polling.js
- [ ] T034 [US4] Wire visibility change to pause/resume in job_detail.js in src/video_policy_orchestrator/server/static/js/job_detail.js

**Checkpoint**: User Story 4 complete - Polling is visibility-aware

---

## Phase 7: User Story 5 - Configurable Polling Interval (Priority: P5)

**Goal**: Polling interval is configurable via server configuration

**Independent Test**: Change polling config, verify polling frequency changes accordingly

### Implementation for User Story 5

- [ ] T035 [US5] Add polling_interval_ms config option to server configuration in src/video_policy_orchestrator/server/app.py or existing config module
- [ ] T036 [US5] Read polling config from data attributes in polling.js init in src/video_policy_orchestrator/server/static/js/polling.js
- [ ] T037 [US5] Validate polling interval range (2000-60000ms) with fallback to default in src/video_policy_orchestrator/server/static/js/polling.js

**Checkpoint**: User Story 5 complete - Polling interval is configurable

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T038 [P] Add subtle loading indicator during polling refresh in src/video_policy_orchestrator/server/static/js/polling.js
- [ ] T039 [P] Add console logging for polling debug (with DEBUG flag) in src/video_policy_orchestrator/server/static/js/polling.js
- [ ] T040 Verify all polling timers cleaned up on page unload (memory leak prevention) in src/video_policy_orchestrator/server/static/js/polling.js
- [ ] T041 [P] Update connection status indicator UI state on error/reconnect in src/video_policy_orchestrator/server/static/js/polling.js
- [ ] T042 Run quickstart.md manual validation checklist
- [ ] T043 Browser testing: Chrome, Firefox, Safari, Edge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Independent of US1 (different page)
- **User Story 3 (P3)**: Depends on US1 and US2 (adds to existing polling implementations)
- **User Story 4 (P4)**: Depends on US1 and US2 (adds visibility awareness to existing polling)
- **User Story 5 (P5)**: Can start after Foundational - Independent (configuration layer)

### Within Each User Story

- DOM update functions before polling integration
- Core implementation before error handling
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- US1 and US2 can run in parallel (different files: jobs.js vs job_detail.js)
- US5 can run in parallel with US1/US2/US3 (configuration layer is separate)
- All Polish tasks marked [P] can run in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch parallel foundational tasks:
Task: "Add Page Visibility API integration in polling.js" [T006]
Task: "Add connection status indicator element to base template" [T007]
Task: "Export VPOPolling namespace for use by page-specific scripts" [T010]
```

## Parallel Example: User Stories 1 and 2

```bash
# After foundational phase, launch in parallel:
# Developer A: User Story 1 (jobs.js)
Task: "Create fetchJobsForPolling() function in jobs.js" [T011]

# Developer B: User Story 2 (job_detail.js)
Task: "Create fetchJobDetailForPolling() function in job_detail.js" [T018]
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T010)
3. Complete Phase 3: User Story 1 (T011-T017)
4. **STOP and VALIDATE**: Test dashboard polling independently
5. Deploy/demo if ready - MVP delivers core value

**Total tasks**: 43 (reduced from 45 after deduplication)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test → Deploy (MVP - dashboard updates!)
3. Add User Story 2 → Test → Deploy (detail view updates!)
4. Add User Story 3 → Test → Deploy (progress info!)
5. Add User Story 4 → Test → Deploy (efficiency!)
6. Add User Story 5 → Test → Deploy (configurability!)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With two developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (jobs.js) + User Story 3 (progress in jobs)
   - Developer B: User Story 2 (job_detail.js) + User Story 4 (visibility)
3. Both: User Story 5 (config) and Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Focus on vanilla JavaScript - no framework dependencies
- Reuse existing patterns from jobs.js and job_detail.js where possible
