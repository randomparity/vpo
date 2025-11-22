# Feature Specification: Media Introspection & Track Modeling

**Feature Branch**: `003-media-introspection`
**Created**: 2025-11-21
**Status**: Draft
**Input**: User description: "Introspect actual video containers, parse tracks, and store in DB with enough detail for policy decisions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Track Enumeration (Priority: P1)

As a user, I want to see all tracks (video, audio, subtitle) for a media file so that I can understand the file structure before applying policies.

**Why this priority**: This is the core user-facing functionality. Without the ability to inspect tracks, users cannot make informed decisions about policy application. This delivers immediate value by providing visibility into media file contents.

**Independent Test**: Can be fully tested by running a single command against a media file and verifying the track information is displayed correctly.

**Acceptance Scenarios**:

1. **Given** a valid MKV file with multiple tracks, **When** the user runs the inspect command on the file, **Then** the system displays a formatted list showing all tracks with their ID, type, codec, language, title, and default flag.
2. **Given** a valid MP4 file with video and audio tracks, **When** the user runs the inspect command, **Then** the system displays track information in the same format as MKV files.
3. **Given** a media file path, **When** the user requests inspection, **Then** the output is human-readable and organized by track type (video, audio, subtitle).

---

### User Story 2 - Track Data Persistence (Priority: P2)

As a developer building policy rules, I want each track represented in the database so that policy rules can target specific tracks by their attributes.

**Why this priority**: Once users can see tracks, the system needs to persist this data for policy evaluation. This enables the policy engine to make decisions based on track metadata.

**Independent Test**: Can be tested by scanning a file, then querying the database to verify track records exist with correct metadata.

**Acceptance Scenarios**:

1. **Given** a media file has been scanned into the library, **When** the file contains multiple audio tracks, **Then** each audio track is stored as a separate record with its metadata (codec, language, channels, title, default flag).
2. **Given** a file with subtitle tracks, **When** the file is scanned, **Then** subtitle tracks are stored with their type (text vs. image-based), language, and title.
3. **Given** a track record in the database, **When** querying by file, **Then** each track has a unique identifier within that file and a reference back to the parent file.

---

### User Story 3 - Robust Media Parsing (Priority: P2)

As an engineer, I want the media introspection system to handle various media formats and edge cases gracefully so that the system remains reliable across diverse media libraries.

**Why this priority**: Real-world media libraries contain files with missing metadata, unusual formats, and corrupted containers. Robust parsing ensures the system works reliably in production.

**Independent Test**: Can be tested by running introspection against fixture files representing various edge cases and verifying appropriate handling.

**Acceptance Scenarios**:

1. **Given** a media file with missing language tags, **When** introspection runs, **Then** the system records the track with "und" (ISO 639-2 undefined) language code rather than failing.
2. **Given** a media file that cannot be parsed, **When** introspection runs, **Then** the system reports a clear error message indicating the file could not be processed.
3. **Given** a media file with uncommon codec identifiers, **When** introspection runs, **Then** the system preserves the original codec string for display and policy matching.

---

### User Story 4 - Test Fixtures for Development (Priority: P3)

As a developer, I want sample media metadata fixtures available so that tests can be written without requiring actual media files.

**Why this priority**: Test fixtures enable test-driven development and CI/CD pipelines without large binary files. This supports ongoing development quality.

**Independent Test**: Can be tested by verifying fixtures load correctly and represent expected track structures.

**Acceptance Scenarios**:

1. **Given** the test fixtures directory, **When** loading the "simple single-track" fixture, **Then** it represents a file with one video and one audio track.
2. **Given** the "multi-audio" fixture, **When** parsed by tests, **Then** it represents a file with one video track and multiple audio tracks with different languages.
3. **Given** the "subtitle-heavy" fixture, **When** parsed by tests, **Then** it represents a file with multiple subtitle tracks in various formats and languages.

---

### Edge Cases

- What happens when a file has no tracks at all? System should report "no tracks found" rather than error.
- What happens when track metadata contains non-UTF8 characters? System should sanitize or replace with safe representations.
- How does system handle tracks with duplicate stream indices? ffprobe guarantees unique stream indices per file; if duplicates occur (malformed container), log warning and skip duplicate.
- What happens when introspection tools are not installed on the system? System should provide a clear error message indicating which tools are missing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST parse video containers (MKV, MP4) and extract track-level metadata.
- **FR-002**: System MUST identify track type for each stream (video, audio, subtitle, attachment, other).
- **FR-003**: System MUST extract codec information for each track.
- **FR-004**: System MUST extract language tags when present, defaulting to "und" (ISO 639-2 undefined) when absent.
- **FR-005**: System MUST extract audio channel configuration (mono, stereo, 5.1, 7.1, etc.).
- **FR-005a**: System MUST extract video resolution (width x height) and frame rate for video tracks.
- **FR-006**: System MUST extract track titles when present.
- **FR-007**: System MUST identify default and forced flags for each track.
- **FR-008**: System MUST store track metadata in persistent storage with a reference to the parent file.
- **FR-008a**: System MUST perform smart merge on rescan: update matching tracks by index, add new tracks, and remove tracks no longer present in the file.
- **FR-009**: System MUST ensure track identifiers are unique within a file but allow the same ID across different files.
- **FR-010**: System MUST provide a command-line interface to inspect a single file and display track information.
- **FR-011**: System MUST handle files with missing or malformed metadata gracefully without crashing.
- **FR-012**: System MUST use ffprobe as the sole introspection backend; mkvmerge support is deferred to a future feature.

### Key Entities

- **Track**: Represents a single stream within a media container. Key attributes include: type (video/audio/subtitle/other), codec identifier, language code, channel configuration (audio only), resolution and frame rate (video only), title, default flag, forced flag, and track index within the file.
- **File**: Represents a media file in the library. Each file has zero or more tracks. Files are identified by their unique path and content hash.
- **IntrospectionResult**: Represents the outcome of analyzing a media file, containing the list of discovered tracks and any warnings or errors encountered during parsing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view complete track information for any supported media file within 5 seconds.
- **SC-002**: System correctly identifies 95% or more of track types and codecs in standard media files. Validation: Run introspection against the 3 test fixtures and verify all track types and codecs match expected values defined in fixture documentation.
- **SC-003**: Track data persists across application restarts with 100% data integrity.
- **SC-004**: System handles 100% of malformed files gracefully (no crashes, clear error messages).
- **SC-005**: At least 3 representative fixture files are available for automated testing.
- **SC-006**: Introspection command output is readable and understandable by non-technical users.

## Clarifications

### Session 2025-11-21

- Q: When both tools are available, which backend should be the primary parser? → A: ffprobe only (mkvmerge deferred to future feature)
- Q: Should video tracks include extended metadata beyond codec? → A: Standard (add resolution, frame rate)
- Q: How should track data be handled when rescanning an existing file? → A: Smart merge (update matching tracks, add new, remove missing)

## Assumptions

- The system requires ffprobe to be installed. The system should detect availability and report clearly when ffprobe is missing.
- Media files follow standard container formats (MKV, MP4). Non-standard or corrupted containers may have limited metadata extraction.
- Language codes follow ISO 639 standards where present in the media file.
- Track indices in the database reflect the order they appear in the container.
- The existing library database schema from feature 002 can be extended to accommodate track data.

## Out of Scope

- Transcoding or modifying media files
- Policy rule definition or evaluation (future feature)
- Thumbnail or preview generation
- Streaming or playback functionality
- Support for non-video containers (audio-only formats like FLAC, MP3)
- Attachment track parsing and storage (fonts, images embedded in containers) - track type identified but metadata not extracted
