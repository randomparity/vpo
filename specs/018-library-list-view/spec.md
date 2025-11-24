# Feature Specification: Library List View

**Feature Branch**: `018-library-list-view`
**Created**: 2025-11-23
**Status**: Draft
**Input**: User description: "Implement Library list view for scanned files - Add a Library page that displays all scanned video files in a tabular or grid format."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse Scanned Library (Priority: P1)

As a user, I want to browse my scanned video library in a table so that I can see what the system knows about my files at a glance.

**Why this priority**: This is the core value proposition - users need to see their scanned files to understand what content is in the library. Without the ability to view files, the entire feature is meaningless.

**Independent Test**: Can be fully tested by navigating to the Library page and verifying that scanned files are displayed in a table with all required columns, delivering immediate visibility into the video library.

**Acceptance Scenarios**:

1. **Given** the system has scanned video files, **When** a user navigates to the Library page, **Then** they see a table displaying files with columns: Filename, Title, Resolution, Audio Languages, Last Scanned, and Policy Profile.
2. **Given** files exist in the library, **When** the Library page loads, **Then** files are sorted by last scanned time in descending order (most recently scanned first).
3. **Given** a file has a long path, **When** viewing the Library page, **Then** the filename is displayed with the full path available via tooltip on hover.
4. **Given** a file has multiple audio tracks, **When** viewing the Library page, **Then** the primary audio language(s) are displayed (e.g., "eng, jpn").

---

### User Story 2 - Handle Empty Library State (Priority: P2)

As a user, I want to see a clear message when no files have been scanned so that I understand the system state and know what action to take.

**Why this priority**: Good UX requires handling edge cases gracefully. New users will encounter this state first, so a helpful empty state is critical for onboarding.

**Independent Test**: Can be tested by viewing the Library page before any scans have been performed.

**Acceptance Scenarios**:

1. **Given** no files have been scanned, **When** a user navigates to the Library page, **Then** they see a helpful empty state message indicating no files are available and suggesting they run a scan.
2. **Given** the library is empty, **When** viewing the empty state, **Then** the message includes guidance on how to scan files (e.g., reference to CLI or scan functionality).

---

### User Story 3 - Navigate Large Libraries with Pagination (Priority: P3)

As a user, I want to navigate through large file collections using pagination so that the page remains responsive and I can find files efficiently.

**Why this priority**: Users with large video libraries (hundreds or thousands of files) need pagination to maintain usability. Without it, page load times would degrade significantly.

**Independent Test**: Can be tested by populating the library with more files than the page limit and verifying pagination controls appear and function correctly.

**Acceptance Scenarios**:

1. **Given** more files exist than the page limit, **When** viewing the Library page, **Then** pagination controls are displayed showing current page and total pages.
2. **Given** pagination is displayed, **When** a user clicks "Next" or a page number, **Then** the table updates to show the corresponding page of results.
3. **Given** the user is on page 1, **When** viewing pagination controls, **Then** the "Previous" control is disabled.
4. **Given** the user is on the last page, **When** viewing pagination controls, **Then** the "Next" control is disabled.

---

### Edge Cases

- What happens when a file has no title metadata? Display "—" placeholder in the Title column (filename is already shown in the Filename column).
- What happens when a file has no audio tracks? Display "—" or "None" in the Audio Languages column.
- What happens when a file has no video track (audio-only file)? Display "—" in the Resolution column.
- How does the system handle files with scan errors? Display with a visual indicator (e.g., warning icon) and "Error" status, showing the error message on hover.
- What happens when resolution cannot be determined? Display "—" in the Resolution column.
- How are multiple audio languages displayed? Show primary languages comma-separated (e.g., "eng, jpn"), limiting to first 3 with "+N more" indicator if needed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a Library page accessible from the main navigation.
- **FR-002**: System MUST display scanned files in a table with columns: Filename, Title, Resolution, Audio Languages, Last Scanned, and Policy Profile.
- **FR-003**: System MUST sort files by last scanned time in descending order by default (most recent first).
- **FR-004**: System MUST display the short filename in the table with the full file path available via tooltip on hover.
- **FR-005**: System MUST display video resolution in human-readable format (e.g., "1080p", "4K", "720p") derived from the primary video track dimensions.
- **FR-006**: System MUST display primary audio language(s) extracted from audio tracks.
- **FR-007**: System MUST display the last scanned timestamp in a human-readable relative format (e.g., "2 hours ago", "3 days ago").
- **FR-008**: System MUST display the policy profile name if one has been applied to the file, or "—" if none.
- **FR-009**: System MUST display an appropriate empty state when no files have been scanned.
- **FR-010**: System MUST provide pagination controls when file count exceeds the page limit.
- **FR-011**: System MUST handle files with scan errors gracefully, displaying error status with visual indicator.
- **FR-012**: System MUST display "—" or appropriate placeholder for missing data (no title, no audio, no video resolution).
- **FR-013**: Table layout SHOULD be consistent with the existing Jobs dashboard where applicable (similar styling, column spacing, hover states).

### Key Entities

- **FileRecord**: Represents a scanned video file in the database. Key attributes: path, filename, directory, extension, size_bytes, modified_at, container_format, scanned_at, scan_status, scan_error.
- **TrackRecord**: Represents a media track within a file. Key attributes: track_type (video/audio/subtitle), codec, language, title, width, height (for video), channels, channel_layout (for audio).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view the Library page and identify file information within 3 seconds of page load.
- **SC-002**: The Library page correctly displays 100% of scanned files in the system with accurate metadata.
- **SC-003**: Pagination loads next/previous pages within 2 seconds for libraries up to 10,000 files.
- **SC-004**: Empty state is displayed appropriately when no files exist in the library.
- **SC-005**: Users can identify the resolution and audio languages of any file within 5 seconds of viewing the Library page.
- **SC-006**: Files with scan errors are clearly identifiable without requiring additional clicks or navigation.

## Assumptions

- The existing files and tracks database tables contain all required fields (path, filename, scanned_at, tracks with resolution and language data).
- A REST API endpoint (`GET /api/library`) will be available or will be created to provide file data with pagination support.
- Page size for pagination defaults to 50 files per page (consistent with Jobs dashboard).
- "Policy Profile" refers to any policy that has been applied to the file via the `apply` command; if no policy has been applied, this shows as "—".
- Resolution mapping uses standard conventions: 3840x2160 → "4K", 1920x1080 → "1080p", 1280x720 → "720p", etc.
- Audio languages use ISO 639-2 three-letter codes as stored in the database (e.g., "eng", "jpn", "fra").
- The Library page link will be added to the main navigation alongside existing pages (Dashboard, Jobs, Settings).
