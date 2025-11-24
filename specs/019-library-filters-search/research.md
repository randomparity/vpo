# Research: Library Filters and Search

**Feature**: 019-library-filters-search
**Date**: 2025-11-23

## Research Summary

This feature extends the existing Library view (018-library-list-view) with additional filters and search. All technical foundations exist; research focuses on best practices for the specific filter implementations.

## Research Tasks

### R1: SQLite Full-Text Search vs LIKE for Text Search

**Context**: Need to search filename and title fields efficiently.

**Decision**: Use SQLite `LIKE` with `LOWER()` for case-insensitive search.

**Rationale**:
- FTS5 would require schema migration and index maintenance
- LIKE with existing indexes performs well for substring matching in libraries of 10,000 files
- Existing query pattern uses WHERE conditions that compose well with LIKE
- Simpler implementation, no schema changes required

**Alternatives Considered**:
- FTS5: More powerful but requires new virtual table and migration
- GLOB: Case-sensitive by default, less intuitive for users

### R2: Resolution Filtering Strategy

**Context**: Filter files by resolution category (4K, 1080p, 720p, etc.)

**Decision**: Use height-based range conditions in SQL WHERE clause.

**Rationale**:
- Resolution categories map to height ranges: 4K (>=2160), 1080p (>=1080 <2160), etc.
- Height is already stored in tracks table via existing introspection
- Existing `get_resolution_label()` function in models.py provides the same mapping

**Implementation**:
```sql
-- Example for 1080p filter
WHERE t.track_type = 'video' AND t.height >= 1080 AND t.height < 2160
```

**Alternatives Considered**:
- Separate resolution column: Would require schema migration
- Client-side filtering: Poor performance for large libraries

### R3: Audio Language Multi-Select Filter

**Context**: Allow filtering by multiple audio languages with OR logic.

**Decision**: Use SQL `IN` clause for language codes.

**Rationale**:
- OR logic is intuitive: "show files with English OR Japanese audio"
- SQL `IN` clause is efficient and readable
- Language codes are already stored in tracks.language column

**Implementation**:
```sql
-- Files with tracks matching any selected language
WHERE t.track_type = 'audio' AND t.language IN ('eng', 'jpn')
```

**Alternatives Considered**:
- AND logic: Too restrictive; users rarely need "must have BOTH languages"
- Separate endpoint: Unnecessary complexity

### R4: Dynamic Language Options

**Context**: Populate language filter dropdown with languages present in library.

**Decision**: Add new API endpoint `/api/library/languages` or include in library metadata response.

**Rationale**:
- Languages vary by library content
- Static list would show unavailable options
- Single query can aggregate distinct languages efficiently

**Implementation**:
```sql
SELECT DISTINCT t.language
FROM tracks t
WHERE t.track_type = 'audio' AND t.language IS NOT NULL
ORDER BY t.language
```

### R5: Subtitle Presence Filter

**Context**: Filter by whether file has subtitle tracks.

**Decision**: Use `EXISTS` subquery to check for subtitle track presence.

**Rationale**:
- Subtitle track type is already in tracks table
- EXISTS is efficient for presence check without counting

**Implementation**:
```sql
-- Has subtitles
WHERE EXISTS (SELECT 1 FROM tracks t2 WHERE t2.file_id = f.id AND t2.track_type = 'subtitle')

-- No subtitles
WHERE NOT EXISTS (SELECT 1 FROM tracks t2 WHERE t2.file_id = f.id AND t2.track_type = 'subtitle')
```

### R6: JavaScript Debounce Implementation

**Context**: Debounce search input to avoid excessive API calls.

**Decision**: Implement simple debounce function in vanilla JavaScript.

**Rationale**:
- 300ms delay balances responsiveness with server load
- No external library needed for simple debounce
- Pattern already used in web ecosystem

**Implementation**:
```javascript
function debounce(fn, delay) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(this, args), delay);
    };
}
```

### R7: URL Query Parameter Sync

**Context**: Persist filter state in URL for shareability and browser history.

**Decision**: Use `URLSearchParams` API with `history.replaceState()`.

**Rationale**:
- Native browser API, no dependencies
- replaceState avoids polluting browser history with every filter change
- Query params are naturally shareable

**Implementation**:
```javascript
function updateUrl(filters) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
        if (value) params.set(key, value);
    }
    history.replaceState(null, '', '?' + params.toString());
}
```

### R8: Active Filter Indicator UX

**Context**: Clearly show which filters are currently active.

**Decision**: Use visual highlighting on filter controls + "Clear filters" button.

**Rationale**:
- Dropdown with non-default value shows selected option
- Search box shows current text
- "Clear filters" button appears only when filters active
- Consistent with existing status filter pattern in 018

**Alternatives Considered**:
- Filter chips/tags: More complex UI; overkill for 4-5 filters
- Sidebar filter panel: Too heavy for this use case

## Dependencies Verified

| Dependency | Status | Notes |
|------------|--------|-------|
| tracks.language column | EXISTS | Used by current audio_languages aggregation |
| tracks.track_type | EXISTS | Supports 'video', 'audio', 'subtitle' |
| tracks.height/width | EXISTS | Used by current resolution display |
| get_files_filtered() | EXISTS | Will be extended with new parameters |
| LibraryFilterParams | EXISTS | Will be extended with new fields |

## No Schema Changes Required

The existing tracks table has all required columns:
- `track_type`: Filter for video/audio/subtitle
- `language`: ISO 639 language codes
- `height`/`width`: Video resolution dimensions

## Resolved NEEDS CLARIFICATION

All technical context items were clear from existing codebase analysis. No clarifications needed.
