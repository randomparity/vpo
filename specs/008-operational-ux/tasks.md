# Tasks: Operational UX - Incremental Scans, Job History & Profiles

**Input**: Design documents from `/specs/008-operational-ux/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Tests included for each user story per standard practice.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Project structure**: `src/vpo/`, `tests/` at repository root
- Based on plan.md: Single CLI application extending existing VPO codebase

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and foundational module structure

- [x] T001 Create logging module structure in src/vpo/logging/__init__.py
- [x] T002 [P] Create jobs tracking module in src/vpo/jobs/tracking.py
- [x] T003 [P] Create config profiles module in src/vpo/config/profiles.py

**Checkpoint**: Commit - "feat(008): Phase 1 - Setup module structure"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Extend JobType enum with SCAN and APPLY values in src/vpo/db/models.py
- [x] T005 Add Job dataclass fields (files_affected_json, summary_json) in src/vpo/db/models.py
- [x] T006 Create schema migration v6→v7 in src/vpo/db/schema.py
- [x] T007 Update initialize_database to call migrate_v6_to_v7 in src/vpo/db/schema.py
- [x] T008 [P] Add LoggingConfig dataclass in src/vpo/config/models.py
- [x] T009 [P] Add Profile dataclass in src/vpo/config/models.py
- [x] T010 [P] Create ScanResult dataclass in src/vpo/scanner/models.py
- [x] T011 Update VPOConfig to include logging field in src/vpo/config/models.py

**Checkpoint**: Foundation ready - Commit "feat(008): Phase 2 - Foundational data models and schema migration"

---

## Phase 3: User Story 1 - Incremental Directory Scanning (Priority: P1)

**Goal**: Enable incremental scanning that skips unchanged files based on mtime/size comparison

**Independent Test**: Scan directory, modify one file, rescan and verify only changed file is introspected

### Tests for User Story 1

- [x] T012 [P] [US1] Unit test for change detection logic in tests/unit/test_incremental_scan.py
- [x] T013 [P] [US1] Unit test for missing file handling in tests/unit/test_incremental_scan.py

### Implementation for User Story 1

- [x] T014 [US1] Implement file_needs_rescan() function in src/vpo/scanner/orchestrator.py
- [x] T015 [US1] Implement detect_missing_files() function in src/vpo/scanner/orchestrator.py
- [x] T016 [US1] Modify scan_directory() to use incremental detection by default in src/vpo/scanner/orchestrator.py
- [x] T017 [US1] Add --full flag to scan command in src/vpo/cli/scan.py
- [x] T018 [US1] Add --prune flag to scan command in src/vpo/cli/scan.py
- [x] T019 [US1] Add --verify-hash flag to scan command in src/vpo/cli/scan.py
- [x] T020 [US1] Implement incremental scan summary output (scanned/skipped/added/removed) in src/vpo/cli/scan.py
- [x] T021 [US1] Create scan job record with config (incremental, prune, verify_hash flags serialized to policy_json) in src/vpo/jobs/tracking.py
- [x] T022 [US1] Wire scan job tracking into scan_directory() in src/vpo/scanner/orchestrator.py

**Checkpoint**: User Story 1 complete - Commit "feat(008): Phase 3 - US1 Incremental directory scanning"

---

## Phase 4: User Story 2 - Job History and Status (Priority: P2)

**Goal**: Provide CLI commands to list and inspect job history for troubleshooting and auditing

**Independent Test**: Run scan operations, then verify `vpo jobs list` and `vpo jobs show` display correct information

### Tests for User Story 2

- [x] T023 [P] [US2] Integration test for jobs list command in tests/integration/test_jobs_cli.py
- [x] T024 [P] [US2] Integration test for jobs show command in tests/integration/test_jobs_cli.py

### Implementation for User Story 2

- [x] T025 [US2] Implement get_jobs_filtered() with status/type/since filters in src/vpo/db/models.py
- [x] T026 [US2] Create jobs CLI command group in src/vpo/cli/jobs.py (already existed)
- [x] T027 [US2] Implement `vpo jobs list` command with table output in src/vpo/cli/jobs.py (already existed)
- [x] T028 [US2] Add --status filter to jobs list in src/vpo/cli/jobs.py (already existed)
- [x] T029 [US2] Add --type filter to jobs list in src/vpo/cli/jobs.py
- [x] T030 [US2] Add --since filter (relative dates: 1d, 1w) to jobs list in src/vpo/cli/jobs.py
- [x] T031 [US2] Add --limit option to jobs list in src/vpo/cli/jobs.py (already existed)
- [x] T032 [US2] Add --json output option to jobs list in src/vpo/cli/jobs.py
- [x] T033 [US2] Implement `vpo jobs show <id>` command with detailed output in src/vpo/cli/jobs.py
- [x] T034 [US2] Add prefix matching for job IDs in jobs show in src/vpo/cli/jobs.py
- [x] T035 [US2] Add --json output option to jobs show in src/vpo/cli/jobs.py
- [x] T036 [US2] Register jobs command group in CLI main in src/vpo/cli/__init__.py (already existed)

**Checkpoint**: User Story 2 complete - Commit "feat(008): Phase 4 - US2 Job history and status commands"

---

## Phase 5: User Story 3 - Configuration Profiles (Priority: P3)

**Goal**: Support named configuration profiles for different library types (movies, TV, kids)

**Independent Test**: Create two profiles with different settings, verify --profile flag applies correct settings

### Tests for User Story 3

- [x] T037 [P] [US3] Unit test for profile loading and validation in tests/unit/test_profiles.py
- [x] T038 [P] [US3] Unit test for profile merging precedence in tests/unit/test_profiles.py
- [x] T039 [P] [US3] Create sample profile fixtures in tests/fixtures/profiles/

### Implementation for User Story 3

- [x] T040 [US3] Implement load_profile() in src/vpo/config/profiles.py
- [x] T041 [US3] Implement list_profiles() in src/vpo/config/profiles.py
- [x] T042 [US3] Implement merge_profile_with_config() for precedence handling in src/vpo/config/profiles.py
- [x] T043 [US3] Add profile validation (name, policy file exists) in src/vpo/config/profiles.py
- [x] T044 [US3] Create profiles CLI command group in src/vpo/cli/profiles.py
- [x] T045 [US3] Implement `vpo profiles list` command in src/vpo/cli/profiles.py
- [x] T046 [US3] Implement `vpo profiles show <name>` command in src/vpo/cli/profiles.py
- [x] T047 [US3] Add --json output options to profiles commands in src/vpo/cli/profiles.py
- [x] T048 [US3] Add global --profile option to CLI main in src/vpo/cli/__init__.py (added to scan/apply)
- [x] T049 [US3] Wire --profile into scan command in src/vpo/cli/scan.py
- [x] T050 [US3] Wire --profile into apply command (if exists) in src/vpo/cli/apply.py
- [x] T051 [US3] Register profiles command group in CLI main in src/vpo/cli/__init__.py

**Checkpoint**: User Story 3 complete - Commit "feat(008): Phase 5 - US3 Configuration profiles"

---

## Phase 6: User Story 4 - Structured Logging and Observability (Priority: P4)

**Goal**: Provide configurable structured logging with JSON format support and file rotation

**Independent Test**: Configure different log levels and JSON format, verify output matches configuration

### Tests for User Story 4

- [x] T052 [P] [US4] Unit test for logging configuration in tests/unit/test_logging_config.py
- [x] T053 [P] [US4] Unit test for JSON formatter output in tests/unit/test_logging_config.py

### Implementation for User Story 4

- [x] T054 [US4] Implement JSONFormatter class in src/vpo/logging/handlers.py
- [x] T055 [US4] Implement configure_logging() from LoggingConfig in src/vpo/logging/config.py
- [x] T056 [US4] Add RotatingFileHandler setup with max_bytes/backup_count in src/vpo/logging/config.py
- [x] T057 [US4] Add stderr fallback when log file unavailable in src/vpo/logging/config.py
- [x] T058 [US4] Export configure_logging in src/vpo/logging/__init__.py
- [x] T059 [US4] Add global --log-level option to CLI main in src/vpo/cli/__init__.py
- [x] T060 [US4] Add global --log-file option to CLI main in src/vpo/cli/__init__.py
- [x] T061 [US4] Add global --log-json flag to CLI main in src/vpo/cli/__init__.py
- [x] T062 [US4] Wire logging configuration into CLI startup in src/vpo/cli/__init__.py
- [x] T063 [US4] Add structured logging calls to scan operations in src/vpo/scanner/orchestrator.py (logging already in place)

**Checkpoint**: User Story 4 complete - Commit "feat(008): Phase 6 - US4 Structured logging and observability"

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation, and cleanup

- [x] T064 [P] Update CLI help text for all new commands and options in src/vpo/cli/
- [x] T065 [P] Add auto job purge at scan/apply start using JobsConfig in src/vpo/jobs/tracking.py
- [x] T066 Verify all commands respect precedence: CLI > profile > config > defaults
- [x] T067 [P] Run ruff check and fix any linting issues
- [x] T068 [P] Run pytest and ensure all tests pass
- [x] T069 Validate feature against quickstart.md scenarios

**Checkpoint**: Feature complete - Commit "feat(008): Phase 7 - Polish and cross-cutting concerns"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user stories
- **User Stories (Phases 3-6)**: All depend on Phase 2 completion
  - User stories can proceed sequentially in priority order (P1 → P2 → P3 → P4)
  - Or in parallel if team capacity allows
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Phase 2
- **User Story 2 (P2)**: Depends on Phase 2; integrates with job records from US1
- **User Story 3 (P3)**: Depends on Phase 2; independent of US1/US2
- **User Story 4 (P4)**: Depends on Phase 2; independent of US1/US2/US3

### Within Each User Story

- Tests MUST be written FIRST and FAIL before implementation
- Data model changes before service logic
- Service logic before CLI wiring
- Core implementation before integration

### Parallel Opportunities

**Phase 1** (all parallelizable):
- T001, T002, T003 can run in parallel

**Phase 2** (partially parallelizable):
- T008, T009, T010 can run in parallel (different files)
- T004-T007 must be sequential (same files)

**Phase 3 (US1)**: T012, T013 can run in parallel (tests)

**Phase 4 (US2)**: T023, T024 can run in parallel (tests)

**Phase 5 (US3)**: T037, T038, T039 can run in parallel (tests/fixtures)

**Phase 6 (US4)**: T052, T053 can run in parallel (tests)

**Phase 7**: T064, T065, T067, T068 can run in parallel

---

## Parallel Example: Phase 2

```bash
# Sequential (same file):
Task: T004 "Extend JobType enum in db/models.py"
Task: T005 "Add Job dataclass fields in db/models.py"

# Then parallel (different files):
Task: T008 "Add LoggingConfig dataclass in config/models.py"
Task: T009 "Add Profile dataclass in config/models.py"
Task: T010 "Create ScanResult dataclass in scanner/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Incremental Scanning)
4. **STOP and VALIDATE**: Test incremental scanning independently
5. Deploy/demo if ready - this alone makes VPO practical for maintenance

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Incremental Scanning) → MVP - periodic maintenance works
3. Add US2 (Job History) → Operational visibility
4. Add US3 (Profiles) → Multi-library ergonomics
5. Add US4 (Logging) → Production readiness

### Commit Strategy (Per User Request)

Each phase ends with a commit checkpoint:
- Phase 1: `feat(008): Phase 1 - Setup module structure`
- Phase 2: `feat(008): Phase 2 - Foundational data models and schema migration`
- Phase 3: `feat(008): Phase 3 - US1 Incremental directory scanning`
- Phase 4: `feat(008): Phase 4 - US2 Job history and status commands`
- Phase 5: `feat(008): Phase 5 - US3 Configuration profiles`
- Phase 6: `feat(008): Phase 6 - US4 Structured logging and observability`
- Phase 7: `feat(008): Phase 7 - Polish and cross-cutting concerns`

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD)
- **Commit after each phase completes** (per user request)
- Stop at any checkpoint to validate story independently
