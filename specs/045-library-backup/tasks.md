# Tasks: Library Backup and Restore

**Input**: Design documents from `/specs/045-library-backup/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are optional for this feature. Core functionality will be validated through the acceptance scenarios.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the backup module structure and shared data types

- [x] T001 [P] Create backup module file at src/vpo/db/backup.py with module docstring
- [x] T002 [P] Define BackupMetadata dataclass in src/vpo/db/backup.py per data-model.md
- [x] T003 [P] Define BackupInfo dataclass in src/vpo/db/backup.py per data-model.md
- [x] T004 [P] Define BackupResult dataclass in src/vpo/db/backup.py per data-model.md
- [x] T005 [P] Define RestoreResult dataclass in src/vpo/db/backup.py per data-model.md
- [x] T006 [P] Define exception hierarchy (BackupError, BackupIOError, BackupValidationError, BackupSchemaError, BackupLockError, InsufficientSpaceError) in src/vpo/db/backup.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core utilities that ALL backup operations depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Implement `_get_default_backup_dir()` helper in src/vpo/db/backup.py that returns ~/.vpo/backups/ as Path
- [x] T008 Implement `_generate_backup_filename()` helper in src/vpo/db/backup.py using UTC ISO-8601 timestamp format
- [x] T009 Implement `_check_disk_space()` helper in src/vpo/db/backup.py using shutil.disk_usage()
- [x] T010 Implement `_check_database_lock()` helper in src/vpo/db/backup.py checking WAL files and attempting exclusive lock
- [x] T011 Implement `_get_library_stats()` helper in src/vpo/db/backup.py to query file count and total size from database
- [x] T012 Implement `_read_backup_metadata()` helper in src/vpo/db/backup.py to extract and parse metadata JSON from archive
- [x] T013 Add new exit codes DATABASE_LOCKED and INSUFFICIENT_SPACE to src/vpo/cli/exit_codes.py if not present

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Create Library Backup (Priority: P1) 🎯 MVP

**Goal**: Users can create compressed backup archives of their library database

**Independent Test**: Run `vpo library backup` and verify archive is created with valid database and metadata

### Implementation for User Story 1

- [x] T014 [US1] Implement `create_backup(db_path, output_path, conn)` function in src/vpo/db/backup.py that uses sqlite3 backup API
- [x] T015 [US1] Add metadata collection (schema version, file count, sizes) to create_backup() in src/vpo/db/backup.py
- [x] T016 [US1] Add tar.gz archive creation with library.db and backup_metadata.json to create_backup() in src/vpo/db/backup.py
- [x] T017 [US1] Add disk space check before backup creation in src/vpo/db/backup.py
- [x] T018 [US1] Add database lock detection before backup creation in src/vpo/db/backup.py
- [x] T019 [US1] Implement `backup_command()` CLI command in src/vpo/cli/library.py with --output, --dry-run, --json options
- [x] T020 [US1] Add normal output formatting (file sizes, compression ratio) to backup_command() in src/vpo/cli/library.py
- [x] T021 [US1] Add JSON output formatting to backup_command() in src/vpo/cli/library.py
- [x] T022 [US1] Add dry-run mode to backup_command() showing what would be backed up in src/vpo/cli/library.py
- [x] T023 [US1] Add error handling for BackupLockError, InsufficientSpaceError, BackupIOError in src/vpo/cli/library.py

**Checkpoint**: User Story 1 complete - users can create backups. This is the MVP.

---

## Phase 4: User Story 2 - Restore Library from Backup (Priority: P2)

**Goal**: Users can restore their library database from a backup archive

**Independent Test**: Create a backup, modify the database, restore from backup, verify database matches backup state

### Implementation for User Story 2

- [x] T024 [US2] Implement `validate_backup(backup_path)` function in src/vpo/db/backup.py to check archive structure and metadata
- [x] T025 [US2] Add SQLite integrity check (quick_check) to validate_backup() in src/vpo/db/backup.py
- [x] T025a [US2] Add archive format validation to validate_backup() in src/vpo/db/backup.py that raises BackupValidationError for non-tar.gz files
- [x] T026 [US2] Implement `restore_backup(backup_path, db_path, force)` function in src/vpo/db/backup.py with atomic temp-file-then-rename
- [x] T027 [US2] Add schema version comparison and warning for mismatches in restore_backup() in src/vpo/db/backup.py
- [x] T028 [US2] Add disk space check before restore in src/vpo/db/backup.py
- [x] T029 [US2] Add database lock detection before restore in src/vpo/db/backup.py
- [x] T030 [US2] Block restore if backup schema version is newer than current VPO schema in src/vpo/db/backup.py
- [x] T031 [US2] Implement `restore_command()` CLI command in src/vpo/cli/library.py with BACKUP_FILE argument, --yes, --dry-run, --json options
- [x] T032 [US2] Add confirmation prompt (unless --yes) to restore_command() in src/vpo/cli/library.py
- [x] T033 [US2] Add schema mismatch warning to restore_command() in src/vpo/cli/library.py
- [x] T034 [US2] Add normal output formatting to restore_command() in src/vpo/cli/library.py
- [x] T035 [US2] Add JSON output formatting to restore_command() in src/vpo/cli/library.py
- [x] T036 [US2] Add dry-run mode to restore_command() validating archive without restoring in src/vpo/cli/library.py
- [x] T037 [US2] Add error handling for BackupValidationError, BackupSchemaError, BackupLockError in src/vpo/cli/library.py

**Checkpoint**: User Stories 1 AND 2 complete - full backup/restore cycle works

---

## Phase 5: User Story 3 - List Available Backups (Priority: P3)

**Goal**: Users can see available backups in the default location with metadata

**Independent Test**: Create multiple backups, run `vpo library backups`, verify all are listed with correct metadata

### Implementation for User Story 3

- [x] T038 [US3] Implement `list_backups(backup_dir)` function in src/vpo/db/backup.py that scans for vpo-library-*.tar.gz files
- [x] T039 [US3] Add metadata extraction from each archive in list_backups() in src/vpo/db/backup.py
- [x] T040 [US3] Add sorting by creation date (newest first) in list_backups() in src/vpo/db/backup.py
- [x] T041 [US3] Implement `backups_command()` CLI command in src/vpo/cli/library.py with --path, --json options
- [x] T042 [US3] Add tabular output formatting with filename, date, size, file count to backups_command() in src/vpo/cli/library.py
- [x] T043 [US3] Add JSON output formatting to backups_command() in src/vpo/cli/library.py
- [x] T044 [US3] Add "no backups found" message with help hint to backups_command() in src/vpo/cli/library.py

**Checkpoint**: All user stories complete - backup, restore, and list all work independently

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T045 [P] Export backup types (BackupMetadata, BackupInfo, BackupResult, RestoreResult, exceptions) from src/vpo/db/__init__.py
- [x] T046 [P] Add structured logging for backup operations in src/vpo/db/backup.py
- [x] T047 [P] Add structured logging for restore operations in src/vpo/db/backup.py
- [x] T048 Update CLI help text with backup command examples in src/vpo/cli/library.py docstrings
- [ ] T049 Run manual validation: create backup, restore, list backups per quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 (backup) can start after Phase 2
  - US2 (restore) can start after Phase 2 (independent of US1)
  - US3 (list) can start after Phase 2 (independent of US1/US2)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Phase 2 - Uses validate_backup() which is US2-specific
- **User Story 3 (P3)**: Can start after Phase 2 - Reuses _read_backup_metadata() from Phase 2

### Within Each User Story

- Core functions before CLI commands
- CLI integration after core functions
- Error handling last

### Parallel Opportunities

- **Phase 1**: All T001-T006 can run in parallel (different dataclasses/exceptions)
- **Phase 3 (US1)**: T019-T023 CLI tasks depend on T014-T018 core functions
- **Phase 4 (US2)**: T031-T037 CLI tasks depend on T024-T030 core functions
- **Phase 5 (US3)**: T041-T044 CLI tasks depend on T038-T040 core functions
- **Phase 6**: T045-T047 can run in parallel

---

## Parallel Example: Phase 1 Setup

```bash
# Launch all dataclass/exception definitions together:
Task: "Create BackupMetadata dataclass in src/vpo/db/backup.py"
Task: "Create BackupInfo dataclass in src/vpo/db/backup.py"
Task: "Create BackupResult dataclass in src/vpo/db/backup.py"
Task: "Create RestoreResult dataclass in src/vpo/db/backup.py"
Task: "Define exception hierarchy in src/vpo/db/backup.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (data types)
2. Complete Phase 2: Foundational (helper functions)
3. Complete Phase 3: User Story 1 (backup)
4. **STOP and VALIDATE**: Test `vpo library backup` works
5. Commit and deploy - users can now back up their libraries

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (backup) → Test independently → Commit (MVP!)
3. Add User Story 2 (restore) → Test independently → Commit
4. Add User Story 3 (list) → Test independently → Commit
5. Each story adds value without breaking previous stories

### Single Developer Strategy

1. Work phases sequentially: Setup → Foundational → US1 → US2 → US3 → Polish
2. Commit after each phase checkpoint
3. Each commit is deployable (after US1)

---

## Notes

- [P] tasks = different files or independent code sections
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable via acceptance scenarios in spec.md
- All file paths are relative to repository root
- Core backup logic in db/backup.py follows VPO DAO pattern (Constitution principle VI)
- CLI commands extend existing library.py (existing command group pattern)
