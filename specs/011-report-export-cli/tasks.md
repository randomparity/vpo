# Tasks: Reporting & Export CLI

**Input**: Design documents from `/specs/011-report-export-cli/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Tests are included as the project uses pytest and follows TDD patterns.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the reports module structure and shared utilities

- [x] T001 Create reports module directory structure at src/video_policy_orchestrator/reports/
- [x] T002 [P] Create reports module __init__.py at src/video_policy_orchestrator/reports/__init__.py
- [x] T003 [P] Create test directory structure at tests/unit/reports/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Implement TimeFilter dataclass and parse_relative_date() in src/video_policy_orchestrator/reports/filters.py
- [x] T005 [P] Implement ReportFormat enum in src/video_policy_orchestrator/reports/formatters.py
- [x] T006 Implement render_text_table() in src/video_policy_orchestrator/reports/formatters.py
- [x] T007 Implement render_csv() in src/video_policy_orchestrator/reports/formatters.py
- [x] T008 Implement render_json() in src/video_policy_orchestrator/reports/formatters.py
- [x] T009 [P] Implement format_timestamp_local() helper in src/video_policy_orchestrator/reports/formatters.py
- [x] T010 [P] Implement format_duration() helper in src/video_policy_orchestrator/reports/formatters.py
- [x] T011 Create report command group skeleton in src/video_policy_orchestrator/cli/report.py
- [x] T012 Register report command group in src/video_policy_orchestrator/cli/__init__.py
- [x] T013 [P] Add unit tests for filters.py in tests/unit/reports/test_filters.py
- [x] T014 [P] Add unit tests for formatters.py in tests/unit/reports/test_formatters.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Job History Audit (Priority: P1) MVP

**Goal**: Users can view job history with filtering by type, status, and time range

**Independent Test**: Run `vpo report jobs` after executing jobs; verify output contains accurate job records with ID, type, status, times, and duration

### Implementation for User Story 1

- [x] T015 [US1] Implement get_jobs_report() query function in src/video_policy_orchestrator/reports/queries.py
- [x] T016 [US1] Implement JobReportRow dataclass in src/video_policy_orchestrator/reports/queries.py
- [x] T017 [US1] Implement `vpo report jobs` subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T018 [US1] Add --type filter option to jobs subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T019 [US1] Add --status filter option to jobs subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T020 [US1] Add --since/--until filter options to jobs subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T021 [US1] Add --format option (text/csv/json) to jobs subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T022 [US1] Add --limit and --no-limit options to jobs subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T023 [P] [US1] Add unit tests for get_jobs_report() in tests/unit/reports/test_queries.py
- [x] T024 [P] [US1] Add integration test for `vpo report jobs` in tests/integration/test_report_cli.py

**Checkpoint**: `vpo report jobs` fully functional with all filters and formats

---

## Phase 4: User Story 2 - Library Snapshot Export (Priority: P2)

**Goal**: Users can export library metadata with resolution, language, and subtitle filters

**Independent Test**: Run `vpo report library` after scanning; verify output contains file path, title, container, resolution, audio languages, subtitle presence

### Implementation for User Story 2

- [x] T025 [US2] Implement get_library_report() query function in src/video_policy_orchestrator/reports/queries.py
- [x] T026 [US2] Implement LibraryReportRow dataclass in src/video_policy_orchestrator/reports/queries.py
- [x] T027 [US2] Implement get_resolution_category() helper in src/video_policy_orchestrator/reports/queries.py
- [x] T028 [US2] Implement `vpo report library` subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T029 [US2] Add --resolution filter option to library subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T030 [US2] Add --language filter option to library subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T031 [US2] Add --has-subtitles/--no-subtitles options to library subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T032 [P] [US2] Add unit tests for get_library_report() in tests/unit/reports/test_queries.py
- [x] T033 [P] [US2] Add integration test for `vpo report library` in tests/integration/test_report_cli.py

**Checkpoint**: `vpo report library` fully functional with all filters

---

## Phase 5: User Story 3 - Multi-Format Output Support (Priority: P3)

**Goal**: All reports support text, CSV, and JSON output formats with proper validation

**Independent Test**: Run any report with `--format text`, `--format csv`, `--format json`; verify each produces valid output

### Implementation for User Story 3

- [x] T034 [US3] Add format validation and error handling in src/video_policy_orchestrator/cli/report.py
- [x] T035 [US3] Ensure CSV output includes headers and proper escaping in src/video_policy_orchestrator/reports/formatters.py
- [x] T036 [US3] Ensure JSON output has stable key ordering in src/video_policy_orchestrator/reports/formatters.py
- [x] T037 [US3] Add text table column width calculation for terminal display in src/video_policy_orchestrator/reports/formatters.py
- [x] T038 [P] [US3] Add format validation tests in tests/unit/reports/test_formatters.py
- [x] T039 [P] [US3] Add CSV escaping tests in tests/unit/reports/test_formatters.py
- [x] T040 [P] [US3] Add JSON validation tests in tests/unit/reports/test_formatters.py

**Checkpoint**: All format outputs validated and working correctly

---

## Phase 6: User Story 4 - Scan History Report (Priority: P4)

**Goal**: Users can view scan operation history with file counts

**Independent Test**: Run `vpo report scans` after performing scans; verify output shows scan ID, times, duration, and file counts

### Implementation for User Story 4

- [x] T041 [US4] Implement get_scans_report() query function in src/video_policy_orchestrator/reports/queries.py
- [x] T042 [US4] Implement ScanReportRow dataclass in src/video_policy_orchestrator/reports/queries.py
- [x] T043 [US4] Implement extract_scan_summary() helper for parsing summary_json in src/video_policy_orchestrator/reports/queries.py
- [x] T044 [US4] Implement `vpo report scans` subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T045 [P] [US4] Add unit tests for get_scans_report() in tests/unit/reports/test_queries.py
- [x] T046 [P] [US4] Add integration test for `vpo report scans` in tests/integration/test_report_cli.py

**Checkpoint**: `vpo report scans` fully functional

---

## Phase 7: User Story 5 - Transcode Operations Report (Priority: P5)

**Goal**: Users can view transcode history with codec filtering and size change tracking

**Independent Test**: Run `vpo report transcodes` after transcode jobs; verify output shows file, codecs, duration, status, and size change

### Implementation for User Story 5

- [x] T047 [US5] Implement get_transcodes_report() query function in src/video_policy_orchestrator/reports/queries.py
- [x] T048 [US5] Implement TranscodeReportRow dataclass in src/video_policy_orchestrator/reports/queries.py
- [x] T049 [US5] Implement `vpo report transcodes` subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T050 [US5] Add --codec filter option to transcodes subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T051 [P] [US5] Add unit tests for get_transcodes_report() in tests/unit/reports/test_queries.py
- [x] T052 [P] [US5] Add integration test for `vpo report transcodes` in tests/integration/test_report_cli.py

**Checkpoint**: `vpo report transcodes` fully functional

---

## Phase 8: User Story 6 - Policy Application Report (Priority: P6)

**Goal**: Users can view policy application history with verbose per-file details

**Independent Test**: Run `vpo report policy-apply` after applying policies; verify output shows operation ID, policy name, files affected, and status

### Implementation for User Story 6

- [x] T053 [US6] Implement get_policy_apply_report() query function in src/video_policy_orchestrator/reports/queries.py
- [x] T054 [US6] Implement PolicyApplyReportRow dataclass in src/video_policy_orchestrator/reports/queries.py
- [x] T055 [US6] Implement PolicyApplyDetailRow dataclass for verbose mode in src/video_policy_orchestrator/reports/queries.py
- [x] T056 [US6] Implement `vpo report policy-apply` subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T057 [US6] Add --policy filter option to policy-apply subcommand in src/video_policy_orchestrator/cli/report.py
- [x] T058 [US6] Add --verbose flag for per-file details in src/video_policy_orchestrator/cli/report.py
- [x] T059 [P] [US6] Add unit tests for get_policy_apply_report() in tests/unit/reports/test_queries.py
- [x] T060 [P] [US6] Add integration test for `vpo report policy-apply` in tests/integration/test_report_cli.py

**Checkpoint**: `vpo report policy-apply` fully functional with verbose mode

---

## Phase 9: User Story 7 - File Output Support (Priority: P7)

**Goal**: Users can write reports to files with overwrite protection

**Independent Test**: Run any report with `--output file.json`; verify file is created with correct content

### Implementation for User Story 7

- [x] T061 [US7] Implement write_report_to_file() helper in src/video_policy_orchestrator/reports/formatters.py
- [x] T062 [US7] Add --output option to all report subcommands in src/video_policy_orchestrator/cli/report.py
- [x] T063 [US7] Add --force flag for overwrite in src/video_policy_orchestrator/cli/report.py
- [x] T064 [US7] Add file existence check and error handling in src/video_policy_orchestrator/cli/report.py
- [x] T065 [P] [US7] Add unit tests for write_report_to_file() in tests/unit/reports/test_formatters.py
- [x] T066 [P] [US7] Add integration test for file output in tests/integration/test_report_cli.py

**Checkpoint**: File output working with overwrite protection

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, error handling improvements, and final validation

- [x] T067 [P] Add comprehensive help text with examples to all report subcommands in src/video_policy_orchestrator/cli/report.py
- [x] T068 [P] Create documentation page at docs/reports.md
- [ ] T069 [P] Add "Reporting & Export" section to README.md
- [x] T070 Handle edge case: empty database displays "No records found" message
- [x] T071 Handle edge case: filters match no records displays appropriate message
- [x] T072 Handle edge case: invalid date format shows clear error with examples
- [x] T073 Handle edge case: long file paths truncated in text output
- [x] T074 Handle edge case: Unicode in file paths/titles preserved in all formats
- [ ] T075 Run quickstart.md validation - verify all examples work
- [x] T076 Run full test suite and fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - User stories can proceed sequentially in priority order (P1 → P2 → ... → P7)
  - Some parallelization possible (see below)
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Phase 2 - No dependencies on other stories
- **User Story 3 (P3)**: Depends on US1 or US2 (needs a report to test formats)
- **User Story 4 (P4)**: Can start after Phase 2 - No dependencies on other stories
- **User Story 5 (P5)**: Can start after Phase 2 - No dependencies on other stories
- **User Story 6 (P6)**: Can start after Phase 2 - No dependencies on other stories
- **User Story 7 (P7)**: Depends on US1 (needs a report to test file output)

### Parallel Opportunities

After Phase 2 completes:
- US1, US2, US4, US5, US6 can all start in parallel (different query functions)
- US3 should wait for at least one report subcommand
- US7 should wait for at least one report subcommand

---

## Parallel Example: Phase 2 Foundation

```bash
# Launch all parallel foundation tasks together:
Task: "Create reports module __init__.py at src/video_policy_orchestrator/reports/__init__.py"
Task: "Create test directory structure at tests/unit/reports/"
Task: "Implement ReportFormat enum in src/video_policy_orchestrator/reports/formatters.py"
```

## Parallel Example: User Story 1

```bash
# Launch parallel test tasks for US1:
Task: "Add unit tests for get_jobs_report() in tests/unit/reports/test_queries.py"
Task: "Add integration test for `vpo report jobs` in tests/integration/test_report_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 - Job History Audit
4. **STOP and VALIDATE**: Test `vpo report jobs` with all filters and formats
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (jobs) → Test independently → MVP ready
3. Add User Story 2 (library) → Test independently
4. Add User Story 3 (formats) → Validates all format handling
5. Add User Story 4 (scans) → Test independently
6. Add User Story 5 (transcodes) → Test independently
7. Add User Story 6 (policy-apply) → Test independently
8. Add User Story 7 (file output) → Test with any report
9. Complete Polish phase → Full feature ready

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently testable after implementation
- The formatters (Phase 2) are shared infrastructure used by all reports
- All subcommands share common options: --format, --output, --force, --limit, --no-limit, --since, --until
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
