# Feature Specification: Transcription Detail View

**Feature Branch**: `022-transcription-detail`
**Created**: 2025-11-24
**Status**: Draft
**Input**: User description: "Implement transcription detail view per audio track - provide a detailed transcription view for each audio track, including language detection results and the text itself."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Transcription Detail for Audio Track (Priority: P1)

As a user, I want to view the detailed transcription results for a specific audio track so that I can verify language detection accuracy and review the transcribed text.

**Why this priority**: This is the core functionality - displaying complete transcription data is essential for verification and debugging of language detection.

**Independent Test**: Can be tested by navigating to a transcription detail page and verifying all transcription data fields are displayed including detected language, confidence score, and transcript text.

**Acceptance Scenarios**:

1. **Given** I am on the File Detail view for a file with transcribed audio tracks, **When** I click on a transcription entry, **Then** I am navigated to the Transcription Detail view showing complete information for that audio track.

2. **Given** I am on the Transcriptions List view, **When** I click on a transcription entry, **Then** I am navigated to the Transcription Detail view for that specific track.

3. **Given** I am viewing a Transcription Detail page, **When** the page loads, **Then** I see the track metadata (codec, language tag, commentary flag), detected language with confidence score, and the transcription text.

---

### User Story 2 - Read Long Transcription Content (Priority: P2)

As a user, I want to navigate through long transcription text easily so that I can review the full content without overwhelming the interface.

**Why this priority**: Transcription samples can be lengthy; good content organization improves usability but requires the core display to work first.

**Independent Test**: Can be tested by viewing a transcription with more than 500 characters and verifying the text is organized into readable chunks or segments.

**Acceptance Scenarios**:

1. **Given** a transcription has more than 500 characters of text, **When** I view the Transcription Detail page, **Then** the text is organized into readable chunks with clear visual separation.

2. **Given** a transcription is truncated or partially available, **When** I view the Transcription Detail page, **Then** I see a clear indicator that the content is incomplete, along with available text.

---

### User Story 3 - Understand Commentary Detection (Priority: P3)

As a user, I want to see which keywords triggered commentary detection so that I can understand why a track was classified as commentary.

**Why this priority**: This is an advanced diagnostic feature that helps users understand the heuristic classification; useful but not essential for basic functionality.

**Independent Test**: Can be tested by viewing a commentary-classified track and verifying commentary keywords are highlighted or listed.

**Acceptance Scenarios**:

1. **Given** a transcription is classified as "commentary", **When** I view the Transcription Detail page, **Then** I see the track type displayed as "Commentary" with visual distinction.

2. **Given** a track was classified as commentary based on metadata (title contains commentary keywords), **When** I view the Transcription Detail page, **Then** I see an indication that the classification was based on track title.

3. **Given** a track was classified as commentary based on transcript patterns, **When** I view the Transcription Detail page, **Then** I see matched keywords or patterns highlighted in the transcription text.

---

### Edge Cases

- What happens when the transcription text is empty or null? Display "No transcription text available" with an explanation that only a sample may have been captured.
- How does the system handle transcription results with very low confidence (< 0.3)? Display a warning indicator that the detection may be unreliable.
- What happens when the referenced track no longer exists? Display an error state indicating the track data is unavailable.
- How does the system handle extremely long transcription text (> 10,000 characters)? Truncate display at 10,000 characters with a visual indicator that content is truncated. Full text is available via the JSON API.
- What happens when the user navigates directly to an invalid transcription ID? Display a 404-style error page with navigation back to the Transcriptions list.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a dedicated detail page for each transcription result, accessible via unique URL.
- **FR-002**: System MUST display track metadata on the detail page: track index, codec, original language tag, and commentary flag (is this track marked as commentary).
- **FR-003**: System MUST display detection results: detected language code, confidence score (numeric and categorical: high/medium/low), and track classification (main/commentary/alternate).
- **FR-004**: System MUST display the transcription text sample when available.
- **FR-005**: System MUST organize long transcription text (> 500 characters) into readable chunks or segments with clear visual separation.
- **FR-006**: System MUST indicate when transcription text is truncated, partially available, or not captured.
- **FR-007**: System MUST provide navigation links back to the parent file detail view and the Transcriptions list.
- **FR-008**: System MUST display commentary classification reasoning when the track is classified as commentary (whether from metadata or transcript patterns).
- **FR-009**: System SHOULD highlight matching commentary keywords in the transcription text when track is classified as commentary via transcript analysis.
- **FR-010**: System MUST display an appropriate error state when the transcription ID is invalid or the track no longer exists.
- **FR-011**: System MUST display plugin name that performed the transcription for diagnostic purposes.

### Key Entities

- **Transcription Result**: A language detection and transcription analysis result for a single audio track, containing detected language, confidence score, track classification, and transcript sample.
- **Track**: The audio track being analyzed, with properties like codec, language tag, title, and default/forced flags.
- **Commentary Classification**: The determination of whether a track is main audio, commentary, or alternate content, based on metadata keywords or transcript pattern analysis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can navigate from File Detail or Transcriptions list to the Transcription Detail page in one click.
- **SC-002**: Users can view complete transcription information (language, confidence, text, classification) for any transcribed audio track within 2 seconds.
- **SC-003**: Users can identify low-confidence detections at a glance through clear visual indicators.
- **SC-004**: Users can understand why a track was classified as commentary through visible reasoning indicators.
- **SC-005**: Long transcription text (> 500 characters) is readable without horizontal scrolling or text overflow.
- **SC-006**: 100% of navigation paths (File Detail, Transcriptions list, direct URL) successfully display the correct transcription data.

## Assumptions

- The existing `transcription_results` table contains `transcript_sample` which holds the transcription text (may be a sample, not full transcription).
- Commentary keywords are defined in `COMMENTARY_KEYWORDS` list in `transcription/models.py`.
- Commentary transcript patterns are defined in `COMMENTARY_TRANSCRIPT_PATTERNS` in `transcription/models.py`.
- The File Detail view (020-file-detail-view) already displays transcription summary data that can link to this detail view.
- The Transcriptions List view (021-transcriptions-list) is implemented and can link to this detail view.
- Visual patterns will follow those established in existing detail views (File Detail, Job Detail) for consistency.
- The detail view will follow the same URL pattern as other detail views (e.g., `/transcriptions/{id}`).
