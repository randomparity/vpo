# Feature Specification: Reporting & Export CLI

**Feature Branch**: `011-report-export-cli`
**Created**: 2025-01-22
**Status**: Draft
**Input**: User description: "Add a report command (or subcommands) that lets users generate text, CSV, or JSON reports about scan results, job history and status, transcode operations, and policy applications so they can track and audit how the system has been operating over time."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Job History Audit (Priority: P1)

As an operator, I want to view a report of job history so that I can audit system activity and debug issues over a time range.

**Why this priority**: Job history is the foundation for understanding what the system has been doing. This is the most frequently needed report for operational monitoring and troubleshooting. It provides visibility into all operation types (scan, apply, transcode, move).

**Independent Test**: Can be fully tested by running `vpo report jobs` after executing various jobs and verifying the output contains accurate job records. Delivers immediate value for operational visibility.

**Acceptance Scenarios**:

1. **Given** jobs exist in the database, **When** I run `vpo report jobs`, **Then** I see a list of jobs with ID, type, status, start/end times, duration, and target information.
2. **Given** jobs exist with various statuses, **When** I run `vpo report jobs --status failed`, **Then** I see only failed jobs with error summaries.
3. **Given** jobs exist from the past month, **When** I run `vpo report jobs --since 7d`, **Then** I see only jobs created in the last 7 days.
4. **Given** I need machine-readable output, **When** I run `vpo report jobs --format json`, **Then** I receive valid JSON output with consistent keys.

---

### User Story 2 - Library Snapshot Export (Priority: P2)

As a user, I want a snapshot report of the current library so that I can export metadata for external analysis or archiving.

**Why this priority**: Library export is essential for data portability and external tooling integration. Users frequently need to analyze their media collection in spreadsheets or custom scripts.

**Independent Test**: Can be fully tested by running `vpo report library` after scanning a directory and verifying the output contains accurate file metadata. Delivers value for library inventory and analysis.

**Acceptance Scenarios**:

1. **Given** files exist in the library database, **When** I run `vpo report library`, **Then** I see file path, title, container type, resolution, audio languages, subtitle presence, and last scanned timestamp for each file.
2. **Given** I need to filter by resolution, **When** I run `vpo report library --resolution 4K`, **Then** I see only files with 4K resolution.
3. **Given** I need CSV for spreadsheet import, **When** I run `vpo report library --format csv`, **Then** I receive properly escaped CSV with headers.

---

### User Story 3 - Multi-Format Output Support (Priority: P3)

As a user, I want reports in text, CSV, or JSON formats so that I can either read them directly or feed them into other tools.

**Why this priority**: Format flexibility enables diverse use cases - human review (text), spreadsheet analysis (CSV), and programmatic integration (JSON). This is a cross-cutting concern that multiplies the value of all reports.

**Independent Test**: Can be tested by running any report command with `--format text`, `--format csv`, and `--format json` and verifying each produces valid, well-formed output. Delivers value for tool integration.

**Acceptance Scenarios**:

1. **Given** a report is requested, **When** I specify `--format text` (or omit format), **Then** I receive human-readable tabular output.
2. **Given** a report is requested, **When** I specify `--format csv`, **Then** I receive valid CSV with header row and proper escaping.
3. **Given** a report is requested, **When** I specify `--format json`, **Then** I receive valid JSON array with stable key ordering.
4. **Given** an invalid format is requested, **When** I run `vpo report jobs --format xml`, **Then** I receive a clear error message listing valid formats.

---

### User Story 4 - Scan History Report (Priority: P4)

As a user, I want a report of scan operations so that I can see when my library was scanned and how many files were affected.

**Why this priority**: Scan history helps users understand when their library was last updated and the scope of each scan. Important for maintenance and troubleshooting but less frequently needed than job history.

**Independent Test**: Can be tested by running `vpo report scans` after performing scans and verifying accurate scan statistics are displayed.

**Acceptance Scenarios**:

1. **Given** scan jobs exist, **When** I run `vpo report scans`, **Then** I see scan ID, start/end time, duration, files scanned, new files, changed files, and status for each scan.
2. **Given** scans exist over time, **When** I run `vpo report scans --since 30d --until 7d`, **Then** I see only scans within that time range.

---

### User Story 5 - Transcode Operations Report (Priority: P5)

As a user, I want a report of transcode operations so that I can see what files were recompressed, how, and with what results.

**Why this priority**: Transcode reports help users track storage savings and processing history. Valuable for capacity planning but dependent on transcode feature usage.

**Independent Test**: Can be tested by running `vpo report transcodes` after transcode jobs complete and verifying accurate transcode details are displayed.

**Acceptance Scenarios**:

1. **Given** transcode jobs exist, **When** I run `vpo report transcodes`, **Then** I see file path, job ID, original codec, target codec, start/end times, status, and size change for each transcode.
2. **Given** I want to analyze specific codec conversions, **When** I run `vpo report transcodes --codec hevc`, **Then** I see only transcodes targeting HEVC.
3. **Given** I need size savings analysis, **When** I run `vpo report transcodes --format csv`, **Then** I receive CSV suitable for calculating aggregate savings.

---

### User Story 6 - Policy Application Report (Priority: P6)

As a user, I want a report of policy applications so that I know which files were changed by which policies and when.

**Why this priority**: Policy application tracking is essential for auditing changes to media files but is less frequently needed than basic job and library reports.

**Independent Test**: Can be tested by running `vpo report policy-apply` after applying policies and verifying accurate change summaries are displayed.

**Acceptance Scenarios**:

1. **Given** policy operations exist, **When** I run `vpo report policy-apply`, **Then** I see operation ID, policy name, files impacted, change type (metadata vs heavy operations), and status.
2. **Given** I need per-file details, **When** I run `vpo report policy-apply --verbose`, **Then** I see file paths with change summaries (e.g., "reordered tracks, updated default audio").

---

### User Story 7 - File Output Support (Priority: P7)

As a user, I want to write reports directly to files so that I can keep historical logs and import them into other tools.

**Why this priority**: File output is a convenience feature that complements stdout. Important for automation and record-keeping but not essential for basic functionality.

**Independent Test**: Can be tested by running any report with `--output report.json` and verifying the file is created with correct content.

**Acceptance Scenarios**:

1. **Given** I want to save a report, **When** I run `vpo report jobs --output jobs.json`, **Then** the report is written to the specified file.
2. **Given** the output file exists, **When** I run `vpo report jobs --output existing.json`, **Then** I receive an error about the existing file.
3. **Given** I want to overwrite, **When** I run `vpo report jobs --output existing.json --force`, **Then** the file is overwritten with the new report.

---

### Edge Cases

- What happens when the database is empty? Report commands display "No records found" message and exit with success.
- What happens when filters match no records? Report displays "No records match the specified filters" message.
- What happens when invalid date format is used for --since/--until? Clear error message with expected format examples.
- How are very long file paths handled in text output? Paths are truncated with ellipsis or wrapped based on terminal width.
- What happens when --output path is not writable? Clear error message indicating permission or path issue.
- How are Unicode characters in file paths/titles handled? Full UTF-8 support in all output formats.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `vpo report` command group as the entry point for all reporting functionality.
- **FR-002**: System MUST support subcommands: `jobs`, `library`, `scans`, `transcodes`, and `policy-apply`.
- **FR-003**: All report subcommands MUST accept `--format` option with values: `text`, `csv`, `json`.
- **FR-004**: System MUST default to `text` format when `--format` is not specified.
- **FR-005**: All report subcommands MUST accept `--output PATH` option to write to a file instead of stdout.
- **FR-006**: System MUST refuse to overwrite existing files unless `--force` flag is provided.
- **FR-007**: Report subcommands MUST accept `--since` and `--until` options for time-based filtering.
- **FR-008**: Time filter options MUST support ISO-8601 timestamps and relative formats (e.g., "7d", "30d", "1w").
- **FR-009**: `vpo report jobs` MUST support filtering by `--type` (scan, apply, transcode, move) and `--status` (queued, running, completed, failed, cancelled).
- **FR-010**: `vpo report library` MUST support filtering by `--resolution`, `--language`, and `--has-subtitles`.
- **FR-011**: `vpo report transcodes` MUST support filtering by `--codec`.
- **FR-012**: `vpo report policy-apply` MUST support `--policy` filter and `--verbose` flag for per-file details.
- **FR-013**: CSV output MUST include a header row and properly escape special characters.
- **FR-014**: JSON output MUST produce a valid JSON array with stable key ordering for diff-friendly outputs.
- **FR-015**: Text output MUST be human-readable with aligned columns suitable for terminal display.
- **FR-016**: All timestamps in reports MUST be displayed in local time with timezone indication.
- **FR-017**: Duration values MUST be displayed in human-readable format (e.g., "5m 23s").
- **FR-018**: `vpo report --help` and `vpo report <subcommand> --help` MUST display comprehensive usage information with examples.
- **FR-019**: System MUST exit with non-zero status code when errors occur (invalid format, write failure, etc.).
- **FR-020**: Reports MUST be read-only operations that do not modify any database state.
- **FR-021**: All report subcommands MUST default to returning a maximum of 100 rows.
- **FR-022**: All report subcommands MUST accept `--limit N` option to specify a custom row limit.
- **FR-023**: All report subcommands MUST accept `--no-limit` flag to return all matching records.

### Key Entities

- **Report**: A generated view of database records formatted for output. Contains rows of data, column definitions, and metadata (generation timestamp, filter criteria applied).
- **ReportFormat**: The output serialization format (text, csv, json). Determines how report data is rendered.
- **TimeFilter**: A time range specification using `since` and `until` bounds. Supports absolute (ISO-8601) and relative (Nd, Nw) formats.
- **JobReport**: Report of job history including job ID, type, status, timing, target, and error summary.
- **LibraryReport**: Snapshot of library files including path, title, container, resolution, languages, subtitles, and scan timestamp.
- **ScanReport**: Report of scan operations including scan ID, timing, file counts (total, new, changed), and status.
- **TranscodeReport**: Report of transcode operations including file path, job ID, codecs, timing, status, and size change.
- **PolicyApplyReport**: Report of policy applications including operation ID, policy name, file count, change types, and status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can generate any report type within 2 seconds for databases with up to 10,000 files.
- **SC-002**: Generated CSV files can be imported into common spreadsheet applications without data loss or formatting issues.
- **SC-003**: Generated JSON files pass validation and can be parsed by standard JSON libraries.
- **SC-004**: 100% of report commands display helpful error messages for invalid inputs (no stack traces in production use).
- **SC-005**: Users can filter reports by time range, reducing result sets to relevant records efficiently.
- **SC-006**: Text reports are readable on standard 80-column terminals with proper truncation/wrapping.
- **SC-007**: File output option successfully writes reports to user-specified paths with appropriate permissions handling.
- **SC-008**: All report commands are documented with usage examples in help text and user documentation.

## Clarifications

### Session 2025-01-22

- Q: Should reports have a default row limit to prevent overwhelming output? → A: Default limit (100 rows) with `--limit N` to override and `--no-limit` for all records.

## Assumptions

- The existing database schema (jobs, files, tracks, operations tables) provides sufficient data for all report types.
- Relative time formats follow common conventions: "d" for days, "w" for weeks (e.g., "7d" = 7 days ago).
- Terminal width detection is available for text output formatting; fallback to 80 columns when unavailable.
- The scan job summary_json field contains file counts (total, new, changed) for scan history reports.
- The jobs.files_affected_json field can be used to determine files impacted by policy apply operations.
- Error messages for failed jobs (jobs.error_message) may be truncated in reports with full details available via `vpo job show <id>`.
