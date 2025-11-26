# Tasks: Web UI Authentication

**Input**: Design documents from `/specs/029-webui-auth/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included - feature requires verification of security behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/video_policy_orchestrator/`, `tests/` at repository root
- Paths follow existing VPO structure per plan.md

---

## Phase 1: Setup (Configuration Extension)

**Purpose**: Extend configuration to support auth token

- [X] T001 [P] Add `auth_token: str | None = None` field to ServerConfig dataclass in src/video_policy_orchestrator/config/models.py
- [X] T002 [P] Add VPO_AUTH_TOKEN environment variable handling in src/video_policy_orchestrator/config/loader.py (env takes precedence over config file)

---

## Phase 2: Foundational (Auth Module)

**Purpose**: Core authentication infrastructure that all user stories depend on

**⚠️ CRITICAL**: User story implementation depends on this phase

- [X] T003 Create auth module with parse_basic_auth() function in src/video_policy_orchestrator/server/auth.py
- [X] T004 Add validate_token() function using secrets.compare_digest() in src/video_policy_orchestrator/server/auth.py
- [X] T005 Add is_auth_enabled() helper function in src/video_policy_orchestrator/server/auth.py
- [X] T006 Create create_auth_middleware() factory function in src/video_policy_orchestrator/server/auth.py

**Checkpoint**: Auth module ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Operator Protects Web UI With Token (Priority: P1) 🎯 MVP

**Goal**: When auth token is configured, all endpoints (except /health) require valid credentials. Invalid/missing credentials return 401.

**Independent Test**: Configure VPO_AUTH_TOKEN, start server, verify unauthenticated requests get 401 and authenticated requests succeed.

### Tests for User Story 1

- [X] T007 [P] [US1] Unit test for parse_basic_auth() including special character tokens (!, @, #, spaces) in tests/unit/server/test_auth.py
- [X] T008 [P] [US1] Unit test for validate_token() with constant-time comparison in tests/unit/server/test_auth.py
- [X] T009 [P] [US1] Unit test for auth middleware rejecting missing credentials in tests/unit/server/test_auth.py
- [X] T010 [P] [US1] Unit test for auth middleware rejecting invalid credentials in tests/unit/server/test_auth.py
- [X] T011 [P] [US1] Unit test for auth middleware allowing valid credentials in tests/unit/server/test_auth.py
- [X] T012 [P] [US1] Unit test for /health endpoint bypassing auth in tests/unit/server/test_auth.py

### Implementation for User Story 1

- [X] T013 [US1] Implement auth_middleware that checks Authorization header in src/video_policy_orchestrator/server/auth.py
- [X] T014 [US1] Add 401 response with WWW-Authenticate header for failed auth in src/video_policy_orchestrator/server/auth.py
- [X] T015 [US1] Add /health path exclusion logic in auth middleware in src/video_policy_orchestrator/server/auth.py
- [X] T016 [US1] Integrate auth middleware into create_app() in src/video_policy_orchestrator/server/app.py
- [X] T017 [US1] Integration test: protected endpoint rejects unauthenticated request in tests/integration/server/test_auth_integration.py
- [X] T018 [US1] Integration test: protected endpoint accepts valid Basic Auth in tests/integration/server/test_auth_integration.py

**Checkpoint**: Core auth protection working - requests without valid token are rejected

---

## Phase 4: User Story 2 - Operator Runs Without Auth (Priority: P2)

**Goal**: When no auth token is configured, server operates without authentication (backward compatible). Warning logged at startup.

**Independent Test**: Start server without VPO_AUTH_TOKEN, verify all endpoints accessible without credentials and warning is logged.

### Tests for User Story 2

- [X] T019 [P] [US2] Unit test for is_auth_enabled() returning False for None/empty token in tests/unit/server/test_auth.py
- [X] T020 [P] [US2] Unit test for is_auth_enabled() returning False for whitespace-only token in tests/unit/server/test_auth.py

### Implementation for User Story 2

- [X] T021 [US2] Add conditional middleware registration (skip if auth disabled) in src/video_policy_orchestrator/server/app.py
- [X] T022 [US2] Add startup warning log when auth is disabled in src/video_policy_orchestrator/server/app.py
- [X] T023 [US2] Integration test: all endpoints accessible when auth disabled in tests/integration/server/test_auth_integration.py
- [X] T024 [US2] Integration test: warning logged when auth disabled in tests/integration/server/test_auth_integration.py

**Checkpoint**: Backward compatibility confirmed - existing deployments without auth continue to work

---

## Phase 5: User Story 3 - Browser-Based Authentication (Priority: P3)

**Goal**: Browser users see native login dialog when accessing protected UI. Credentials cached for session.

**Independent Test**: Open Web UI in browser with auth enabled, verify login dialog appears, enter credentials, verify subsequent pages don't re-prompt.

### Tests for User Story 3

- [X] T025 [P] [US3] Unit test for WWW-Authenticate header format in 401 response in tests/unit/server/test_auth.py

### Implementation for User Story 3

- [X] T026 [US3] Verify 401 response includes correct WWW-Authenticate: Basic realm="VPO" header in src/video_policy_orchestrator/server/auth.py
- [X] T027 [US3] Integration test: 401 response triggers browser auth dialog (verify header presence) in tests/integration/server/test_auth_integration.py

**Checkpoint**: Browser authentication flow complete - users can log in via native browser dialog

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final validation

- [ ] T028 [P] Add auth configuration section to docs/usage/authentication.md with examples for env var and config file
- [ ] T029 [P] Add security disclaimer to docs/usage/authentication.md noting auth is minimal/not production-grade per FR-010
- [ ] T030 Run all tests to verify no regressions: `uv run pytest tests/unit/server/test_auth.py tests/integration/server/test_auth_integration.py`
- [ ] T031 Manual validation: follow quickstart.md steps end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 (Phase 3): Must complete first (core auth logic)
  - US2 (Phase 4): Can proceed after US1 or in parallel
  - US3 (Phase 5): Can proceed after US1 or in parallel
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P2)**: Shares auth.py with US1 but tests different code path - can work in parallel
- **User Story 3 (P3)**: Verifies header behavior from US1 - minimal dependency, mostly parallel

### Within Each User Story

- Tests written first (T007-T012, T019-T020, T025)
- Implementation follows tests
- Integration tests verify end-to-end behavior

### Parallel Opportunities

- T001, T002: Config changes can run in parallel (different files)
- T007-T012: All US1 unit tests can run in parallel
- T019-T020: US2 unit tests can run in parallel
- US2 and US3 can largely proceed in parallel once US1 core is done

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all US1 unit tests together:
Task: "Unit test for parse_basic_auth() in tests/unit/server/test_auth.py"
Task: "Unit test for validate_token() in tests/unit/server/test_auth.py"
Task: "Unit test for auth middleware rejecting missing credentials in tests/unit/server/test_auth.py"
Task: "Unit test for auth middleware rejecting invalid credentials in tests/unit/server/test_auth.py"
Task: "Unit test for auth middleware allowing valid credentials in tests/unit/server/test_auth.py"
Task: "Unit test for /health endpoint bypassing auth in tests/unit/server/test_auth.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T006)
3. Complete Phase 3: User Story 1 (T007-T018)
4. **STOP and VALIDATE**: Test with `VPO_AUTH_TOKEN=secret vpo serve` and curl commands
5. Deploy/demo if ready - core protection is functional

### Incremental Delivery

1. Setup + Foundational → Auth module ready
2. Add User Story 1 → Core auth working → MVP!
3. Add User Story 2 → Backward compatibility confirmed
4. Add User Story 3 → Browser UX verified
5. Polish → Documentation complete

### Single Developer Strategy

Execute phases sequentially in order:
1. Phase 1 → Phase 2 → Phase 3 (MVP) → Phase 4 → Phase 5 → Phase 6

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable after Foundational phase
- Commit after each phase completion
- All tasks modify existing VPO codebase - follow existing patterns
- auth.py is a new file; all other changes extend existing files
