# Tasks: Web UI REST API Endpoints

**Input**: Design documents from `/specs/028-webui-rest-api/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Key Finding**: All 16 API endpoints are already implemented. This feature is documentation-only.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Documentation**: `docs/` at repository root
- **Existing code**: `src/vpo/server/ui/routes.py`
- **Existing models**: `src/vpo/server/ui/models.py`

---

## Phase 1: Setup (Documentation Framework)

**Purpose**: Create API documentation structure and verify existing endpoints

- [X] T001 Create docs/api-webui.md with initial structure (title, introduction, conventions section)
- [X] T002 Add API documentation entry to docs/INDEX.md with proper categorization

**Checkpoint**: Documentation file exists with basic structure

**Commit**: `docs: Create API reference structure for Web UI endpoints`

---

## Phase 2: Foundational (Endpoint Verification)

**Purpose**: Verify all endpoints are functional before documenting them

**Note**: All endpoints are already implemented. This phase confirms they work as expected.

- [X] T003 Start daemon and verify GET /api/jobs returns valid JSON response
- [X] T004 [P] Verify GET /api/library returns valid JSON response
- [X] T005 [P] Verify GET /api/transcriptions returns valid JSON response
- [X] T006 [P] Verify GET /api/policies returns valid JSON response
- [X] T007 [P] Verify GET /api/plans returns valid JSON response

**Checkpoint**: All list endpoints confirmed functional

---

## Phase 3: User Story 1 - Document List Endpoints (Priority: P1) MVP

**Goal**: Document all GET list endpoints so frontend developers can fetch paginated data

**Independent Test**: A developer can read the documentation and successfully call any list endpoint

### Implementation for User Story 1

- [X] T008 [US1] Document GET /api/jobs in docs/api-webui.md (query params: status, type, since, limit, offset)
- [X] T009 [P] [US1] Document GET /api/library in docs/api-webui.md (query params: status, search, resolution, audio_lang, subtitles, limit, offset)
- [X] T010 [P] [US1] Document GET /api/library/languages in docs/api-webui.md (no params, returns available languages)
- [X] T011 [P] [US1] Document GET /api/transcriptions in docs/api-webui.md (query params: show_all, limit, offset)
- [X] T012 [P] [US1] Document GET /api/policies in docs/api-webui.md (no params, returns all policies)
- [X] T013 [P] [US1] Document GET /api/plans in docs/api-webui.md (query params: status, since, policy_name, limit, offset)

**Checkpoint**: All list endpoints documented with parameters and response examples

**Commit**: `docs: Add list endpoint documentation for Web UI API (US1)`

---

## Phase 4: User Story 2 - Document Detail Endpoints (Priority: P1)

**Goal**: Document all GET detail endpoints so frontend developers can fetch single resources

**Independent Test**: A developer can read the documentation and successfully fetch details for any resource

### Implementation for User Story 2

- [X] T014 [US2] Document GET /api/jobs/{id} in docs/api-webui.md (path param: job_id as UUID)
- [X] T015 [P] [US2] Document GET /api/jobs/{id}/logs in docs/api-webui.md (query params: lines, offset)
- [X] T016 [P] [US2] Document GET /api/jobs/{id}/errors in docs/api-webui.md (returns scan errors for job)
- [X] T017 [P] [US2] Document GET /api/library/{id} in docs/api-webui.md (path param: file_id as integer)
- [X] T018 [P] [US2] Document GET /api/transcriptions/{id} in docs/api-webui.md (path param: transcription_id as integer)
- [X] T019 [P] [US2] Document GET /api/policies/{name} in docs/api-webui.md (path param: name as string)

**Checkpoint**: All detail endpoints documented with path parameters and response examples

**Commit**: `docs: Add detail endpoint documentation for Web UI API (US2)`

---

## Phase 5: User Story 3 - Document Policy Modification Endpoints (Priority: P2)

**Goal**: Document PUT and POST endpoints for policy editing

**Independent Test**: A developer can read the documentation and successfully update a policy

### Implementation for User Story 3

- [X] T020 [US3] Document PUT /api/policies/{name} in docs/api-webui.md (request body, CSRF requirement, concurrency handling)
- [X] T021 [P] [US3] Document POST /api/policies/{name}/validate in docs/api-webui.md (dry-run validation)
- [X] T022 [US3] Document validation error response format in docs/api-webui.md (structured errors with field, message, code)
- [X] T023 [US3] Document concurrent modification handling (409 Conflict response) in docs/api-webui.md

**Checkpoint**: Policy modification endpoints documented with request/response examples and error cases

**Commit**: `docs: Add policy modification endpoint documentation (US3)`

---

## Phase 6: User Story 4 - Document Plan Action Endpoints (Priority: P2)

**Goal**: Document POST endpoints for plan approve/reject workflow

**Independent Test**: A developer can read the documentation and successfully approve or reject a plan

### Implementation for User Story 4

- [X] T024 [US4] Document POST /api/plans/{id}/approve in docs/api-webui.md (CSRF requirement, job creation)
- [X] T025 [P] [US4] Document POST /api/plans/{id}/reject in docs/api-webui.md (CSRF requirement, state transition)
- [X] T026 [US4] Document plan state machine (pending → approved/rejected) in docs/api-webui.md
- [X] T027 [US4] Document PlanActionResponse format (success, plan, job_id, job_url, warning, error)

**Checkpoint**: Plan action endpoints documented with state transitions and response examples

**Commit**: `docs: Add plan action endpoint documentation (US4)`

---

## Phase 7: User Story 5 - Complete API Reference (Priority: P3)

**Goal**: Finalize comprehensive API reference documentation

**Independent Test**: A frontend developer can implement all UI features using only the documentation

### Implementation for User Story 5

- [X] T028 [US5] Add common response patterns section to docs/api-webui.md (pagination, errors, timestamps)
- [X] T029 [P] [US5] Add CSRF protection section to docs/api-webui.md (how to obtain and use tokens)
- [X] T030 [P] [US5] Add error handling section to docs/api-webui.md (400, 404, 409, 503 responses)
- [X] T031 [US5] Add authentication notes section to docs/api-webui.md (future feature placeholder)
- [X] T032 [US5] Review and verify all documentation examples match actual API behavior

**Checkpoint**: Complete API reference documentation ready for use

**Commit**: `docs: Complete Web UI API reference documentation (US5)`

---

## Phase 8: Polish & Final Verification

**Purpose**: Final review and integration

- [X] T033 [P] Verify docs/api-webui.md follows VPO documentation conventions
- [X] T034 [P] Run spell check and grammar review on docs/api-webui.md
- [X] T035 Verify all linked resources (related docs) are valid in docs/api-webui.md
- [X] T036 Mark tasks complete in specs/028-webui-rest-api/tasks.md

**Commit**: `docs: Finalize Web UI REST API documentation (028-webui-rest-api)`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - creates documentation structure
- **Foundational (Phase 2)**: Depends on Setup - verifies endpoints work
- **User Stories (Phase 3-7)**: All depend on Phase 1 & 2 completion
  - User stories can proceed sequentially in priority order (P1 → P2 → P3)
  - Or tasks within each story can run in parallel where marked [P]
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: List endpoints - no dependencies on other stories
- **User Story 2 (P1)**: Detail endpoints - can reference list endpoint patterns from US1
- **User Story 3 (P2)**: Policy modification - references patterns from US1/US2
- **User Story 4 (P2)**: Plan actions - references patterns from US1/US2
- **User Story 5 (P3)**: Complete reference - integrates all previous documentation

### Within Each User Story

- Tasks marked [P] can run in parallel (documenting different endpoints)
- Non-[P] tasks may depend on previous tasks for consistency

### Parallel Opportunities

- T004-T007: All foundational verification can run in parallel
- T009-T013: All list endpoint documentation can run in parallel
- T015-T019: All detail endpoint documentation can run in parallel
- T029-T030: Common sections can be written in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all list endpoint documentation tasks together:
Task: "Document GET /api/library in docs/api-webui.md"
Task: "Document GET /api/library/languages in docs/api-webui.md"
Task: "Document GET /api/transcriptions in docs/api-webui.md"
Task: "Document GET /api/policies in docs/api-webui.md"
Task: "Document GET /api/plans in docs/api-webui.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T007) - verify endpoints work
3. Complete Phase 3: User Story 1 (T008-T013) - document list endpoints
4. **STOP and VALIDATE**: Frontend developer can use list endpoints
5. Commit and potentially deploy documentation

### Incremental Delivery

1. Complete Setup + Foundational → Documentation structure ready
2. Add User Story 1 → List endpoint docs → Usable MVP
3. Add User Story 2 → Detail endpoint docs → Enhanced docs
4. Add User Story 3 → Policy modification docs → Complete write docs
5. Add User Story 4 → Plan action docs → Complete action docs
6. Add User Story 5 → Final polish → Production-ready docs

### Commit Strategy (Per User Request)

Commit after each phase completes:
- Phase 1: `docs: Create API reference structure for Web UI endpoints`
- Phase 3: `docs: Add list endpoint documentation for Web UI API (US1)`
- Phase 4: `docs: Add detail endpoint documentation for Web UI API (US2)`
- Phase 5: `docs: Add policy modification endpoint documentation (US3)`
- Phase 6: `docs: Add plan action endpoint documentation (US4)`
- Phase 7: `docs: Complete Web UI API reference documentation (US5)`
- Phase 8: `docs: Finalize Web UI REST API documentation (028-webui-rest-api)`

---

## Notes

- All 16 endpoints already implemented - this is documentation-only work
- No code changes required to endpoints
- Reference `contracts/openapi.yaml` for response schemas
- Reference `data-model.md` for entity definitions
- Reference existing handler docstrings in `server/ui/routes.py` for behavior details
- Commit after each phase as requested by user
