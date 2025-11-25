# Tasks: Plan Approve/Reject Actions

**Input**: Design documents from `/specs/027-plan-approve-reject/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in spec. Manual testing documented in quickstart.md.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4)
- Paths relative to `src/video_policy_orchestrator/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project setup needed - this feature modifies existing code.

- [ ] T001 Review existing api_plan_approve_handler in server/ui/routes.py (lines 2060-2126)
- [ ] T002 Review existing api_plan_reject_handler in server/ui/routes.py (lines 2129-2195)
- [ ] T003 [P] Review existing PlanActionResponse dataclass in server/ui/models.py
- [ ] T004 [P] Review existing handleApprove and handleReject in server/static/js/plans.js

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend response model to support job creation - blocks US1 and US4

**⚠️ CRITICAL**: Response model changes must be complete before approve handler modifications

- [x] T005 Add job_id field to PlanActionResponse dataclass in server/ui/models.py
- [x] T006 Add job_url field to PlanActionResponse dataclass in server/ui/models.py
- [x] T007 Add warning field to PlanActionResponse dataclass in server/ui/models.py
- [x] T008 Update PlanActionResponse.to_dict() method to include new fields in server/ui/models.py

**Checkpoint**: Response model ready - user story implementation can begin

---

## Phase 3: User Story 1 - Approve Plan and Queue Job (Priority: P1) 🎯 MVP

**Goal**: When operator approves a pending plan, create an APPLY job with priority scheduling and return job link

**Independent Test**: Navigate to plans list → Click Approve on pending plan → Confirm → Verify plan status = "approved" AND job appears in jobs queue with priority=10

### Implementation for User Story 1

- [x] T009 [US1] Import Job, JobType, JobStatus, insert_job from db.models in server/ui/routes.py
- [x] T010 [US1] Import uuid and datetime modules in server/ui/routes.py (if not already present)
- [x] T011 [US1] Fetch PlanRecord before status update in api_plan_approve_handler in server/ui/routes.py
- [x] T012 [US1] Create Job instance with JobType.APPLY and priority=10 in api_plan_approve_handler in server/ui/routes.py
- [x] T013 [US1] Call insert_job() to persist job within transaction in api_plan_approve_handler in server/ui/routes.py
- [x] T014 [US1] Update api_plan_approve_handler to return job_id and job_url in response in server/ui/routes.py
- [x] T015 [US1] Add structured audit logging for approve action with plan_id, job_id, timestamp in server/ui/routes.py

**Checkpoint**: Approve action creates job and returns job_id - US1 backend complete

---

## Phase 4: User Story 2 - Reject Plan (Priority: P1)

**Goal**: Reject action marks plan as permanently rejected with audit logging

**Independent Test**: Navigate to plans list → Click Reject on pending plan → Confirm → Verify plan status = "rejected"

### Implementation for User Story 2

- [x] T016 [US2] Add structured audit logging for reject action with plan_id, timestamp in api_plan_reject_handler in server/ui/routes.py

**Checkpoint**: Reject action logs audit entry - US2 backend complete

**Note**: Reject handler already updates status correctly. Only audit logging needs to be added.

---

## Phase 5: User Story 3 - Confirmation Dialogs (Priority: P2)

**Goal**: Both approve and reject actions require confirmation dialog before execution

**Independent Test**: Click Approve → Verify dialog appears → Cancel → Verify no state change

### Implementation for User Story 3

- [ ] T017 [US3] Add confirmation dialog to handleApprove function in server/static/js/plans.js
- [ ] T018 [US3] Customize approve dialog title to "Approve Plan" in server/static/js/plans.js
- [ ] T019 [US3] Customize approve dialog message to explain job creation in server/static/js/plans.js
- [ ] T020 [US3] Customize approve dialog confirmText to "Approve and Queue" in server/static/js/plans.js

**Checkpoint**: Both actions show confirmation dialogs - US3 complete

**Note**: Reject already has confirmation dialog (lines 503-517 in plans.js). Only approve needs it.

---

## Phase 6: User Story 4 - Navigation After Approval (Priority: P2)

**Goal**: After approval, show success message with link to created job

**Independent Test**: Approve plan → Verify toast shows job link → Click link → Navigate to job detail

### Implementation for User Story 4

- [ ] T021 [US4] Update handleApprove success handler to check for job_url in response in server/static/js/plans.js
- [ ] T022 [US4] Modify showToast call to include job link HTML when job_url present in server/static/js/plans.js
- [ ] T023 [US4] Handle warning field in response (file deleted case) in server/static/js/plans.js

**Checkpoint**: Success toast shows job link - US4 complete

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Error handling improvements and edge cases

- [ ] T024 [P] Add file existence check before approval in api_plan_approve_handler in server/ui/routes.py
- [ ] T025 [P] Return warning in response if file no longer exists in api_plan_approve_handler in server/ui/routes.py
- [ ] T026 Verify double-submit prevention works with new confirmation flow in server/static/js/plans.js
- [ ] T027 Run manual test cases from quickstart.md to validate all scenarios
- [ ] T028 Verify concurrent modification error handling works correctly

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - code review only
- **Phase 2 (Foundational)**: No dependencies - can start immediately
- **Phase 3 (US1)**: Depends on Phase 2 completion (needs response model fields)
- **Phase 4 (US2)**: No dependencies on other phases - can run parallel to Phase 3
- **Phase 5 (US3)**: No backend dependencies - can run parallel to Phase 3/4
- **Phase 6 (US4)**: Depends on Phase 3 (needs job_url in response)
- **Phase 7 (Polish)**: Depends on all user stories complete

### User Story Dependencies

```
Phase 2 (Foundational)
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
Phase 3 (US1)     Phase 4 (US2)     Phase 5 (US3)
    │                  │                  │
    ▼                  │                  │
Phase 6 (US4)          │                  │
    │                  │                  │
    └──────────────────┴──────────────────┘
                       │
                       ▼
               Phase 7 (Polish)
```

### Parallel Opportunities

**Within Phase 1 (all parallel - code review only):**
- T003, T004 can run in parallel

**Within Phase 2 (sequential - same file):**
- T005 → T006 → T007 → T008 (all modify same dataclass)

**Across Phases 3, 4, 5 (can run in parallel):**
- US1 tasks (T009-T015) - backend routes.py
- US2 tasks (T016) - backend routes.py (different handler, but same file - sequential with US1)
- US3 tasks (T017-T020) - frontend plans.js (parallel with backend work)

**Within Phase 7 (parallel):**
- T024, T025 can run in parallel

---

## Parallel Example: Initial Backend + Frontend

```bash
# After Phase 2, launch backend and frontend work in parallel:

# Backend (routes.py modifications):
Task: "[US1] Import Job, JobType, JobStatus, insert_job from db.models"
Task: "[US1] Create Job instance with JobType.APPLY and priority=10"
Task: "[US1] Call insert_job() to persist job within transaction"
# ... continue US1 backend tasks

# Frontend (plans.js modifications - can run in parallel):
Task: "[US3] Add confirmation dialog to handleApprove function"
Task: "[US3] Customize approve dialog title to 'Approve Plan'"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Response model fields
2. Complete Phase 3: US1 - Approve creates job
3. **STOP and VALIDATE**: Test approve action creates job with priority=10
4. This delivers core value - plans can now be executed

### Incremental Delivery

1. **Phase 2** → Response model ready
2. **Phase 3 (US1)** → Approve creates job → Test → **MVP Complete!**
3. **Phase 4 (US2)** → Reject has audit logging → Test
4. **Phase 5 (US3)** → Approve has confirmation → Test
5. **Phase 6 (US4)** → Toast shows job link → Test
6. **Phase 7** → Polish and edge cases → Final validation

### Single Developer Strategy

1. Complete Phases 1-2 (setup + foundational)
2. Complete Phase 3 (US1) - most important
3. Complete Phase 5 (US3) - adds confirmation to US1
4. Complete Phase 6 (US4) - enhances US1 with job link
5. Complete Phase 4 (US2) - reject audit logging
6. Complete Phase 7 - polish

---

## Notes

- Total tasks: 28
- US1: 7 tasks (T009-T015) - Core approve + job creation
- US2: 1 task (T016) - Reject audit logging only
- US3: 4 tasks (T017-T020) - Approve confirmation dialog
- US4: 3 tasks (T021-T023) - Job link in success toast
- Setup: 4 tasks (T001-T004) - Code review
- Foundational: 4 tasks (T005-T008) - Response model
- Polish: 5 tasks (T024-T028) - Edge cases and validation
- Main parallel opportunity: Backend (routes.py) and Frontend (plans.js) can be developed simultaneously
- All backend tasks for same handler should be sequential (same function)
- Commit after each user story phase for clean history
