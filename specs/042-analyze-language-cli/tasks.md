# Tasks: Analyze-Language CLI Commands

**Input**: Design documents from `/specs/042-analyze-language-cli/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), data-model.md, contracts/cli-analyze-language.md, quickstart.md

**Tests**: Tests are included as this feature extends a critical user-facing CLI interface.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/video_policy_orchestrator/`, `tests/` at repository root
- Paths follow existing VPO structure per plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and module structure

- [ ] T001 Create CLI module file at src/video_policy_orchestrator/cli/analyze_language.py with Click group skeleton
- [ ] T002 [P] Create test file at tests/unit/cli/test_analyze_language.py with test class structure

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database queries that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Database Status Queries (db/views.py)

- [ ] T003 Add AnalysisStatusSummary dataclass to src/video_policy_orchestrator/db/types.py
- [ ] T004 Add FileAnalysisStatus dataclass to src/video_policy_orchestrator/db/types.py
- [ ] T005 [P] Implement get_analysis_status_summary() in src/video_policy_orchestrator/db/views.py
- [ ] T006 [P] Implement get_files_analysis_status() with filter support in src/video_policy_orchestrator/db/views.py
- [ ] T007 [P] Implement get_file_analysis_detail() in src/video_policy_orchestrator/db/views.py

### Database Deletion Queries (db/queries.py)

- [ ] T008 [P] Implement delete_analysis_for_file() in src/video_policy_orchestrator/db/queries.py
- [ ] T009 [P] Implement delete_analysis_by_path_prefix() in src/video_policy_orchestrator/db/queries.py
- [ ] T010 [P] Implement delete_all_analysis() in src/video_policy_orchestrator/db/queries.py
- [ ] T011 [P] Implement get_file_ids_by_path_prefix() in src/video_policy_orchestrator/db/queries.py

### Export Public API

- [ ] T012 Export new types and functions in src/video_policy_orchestrator/db/__init__.py

### Unit Tests for Foundational Queries

- [ ] T013 [P] Add tests for get_analysis_status_summary() in tests/unit/db/test_views.py
- [ ] T014 [P] Add tests for delete_analysis_for_file() in tests/unit/db/test_queries.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Run Language Analysis on Demand (Priority: P1) MVP

**Goal**: Run language analysis on specific files or directories without performing a full scan

**Independent Test**: Run `vpo analyze-language run <file>` on a media file and verify language analysis results are generated and stored

### Tests for User Story 1

- [ ] T015 [P] [US1] Add test for run_command argument validation in tests/unit/cli/test_analyze_language.py
- [ ] T016 [P] [US1] Add test for run_command with file not in database in tests/unit/cli/test_analyze_language.py
- [ ] T017 [P] [US1] Add test for run_command with --force flag in tests/unit/cli/test_analyze_language.py

### Implementation for User Story 1

- [ ] T018 [US1] Add AnalysisRunResult dataclass for batch results in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T019 [US1] Implement _check_plugin_available() helper in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T020 [US1] Implement _resolve_files_from_paths() helper with --recursive support in src/video_policy_orchestrator/cli/analyze_language.py (resolve paths to FileRecords, warn and skip paths not in database, error if no valid files found)
- [ ] T021 [US1] Implement run_command() with --force, --recursive, --json options (FR-002, FR-003, FR-004) in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T022 [US1] Add progress bar for multi-file analysis in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T023 [US1] Add human-readable output formatting for run results in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T024 [US1] Add JSON output formatting for run results in src/video_policy_orchestrator/cli/analyze_language.py

**Checkpoint**: `vpo analyze-language run` should be fully functional

---

## Phase 4: User Story 2 - View Language Analysis Status (Priority: P2)

**Goal**: View language analysis status for files in the library with filtering and JSON output

**Independent Test**: Run `vpo analyze-language status` and verify correct summary statistics are displayed

### Tests for User Story 2

- [ ] T025 [P] [US2] Add test for status_command summary output in tests/unit/cli/test_analyze_language.py
- [ ] T026 [P] [US2] Add test for status_command with file path in tests/unit/cli/test_analyze_language.py
- [ ] T027 [P] [US2] Add test for status_command --filter option in tests/unit/cli/test_analyze_language.py

### Implementation for User Story 2

- [ ] T028 [US2] Implement status_command() with --filter, --json, --limit options in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T029 [US2] Add _format_status_summary() helper for library-wide summary in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T030 [US2] Add _format_file_detail() helper for single-file detail in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T031 [US2] Add _format_file_list() helper for filtered file list in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T032 [US2] Add JSON output formatting for status results in src/video_policy_orchestrator/cli/analyze_language.py

**Checkpoint**: `vpo analyze-language status` should be fully functional

---

## Phase 5: User Story 3 - Clear Cached Analysis Results (Priority: P3)

**Goal**: Clear cached analysis results for specific files, directories, or entire library

**Independent Test**: Run `vpo analyze-language clear --all --yes` and verify all results are removed

### Tests for User Story 3

- [ ] T033 [P] [US3] Add test for clear_command requires path or --all in tests/unit/cli/test_analyze_language.py
- [ ] T034 [P] [US3] Add test for clear_command --dry-run output in tests/unit/cli/test_analyze_language.py
- [ ] T035 [P] [US3] Add test for clear_command confirmation prompt in tests/unit/cli/test_analyze_language.py

### Implementation for User Story 3

- [ ] T036 [US3] Implement clear_command() with --all, --yes, --dry-run, --recursive, --json options in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T037 [US3] Add _count_affected_results() helper for preview in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T038 [US3] Add confirmation prompt logic with click.confirm() in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T039 [US3] Add human-readable output formatting for clear results in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T040 [US3] Add JSON output formatting for clear results in src/video_policy_orchestrator/cli/analyze_language.py

**Checkpoint**: `vpo analyze-language clear` should be fully functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Command registration, integration tests, and documentation

### Command Registration

- [ ] T041 Register analyze_language_group in src/video_policy_orchestrator/cli/__init__.py

### Integration Tests

- [ ] T042 [P] Create integration test file at tests/integration/test_analyze_language_cli.py
- [ ] T043 [P] Add integration test for full run→status→clear workflow in tests/integration/test_analyze_language_cli.py

### Documentation

- [ ] T044 Update docs/usage/multi-language-detection.md with analyze-language CLI commands

### Edge Case Handling

- [ ] T045 [P] Add plugin unavailable error handling across all commands in src/video_policy_orchestrator/cli/analyze_language.py
- [ ] T046 [P] Add no audio tracks warning handling in run_command in src/video_policy_orchestrator/cli/analyze_language.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 (P1): Can start after Foundational (Phase 2)
  - US2 (P2): Can start after Foundational (Phase 2) - No dependency on US1
  - US3 (P3): Can start after Foundational (Phase 2) - No dependency on US1/US2
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1: Setup
    │
    ▼
Phase 2: Foundational (BLOCKS ALL)
    │
    ├────────────────┬────────────────┐
    │                │                │
    ▼                ▼                ▼
Phase 3: US1     Phase 4: US2     Phase 5: US3
(run)            (status)         (clear)
    │                │                │
    └────────────────┴────────────────┘
                     │
                     ▼
              Phase 6: Polish
```

### Within Each User Story

- Tests written first (TDD approach)
- Helper functions before main command
- Core implementation before formatting
- Verify tests pass after implementation

### Parallel Opportunities

**Setup (Phase 1)**:
- T001, T002 can run in parallel

**Foundational (Phase 2)**:
- T005, T006, T007 (view queries) can run in parallel
- T008, T009, T010, T011 (deletion queries) can run in parallel
- T013, T014 (tests) can run in parallel

**User Story 1 (Phase 3)**:
- T015, T016, T017 (tests) can run in parallel

**User Story 2 (Phase 4)**:
- T025, T026, T027 (tests) can run in parallel

**User Story 3 (Phase 5)**:
- T033, T034, T035 (tests) can run in parallel

**Polish (Phase 6)**:
- T042, T043 (integration tests) can run in parallel
- T045, T046 (edge cases) can run in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch all view queries together:
Task: "Implement get_analysis_status_summary() in src/video_policy_orchestrator/db/views.py"
Task: "Implement get_files_analysis_status() in src/video_policy_orchestrator/db/views.py"
Task: "Implement get_file_analysis_detail() in src/video_policy_orchestrator/db/views.py"

# Launch all deletion queries together:
Task: "Implement delete_analysis_for_file() in src/video_policy_orchestrator/db/queries.py"
Task: "Implement delete_analysis_by_path_prefix() in src/video_policy_orchestrator/db/queries.py"
Task: "Implement delete_all_analysis() in src/video_policy_orchestrator/db/queries.py"
Task: "Implement get_file_ids_by_path_prefix() in src/video_policy_orchestrator/db/queries.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 - Run command
4. **STOP and VALIDATE**: Test `vpo analyze-language run movie.mkv`
5. Can demo language analysis capability

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test run command → Demo (MVP!)
3. Add User Story 2 → Test status command → Demo
4. Add User Story 3 → Test clear command → Demo
5. Polish → Production ready

### Suggested MVP Scope

**Minimum for Value**: User Story 1 only
- US1 provides core analysis capability
- US2 (status) can be added next for visibility
- US3 (clear) adds maintenance capability

---

## Summary

| Phase | Tasks | Parallel Tasks | Description |
|-------|-------|----------------|-------------|
| Setup | 2 | 2 | Module structure |
| Foundational | 12 | 9 | Database queries |
| US1 (Run) | 10 | 3 | Run analysis command |
| US2 (Status) | 8 | 3 | Status viewing command |
| US3 (Clear) | 8 | 3 | Cache clearing command |
| Polish | 6 | 4 | Registration, tests, docs |
| **Total** | **46** | **24** | |

**Independent Test Criteria**:
- US1: Run `vpo analyze-language run <file>` on media file, verify results stored
- US2: Run `vpo analyze-language status`, verify summary matches database state
- US3: Run `vpo analyze-language clear --all --yes`, verify all results cleared
