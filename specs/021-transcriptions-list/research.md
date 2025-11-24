# Research: Transcriptions Overview List

**Feature**: 021-transcriptions-list
**Date**: 2025-11-24

## Overview

This document captures research findings for implementing the Transcriptions page. Most patterns are already established in the codebase through the Library List view (018) and File Detail view (020).

## Research Topics

### 1. Database Query Pattern for Transcription Aggregation

**Decision**: Use a JOIN-based query with conditional aggregation (matching `get_files_filtered()` pattern)

**Rationale**: The existing `get_files_filtered()` function in `db/models.py` demonstrates an efficient pattern for aggregating track data per file using `LEFT JOIN` with `GROUP_CONCAT` and `MAX(CASE WHEN ...)`. This approach:
- Executes as a single query (no N+1 problem)
- Handles files with multiple tracks efficiently
- Supports pagination at the database level

**Alternatives considered**:
- Separate queries per file: Rejected - N+1 query problem at scale
- Subqueries: Rejected - JOIN approach more readable and equally performant

**Implementation approach**:
```sql
SELECT
    f.id, f.filename, f.path, f.scan_status,
    COUNT(DISTINCT tr.id) as transcription_count,
    GROUP_CONCAT(DISTINCT tr.detected_language) as detected_languages,
    MIN(tr.confidence_score) as min_confidence,
    MAX(tr.confidence_score) as max_confidence,
    AVG(tr.confidence_score) as avg_confidence
FROM files f
LEFT JOIN tracks t ON f.id = t.file_id AND t.track_type = 'audio'
LEFT JOIN transcription_results tr ON t.id = tr.track_id
WHERE ... (optional transcription filter)
GROUP BY f.id
```

### 2. Confidence Score Display Format

**Decision**: Display as categorical labels (High/Medium/Low) with color coding

**Rationale**: The spec requires confidence information "in a user-friendly format that non-technical users can understand" (SC-005). Categorical labels are more intuitive than percentages.

**Thresholds** (from FR-009):
- **High** (green): >= 0.8 (80%)
- **Medium** (yellow): >= 0.5 and < 0.8 (50-79%)
- **Low** (red): < 0.5 (below 50%)

**Alternatives considered**:
- Raw percentage display: Rejected - less intuitive for non-technical users
- Star ratings: Rejected - doesn't match existing UI patterns

### 3. Default Filter State

**Decision**: Default to showing only files with transcription results (clarified in spec)

**Rationale**: The Transcriptions page's primary purpose is showing transcription data. Starting with only transcribed files provides immediate value without requiring user action.

**Implementation**:
- Query parameter `show_all=false` by default
- Toggle button labeled "Show all files" to enable `show_all=true`

### 4. Pagination Strategy

**Decision**: Follow Library view pagination pattern (50 files per page, limit/offset)

**Rationale**: Consistency with existing UI and meets SC-006 requirement for handling 100+ files.

**Implementation**:
- Same pagination controls as Library view
- Same limit (50) and offset (0) defaults
- Same info display format ("Showing X-Y of Z files")

### 5. Navigation to File Detail

**Decision**: Click file row to navigate to existing `/library/{file_id}` route

**Rationale**:
- File Detail view (020) already displays transcription data per track
- Reuses existing functionality without duplication
- Maintains consistent UX across the application

**Implementation**:
- File rows are clickable links to `/library/{file_id}`
- Preserve back navigation state via Referer header (existing pattern)

### 6. API Response Structure

**Decision**: Mirror `FileListResponse` structure with transcription-specific fields

**Rationale**: Consistency with existing API patterns enables code reuse in JavaScript client.

**Response structure**:
```json
{
  "files": [
    {
      "id": 123,
      "filename": "movie.mkv",
      "path": "/path/to/movie.mkv",
      "has_transcription": true,
      "detected_languages": ["eng", "jpn"],
      "confidence_level": "high",
      "confidence_avg": 0.92,
      "transcription_count": 2,
      "scan_status": "ok"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0,
  "has_filters": true
}
```

### 7. Empty State Handling

**Decision**: Show contextual empty message based on filter state

**Rationale**: Different messages help users understand why the list is empty.

**Messages**:
- Default (transcribed only): "No transcription data available. Run language detection on your library to populate this view."
- Show all + no files: "No files in library. Scan a directory to add files."
- Filtered but no matches: "No files match your current filter."

### 8. UI Component Patterns

**Decision**: Reuse Library view HTML/CSS patterns with minimal modifications

**Rationale**: Consistency and reduced development effort.

**Components to reuse**:
- Filter bar structure (`library-filters` class)
- Table structure (`library-table` class)
- Pagination controls
- Loading/error/empty states
- Row click navigation pattern

**New components needed**:
- Confidence badge (small colored indicator)
- Languages list display (comma-separated with overflow handling)
- "Has transcription" indicator (checkmark icon or badge)

## Existing Code References

| Component | File | Pattern |
|-----------|------|---------|
| Query function | `db/models.py:1353` | `get_files_filtered()` |
| Filter params | `server/ui/models.py:584` | `LibraryFilterParams` |
| List item model | `server/ui/models.py:683` | `FileListItem` |
| Response model | `server/ui/models.py:724` | `FileListResponse` |
| Route handler | `server/ui/routes.py:740` | `library_handler` |
| API handler | `server/ui/routes.py:771` | `library_api_handler` |
| Template | `templates/sections/library.html` | Full structure |
| JavaScript | `static/js/library.js` | Client-side logic |

## Dependencies

No new external dependencies required. All functionality can be implemented using:
- Existing Python packages (aiohttp, jinja2)
- Existing database schema and query patterns
- Existing CSS styles with minor additions
- Vanilla JavaScript following existing patterns

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance with large libraries | High | Use efficient JOIN query with pagination |
| Inconsistent confidence display | Medium | Clear threshold definitions in code |
| Empty state confusion | Low | Contextual messages based on filter state |

## Conclusion

No significant technical unknowns remain. Implementation follows well-established patterns from Library List view (018) and File Detail view (020). The main work is:
1. New database query function for transcription aggregation
2. New UI models for transcription list items
3. Updated route handlers
4. New Jinja2 template (based on library.html)
5. New JavaScript file (based on library.js)
6. Unit and integration tests
