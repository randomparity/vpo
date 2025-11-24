# Feature Specification: Transcriptions Overview List

**Feature Branch**: `021-transcriptions-list`
**Created**: 2025-11-24
**Status**: Draft
**Input**: User description: "Create a Transcriptions page that shows which files have transcription data and high-level language/confidence info."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Files with Transcription Data (Priority: P1)

As a user, I want to see a list of files that have transcription results so that I can confirm language detection ran on my library.

**Why this priority**: This is the core functionality - displaying the transcriptions list is the foundation that all other features depend on.

**Independent Test**: Can be tested by navigating to the Transcriptions page and verifying files with transcription data appear in a table with relevant columns.

**Acceptance Scenarios**:

1. **Given** a library with files that have transcription results, **When** I navigate to the Transcriptions page, **Then** I see a table listing files with transcription data including filename, transcription indicator, detected languages, and confidence levels.

2. **Given** a library with no transcription results, **When** I navigate to the Transcriptions page, **Then** I see an empty state message indicating no transcription data is available.

3. **Given** a file with multiple audio tracks that have transcription results, **When** I view that file in the list, **Then** I see aggregated language information for all tracks.

---

### User Story 2 - Toggle Filter to Show All Files (Priority: P2)

As a user, I want to optionally view all files (including those without transcription data) so that I can see which files still need analysis.

**Why this priority**: The default view shows only transcribed files; this filter provides access to the full library when needed.

**Independent Test**: Can be tested by toggling the "show all files" filter and verifying the list expands to include non-transcribed files.

**Acceptance Scenarios**:

1. **Given** I am on the Transcriptions page (default: showing only transcribed files), **When** I enable the "show all files" toggle, **Then** all files are displayed including those without transcription data.

2. **Given** the "show all files" toggle is enabled, **When** I disable the toggle, **Then** the view returns to showing only files with transcription results.

---

### User Story 3 - Navigate to File Detail (Priority: P3)

As a user, I want to click on a file in the Transcriptions list to see detailed information so that I can examine specific transcription results.

**Why this priority**: Navigation to details enables deeper investigation but requires the core list to be functional first.

**Independent Test**: Can be tested by clicking a file row and verifying navigation to the file detail view.

**Acceptance Scenarios**:

1. **Given** I am viewing the Transcriptions list, **When** I click on a file entry, **Then** I am navigated to the File Detail view for that file.

2. **Given** I navigated from the Transcriptions page to File Detail, **When** I use browser back navigation, **Then** I return to the Transcriptions page with my previous view state preserved.

---

### Edge Cases

- What happens when a file has transcription data but the file itself is no longer accessible (deleted/moved)? Display with an error indicator.
- How does the system handle files with audio tracks that have no transcription results yet? Show "Not analyzed" or similar indicator.
- What happens when confidence scores are at boundary values (0.0, 1.0)? Display appropriately without visual artifacts.
- How does the system handle a very large number of files with transcription data? Use pagination to maintain performance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a table of files with columns: filename/path, transcription indicator, detected languages, and confidence indicators.
- **FR-002**: System MUST show a clear visual indicator (icon or badge) for files that have transcription data versus those that do not.
- **FR-003**: System MUST display all detected languages for a file when multiple audio tracks have transcription results.
- **FR-004**: System MUST show confidence levels using a clear format (high/medium/low categories mapped from numeric scores).
- **FR-005**: System MUST default to showing only files with transcription results, with a toggle to show all files.
- **FR-006**: Users MUST be able to click a file row to navigate to the file detail view.
- **FR-007**: System MUST paginate results when the file list exceeds a reasonable page size (consistent with Library view).
- **FR-008**: System MUST show an appropriate empty state when no files have transcription data.
- **FR-009**: System MUST display confidence scores with appropriate precision (e.g., percentage or categorical: high >= 0.8, medium >= 0.5, low < 0.5).

### Key Entities

- **File**: A media file in the library, may have zero or more audio tracks with transcription results.
- **Transcription Result**: Language detection result for a single audio track, containing detected language code, confidence score (0.0-1.0), and track classification (main/commentary/alternate).
- **Confidence Level**: Categorical representation of numeric confidence score for display purposes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view the Transcriptions page and see all files with transcription data within 2 seconds for libraries up to 10,000 files.
- **SC-002**: Users can identify which files have transcription data at a glance using clear visual indicators.
- **SC-003**: Users can filter to show only files with transcription results with a single interaction.
- **SC-004**: Users can navigate from the Transcriptions list to a file's detail view with one click.
- **SC-005**: The page displays confidence information in a user-friendly format that non-technical users can understand.
- **SC-006**: Page remains responsive and usable when displaying 100+ files through pagination.

## Clarifications

### Session 2025-11-24

- Q: What should be the default view when a user first navigates to the Transcriptions page? → A: Show only files with transcription results (filtered by default).

## Assumptions

- The existing transcription results table (`transcription_results`) contains the necessary data to display.
- Confidence scores are stored as floating-point values between 0.0 and 1.0.
- The existing File Detail view (020-file-detail-view) already shows transcription data for individual files.
- The Transcriptions page will follow the same visual patterns established in the Library List view (018-library-list-view).
- Pagination defaults will match those used in the Library view for consistency.
