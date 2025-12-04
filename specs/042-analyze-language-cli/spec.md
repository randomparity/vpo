# Feature Specification: Analyze-Language CLI Commands

**Feature Branch**: `042-analyze-language-cli`
**Created**: 2025-12-04
**Status**: Draft
**Input**: User description: "Implement dedicated analyze-language CLI command group with run, status, and clear subcommands for managing language analysis results (deferred from issue #270)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Language Analysis on Demand (Priority: P1)

As a VPO user, I want to run language analysis on specific files or directories without performing a full scan, so that I can analyze language content independently of the scanning workflow.

**Why this priority**: This is the core functionality that enables standalone language analysis. Without this, users must use `vpo scan --analyze-languages` which re-scans the entire directory, even for files already in the database.

**Independent Test**: Can be fully tested by running `vpo analyze-language run <file>` on a media file and verifying language analysis results are generated and stored.

**Acceptance Scenarios**:

1. **Given** a media file that exists in the VPO database, **When** `vpo analyze-language run movie.mkv` is executed, **Then** language analysis is performed on all audio tracks and results are stored in the database.

2. **Given** a media file not yet in the database, **When** `vpo analyze-language run movie.mkv` is executed, **Then** the system reports that the file must be scanned first before language analysis.

3. **Given** a directory containing multiple media files, **When** `vpo analyze-language run /media/movies/` is executed, **Then** language analysis is performed on all files in the directory that exist in the database.

4. **Given** a file with existing language analysis results, **When** `vpo analyze-language run movie.mkv` is executed without `--force`, **Then** cached results are returned without re-analysis.

5. **Given** a file with existing language analysis results, **When** `vpo analyze-language run movie.mkv --force` is executed, **Then** fresh analysis is performed and cached results are updated.

---

### User Story 2 - View Language Analysis Status (Priority: P2)

As a VPO user, I want to see the language analysis status for files in my library, so that I can understand which files have been analyzed and what languages were detected.

**Why this priority**: Users need visibility into analysis state to make informed decisions about which files need analysis and to review detection results.

**Independent Test**: Can be fully tested by running `vpo analyze-language status` after some files have been analyzed and verifying the output shows correct analysis state.

**Acceptance Scenarios**:

1. **Given** a library with some files analyzed and some not, **When** `vpo analyze-language status` is executed, **Then** a summary showing total files, analyzed files, and pending files is displayed.

2. **Given** a specific file with language analysis results, **When** `vpo analyze-language status movie.mkv` is executed, **Then** detailed language breakdown for each audio track is displayed (primary language, secondary languages, classification).

3. **Given** a file without language analysis results, **When** `vpo analyze-language status movie.mkv` is executed, **Then** the system indicates the file has not been analyzed.

4. **Given** the `--json` flag is provided, **When** `vpo analyze-language status` is executed, **Then** output is formatted as valid JSON for programmatic consumption.

5. **Given** the `--filter multi-language` flag is provided, **When** `vpo analyze-language status --filter multi-language` is executed, **Then** only files classified as MULTI_LANGUAGE are shown.

---

### User Story 3 - Clear Cached Analysis Results (Priority: P3)

As a VPO user, I want to clear cached language analysis results, so that I can free up database space or force re-analysis of files whose audio may have changed.

**Why this priority**: Cache management is important for long-term maintenance but is less frequently used than running analysis or viewing status.

**Independent Test**: Can be fully tested by running `vpo analyze-language clear` on files with existing results and verifying the results are removed from the database.

**Acceptance Scenarios**:

1. **Given** a specific file with language analysis results, **When** `vpo analyze-language clear movie.mkv` is executed, **Then** analysis results for that file are removed from the database.

2. **Given** a directory path, **When** `vpo analyze-language clear /media/movies/` is executed, **Then** analysis results for all files in that directory are removed.

3. **Given** no path argument and `--all` flag, **When** `vpo analyze-language clear --all` is executed, **Then** all language analysis results in the database are removed.

4. **Given** a potentially destructive clear operation, **When** the command is executed without `--yes`, **Then** the user is prompted for confirmation before deletion.

5. **Given** the `--dry-run` flag is provided, **When** `vpo analyze-language clear --dry-run` is executed, **Then** the system shows what would be deleted without actually removing anything.

---

### Edge Cases

- What happens when the transcription plugin is not installed? The system should report a clear error indicating the whisper_transcriber plugin is required for language analysis.
- What happens when analysis is run on a file with no audio tracks? The system should report "no audio tracks found" and skip the file.
- What happens when analysis is interrupted mid-file? Partial results should not be committed; the file should remain in "not analyzed" state.
- What happens when clearing results for a file that has no results? The system should report "no results to clear" without error.
- What happens with very large libraries (10,000+ files)? The status command should paginate results or provide summary-only mode to avoid overwhelming output.
- What happens when some paths in a batch don't exist or aren't in the database? The system should warn for each invalid path, continue processing valid paths, and error only if no valid files are found.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `vpo analyze-language` command group with subcommands.
- **FR-002**: The `run` subcommand MUST accept file paths or directory paths as arguments.
- **FR-003**: The `run` subcommand MUST support a `--force` flag to bypass cache and re-analyze.
- **FR-004**: The `run` subcommand MUST support a `--recursive` flag for directory processing.
- **FR-005**: The `run` subcommand MUST validate that files exist in the VPO database before analysis.
- **FR-006**: The `status` subcommand MUST show summary statistics when no path is provided.
- **FR-007**: The `status` subcommand MUST show detailed results when a specific file path is provided.
- **FR-008**: The `status` subcommand MUST support `--json` output format.
- **FR-009**: The `status` subcommand MUST support `--filter` to show only single-language or multi-language files.
- **FR-010**: The `clear` subcommand MUST accept file paths, directory paths, or `--all` flag.
- **FR-011**: The `clear` subcommand MUST require confirmation for bulk deletions unless `--yes` is provided.
- **FR-012**: The `clear` subcommand MUST support `--dry-run` to preview deletions.
- **FR-013**: All subcommands MUST display appropriate error messages when the transcription plugin is unavailable.
- **FR-014**: Progress reporting MUST be shown for operations on multiple files.

### Key Entities

- **LanguageAnalysisResult**: Existing entity storing analysis results per track. Contains primary language, secondary languages with percentages, classification (SINGLE_LANGUAGE/MULTI_LANGUAGE), and analysis metadata.
- **LanguageSegment**: Existing entity storing detected language segments with timestamps and confidence scores.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can analyze language content in a single file in under 60 seconds (for files under 2 hours).
- **SC-002**: Users can view analysis status for their entire library in under 5 seconds.
- **SC-003**: Users can clear all cached results in under 10 seconds for libraries with up to 10,000 files.
- **SC-004**: Command help text clearly explains all options and provides usage examples.
- **SC-005**: All operations provide clear success/failure feedback with actionable error messages.

## Dependencies

- **Language Analysis Module**: The `language_analysis` module from issue #270 is already implemented and provides the core analysis functionality.
- **Transcription Plugin**: The whisper_transcriber plugin must be installed for language analysis to function.
- **Database Schema**: The `language_analysis_results` and `language_segments` tables already exist (schema version 17+).

## Assumptions

- The existing `analyze_track_languages()` service function handles all analysis logic; CLI only needs to orchestrate calls.
- Users understand that language analysis requires the Whisper transcription plugin to be installed.
- The database contains file records for any files the user wants to analyze (files must be scanned first).
- Output formatting follows existing VPO CLI patterns (human-readable by default, JSON optional).

## Out of Scope

- Batch processing configuration (e.g., limiting concurrent analysis jobs) — use existing VPO job system if needed.
- Web UI integration for the analyze-language commands — this is CLI-only.
- Analysis of files not in the database — users must run `vpo scan` first.
- Custom Whisper model selection — uses transcription plugin's configured model.
