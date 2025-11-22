# Tasks: Library Scanner

**Input**: Design documents from `/specs/002-library-scanner/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD approach per constitution check - tests will be included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Rust crate**: `crates/vpo-core/`
- **Python package**: `src/video_policy_orchestrator/`
- **Tests**: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization with hybrid Python/Rust build system

- [X] T001 Update pyproject.toml with maturin build system and click dependency in pyproject.toml
- [X] T002 [P] Create Rust crate structure with Cargo.toml in crates/vpo-core/Cargo.toml
- [X] T003 [P] Create Rust lib.rs with PyO3 module skeleton in crates/vpo-core/src/lib.rs
- [X] T004 [P] Create Python type stubs for Rust extension in src/video_policy_orchestrator/_core.pyi
- [X] T005 [P] Create test fixtures directory structure in tests/fixtures/sample_videos/
- [X] T006 [P] Create shared test fixtures in tests/conftest.py
- [X] T007 Verify maturin build works with `maturin develop`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Implement discover_videos function in crates/vpo-core/src/discovery.rs
- [X] T008b [P] Implement symlink cycle detection in discover_videos in crates/vpo-core/src/discovery.rs
- [X] T009 [P] Implement hash_files function in crates/vpo-core/src/hasher.rs
- [X] T010 Export Rust functions via PyO3 in crates/vpo-core/src/lib.rs
- [X] T011 Verify Rust extension imports in Python with basic smoke test
- [X] T012 Create FileInfo and TrackInfo dataclasses in src/video_policy_orchestrator/db/models.py
- [X] T013 Create FileRecord and TrackRecord dataclasses in src/video_policy_orchestrator/db/models.py
- [X] T014 Implement database connection manager in src/video_policy_orchestrator/db/connection.py
- [X] T015 Implement schema creation with all tables in src/video_policy_orchestrator/db/schema.py

**Checkpoint**: Foundation ready - Rust core works, database initializes, models defined

---

## Phase 3: User Story 1 - Directory Scan CLI (Priority: P1) MVP

**Goal**: Implement `vpo scan /path/to/videos` command that recursively discovers video files and displays summary

**Independent Test**: Run `vpo scan /tmp/test-videos` against a directory with video files; verify files are discovered and counted in output

### Tests for User Story 1

- [X] T016 [P] [US1] Unit test for Rust discover_videos in tests/unit/test_core.py
- [X] T017 [P] [US1] Unit test for Rust hash_files in tests/unit/test_core.py
- [X] T018 [P] [US1] Integration test for scan command in tests/integration/test_scan_command.py
- [X] T018b [P] [US1] Integration test for --dry-run flag (no DB writes) in tests/integration/test_scan_command.py

### Implementation for User Story 1

- [X] T019 [US1] Create CLI entry point with click group in src/video_policy_orchestrator/cli/__init__.py
- [X] T020 [US1] Implement scan command skeleton with arguments in src/video_policy_orchestrator/cli/scan.py
- [X] T021 [US1] Add --extensions option parsing in src/video_policy_orchestrator/cli/scan.py
- [X] T022 [US1] Add --db option for database path in src/video_policy_orchestrator/cli/scan.py
- [X] T023 [US1] Add --dry-run flag implementation in src/video_policy_orchestrator/cli/scan.py
- [X] T024 [US1] Add --verbose and --json output flags in src/video_policy_orchestrator/cli/scan.py
- [X] T025 [US1] Create scanner orchestrator that coordinates Rust core in src/video_policy_orchestrator/scanner/orchestrator.py
- [X] T026 [US1] Implement scan summary output (human-readable format) in src/video_policy_orchestrator/cli/scan.py
- [X] T027 [US1] Implement scan summary output (JSON format) in src/video_policy_orchestrator/cli/scan.py
- [X] T028 [US1] Add CLI entry point to pyproject.toml [project.scripts]
- [X] T029 [US1] Handle directory validation and error messages in src/video_policy_orchestrator/cli/scan.py

**Checkpoint**: `vpo scan /path` works, discovers files, shows summary. Database connection is wired but data is not yet persisted (added in US2).

---

## Phase 4: User Story 2 - Database Schema for Library (Priority: P2)

**Goal**: Persist scan results to SQLite database with files and tracks tables; support idempotent re-scanning

**Independent Test**: Run scan twice on same directory; verify database contains correct file count (no duplicates) and tables exist with correct schema

### Tests for User Story 2

- [ ] T030 [P] [US2] Unit test for schema creation in tests/unit/test_schema.py
- [ ] T031 [P] [US2] Unit test for file upsert operations in tests/unit/test_models.py
- [ ] T031b [P] [US2] Unit test for track storage (all fields per FR-010) in tests/unit/test_models.py
- [ ] T032 [P] [US2] Integration test for database persistence in tests/integration/test_database.py

### Implementation for User Story 2

- [ ] T033 [US2] Implement file insert/update (upsert) operations in src/video_policy_orchestrator/db/models.py
- [ ] T034 [US2] Implement track insert with cascade delete (type, codec, language, title, default, forced, ordering per FR-010) in src/video_policy_orchestrator/db/models.py
- [ ] T035 [US2] Implement file lookup by path in src/video_policy_orchestrator/db/models.py
- [ ] T036 [US2] Implement modified_at change detection for skip logic in src/video_policy_orchestrator/scanner/orchestrator.py
- [ ] T037 [US2] Integrate database writes into scanner orchestrator in src/video_policy_orchestrator/scanner/orchestrator.py
- [ ] T038 [US2] Update scan summary to show new/updated/skipped counts in src/video_policy_orchestrator/cli/scan.py
- [ ] T039 [US2] Ensure database directory (~/.vpo/) is created if missing in src/video_policy_orchestrator/db/connection.py

**Checkpoint**: Scan results persist to `~/.vpo/library.db`; re-scanning updates rather than duplicates

---

## Phase 5: User Story 3 - Metadata Extraction Stub (Priority: P3)

**Goal**: Implement MediaIntrospector Protocol with stub implementation that returns placeholder track data

**Independent Test**: Call `StubIntrospector().get_file_info(path)` with a video file path; verify it returns FileInfo with container_format inferred from extension

### Tests for User Story 3

- [ ] T040 [P] [US3] Unit test for MediaIntrospector protocol in tests/unit/test_introspector.py
- [ ] T041 [P] [US3] Unit test for StubIntrospector in tests/unit/test_introspector.py

### Implementation for User Story 3

- [ ] T042 [US3] Define MediaIntrospector Protocol in src/video_policy_orchestrator/introspector/interface.py
- [ ] T043 [US3] Define MediaIntrospectionError exception in src/video_policy_orchestrator/introspector/interface.py
- [ ] T044 [US3] Implement StubIntrospector with extension-based format detection in src/video_policy_orchestrator/introspector/stub.py
- [ ] T045 [US3] Implement container format mapping (mkv->matroska, mp4->mp4, etc.) in src/video_policy_orchestrator/introspector/stub.py
- [ ] T046 [US3] Integrate MediaIntrospector into scanner orchestrator in src/video_policy_orchestrator/scanner/orchestrator.py
- [ ] T047 [US3] Store container_format in database records in src/video_policy_orchestrator/scanner/orchestrator.py

**Checkpoint**: Scanner uses MediaIntrospector interface; stub returns container format; ready for future ffprobe integration

---

## Phase 6: User Story 4 - Spec Documentation Update (Priority: P4)

**Goal**: Ensure documentation accurately reflects implemented data model and scanning behavior

**Independent Test**: Review docs/ARCHITECTURE.md for ER diagram reference and accuracy

### Implementation for User Story 4

- [ ] T048 [US4] Update docs/ARCHITECTURE.md with database ER diagram reference
- [ ] T049 [US4] Add example JSON showing scanned file structure to docs/ARCHITECTURE.md
- [ ] T050 [US4] Update CLAUDE.md with new technologies (Rust, maturin, click)

**Checkpoint**: Documentation complete and accurate

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, edge cases, and quality improvements across all user stories

- [ ] T051 [P] Implement graceful Ctrl+C handling with partial commit in src/video_policy_orchestrator/scanner/orchestrator.py
- [ ] T052 [P] Add progress output for long scans (every 100 files) in src/video_policy_orchestrator/scanner/orchestrator.py
- [ ] T053 [P] Implement verbose error output with full error list in src/video_policy_orchestrator/cli/scan.py
- [ ] T054 [P] Add database locked error handling in src/video_policy_orchestrator/db/connection.py
- [ ] T056 Run full test suite and fix any failures
- [ ] T057 Run ruff linting and formatting checks
- [ ] T058 Run cargo clippy and cargo fmt for Rust code
- [ ] T059 Validate quickstart.md instructions work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← BLOCKS all user stories
    ↓
┌───────────────────────────────────────────────┐
│ Phase 3 (US1: CLI)                            │
│     ↓                                         │
│ Phase 4 (US2: Database) ← depends on US1      │
│     ↓                                         │
│ Phase 5 (US3: Introspector) ← can run after   │
│                               US2 or parallel │
│     ↓                                         │
│ Phase 6 (US4: Documentation)                  │
└───────────────────────────────────────────────┘
    ↓
Phase 7 (Polish)
```

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 (Foundational). No other story dependencies.
- **US2 (P2)**: Depends on US1 (needs scan command to test persistence)
- **US3 (P3)**: Can start after Phase 2. Integrates with US1/US2 but independently testable.
- **US4 (P4)**: Can start after US2 (needs schema to document)

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Models/dataclasses before services
3. Services before CLI commands
4. Core implementation before integration
5. Story complete before next priority

### Parallel Opportunities

**Setup Phase (T001-T007)**:
```
T001 (pyproject.toml)
    ↓
T002, T003, T004, T005, T006 ← all [P] can run in parallel
    ↓
T007 (verify build)
```

**Foundational Phase (T008-T015)**:
```
T008, T009 ← [P] Rust functions in parallel
    ↓
T010 (export)
    ↓
T011 (verify)

T012, T013 ← [P] dataclasses in parallel
    ↓
T014 (connection)
    ↓
T015 (schema)
```

**User Story 1 Tests (T016-T018)**:
```
T016, T017, T018 ← all [P] can run in parallel
```

---

## Parallel Example: User Story 1

```bash
# Launch all tests for US1 together:
Task: "Unit test for Rust discover_videos in tests/unit/test_core.py"
Task: "Unit test for Rust hash_files in tests/unit/test_core.py"
Task: "Integration test for scan command in tests/integration/test_scan_command.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational (T008-T015)
3. Complete Phase 3: User Story 1 (T016-T029)
4. **STOP and VALIDATE**: Test `vpo scan /path` independently
5. Demo: Basic scanning with summary output

### Incremental Delivery

1. **MVP**: Setup + Foundational + US1 → `vpo scan` discovers files, shows summary
2. **+Persistence**: Add US2 → Results saved to database, idempotent re-scan
3. **+Abstraction**: Add US3 → MediaIntrospector ready for future ffprobe
4. **+Documentation**: Add US4 → Docs updated
5. **+Polish**: Final phase → Error handling, edge cases

### Suggested MVP Scope

**Minimum for demo**: Tasks T001-T029 (Setup + Foundational + US1)
- User can run `vpo scan /media/videos`
- Files are discovered recursively
- Summary displayed with file count and elapsed time
- No persistence yet (added in US2)

---

## Summary

| Phase | Story | Task Count | Parallel Tasks |
|-------|-------|------------|----------------|
| 1. Setup | - | 7 | 5 |
| 2. Foundational | - | 9 | 3 |
| 3. US1: CLI | P1 | 15 | 4 |
| 4. US2: Database | P2 | 11 | 4 |
| 5. US3: Introspector | P3 | 8 | 2 |
| 6. US4: Documentation | P4 | 3 | 0 |
| 7. Polish | - | 8 | 4 |
| **Total** | | **61** | **22** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Rust code (crates/vpo-core/) must compile before Python tests can run
