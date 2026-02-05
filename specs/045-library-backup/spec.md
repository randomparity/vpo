# Feature Specification: Library Backup and Restore

**Feature Branch**: `045-library-backup`
**Created**: 2026-02-05
**Status**: Draft
**Input**: User description: "Extend the vpo library command to support backup and restore functionality. Support compressed archives."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create Library Backup (Priority: P1)

A user wants to create a backup of their VPO library database before making significant changes, migrating to a new system, or as part of their regular backup routine. They run a single command and receive a compressed archive containing their complete library state.

**Why this priority**: This is the core functionality that enables all disaster recovery and migration use cases. Without backup capability, restore is meaningless.

**Independent Test**: Can be fully tested by creating a backup of an existing library and verifying the archive contains valid, complete data. Delivers immediate value for disaster recovery.

**Acceptance Scenarios**:

1. **Given** a library with scanned files, **When** user runs `vpo library backup`, **Then** a compressed archive is created containing the complete database
2. **Given** a library with scanned files, **When** user runs `vpo library backup --output /path/to/backup.tar.gz`, **Then** the backup is created at the specified location
3. **Given** a library with scanned files, **When** user runs `vpo library backup --dry-run`, **Then** the system shows what would be backed up without creating the archive

---

### User Story 2 - Restore Library from Backup (Priority: P2)

A user needs to restore their VPO library from a previous backup after data loss, system migration, or to recover from a bad operation. They run a restore command pointing to their backup archive and the library is restored to the backed-up state.

**Why this priority**: Restore completes the backup-restore cycle. While backup alone has value, restore is essential for the backup to be useful in recovery scenarios.

**Independent Test**: Can be fully tested by restoring from a previously created backup and verifying the library state matches the backup.

**Acceptance Scenarios**:

1. **Given** a valid backup archive, **When** user runs `vpo library restore /path/to/backup.tar.gz`, **Then** the library database is replaced with the backup contents
2. **Given** an existing library with data, **When** user attempts restore without `--yes`, **Then** the system prompts for confirmation before overwriting
3. **Given** a valid backup archive, **When** user runs `vpo library restore --dry-run /path/to/backup.tar.gz`, **Then** the system validates the archive and shows what would be restored without making changes
4. **Given** a file that is not a valid tar.gz archive, **When** user runs `vpo library restore /path/to/invalid.zip`, **Then** the system displays an error message indicating the archive format is not supported

---

### User Story 3 - List Available Backups (Priority: P3)

A user wants to see what backups exist in their default backup location to choose which one to restore or to verify their backup routine is working.

**Why this priority**: Convenience feature that improves usability but is not essential for core backup/restore functionality.

**Independent Test**: Can be tested by creating multiple backups and verifying the list command shows them with relevant metadata.

**Acceptance Scenarios**:

1. **Given** multiple backup files in the default backup directory, **When** user runs `vpo library backups`, **Then** the system lists all backups with creation date and size
2. **Given** no backups exist, **When** user runs `vpo library backups`, **Then** the system shows a message indicating no backups found

---

### Edge Cases

- What happens when the backup destination has insufficient disk space?
- How does the system handle a corrupted or incomplete backup archive during restore?
- What happens if the user tries to restore a backup from a newer schema version?
- How does the system handle concurrent access (daemon running) during backup/restore?
- What happens when the backup archive uses an unsupported compression format?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create compressed backup archives of the library database
- **FR-002**: System MUST support gzip compression for backup archives (`.tar.gz` format)
- **FR-003**: System MUST allow users to specify a custom output path for backups
- **FR-004**: System MUST use a default backup location when no output path is specified (`~/.vpo/backups/`)
- **FR-005**: System MUST generate backup filenames with timestamps (e.g., `vpo-library-2026-02-05T143022Z.tar.gz`)
- **FR-006**: System MUST restore library database from a valid backup archive
- **FR-007**: System MUST validate backup archive integrity before restoration
- **FR-008**: System MUST require confirmation before overwriting an existing library during restore
- **FR-009**: System MUST support `--dry-run` mode for both backup and restore operations
- **FR-010**: System MUST support `--json` output for programmatic use
- **FR-011**: System MUST list available backups in the default backup directory
- **FR-012**: System MUST display backup metadata (creation date, size, schema version)
- **FR-013**: System MUST check for sufficient disk space before creating a backup
- **FR-014**: System MUST prevent backup/restore when the daemon has an exclusive lock on the database
- **FR-015**: System MUST include schema version in backup metadata for compatibility checking
- **FR-016**: System MUST warn users when restoring from a backup with a different schema version

### Key Entities

- **Backup Archive**: A compressed tarball containing the SQLite database file and metadata. Key attributes: creation timestamp, original database size, schema version, compression format.
- **Backup Metadata**: Information about a backup stored alongside or within the archive. Includes: creation time (UTC), VPO version, schema version, file count at backup time, total library size.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create a complete library backup in under 30 seconds for libraries under 100MB
- **SC-002**: Backup archives achieve at least 50% compression ratio compared to the raw database size
- **SC-003**: Users can restore from backup and resume normal operations within 60 seconds for libraries under 100MB
- **SC-004**: Backup integrity validation catches 100% of truncated or corrupted archives
- **SC-005**: Users can identify the correct backup to restore from the backup list without needing to inspect archive contents manually

## Assumptions

- The SQLite database file is the only artifact that needs to be backed up (media files are not included as they exist on the filesystem)
- Users have standard filesystem permissions for reading the database and writing to the backup location
- The `tarfile` Python standard library module provides sufficient compression capabilities
- Backup operations will acquire a read lock on the database to ensure consistency
- Default backup location `~/.vpo/backups/` will be created automatically if it doesn't exist
