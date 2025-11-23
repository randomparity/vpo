# Feature Specification: Jobs Dashboard List View

**Feature Branch**: `015-jobs-dashboard`
**Created**: 2025-11-23
**Status**: Draft
**Input**: User description: "Implement Jobs dashboard list view - Create a Jobs dashboard page showing all recent jobs with key metadata and filtering options."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Recent Jobs (Priority: P1)

As an operator, I want to see a dashboard showing all recent jobs so that I can quickly understand what the system is doing and identify any issues.

**Why this priority**: This is the core value proposition of the feature - without the ability to view jobs, no other functionality is meaningful. Operators need immediate visibility into system activity.

**Independent Test**: Can be fully tested by navigating to the Jobs page and verifying that jobs are displayed in a table with all required columns, delivering immediate visibility into system activity.

**Acceptance Scenarios**:

1. **Given** the system has executed jobs, **When** an operator navigates to the Jobs page, **Then** they see a table displaying jobs with columns: Job ID, Type, Status, Start time, End time/duration, and Target.
2. **Given** jobs exist in the system, **When** the Jobs page loads, **Then** jobs are sorted by start time in descending order (most recent first).
3. **Given** a job is currently running, **When** viewing the Jobs page, **Then** the job displays with status "running" and shows elapsed duration instead of end time.

---

### User Story 2 - Filter Jobs by Status (Priority: P2)

As an operator, I want to filter jobs by their status so that I can quickly find failed or queued jobs that need attention.

**Why this priority**: Filtering by status is the most common filtering need - operators typically want to see failed jobs first or check what's currently running.

**Independent Test**: Can be tested by selecting a status filter and verifying only jobs with that status are displayed.

**Acceptance Scenarios**:

1. **Given** jobs exist with various statuses (queued, running, completed, failed, cancelled), **When** an operator selects "failed" from the status filter, **Then** only failed jobs are displayed.
2. **Given** a status filter is applied, **When** the operator clears the filter, **Then** all jobs are displayed again.
3. **Given** no jobs match the selected status filter, **When** the filter is applied, **Then** an appropriate empty state message is displayed.

---

### User Story 3 - Filter Jobs by Type (Priority: P3)

As an operator, I want to filter jobs by type so that I can focus on specific kinds of operations (scans, transcodes, etc.).

**Why this priority**: Type filtering helps operators understand patterns by operation type and is a natural complement to status filtering.

**Independent Test**: Can be tested by selecting a job type filter and verifying only jobs of that type are displayed.

**Acceptance Scenarios**:

1. **Given** jobs exist of various types (scan, apply, transcode, move), **When** an operator selects "transcode" from the type filter, **Then** only transcode jobs are displayed.
2. **Given** type and status filters are both available, **When** an operator applies both filters, **Then** jobs matching both criteria are displayed.

---

### User Story 4 - Filter Jobs by Time Range (Priority: P4)

As an operator, I want to filter jobs by time range so that I can focus on recent activity or investigate historical issues.

**Why this priority**: Time-based filtering is useful for narrowing down large job lists but is less critical than status/type filtering for day-to-day operations.

**Independent Test**: Can be tested by selecting a time range filter and verifying only jobs within that range are displayed.

**Acceptance Scenarios**:

1. **Given** jobs exist spanning multiple days, **When** an operator selects "last 24 hours", **Then** only jobs started within the last 24 hours are displayed.
2. **Given** jobs exist spanning multiple weeks, **When** an operator selects "last 7 days", **Then** only jobs started within the last 7 days are displayed.

---

### User Story 5 - Empty State Handling (Priority: P5)

As an operator, I want to see a clear message when no jobs exist so that I understand the system state rather than seeing a broken interface.

**Why this priority**: Good UX requires handling edge cases gracefully, though this is less critical than core functionality.

**Independent Test**: Can be tested by viewing the Jobs page when no jobs have been executed.

**Acceptance Scenarios**:

1. **Given** no jobs have ever been executed, **When** an operator navigates to the Jobs page, **Then** they see a helpful empty state message explaining that no jobs are available.
2. **Given** filters are applied that match no jobs, **When** viewing the Jobs page, **Then** the empty state indicates that no jobs match the current filters.

---

### Edge Cases

- What happens when a job has no target (e.g., system maintenance job)? Display "N/A" or similar placeholder.
- How does the system handle very long file paths in the Target column? Truncate with ellipsis and show full path on hover/click.
- What happens when job count exceeds reasonable display limits? Implement pagination (assumption: default page size of 50 jobs).
- How are jobs with unknown/corrupt status displayed? Display with a distinct visual indicator and "unknown" status.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a Jobs page accessible from the main navigation.
- **FR-002**: System MUST display jobs in a table/grid with columns: Job ID, Type, Status, Start time, End time (or duration), and Target.
- **FR-003**: System MUST sort jobs by start time in descending order by default.
- **FR-004**: System MUST support status values: queued, running, completed, failed, cancelled.
- **FR-005**: System MUST support job type values: scan, apply, transcode, move (and any other types in the existing schema).
- **FR-006**: System MUST provide a filter control for filtering by job status.
- **FR-007**: System MUST provide a filter control for filtering by job type.
- **FR-008**: System MUST provide a filter control for filtering by time range with at least "last 24 hours" and "last 7 days" options.
- **FR-009**: System MUST allow multiple filters to be combined (AND logic).
- **FR-010**: System MUST display an appropriate empty state when no jobs exist.
- **FR-011**: System MUST display an appropriate empty state when filters match no jobs.
- **FR-012**: System MUST display running jobs with elapsed duration instead of end time.
- **FR-013**: System MUST handle long target paths gracefully (truncation with full path available).
- **FR-014**: System MUST paginate results when job count exceeds the page limit.

### Key Entities

- **Job**: Represents a unit of work executed by the system. Key attributes: unique identifier, type (scan/apply/transcode/move), status (queued/running/completed/failed/cancelled), start timestamp, end timestamp (nullable for running/queued jobs), target (file path, directory, or profile name).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can view the Jobs dashboard and identify job status within 3 seconds of page load.
- **SC-002**: Operators can filter jobs by status, type, or time range within 2 clicks/interactions.
- **SC-003**: The Jobs page correctly displays 100% of jobs in the system with accurate metadata.
- **SC-004**: Empty states are displayed appropriately when no jobs or no matching jobs exist.
- **SC-005**: All filter combinations work correctly and display matching results.

## Assumptions

- Backend API endpoints for listing jobs with filtering capabilities will be available (noted as a dependency in the original requirement).
- Live/real-time updates are out of scope for this feature (to be addressed in a separate issue).
- The existing jobs table/schema in the database contains all required fields (type, status, timestamps, target).
- Page size for pagination defaults to 50 jobs per page.
- Time range filters use the job's start time for comparison.
- "Duration" for running jobs displays elapsed time from start until now.
