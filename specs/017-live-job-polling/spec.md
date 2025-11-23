# Feature Specification: Live Job Status Updates (Polling)

**Feature Branch**: `017-live-job-polling`
**Created**: 2025-11-23
**Status**: Draft
**Input**: User description: "Add live job status updates (polling) - Enhance the Jobs dashboard and Job detail view to update job statuses automatically using polling."

## Clarifications

### Session 2025-11-23

- Q: What backoff parameters for retry logic? → A: Moderate: 10s initial delay, 2 min max, double after 3 consecutive failures

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Status Updates on Jobs Dashboard (Priority: P1)

As an operator, I want job statuses to update automatically on the Jobs dashboard so that I can see real-time progress without manually refreshing the page.

**Why this priority**: This is the core value proposition - operators need to monitor running jobs without constant manual intervention. Automatic updates provide immediate awareness of job state changes and completion.

**Independent Test**: Can be fully tested by starting a job, opening the Jobs dashboard, and observing status changes (queued → running → completed) without any manual page refresh.

**Acceptance Scenarios**:

1. **Given** the Jobs dashboard is open and a job is running, **When** the job completes, **Then** the dashboard automatically updates to show "completed" status within the polling interval.
2. **Given** the Jobs dashboard is open, **When** a new job is created by another process, **Then** the new job appears in the list within the polling interval.
3. **Given** jobs are displayed on the dashboard, **When** automatic refresh occurs, **Then** existing filter and sort states are preserved.
4. **Given** the Jobs dashboard is open, **When** polling occurs, **Then** the update is seamless without full page reload or visible flickering.

---

### User Story 2 - Automatic Status Updates on Job Detail View (Priority: P2)

As an operator, I want the Job detail view to update automatically so that I can monitor a specific job's progress without manual refresh.

**Why this priority**: Once an operator drills into a specific job, they need to see that job's progress update in real-time. This builds on the dashboard polling with more detailed information.

**Independent Test**: Can be tested by opening a running job's detail view and observing progress percentage and status update without manual refresh.

**Acceptance Scenarios**:

1. **Given** a Job detail view is open for a running job, **When** the job's progress changes, **Then** the progress indicator updates within the polling interval.
2. **Given** a Job detail view is open for a running job, **When** the job completes or fails, **Then** the status, completion time, and duration update automatically.
3. **Given** a Job detail view is open, **When** new log entries are written, **Then** the log display updates to show recent entries.

---

### User Story 3 - Progress Information for Running Jobs (Priority: P3)

As an operator, I want to see detailed progress information for running jobs so that I understand how far along each job is.

**Why this priority**: Progress information transforms a binary "running/not running" indicator into actionable insight about job completion timeline.

**Independent Test**: Can be tested by starting a scan job on a directory with multiple files and verifying progress percentage and processed file count update.

**Acceptance Scenarios**:

1. **Given** a running job with progress tracking, **When** viewing the Jobs dashboard, **Then** the job row displays progress percentage (e.g., "45%").
2. **Given** a running job with file-level progress, **When** viewing the Job detail view, **Then** processed file count is displayed (e.g., "Processing 25 of 100 files").
3. **Given** a job type that doesn't support progress tracking, **When** viewing the job, **Then** an indeterminate progress indicator is shown instead of percentage.

---

### User Story 4 - Polling Efficiency and Tab Visibility (Priority: P4)

As an operator, I want polling to stop or slow down when I switch tabs so that system resources aren't wasted polling an invisible page.

**Why this priority**: Resource efficiency improves user experience by not consuming bandwidth and server resources when the page isn't visible.

**Independent Test**: Can be tested by opening the Jobs dashboard, switching to another browser tab, waiting longer than the polling interval, and verifying reduced or no network requests.

**Acceptance Scenarios**:

1. **Given** the Jobs page is visible, **When** the operator switches to another browser tab, **Then** polling pauses or reduces frequency.
2. **Given** polling was paused due to tab visibility, **When** the operator returns to the Jobs tab, **Then** polling resumes immediately with a fresh data fetch.
3. **Given** the browser/tab is closed, **When** the page unloads, **Then** all polling timers are cleaned up properly.

---

### User Story 5 - Configurable Polling Interval (Priority: P5)

As an operator, I want to configure the polling interval so that I can balance responsiveness with server load based on my environment.

**Why this priority**: Different deployments have different needs - a local development environment may want fast updates while a shared server may prefer less frequent polling.

**Independent Test**: Can be tested by changing the polling interval configuration and verifying the polling frequency changes accordingly.

**Acceptance Scenarios**:

1. **Given** the default polling interval is set, **When** the Jobs page loads, **Then** polling occurs at the default interval (5 seconds).
2. **Given** the polling interval is configured to a custom value, **When** the Jobs page loads, **Then** polling occurs at the configured interval.
3. **Given** a valid polling interval range exists, **When** an operator attempts to set an invalid value, **Then** the system uses the default or nearest valid value.

---

### Edge Cases

- What happens when a polling request fails (network error)? Display a subtle error indicator and retry on next interval; don't disrupt user workflow.
- How does the system handle rapid status changes between polls? Display the latest state; intermediate states are not guaranteed to be shown.
- What happens when many jobs change simultaneously? Update all changed jobs in a single UI refresh.
- How does polling behave when the server is unavailable? Show a connection status indicator; exponential backoff for retries.
- What if the job is deleted while viewing its detail page? Display a "Job no longer exists" message and offer navigation back to the list.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically refresh job data on the Jobs dashboard at a configurable interval.
- **FR-002**: System MUST automatically refresh job data on the Job detail view at a configurable interval.
- **FR-003**: System MUST support a polling interval range of 2-60 seconds, with a default of 5 seconds.
- **FR-004**: System MUST preserve current filter, sort, and pagination state when polling updates occur.
- **FR-005**: System MUST update the UI without full page reload (partial/incremental update).
- **FR-006**: System MUST display progress percentage for jobs that support progress tracking.
- **FR-007**: System MUST display processed item count (e.g., "25 of 100 files") in the detail view for jobs with item-level progress.
- **FR-008**: System MUST show an indeterminate progress indicator for jobs without progress data.
- **FR-009**: System MUST pause or reduce polling frequency when the page/tab is not visible.
- **FR-010**: System MUST resume polling immediately when the page/tab becomes visible again.
- **FR-011**: System MUST handle polling errors gracefully without disrupting user experience.
- **FR-012**: System MUST implement retry logic with exponential backoff: 10-second initial delay, doubling after 3 consecutive failures, capped at 2 minutes maximum.
- **FR-013**: System MUST clean up polling resources when navigating away from polling-enabled pages.
- **FR-014**: System MUST update log display on the detail view during polling (if new log content exists).
- **FR-015**: System MUST provide a visual indicator when data is being refreshed (subtle loading state).

### Key Entities

- **Polling Configuration**: Settings controlling automatic refresh behavior. Key attributes: interval (in seconds), enabled state, visibility-aware behavior.
- **Job Progress**: Extension to existing Job entity for progress tracking. Key attributes: progress percentage (0-100, nullable), processed item count, total item count.
- **Refresh State**: Client-side state tracking polling status. Key attributes: last refresh timestamp, next refresh scheduled, connection status, error count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Job status changes are reflected on screen within the configured polling interval plus 1 second render time.
- **SC-002**: Operators can monitor running jobs hands-free, with 100% of status changes eventually displayed.
- **SC-003**: Polling pauses within 2 seconds of tab becoming hidden, reducing unnecessary network requests.
- **SC-004**: System handles network interruptions gracefully, with automatic recovery when connection is restored.
- **SC-005**: UI updates are seamless with no visible page flicker or scroll position reset.
- **SC-006**: Progress information (when available) updates smoothly, giving operators clear indication of job completion percentage.

## Assumptions

- The Jobs dashboard (015-jobs-dashboard) and Job detail view (016-job-detail-view) are implemented and functional.
- Backend API endpoints already exist for fetching job lists and job details; no new endpoints are required, only client-side polling logic.
- Progress tracking fields (`progress_percent`, `processed_count`, `total_count`) exist in the jobs table or can be derived from `summary_json`.
- The Page Visibility API is available in target browsers for detecting tab visibility.
- Future enhancement to WebSocket/SSE for push updates is out of scope; polling is the chosen approach for this feature.
- Polling interval configuration will be managed via the daemon configuration (not per-user or UI-configurable initially).
- Log content polling on the detail view may be heavier; consider longer intervals or on-demand refresh for logs specifically.
