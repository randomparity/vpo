# Feature Specification: Job Detail View with Logs

**Feature Branch**: `016-job-detail-view`
**Created**: 2025-11-23
**Status**: Draft
**Input**: User description: "Implement Job detail view with logs - Add a job detail view accessible from the Jobs dashboard showing full job metadata, human-readable summary, and logs."

## Clarifications

### Session 2025-11-23

- Q: How should job logs be stored (database field vs file-based)? → A: File-based storage with database path reference

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Full Job Details (Priority: P1)

As an operator, I want to click on a job in the dashboard list to view its complete details, so that I can understand exactly what the job did and verify its outcome.

**Why this priority**: This is the core value proposition - without the ability to see full job details, operators cannot troubleshoot or verify job execution. The detail view is the foundation for all other functionality.

**Independent Test**: Can be fully tested by clicking any job in the list and verifying all job fields are displayed correctly, delivering immediate visibility into job specifics.

**Acceptance Scenarios**:

1. **Given** a job exists in the system, **When** an operator clicks on the job row in the list, **Then** a detail view opens showing all job fields (ID, type, status, timestamps, target path, policy name, progress, error message if any).
2. **Given** a job detail view is open, **When** viewing the metadata section, **Then** timestamps are displayed in human-readable format with relative time (e.g., "2 hours ago").
3. **Given** a job has completed, **When** viewing its detail, **Then** the duration is displayed (e.g., "Completed in 45 seconds").

---

### User Story 2 - View Human-Readable Summary (Priority: P2)

As an operator, I want to see a human-readable summary of what a job accomplished, so that I can quickly understand its outcome without parsing raw data.

**Why this priority**: Summaries provide immediate context and value beyond raw metadata, making the detail view actionable for operators.

**Independent Test**: Can be tested by opening a completed job's detail view and verifying a meaningful summary is displayed.

**Acceptance Scenarios**:

1. **Given** a completed scan job with summary data, **When** viewing its detail, **Then** a summary is displayed (e.g., "Scanned 85 files in /movies, 3 changed since last scan").
2. **Given** a completed apply job, **When** viewing its detail, **Then** a summary describes actions taken (e.g., "Applied policy 'normalize-audio' to 5 files").
3. **Given** a job without summary data, **When** viewing its detail, **Then** the summary section shows "No summary available" rather than being empty or broken.

---

### User Story 3 - View Job Logs (Priority: P3)

As an operator, I want to view the log output from a job execution, so that I can troubleshoot issues and understand what happened during processing.

**Why this priority**: Logs are critical for troubleshooting but are secondary to basic job information. Most operators will only need logs when investigating problems.

**Independent Test**: Can be tested by opening a job that has log output and verifying logs are displayed in a scrollable area.

**Acceptance Scenarios**:

1. **Given** a job has associated log output, **When** viewing its detail, **Then** the logs are displayed in a scrollable, monospace-formatted area.
2. **Given** a job has no logs, **When** viewing its detail, **Then** the log section displays "No logs available" message.
3. **Given** a job has extensive log output (over 1000 lines), **When** viewing its detail, **Then** only recent logs are shown initially with ability to load more.

---

### User Story 4 - Navigate Back to Job List (Priority: P4)

As an operator, I want to easily navigate back to the job list from the detail view, so that I can continue reviewing other jobs.

**Why this priority**: Navigation is essential for usability but is straightforward functionality that builds on the detail view.

**Independent Test**: Can be tested by opening a job detail and verifying the back navigation returns to the job list with filters preserved.

**Acceptance Scenarios**:

1. **Given** a job detail view is open, **When** the operator clicks the back/close control, **Then** they return to the job list.
2. **Given** filters were applied before opening a job detail, **When** returning to the list, **Then** the same filters are still applied.

---

### Edge Cases

- What happens when job ID in URL does not exist? Display a "Job not found" error message with link back to job list.
- How does the system handle very long file paths? Truncate with ellipsis and show full path on hover or in a tooltip.
- What happens when job has null/empty fields? Display "—" or "N/A" placeholder rather than empty space or "null" text.
- How are concurrent updates handled (job completes while viewing)? The view shows data as of page load; operator can refresh to see updates.
- What happens with very long error messages? Display with word-wrap in a scrollable container, max height capped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a job detail view accessible by clicking a job row in the list or via direct URL `/jobs/{job_id}`.
- **FR-002**: System MUST display all job fields: ID (short form), type, status, priority, target path, policy name, creation time, start time, completion time, duration, progress, error message.
- **FR-003**: System MUST display timestamps in human-readable format with both absolute time and relative time.
- **FR-004**: System MUST display a human-readable summary when `summary_json` data is available.
- **FR-005**: System MUST generate appropriate summary text based on job type:
  - Scan jobs: file counts, changes detected
  - Apply jobs: policy name, files affected
  - Transcode jobs: input/output info
  - Move jobs: source and destination info
- **FR-006**: System MUST display job logs in a scrollable, monospace-formatted area.
- **FR-007**: System MUST handle missing logs gracefully with an appropriate placeholder message.
- **FR-008**: System MUST handle long logs with initial truncation and ability to load more (lazy loading or pagination).
- **FR-009**: System MUST provide navigation back to the job list.
- **FR-010**: System MUST preserve job list filter state when navigating back from detail view.
- **FR-011**: System MUST handle invalid/missing job IDs with a user-friendly error page.
- **FR-012**: System MUST display status with visual indicator (color/badge) matching the list view styling.

### Key Entities

- **Job**: Existing entity from jobs table. Key display attributes: id, job_type, status, file_path, policy_name, progress_percent, created_at, started_at, completed_at, error_message, summary_json.
- **Job Summary**: Derived from `summary_json` field. Contains job-type-specific outcome information (file counts, actions taken, etc.).
- **Job Logs**: Text content from job execution output. Stored in log files on disk, with file path referenced in the jobs table (e.g., `log_path` field). Files keyed by job ID (e.g., `~/.vpo/logs/{job_id}.log`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can view complete job details within 2 seconds of clicking a job row.
- **SC-002**: Job summaries provide actionable information in 90% of completed jobs (those with summary data).
- **SC-003**: Operators can identify failed jobs and their error cause within 5 seconds of opening the detail view.
- **SC-004**: Log viewing supports at least 10,000 lines without browser performance degradation.
- **SC-005**: Navigation between list and detail views maintains filter state 100% of the time.
- **SC-006**: All job fields are displayed correctly for 100% of jobs, regardless of completion status.

## Assumptions

- The `summary_json` field in the jobs table already stores structured job outcome data (per 008-operational-ux spec).
- Job logs are stored in files on disk (e.g., `~/.vpo/logs/{job_id}.log`), with a `log_path` field added to the jobs table to reference the file location. This approach avoids database bloat and supports streaming large logs.
- The existing Jobs dashboard (015-jobs-dashboard) list view is implemented and functional.
- The detail view will be implemented as a separate page route (`/jobs/{job_id}`) rather than a modal/drawer overlay, for better URL sharing and deep-linking.
- Default log truncation will show the most recent 500 lines initially, with lazy loading for older content.
- Log content is plain text; no special formatting or syntax highlighting is required for initial implementation.
