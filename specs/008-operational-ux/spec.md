# Feature Specification: Operational UX - Incremental Scans, Job History & Profiles

**Feature Branch**: `008-operational-ux`
**Created**: 2025-11-22
**Status**: Draft
**Input**: User description: "Scheduling, Incremental Scans, and Operational UX - Make the system usable for periodic maintenance: incremental scans, job history, and operational quality-of-life features."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Incremental Directory Scanning (Priority: P1)

As a user with a large video library, I want to rescan my library and only process changed or new files, so that periodic maintenance runs complete quickly without re-introspecting unchanged files.

**Why this priority**: This is the foundational feature that makes VPO practical for ongoing library maintenance. Without incremental scanning, users must choose between full rescans (slow) or manual tracking of changes (error-prone).

**Independent Test**: Can be fully tested by scanning a directory, modifying one file, then running incremental scan and verifying only the changed file is re-introspected.

**Acceptance Scenarios**:

1. **Given** a previously scanned library with 1000 files, **When** I run `vpo scan /path/to/library`, **Then** the system automatically uses incremental mode and only introspects files where mtime or size has changed since the last scan.

2. **Given** a previously scanned library, **When** new files are added to the library, **Then** incremental scan discovers and introspects only the new files.

3. **Given** a previously scanned library, **When** files are deleted from the library, **Then** incremental scan marks the missing files as removed in the database (or optionally deletes their records).

4. **Given** a library with 500 unchanged files and 5 changed files, **When** I run incremental scan, **Then** the operation completes in time proportional to the 5 changed files, not the full 500.

5. **Given** I run incremental scan, **When** the scan completes, **Then** I see a summary showing: files scanned, files skipped (unchanged), files added, files removed.

---

### User Story 2 - Job History and Status (Priority: P2)

As an operator, I want to list recent operations and their outcomes, so that I can troubleshoot failures and audit changes made to my library.

**Why this priority**: Essential for operational use. Without visibility into past operations, users cannot diagnose problems or understand what changes have been made.

**Independent Test**: Can be fully tested by running several operations, then using job history commands to list and inspect them.

**Acceptance Scenarios**:

1. **Given** I have run several scan, apply, or transcode operations, **When** I run `vpo jobs list`, **Then** I see a table of recent jobs showing ID, type, status, file path, and timestamps.

2. **Given** a specific job ID (or unique prefix), **When** I run `vpo jobs show <id>`, **Then** I see detailed information including: full configuration used, start/end times, duration, any errors or warnings, and files affected.

3. **Given** I run `vpo jobs list`, **When** there are many jobs, **Then** I can filter by status (completed, failed, running) and by time range.

4. **Given** a failed job, **When** I view its details, **Then** I see the error message, stack trace (if available), and context about what was being processed when failure occurred.

5. **Given** jobs accumulate over time, **When** retention period expires, **Then** old job records are automatically cleaned up according to configured retention policy.

---

### User Story 3 - Configuration Profiles (Priority: P3)

As a user with different video collections (Movies, TV Shows, Kids content), I want to use separate policy configuration profiles, so that each collection follows different rules without manually specifying policies each time.

**Why this priority**: Quality-of-life improvement that makes the tool more ergonomic for users with diverse libraries. Can function without it by specifying policies manually.

**Independent Test**: Can be fully tested by creating two profiles with different settings, then verifying the correct profile is applied based on the `--profile` flag.

**Acceptance Scenarios**:

1. **Given** I have created a profile named "movies" with specific policy settings, **When** I run `vpo scan --profile movies /path/to/movies`, **Then** the scan uses the "movies" profile configuration.

2. **Given** I have profiles defined in `~/.vpo/profiles/`, **When** I run `vpo profiles list`, **Then** I see all available profile names and their descriptions.

3. **Given** no profile is specified, **When** I run any vpo command, **Then** the default profile (or base configuration) is used.

4. **Given** a profile specifies a default policy file, **When** I run `vpo apply --profile movies /path/to/file.mkv`, **Then** the profile's default policy is used without requiring `--policy` flag.

5. **Given** I specify both `--profile` and explicit options, **When** I run a command, **Then** explicit options override profile settings (explicit wins).

---

### User Story 4 - Structured Logging and Observability (Priority: P4)

As a maintainer deploying VPO in automated workflows, I want structured logs with configurable levels and output formats, so that I can integrate with log aggregation systems and diagnose issues in production.

**Why this priority**: Important for production deployments but the tool is usable without it. Can be added incrementally after core features.

**Independent Test**: Can be fully tested by configuring different log levels and formats, then verifying log output matches configuration.

**Acceptance Scenarios**:

1. **Given** I configure logging in `~/.vpo/config.yaml`, **When** I run vpo commands, **Then** logs are written to the configured destination (file, stderr, or both).

2. **Given** I set log level to "debug", **When** I run vpo commands, **Then** I see detailed internal operation logs including tool invocations and timing.

3. **Given** I enable JSON log format, **When** logs are written, **Then** each log entry is a valid JSON object with timestamp, level, message, and context fields.

4. **Given** I set log level to "warning", **When** I run vpo commands, **Then** only warnings and errors appear in the log (not info or debug messages).

5. **Given** logging is configured to a file, **When** the log file grows large, **Then** log rotation is handled according to configuration.

---

### Edge Cases

- What happens when incremental scan encounters a file with unchanged mtime/size but corrupted content? (Answer: Provide `--verify-hash` option to use content hash for change detection instead of mtime/size.)
- How does the system handle a file that was renamed but otherwise unchanged? (Answer: Detected as new file at new path; old path marked as removed. Content hash can optionally link them.)
- What if a profile references a policy file that doesn't exist? (Answer: Fail with clear error message at command startup, not during processing.)
- What happens if job history database becomes corrupted? (Answer: Users can delete `~/.vpo/library.db` to reset. Future enhancement: `vpo doctor --repair-jobs` command.)
- How are log files handled when disk is full? (Answer: Log to stderr as fallback; emit warning about log file unavailability.)

## Requirements *(mandatory)*

### Functional Requirements

**Incremental Scanning**
- **FR-001**: System MUST track file modification time (mtime) and size in the database for change detection.
- **FR-002**: System MUST use incremental mode by default when prior scan data exists for the target directory.
- **FR-003**: System MUST skip introspection for files where mtime and size are unchanged since last scan.
- **FR-004**: System MUST detect and record newly added files during incremental scan.
- **FR-005**: System MUST detect files that no longer exist and mark them appropriately (configurable: mark-removed vs delete-record).
- **FR-006**: System MUST provide a summary at end of incremental scan showing counts: scanned, skipped, added, removed.
- **FR-007**: System MUST support `--full` flag to force a complete rescan, bypassing incremental detection.
- **FR-008**: System SHOULD provide `--verify-hash` option to use content hash instead of mtime/size for change detection.

**Job History**
- **FR-009**: System MUST record all scan, apply, and transcode operations as jobs in the database.
- **FR-010**: System MUST track for each job: ID, type, status, start time, end time, configuration used, files affected.
- **FR-011**: System MUST provide `vpo jobs list` command to display recent jobs.
- **FR-012**: System MUST provide `vpo jobs show <id>` command to display detailed job information.
- **FR-013**: System MUST support filtering jobs by status and time range in list command.
- **FR-014**: System MUST record error details for failed jobs including message and context.
- **FR-015**: System MUST automatically purge old jobs according to configured retention period.

**Configuration Profiles**
- **FR-016**: System MUST support named configuration profiles stored in `~/.vpo/profiles/` directory.
- **FR-017**: System MUST provide `--profile <name>` flag on all relevant commands.
- **FR-018**: System MUST provide `vpo profiles list` command to show available profiles.
- **FR-019**: System MUST allow profiles to specify: default policy, tool paths, behavior settings.
- **FR-020**: System MUST apply profile settings as defaults that can be overridden by explicit command-line options.
- **FR-021**: System MUST provide `vpo profiles show <name>` to display profile configuration.

**Logging and Observability**
- **FR-022**: System MUST support configurable log levels: debug, info, warning, error.
- **FR-023**: System MUST support logging to file with configurable path.
- **FR-024**: System MUST support JSON log format as an option.
- **FR-025**: System MUST include timestamp, level, and message in all log entries.
- **FR-026**: System MUST support logging to stderr in addition to or instead of file.
- **FR-027**: System SHOULD support basic log rotation (by size or daily).

### Key Entities

- **ScanState**: Tracks per-file scan state including last scan time, mtime at scan, size at scan, enabling incremental detection.
- **Job**: Expanded from existing model to include all operation types (scan, apply, transcode) with unified tracking.
- **Profile**: Named configuration bundle containing policy references, tool paths, and behavior overrides.
- **LogConfig**: Logging configuration including level, destination, format, and rotation settings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Incremental scan of a 1000-file library with 10 changed files completes in under 10% of the time required for a full scan.
- **SC-002**: Users can retrieve details of any operation performed in the last 30 days within 2 seconds.
- **SC-003**: Profile-based commands require 50% fewer command-line arguments compared to explicit specification.
- **SC-004**: Logs capture sufficient context that 90% of operational issues can be diagnosed without reproducing the problem.
- **SC-005**: All scan operations automatically use incremental mode when prior scan data exists (opt-out rather than opt-in for efficiency).
- **SC-006**: Job history provides complete audit trail: users can answer "what changed and why" for any file in their library.

## Clarifications

### Session 2025-11-22

- Q: Which should be the default behavior for `vpo scan` when the directory has been scanned before? → A: Opt-out model - Incremental by default when prior data exists, `--full` flag forces full rescan.

## Assumptions

- File modification time (mtime) is reliable for change detection on the user's filesystem. This is true for most modern filesystems but may not hold for network mounts with clock skew.
- Users have a single VPO configuration directory (`~/.vpo/`) per system. Multi-user scenarios share this directory or use `--config` override.
- Job retention defaults to 30 days, matching the existing `JobsConfig.retention_days` setting.
- Log rotation will use standard practices: rotate at 10MB by default, keep 5 rotated files.
- Profile YAML format follows existing VPO configuration patterns for consistency.

## Constraints

- Must integrate with existing database schema without breaking migrations.
- Must preserve backward compatibility with existing CLI commands (new flags are additive).
- Logging implementation must not significantly impact performance for normal operations.
- Profile system must not require profile creation for basic usage (graceful fallback to defaults).
