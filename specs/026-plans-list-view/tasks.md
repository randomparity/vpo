# Tasks: Plans List View

**Input**: Design documents from `/specs/026-plans-list-view/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in spec - tests omitted.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- **Backend**: `src/video_policy_orchestrator/`
- **Templates**: `src/video_policy_orchestrator/server/ui/templates/sections/`
- **JavaScript**: `src/video_policy_orchestrator/server/static/js/`

---

## Phase 1: Setup

**Purpose**: Database schema and core data model for plans

- [ ] T001 Add PlanStatus enum to src/video_policy_orchestrator/db/models.py with values: pending, approved, rejected, applied, canceled
- [ ] T002 Add PlanRecord dataclass to src/video_policy_orchestrator/db/models.py following OperationRecord pattern
- [ ] T003 Add plans table DDL and migration logic to src/video_policy_orchestrator/db/schema.py (schema v7 → v8)
- [ ] T004 Add indexes for plans table (status, created_at DESC, file_id, policy_name) in src/video_policy_orchestrator/db/schema.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database operations and API models that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Implement create_plan() function in src/video_policy_orchestrator/db/operations.py
- [ ] T006 Implement get_plan_by_id() function in src/video_policy_orchestrator/db/operations.py
- [ ] T007 Implement get_plans_filtered() function with pagination in src/video_policy_orchestrator/db/operations.py
- [ ] T008 Implement update_plan_status() function with state machine validation in src/video_policy_orchestrator/db/operations.py
- [ ] T009 [P] Add PlanFilterParams dataclass to src/video_policy_orchestrator/server/ui/models.py with from_query() method
- [ ] T010 [P] Add PlanListItem dataclass to src/video_policy_orchestrator/server/ui/models.py with to_dict() method
- [ ] T011 [P] Add PlanListResponse dataclass to src/video_policy_orchestrator/server/ui/models.py with to_dict() method
- [ ] T012 [P] Add PlansContext dataclass to src/video_policy_orchestrator/server/ui/models.py for template context

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - View All Plans (Priority: P1) 🎯 MVP

**Goal**: Display list of all plans with ID, creation time, source, file count, status

**Independent Test**: Navigate to /plans and verify plans are displayed with all required columns; verify empty state when no plans exist

### Implementation for User Story 1

- [ ] T013 [US1] Implement plans_handler() HTML route for GET /plans in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T014 [US1] Implement api_plans_handler() JSON route for GET /api/plans in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T015 [US1] Register /plans and /api/plans routes in src/video_policy_orchestrator/server/ui/routes.py setup_ui_routes()
- [ ] T016 [US1] Create plans.html template with table structure in src/video_policy_orchestrator/server/ui/templates/sections/plans.html
- [ ] T017 [US1] Add status badge styling (color-coded by status) to plans.html template
- [ ] T018 [US1] Add empty state message display to plans.html template
- [ ] T019 [US1] Create plans.js with initial fetch and table rendering in src/video_policy_orchestrator/server/static/js/plans.js
- [ ] T020 [US1] Implement formatSourceDisplay() helper for "[Deleted]" indicator handling in src/video_policy_orchestrator/server/static/js/plans.js
- [ ] T021 [US1] Implement formatRelativeTime() helper for "2 hours ago" display in src/video_policy_orchestrator/server/static/js/plans.js
- [ ] T022 [US1] Add pagination controls and logic to plans.js
- [ ] T023 [US1] Add "Plans" link to navigation in src/video_policy_orchestrator/server/ui/templates/base.html

**Checkpoint**: User Story 1 complete - basic list view functional with pagination

---

## Phase 4: User Story 2 - Filter Plans by Status (Priority: P2)

**Goal**: Allow filtering plans by status (pending, approved, rejected, applied, canceled)

**Independent Test**: Apply status filter and verify only matching plans appear; clear filter and verify all plans return

### Implementation for User Story 2

- [ ] T024 [US2] Add status filter dropdown to plans.html filter bar
- [ ] T025 [US2] Implement status filter state management in plans.js (currentFilters.status)
- [ ] T026 [US2] Wire status dropdown change event to refetch with filter in plans.js
- [ ] T027 [US2] Ensure API handler parses status query parameter in src/video_policy_orchestrator/server/ui/routes.py

**Checkpoint**: User Story 2 complete - status filtering works independently

---

## Phase 5: User Story 3 - Filter Plans by Creation Time (Priority: P2)

**Goal**: Allow filtering plans by time range (24h, 7d, 30d)

**Independent Test**: Apply time filter and verify only plans within range appear; clear filter and verify all plans return

### Implementation for User Story 3

- [ ] T028 [US3] Add time range filter dropdown to plans.html filter bar (Today, Last 7 days, Last 30 days)
- [ ] T029 [US3] Implement time filter state management in plans.js (currentFilters.since)
- [ ] T030 [US3] Wire time dropdown change event to refetch with filter in plans.js
- [ ] T031 [US3] Ensure API handler parses since query parameter and computes datetime threshold in src/video_policy_orchestrator/server/ui/routes.py

**Checkpoint**: User Story 3 complete - time filtering works independently

---

## Phase 6: User Story 4 - Approve or Reject Plans Inline (Priority: P2)

**Goal**: Allow approve/reject actions directly from list view for pending plans

**Independent Test**: Click Approve on pending plan → status changes to approved; click Reject → status changes to rejected; non-pending plans show no buttons

### Implementation for User Story 4

- [ ] T032 [US4] Add PlanActionResponse dataclass to src/video_policy_orchestrator/server/ui/models.py
- [ ] T033 [US4] Implement api_plan_approve_handler() for POST /api/plans/{id}/approve in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T034 [US4] Implement api_plan_reject_handler() for POST /api/plans/{id}/reject in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T035 [US4] Register /api/plans/{id}/approve and /api/plans/{id}/reject routes in setup_ui_routes()
- [ ] T036 [US4] Add Approve/Reject button column to plans.html table (conditional on pending status)
- [ ] T037 [US4] Implement handleApprove() and handleReject() click handlers in plans.js
- [ ] T038 [US4] Add toast notification for successful approve/reject action in plans.js
- [ ] T039 [US4] Update row status immediately after successful action (optimistic or refetch) in plans.js

**Checkpoint**: User Story 4 complete - inline actions work for pending plans

---

## Phase 7: User Story 5 - Navigate to Plan Details (Priority: P3)

**Goal**: Allow clicking a plan row to navigate to detail view

**Independent Test**: Click on plan row (not action button) → browser navigates to /plans/{id}

### Implementation for User Story 5

- [ ] T040 [US5] Add clickable row wrapper to plans.html table rows (excluding action buttons)
- [ ] T041 [US5] Implement row click handler in plans.js that navigates to /plans/{plan_id}
- [ ] T042 [US5] Add cursor:pointer styling for plan rows in plans.html or CSS
- [ ] T043 [US5] Ensure action button clicks don't bubble up to row click handler (event.stopPropagation)

**Checkpoint**: User Story 5 complete - plan rows are clickable (detail view is separate feature)

---

## Phase 8: User Story 6 - Live Updates via Polling (Priority: P3)

**Goal**: Auto-refresh list every 5 seconds to show status changes from other users/processes

**Independent Test**: Change plan status via another session → list updates within 5 seconds without manual refresh

### Implementation for User Story 6

- [ ] T044 [US6] Import and initialize VPOPolling module in plans.js
- [ ] T045 [US6] Implement fetchPlansForPolling() that preserves current filter/pagination state in plans.js
- [ ] T046 [US6] Implement smart row updates (compare cached data, update only changed rows) in plans.js
- [ ] T047 [US6] Add connection status indicator to plans.html (similar to jobs dashboard)
- [ ] T048 [US6] Ensure polling pauses when tab is hidden and resumes when visible in plans.js

**Checkpoint**: User Story 6 complete - live polling updates the list automatically

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T049 [P] Add structured logging for plan status transitions in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T050 [P] Add error handling for API failures with user-friendly messages in plans.js
- [ ] T051 [P] Verify empty filter results show appropriate message in plans.js
- [ ] T052 Run manual test of all user stories per quickstart.md validation
- [ ] T053 Update navigation active state when on Plans page
- [ ] T054 [P] Update docs/usage/ with plans approval workflow documentation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1 (P1) should complete first as MVP
  - US2, US3, US4 (all P2) can proceed in parallel after US1
  - US5, US6 (both P3) can proceed in parallel after P2 stories
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: MVP - delivers core list view. Must complete before others.
- **User Story 2 (P2)**: Extends US1 with status filter - independent of US3, US4
- **User Story 3 (P2)**: Extends US1 with time filter - independent of US2, US4
- **User Story 4 (P2)**: Extends US1 with action buttons - independent of US2, US3
- **User Story 5 (P3)**: Extends US1 with navigation - requires clickable rows from US1
- **User Story 6 (P3)**: Extends US1 with polling - requires JS infrastructure from US1

### Within Each User Story

- API endpoints before UI components
- HTML template structure before JavaScript behavior
- Core functionality before polish (styling, notifications)

### Parallel Opportunities

**Setup Phase:**
```
T001, T002 → T003, T004 (sequential: model before schema)
```

**Foundational Phase:**
```
T005-T008 → sequential (DB operations build on each other)
T009, T010, T011, T012 → parallel (different API model files/classes)
```

**User Story 1:**
```
T013-T015 → sequential (route handlers)
T016-T018 → parallel with T013-T015 (template)
T019-T022 → after T016 (JS needs template)
T023 → parallel with any
```

**P2 Stories (US2, US3, US4) after US1:**
```
US2: T024-T027 → parallel with US3 and US4
US3: T028-T031 → parallel with US2 and US4
US4: T032-T039 → parallel with US2 and US3
```

---

## Parallel Example: Foundational Phase

```bash
# After T005-T008 complete, launch API models in parallel:
Task: "Add PlanFilterParams dataclass to src/video_policy_orchestrator/server/ui/models.py"
Task: "Add PlanListItem dataclass to src/video_policy_orchestrator/server/ui/models.py"
Task: "Add PlanListResponse dataclass to src/video_policy_orchestrator/server/ui/models.py"
Task: "Add PlansContext dataclass to src/video_policy_orchestrator/server/ui/models.py"
```

## Parallel Example: P2 Stories

```bash
# After US1 complete, launch all P2 stories in parallel:
# Developer A: US2 (status filter)
Task: "Add status filter dropdown to plans.html filter bar"

# Developer B: US3 (time filter)
Task: "Add time range filter dropdown to plans.html filter bar"

# Developer C: US4 (inline actions)
Task: "Implement api_plan_approve_handler() for POST /api/plans/{id}/approve"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T012)
3. Complete Phase 3: User Story 1 (T013-T023)
4. **STOP and VALIDATE**: Test US1 independently - list displays plans with pagination
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test → Deploy (MVP with basic list!)
3. Add User Stories 2, 3, 4 (P2) → Test → Deploy (filtering + actions)
4. Add User Stories 5, 6 (P3) → Test → Deploy (navigation + polling)
5. Complete Polish → Final release

### Single Developer Strategy

Execute in strict priority order:
1. Setup (Phase 1)
2. Foundational (Phase 2)
3. US1 → US2 → US3 → US4 → US5 → US6
4. Polish (Phase 9)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Plan detail view (US5 navigation target) is a separate feature - this feature only adds the link
