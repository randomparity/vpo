# Feature Specification: File Detail View

**Feature Branch**: `020-file-detail-view`
**Created**: 2025-11-23
**Status**: Draft
**Input**: User description: "Implement file detail view with tracks and scan info - Add a file detail view that shows track-level metadata and scan-related information for a specific file."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View File Details from Library (Priority: P1)

A user browsing their video library wants to inspect a specific file to see detailed information about its tracks, container format, and scan history. From the Library view, they click on a file to open a detailed view showing all relevant metadata.

**Why this priority**: This is the core navigation path - users need to be able to reach file details from the library. Without this, the feature has no entry point.

**Independent Test**: Can be fully tested by scanning a directory with video files, navigating to Library, clicking a file, and verifying the detail page displays with correct file metadata.

**Acceptance Scenarios**:

1. **Given** a user is viewing the Library list, **When** they click on a file row, **Then** they navigate to `/library/{file_id}` showing the file detail view.
2. **Given** a user is on a file detail page, **When** they click the back navigation, **Then** they return to the Library list.

---

### User Story 2 - Inspect Track-Level Metadata (Priority: P1)

A user needs to understand the track composition of a video file - which audio tracks exist, their languages, codecs, and flags (default, forced, commentary). This helps them verify the file is properly configured or identify issues.

**Why this priority**: Track inspection is the primary value of the detail view. Users need this to understand their media files.

**Independent Test**: Can be tested by viewing a file with multiple tracks and verifying each track displays: index, type (video/audio/subtitle), codec, language, channels (for audio), resolution (for video), and flags.

**Acceptance Scenarios**:

1. **Given** a file with multiple video, audio, and subtitle tracks, **When** the user views the file detail, **Then** they see all tracks grouped by type with relevant metadata displayed.
2. **Given** an audio track with 5.1 surround sound, **When** viewing the track details, **Then** channels (6) and channel layout (5.1) are displayed.
3. **Given** a video track, **When** viewing the track details, **Then** resolution (width x height) and frame rate are displayed.
4. **Given** a track marked as default or forced, **When** viewing the track details, **Then** the appropriate flag badges are visible.

---

### User Story 3 - View File Information (Priority: P2)

A user wants to see basic file information including the full path, container format, file size, and modification date.

**Why this priority**: Important context information but less critical than track metadata for most use cases.

**Independent Test**: Can be tested by viewing any file and verifying file path, container format, size (human-readable), and dates are displayed.

**Acceptance Scenarios**:

1. **Given** a scanned file, **When** viewing the file detail, **Then** the user sees the full file path, filename, container format (e.g., "matroska"), and file size in human-readable format (e.g., "4.2 GB").
2. **Given** a file with scan error status, **When** viewing the file detail, **Then** the error message is prominently displayed.

---

### User Story 4 - Navigate to Related Jobs (Priority: P2)

A user wants to understand the history of operations performed on a file. They can see links to the scan job that discovered the file and any policy application jobs.

**Why this priority**: Provides valuable context about file history, but the core feature works without it.

**Independent Test**: Can be tested by viewing a file, clicking the scan job link, and verifying navigation to the correct job detail page.

**Acceptance Scenarios**:

1. **Given** a file that was scanned, **When** viewing the file detail, **Then** a link to the scan job (with job ID) is displayed.
2. **Given** a file with a policy application job, **When** viewing the file detail, **Then** a link to the apply job is displayed.
3. **Given** a file with no associated jobs, **When** viewing the file detail, **Then** job links are not displayed (graceful empty state).

> **Implementation Note**: The current database schema links files to scan jobs via `files.job_id`. Apply job linkage requires querying the `jobs` table by `file_path` where `job_type = 'apply'`. This is deferred to a future enhancement if apply jobs become common.

---

### User Story 5 - View Transcription Summary (Priority: P3)

A user with transcription results wants to see a summary of detected languages and transcription status for audio tracks.

**Why this priority**: Transcription is an optional feature that builds on top of the core track metadata.

**Independent Test**: Can be tested by viewing a file that has transcription results and verifying the summary shows detected language and confidence.

**Acceptance Scenarios**:

1. **Given** a file with transcription results for audio tracks, **When** viewing the file detail, **Then** transcription status is shown per audio track with detected language and confidence score.
2. **Given** a file without transcription results, **When** viewing the file detail, **Then** the transcription section is hidden or shows "No transcription data".

---

### Edge Cases

- What happens when the file ID doesn't exist? Display a 404 error page with helpful message.
- What happens when the file has many tracks (e.g., 20+)? Track sections should be collapsible to maintain readability.
- What happens when database is unavailable? Display service unavailable error (503).
- What happens when accessing via direct URL with invalid file ID format? Return 400 Bad Request.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a file detail page accessible at `/library/{file_id}` route.
- **FR-002**: System MUST display file metadata including path, filename, container format, size, and modified date.
- **FR-003**: System MUST display all tracks grouped by type (video, audio, subtitle, other).
- **FR-004**: For video tracks, system MUST display codec, resolution (width x height), and frame rate.
- **FR-005**: For audio tracks, system MUST display codec, language, channels, channel layout, title, and flags (default/forced).
- **FR-006**: For subtitle tracks, system MUST display codec, language, title, and flags (default/forced).
- **FR-007**: System MUST provide navigation back to the Library list.
- **FR-008**: System MUST display scan job link when available (linking to `/jobs/{job_id}`).
- **FR-009**: System MUST provide a JSON API endpoint at `/api/library/{file_id}` for file detail data.
- **FR-010**: System MUST handle non-existent file IDs with appropriate error responses (404 for HTML, JSON error for API).
- **FR-011**: System MUST validate file ID format and return 400 for invalid formats.
- **FR-012**: System MUST display transcription results when available for audio tracks.
- **FR-013**: Track sections MUST be collapsible when the file has many tracks (threshold: 5+ total tracks).

### Key Entities

- **File**: Represents a scanned video file with path, container format, size, dates, and scan status.
- **Track**: Media stream within a file (video/audio/subtitle/other) with type-specific metadata.
- **Job**: Background operation (scan/apply) linked to files via file_id or job_id.
- **TranscriptionResult**: Language detection result linked to audio tracks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can navigate from Library to file detail and back within 2 clicks.
- **SC-002**: File detail page displays all track metadata in under 2 seconds for files with up to 50 tracks.
- **SC-003**: Users can identify track types, languages, and flags at a glance without scrolling horizontally.
- **SC-004**: Error states (file not found, invalid ID) display clear, user-friendly messages.
- **SC-005**: 95% of file detail page loads complete successfully without errors.

## Assumptions

- File IDs are integer database primary keys (consistent with existing library API).
- The existing database schema provides all required track metadata fields.
- Job linkage uses the existing `job_id` foreign key on files table.
- Users access the application via modern web browsers with JavaScript enabled.
- Transcription results may not exist for all audio tracks (optional feature).
- Container format is available from the ffprobe introspection stored in database.
