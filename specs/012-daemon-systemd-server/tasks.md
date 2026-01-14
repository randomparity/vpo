# Tasks: Daemon Mode & Systemd-Friendly Server

**Input**: Design documents from `/specs/012-daemon-systemd-server/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Included per plan.md (tests/unit/server/, tests/integration/)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add aiohttp dependency and create server module structure

- [X] T001 Add aiohttp>=3.9 dependency to pyproject.toml
- [X] T002 Create server module directory structure at src/vpo/server/
- [X] T003 [P] Create src/vpo/server/__init__.py with module exports
- [X] T004 Commit Phase 1 changes with message "feat(012): Setup server module structure and aiohttp dependency"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Add ServerConfig dataclass to src/vpo/config/models.py per data-model.md
- [X] T006 Add server field to VPOConfig dataclass in src/vpo/config/models.py
- [X] T007 Add server config loading (TOML + env vars) to src/vpo/config/loader.py
- [X] T008 [P] Create ShutdownState dataclass in src/vpo/server/lifecycle.py per data-model.md
- [X] T009 [P] Create HealthStatus dataclass in src/vpo/server/app.py per data-model.md
- [X] T010 Add database health check helper function to src/vpo/db/connection.py
- [X] T011 Commit Phase 2 changes with message "feat(012): Add ServerConfig and foundational data models"

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Run VPO as a Background Service (Priority: P1)

**Goal**: Implement `vpo serve` command that runs daemon in foreground, binds to port, handles SIGTERM/SIGINT gracefully

**Independent Test**: Run `vpo serve`, verify it starts and binds to port 8321, send SIGTERM, verify clean shutdown within 30 seconds

### Tests for User Story 1

- [X] T012 [P] [US1] Create tests/unit/server/test_lifecycle.py with tests for DaemonLifecycle class
- [X] T013 [P] [US1] Create tests/unit/server/test_signals.py with tests for signal handler registration

### Implementation for User Story 1

- [X] T014 [US1] Implement DaemonLifecycle class in src/vpo/server/lifecycle.py (startup/shutdown coordination)
- [X] T015 [US1] Implement signal handler setup in src/vpo/server/signals.py (SIGTERM, SIGINT)
- [X] T016 [US1] Implement aiohttp Application with basic route structure in src/vpo/server/app.py
- [X] T017 [US1] Create src/vpo/cli/serve.py with `vpo serve` command (--bind, --port flags)
- [X] T018 [US1] Register serve command in src/vpo/cli/__init__.py
- [X] T019 [US1] Implement graceful shutdown logic (wait for tasks up to timeout, then cancel) in lifecycle.py
- [X] T020 [US1] Add startup error handling (DB unreachable, port in use) with non-zero exit codes in serve.py
- [X] T021 [US1] Run tests and verify `uv run pytest tests/unit/server/` passes
- [X] T022 Commit Phase 3 changes with message "feat(012): Implement vpo serve daemon command with graceful shutdown"

**Checkpoint**: User Story 1 complete - `vpo serve` starts, runs, and shuts down gracefully on SIGTERM

---

## Phase 4: User Story 2 - Deploy VPO via Systemd (Priority: P2)

**Goal**: Provide systemd unit file and documentation for service deployment

**Independent Test**: Install unit file, run `systemctl start vpo`, verify service running, logs in journalctl

### Implementation for User Story 2

- [X] T023 [US2] Create docs/systemd/ directory
- [X] T024 [US2] Create example systemd unit file at docs/systemd/vpo.service per research.md
- [X] T025 [US2] Create docs/systemd.md with installation and usage instructions
- [X] T026 [US2] Ensure daemon logs go to stderr (journald compatible) - verify in server/app.py
- [X] T027 Commit Phase 4 changes with message "feat(012): Add systemd unit file and deployment documentation"

**Checkpoint**: User Story 2 complete - systemd unit file ready for deployment

---

## Phase 5: User Story 3 - Configure Daemon Settings (Priority: P3)

**Goal**: Support config file and CLI flag overrides for server settings

**Independent Test**: Create config.toml with custom port, run `vpo serve`, verify uses config port. Then override with `--port` flag, verify flag wins.

### Implementation for User Story 3

- [X] T028 [US3] Add --config flag to serve command in src/vpo/cli/serve.py
- [X] T029 [US3] Add --log-level and --log-format flags to serve command
- [X] T030 [US3] Implement config precedence (CLI > config file > env > defaults) in serve.py
- [X] T031 [US3] Add config validation with clear error messages on malformed config
- [X] T032 [US3] Update serve command help text to document all flags
- [X] T033 Commit Phase 5 changes with message "feat(012): Add daemon configuration via config file and CLI flags"

**Checkpoint**: User Story 3 complete - daemon fully configurable via file and flags

---

## Phase 6: User Story 4 - Monitor Daemon Health (Priority: P3)

**Goal**: Implement GET /health endpoint returning JSON status per OpenAPI contract

**Independent Test**: Start daemon, `curl http://127.0.0.1:8321/health`, verify 200 with JSON body. Stop DB, verify 503.

### Tests for User Story 4

- [X] T034 [P] [US4] Create tests/integration/test_serve_command.py with health endpoint tests

### Implementation for User Story 4

- [X] T035 [US4] Implement /health route handler in src/vpo/server/app.py
- [X] T036 [US4] Implement database connectivity check (async wrapper around sync SELECT 1) in app.py
- [X] T037 [US4] Implement HealthStatus JSON serialization per contracts/openapi.yaml
- [X] T038 [US4] Add uptime tracking to DaemonLifecycle in lifecycle.py
- [X] T039 [US4] Return 503 when shutting_down=True or database disconnected
- [X] T040 [US4] Run integration tests and verify `uv run pytest tests/integration/test_serve_command.py` passes
- [X] T041 Commit Phase 6 changes with message "feat(012): Implement /health endpoint for daemon monitoring"

**Checkpoint**: User Story 4 complete - health endpoint operational

---

## Phase 7: User Story 5 - Structured Logging for Observability (Priority: P4)

**Goal**: Ensure JSON logging works in daemon mode with context fields

**Independent Test**: Run `vpo serve --log-format json`, verify log output is valid JSON with timestamp, level, logger, message fields

### Implementation for User Story 5

- [X] T042 [US5] Verify existing JSONFormatter in src/vpo/logging/handlers.py includes required fields
- [X] T043 [US5] Add daemon=True context to log records in daemon mode
- [X] T044 [US5] Ensure no print() calls in daemon code path - all output via logger
- [X] T045 [US5] Test JSON log output is valid and parseable
- [X] T046 Commit Phase 7 changes with message "feat(012): Ensure structured JSON logging works in daemon mode"

**Checkpoint**: User Story 5 complete - JSON logging operational

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, final integration, and cleanup

- [X] T047 [P] Create docs/daemon-mode.md with comprehensive daemon documentation
- [X] T048 [P] Update README.md with "Daemon Mode / Service Deployment" section linking to docs
- [X] T049 Run full test suite `uv run pytest` and fix any failures
- [X] T050 Run linting `uv run ruff check .` and fix any issues
- [X] T051 Validate against quickstart.md scenarios
- [X] T052 Update docs/INDEX.md with new documentation pages
- [X] T053 Commit Phase 8 changes with message "docs(012): Add daemon mode documentation and README update"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (Phase 3): Core daemon - must complete first
  - US2 (Phase 4): Depends on US1 (needs working daemon for systemd)
  - US3 (Phase 5): Can parallel with US2 (configuration layer)
  - US4 (Phase 6): Depends on US1 (needs running daemon for health endpoint)
  - US5 (Phase 7): Can parallel with US2-4 (logging is independent)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: CRITICAL - all other stories depend on this
- **User Story 2 (P2)**: Depends on US1 (needs daemon to document)
- **User Story 3 (P3)**: Depends on US1 (configuration for daemon)
- **User Story 4 (P3)**: Depends on US1 (health endpoint in daemon)
- **User Story 5 (P4)**: Depends on US1 (logging in daemon mode)

### Within Each User Story

- Tests written first (where applicable)
- Data models before services
- Services before CLI integration
- Commit at end of each phase

### Parallel Opportunities

**Phase 2 (Foundational)**:
```
T008 [P] ShutdownState dataclass
T009 [P] HealthStatus dataclass
```

**Phase 3 (US1 Tests)**:
```
T012 [P] test_lifecycle.py
T013 [P] test_signals.py
```

**Phase 8 (Polish)**:
```
T047 [P] daemon-mode.md
T048 [P] README update
```

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch in parallel (different files):
Task: "Create ShutdownState dataclass in src/vpo/server/lifecycle.py"
Task: "Create HealthStatus dataclass in src/vpo/server/app.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test `vpo serve` starts, runs, shuts down gracefully
5. Can deploy basic daemon at this point

### Incremental Delivery

1. Phase 1-2: Foundation ready
2. Phase 3 (US1): Basic daemon → Can demo `vpo serve`
3. Phase 4 (US2): Systemd support → Can deploy as service
4. Phase 5 (US3): Configuration → Production-ready config
5. Phase 6 (US4): Health checks → Monitoring ready
6. Phase 7 (US5): JSON logging → Observability ready
7. Phase 8: Polish → Feature complete

### Suggested MVP Scope

**MVP = Phase 1 + Phase 2 + Phase 3 (User Story 1)**

This delivers:
- Working `vpo serve` command
- Graceful shutdown on SIGTERM/SIGINT
- Basic daemon functionality

Additional stories add production-readiness incrementally.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in same phase
- [Story] label maps task to specific user story for traceability
- Each commit at end of phase ensures atomic, reviewable progress
- Test tasks run tests AFTER implementation (not TDD for this feature)
- All file paths are relative to repository root `/home/dave/src/vpo/`
