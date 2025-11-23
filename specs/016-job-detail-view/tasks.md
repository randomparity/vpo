# Tasks: Job Detail View with Logs

**Input**: Design documents from `/specs/016-job-detail-view/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in specification. Test tasks are NOT included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/video_policy_orchestrator/`, `tests/` at repository root
- Paths follow existing VPO project structure per plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for job detail feature

- [ ] T001 Create logs directory structure in src/video_policy_orchestrator/jobs/ (create __init__.py if needed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 Add log_path field to Job dataclass in src/video_policy_orchestrator/db/models.py
- [ ] T003 Update _row_to_job() to handle log_path field in src/video_policy_orchestrator/db/models.py
- [ ] T004 Update insert_job() to include log_path field in src/video_policy_orchestrator/db/models.py
- [ ] T005 Update get_job() query to select log_path field in src/video_policy_orchestrator/db/models.py
- [ ] T006 Update get_jobs_filtered() query to select log_path field in src/video_policy_orchestrator/db/models.py
- [ ] T007 Implement migrate_v7_to_v8() for log_path column in src/video_policy_orchestrator/db/schema.py
- [ ] T008 Update initialize_database() to call migrate_v7_to_v8() in src/video_policy_orchestrator/db/schema.py
- [ ] T009 Update SCHEMA_VERSION to 8 and SCHEMA_SQL to include log_path in src/video_policy_orchestrator/db/schema.py
- [ ] T010 [P] Create log file utilities module in src/video_policy_orchestrator/jobs/logs.py (get_log_directory, get_log_path, read_log_tail with DEFAULT_LOG_LINES=500, count_log_lines)
- [ ] T011 [P] Add JobDetailItem dataclass to src/video_policy_orchestrator/server/ui/models.py
- [ ] T012 [P] Add JobLogsResponse dataclass to src/video_policy_orchestrator/server/ui/models.py
- [ ] T013 [P] Add JobDetailContext dataclass to src/video_policy_orchestrator/server/ui/models.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - View Full Job Details (Priority: P1) 🎯 MVP

**Goal**: Click on a job in the dashboard list to view its complete details with all metadata fields

**Independent Test**: Navigate to `/jobs/{job_id}`, verify all job fields displayed correctly (ID, type, status, timestamps, target path, policy name, progress, error message)

### Implementation for User Story 1

- [ ] T014 [US1] Add api_job_detail_handler() route handler in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T015 [US1] Add job_detail_handler() HTML page handler in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T016 [US1] Register /jobs/{job_id} and /api/jobs/{job_id} routes in setup_ui_routes() in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T017 [US1] Create job_detail.html template with status badge (FR-012) in src/video_policy_orchestrator/server/ui/templates/sections/job_detail.html
- [ ] T018 [US1] Add CSS styles for job detail view including status badge colors (FR-012) in src/video_policy_orchestrator/server/ui/static/css/styles.css
- [ ] T019 [US1] Update jobs.html to make job rows clickable (link to detail) in src/video_policy_orchestrator/server/ui/templates/sections/jobs.html
- [ ] T020 [US1] Create job_detail.js for relative timestamps and client-side enhancements in src/video_policy_orchestrator/server/ui/static/js/job_detail.js

**Checkpoint**: User Story 1 complete - can view full job details with metadata, timestamps, and status badge

---

## Phase 4: User Story 2 - View Human-Readable Summary (Priority: P2)

**Goal**: See a human-readable summary of what a job accomplished based on job type

**Independent Test**: Open a completed scan/apply job, verify summary displays (e.g., "Scanned 85 files, 3 changed")

### Implementation for User Story 2

- [ ] T021 [US2] Add generate_summary_text() function for human-readable summaries in src/video_policy_orchestrator/server/ui/models.py
- [ ] T022 [US2] Implement scan job summary formatting in generate_summary_text() in src/video_policy_orchestrator/server/ui/models.py
- [ ] T023 [US2] Implement apply job summary formatting in generate_summary_text() in src/video_policy_orchestrator/server/ui/models.py
- [ ] T024 [US2] Implement transcode job summary formatting in generate_summary_text() in src/video_policy_orchestrator/server/ui/models.py
- [ ] T025 [US2] Implement move job summary formatting in generate_summary_text() in src/video_policy_orchestrator/server/ui/models.py
- [ ] T026 [US2] Add summary section to job_detail.html template in src/video_policy_orchestrator/server/ui/templates/sections/job_detail.html
- [ ] T027 [US2] Handle missing summary_json gracefully (show "No summary available") in src/video_policy_orchestrator/server/ui/models.py

**Checkpoint**: User Story 2 complete - job summaries display human-readable outcome text based on job type

---

## Phase 5: User Story 3 - View Job Logs (Priority: P3)

**Goal**: View log output from job execution in a scrollable area with lazy loading

**Independent Test**: Open a job with logs, verify logs display in monospace format; test "Load More" for large logs

### Implementation for User Story 3

- [ ] T028 [US3] Add api_job_logs_handler() route handler in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T029 [US3] Register /api/jobs/{job_id}/logs route in setup_ui_routes() in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T030 [US3] Add logs section with scrollable container to job_detail.html in src/video_policy_orchestrator/server/ui/templates/sections/job_detail.html
- [ ] T031 [US3] Add CSS styles for logs container (monospace, scrollable, max-height) in src/video_policy_orchestrator/server/ui/static/css/styles.css
- [ ] T032 [US3] Implement logs fetching and display in job_detail.js in src/video_policy_orchestrator/server/ui/static/js/job_detail.js
- [ ] T033 [US3] Implement "Load More" pagination for large logs in job_detail.js in src/video_policy_orchestrator/server/ui/static/js/job_detail.js
- [ ] T034 [US3] Handle missing logs gracefully (show "No logs available") in job_detail.js in src/video_policy_orchestrator/server/ui/static/js/job_detail.js

**Checkpoint**: User Story 3 complete - logs display with lazy loading support

---

## Phase 6: User Story 4 - Navigate Back to Job List (Priority: P4)

**Goal**: Navigate back to job list from detail view with filter state preserved

**Independent Test**: Apply filters on jobs list, click into detail, click back - verify filters preserved

### Implementation for User Story 4

- [ ] T035 [US4] Add back navigation link to job_detail.html template in src/video_policy_orchestrator/server/ui/templates/sections/job_detail.html
- [ ] T036 [US4] Implement filter state preservation (read referer or URL params) in job_detail_handler() in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T037 [US4] Style back navigation button/link in src/video_policy_orchestrator/server/ui/static/css/styles.css

**Checkpoint**: User Story 4 complete - navigation back to list preserves filter state

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, edge cases, and final polish

- [ ] T038 [P] Add 404 error page for job not found in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T039 [P] Add UUID format validation for job_id parameter in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T040 [P] Handle long file paths (truncation with tooltip) in job_detail.html and CSS
- [ ] T041 [P] Handle null/empty fields (display "—" placeholder) in job_detail.html template
- [ ] T042 [P] Handle long error messages (word-wrap, scrollable) in CSS styles
- [ ] T043 Run manual validation per quickstart.md scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can proceed in priority order (P1 → P2 → P3 → P4)
  - Or in parallel if team capacity allows
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - MVP, no dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Extends US1 template but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Adds logs to US1 template but independently testable
- **User Story 4 (P4)**: Can start after US1 - Adds navigation to existing detail view

### Within Each User Story

- Models/utilities before route handlers
- Route handlers before templates
- Templates before JavaScript
- Core implementation before polish

### Parallel Opportunities

- Phase 2: T010, T011, T012, T013 can run in parallel (different files)
- Phase 7: T037, T038, T039, T040, T041 can run in parallel (different concerns)
- User stories can be parallelized across team members after Phase 2 completes

---

## Parallel Example: Foundational Phase

```bash
# Launch all parallel foundational tasks together:
Task: "Create log file utilities module in src/video_policy_orchestrator/jobs/logs.py"
Task: "Add JobDetailItem dataclass to src/video_policy_orchestrator/server/ui/models.py"
Task: "Add JobLogsResponse dataclass to src/video_policy_orchestrator/server/ui/models.py"
Task: "Add JobDetailContext dataclass to src/video_policy_orchestrator/server/ui/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 - View Full Job Details
4. **STOP and VALIDATE**: Test clicking jobs and viewing details
5. Deploy/demo if ready - basic job detail view is functional

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test summaries → Deploy/Demo
4. Add User Story 3 → Test logs → Deploy/Demo
5. Add User Story 4 → Test navigation → Deploy/Demo
6. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Schema migration (T007-T009) must be tested with existing databases
