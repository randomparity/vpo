# Feature Specification: Library Filters and Search

**Feature Branch**: `019-library-filters-search`
**Created**: 2025-11-23
**Status**: Draft
**Input**: User description: "Add metadata filters and search to Library"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Text Search for Files (Priority: P1)

A user with a large library (hundreds or thousands of files) wants to quickly find a specific file by typing part of its filename or title. The user types in a search box and sees results filter in real-time as they type.

**Why this priority**: Text search is the fastest way to find a specific file when you know what you're looking for. It provides immediate value for the most common use case: "I know the movie name, where is it?"

**Independent Test**: Can be fully tested by typing a search term and verifying matching files appear. Delivers standalone value for finding files by name.

**Acceptance Scenarios**:

1. **Given** a library with 500 files, **When** the user types "avatar" in the search box, **Then** only files with "avatar" in filename or title are displayed within 500ms of typing pause
2. **Given** a search box with text "matrix", **When** the user clears the search box, **Then** all files are shown again (respecting other active filters)
3. **Given** a search term that matches no files, **When** results load, **Then** an empty state message indicates "No matching files" with suggestion to adjust filters

---

### User Story 2 - Filter by Resolution (Priority: P2)

A user wants to view only files of a specific resolution (e.g., only 4K content) to assess their high-definition library or to find files that need quality upgrades.

**Why this priority**: Resolution is a primary metadata attribute visible in the current table. Users organizing media collections frequently filter by quality tier.

**Independent Test**: Can be tested by selecting "4K" from resolution dropdown and verifying only 4K files appear in the table.

**Acceptance Scenarios**:

1. **Given** a library with mixed resolutions, **When** the user selects "1080p" from the resolution filter, **Then** only files with 1080p resolution are displayed
2. **Given** a resolution filter is active, **When** the user selects "All resolutions", **Then** the filter is cleared and all files are shown

---

### User Story 3 - Filter by Audio Language (Priority: P2)

A user wants to find files that contain specific audio tracks (e.g., Japanese audio for anime, or files with English audio for accessibility).

**Why this priority**: Audio language is crucial for multilingual libraries. Users often want to verify language availability or find content in specific languages.

**Independent Test**: Can be tested by selecting language(s) and verifying only files with matching audio tracks appear.

**Acceptance Scenarios**:

1. **Given** a library with files in multiple languages, **When** the user selects "jpn" from the audio language filter, **Then** only files containing Japanese audio tracks are displayed
2. **Given** the audio language filter, **When** the user selects multiple languages ("eng" and "jpn"), **Then** files containing either language are displayed (OR logic)

---

### User Story 4 - Filter by Subtitle Presence (Priority: P3)

A user wants to identify files that have subtitles versus those that don't, either to find accessible content or to identify files needing subtitle tracks added.

**Why this priority**: Subtitle presence is a binary filter that's easy to understand and useful for accessibility planning.

**Independent Test**: Can be tested by selecting "Has subtitles" and verifying only files with subtitle tracks appear.

**Acceptance Scenarios**:

1. **Given** a mixed library, **When** the user selects "Has subtitles", **Then** only files with at least one subtitle track are displayed
2. **Given** a mixed library, **When** the user selects "No subtitles", **Then** only files without subtitle tracks are displayed

---

### User Story 5 - Clear All Filters (Priority: P3)

A user has applied multiple filters and wants to quickly reset to see the full library without manually clearing each filter.

**Why this priority**: Essential UX for any multi-filter interface. Prevents user frustration when exploring with various filter combinations.

**Independent Test**: Can be tested by applying multiple filters, clicking "Clear filters", and verifying all filters reset and full library displays.

**Acceptance Scenarios**:

1. **Given** active filters (search text, resolution, audio language), **When** the user clicks "Clear filters", **Then** all filters are cleared and the full library is displayed
2. **Given** no active filters, **When** viewing the filter area, **Then** the "Clear filters" action is not displayed or is disabled

---

### User Story 6 - Active Filter Visibility (Priority: P3)

A user wants to see at a glance which filters are currently applied so they understand why they're seeing a subset of files.

**Why this priority**: Critical for usability when multiple filters can be combined. Users must understand current filter state.

**Independent Test**: Can be tested by applying filters and verifying visual indicators show active filter values.

**Acceptance Scenarios**:

1. **Given** a resolution filter set to "4K", **When** viewing the library, **Then** the active filter is clearly visible (e.g., badge, highlighted dropdown, or filter chip)
2. **Given** multiple active filters, **When** viewing the filter area, **Then** all active filters are displayed with their current values

---

### Edge Cases

- What happens when filters return zero results? Display empty state with helpful message
- How does search handle special characters? Search matches literal characters in filename/title
- What happens with very long filter combinations in URL? Query parameters are encoded; reasonable length limits apply
- How does pagination interact with filters? Pagination resets to page 1 when any filter changes
- What if a file has no audio tracks? Shows as "no audio" in the filter results

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a text search input that filters files by filename and title
- **FR-002**: System MUST debounce search input (300-500ms delay) to avoid excessive API calls
- **FR-003**: System MUST provide a resolution filter dropdown with options: All, 4K, 1080p, 720p, 480p, Other
- **FR-004**: System MUST provide an audio language filter allowing selection of available languages
- **FR-005**: System MUST provide a subtitle presence filter with options: All, Has subtitles, No subtitles
- **FR-006**: System MUST display active filters visually so users know which filters are applied
- **FR-007**: System MUST provide a "Clear filters" action that resets all filters at once
- **FR-008**: System MUST update table results without full-page reload when filters change
- **FR-009**: System MUST reset pagination to first page when any filter changes
- **FR-010**: System MUST persist filter state in URL query parameters for shareability and back-button support
- **FR-011**: System MUST provide clear empty state messaging when no files match current filters
- **FR-012**: Search MUST be case-insensitive

### Key Entities

- **Filter State**: Collection of active filter values (search term, resolution, audio languages, subtitle presence, status)
- **Resolution Categories**: Predefined resolution buckets (4K: height >= 2160, 1080p: height >= 1080, etc.)
- **Language Options**: Available audio language codes derived from indexed library data

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can find a specific file by name in under 5 seconds in a library of 1000+ files
- **SC-002**: Filter changes display updated results within 1 second
- **SC-003**: Users can combine at least 4 filters simultaneously (search + resolution + audio + subtitles)
- **SC-004**: 95% of filter operations complete without full page reload
- **SC-005**: Users can share filtered views via URL with all filters preserved
- **SC-006**: Users can clear all filters with a single action

## Assumptions

- The existing Library view infrastructure (018-library-list-view) provides the foundation for this feature
- Audio language data is already stored in the database from ffprobe introspection
- Subtitle track presence can be determined from existing track data
- Policy profile filtering is deferred as policies are not yet fully implemented (Policy column currently shows em-dash)
- The backend API will be extended to support additional query parameters for the new filters
- Language filter options will be dynamically populated from languages present in the library
