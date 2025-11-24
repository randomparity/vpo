# Research: Library List View

**Feature**: 018-library-list-view
**Date**: 2025-11-23

## Overview

This document captures research findings for implementing the Library list view feature. Since the codebase already has established patterns from the Jobs dashboard implementation, this research focuses on confirming those patterns and identifying any unique requirements for the Library page.

## Research Topics

### 1. Database Query Pattern for Files with Tracks

**Decision**: Create `get_files_filtered()` function following `get_jobs_filtered()` pattern

**Rationale**:
- The Jobs dashboard uses `get_jobs_filtered()` with WHERE clause building, COUNT for total, and LIMIT/OFFSET for pagination
- This pattern is proven efficient and thread-safe with `DaemonConnectionPool`
- Files table already has `scanned_at` indexed for sorting
- Track data requires a JOIN to aggregate audio languages and video resolution

**Implementation Notes**:
- Use LEFT JOIN to tracks table to get track metadata
- Group results by file_id to aggregate track info
- Return both file metadata and computed display values (resolution label, language list)
- Query pattern: `SELECT ... FROM files LEFT JOIN tracks ... GROUP BY files.id ORDER BY scanned_at DESC LIMIT ? OFFSET ?`

**Alternatives Considered**:
- Separate queries for files and tracks: Rejected - N+1 query problem for large result sets
- Denormalized columns on files table: Rejected - Violates normalization principles; track data changes on rescan

### 2. Resolution Label Mapping

**Decision**: Map video dimensions to human-readable labels at the application layer

**Rationale**:
- Resolution labels (1080p, 4K, etc.) are presentation concerns, not data
- Stored dimensions (width, height) are the source of truth
- Mapping in Python allows flexibility for edge cases

**Mapping Table**:
```python
RESOLUTION_LABELS = {
    (3840, 2160): "4K",
    (2560, 1440): "1440p",
    (1920, 1080): "1080p",
    (1280, 720): "720p",
    (854, 480): "480p",
    (640, 360): "360p",
}

def get_resolution_label(width: int | None, height: int | None) -> str:
    """Map video dimensions to human-readable resolution label."""
    if width is None or height is None:
        return "—"

    # Check for exact matches first
    if (width, height) in RESOLUTION_LABELS:
        return RESOLUTION_LABELS[(width, height)]

    # Fallback: use height-based approximation
    if height >= 2160:
        return "4K"
    elif height >= 1440:
        return "1440p"
    elif height >= 1080:
        return "1080p"
    elif height >= 720:
        return "720p"
    elif height >= 480:
        return "480p"
    else:
        return f"{height}p"
```

**Alternatives Considered**:
- Store resolution label in database: Rejected - Redundant data; complicates schema
- JavaScript client-side mapping: Rejected - Server already has the data; keep presentation consistent

### 3. Audio Language Aggregation

**Decision**: Aggregate distinct audio languages from tracks, display first 3 with "+N more" for overflow

**Rationale**:
- Files may have many audio tracks (e.g., multilingual releases)
- Displaying all languages clutters the UI
- 3 languages fits typical column width while showing diversity

**Implementation**:
```python
def format_audio_languages(languages: list[str | None]) -> str:
    """Format audio language list for display."""
    # Filter None and deduplicate while preserving order
    unique = list(dict.fromkeys(lang for lang in languages if lang))

    if not unique:
        return "—"

    if len(unique) <= 3:
        return ", ".join(unique)

    return f"{', '.join(unique[:3])} +{len(unique) - 3} more"
```

**Alternatives Considered**:
- Show all languages: Rejected - UI clutter for multilingual files
- Show only first language: Rejected - Loses important information for mixed content

### 4. Relative Time Formatting

**Decision**: Use the existing JavaScript `formatRelativeTime()` pattern from Jobs dashboard

**Rationale**:
- Jobs page already formats timestamps as "2 hours ago", "3 days ago"
- Consistent UX across pages
- Client-side formatting allows real-time updates without refresh

**Implementation**: Reuse pattern from `jobs.js`:
```javascript
function formatRelativeTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffDay > 0) return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`;
    if (diffHour > 0) return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
    if (diffMin > 0) return `${diffMin} minute${diffMin > 1 ? 's' : ''} ago`;
    return 'Just now';
}
```

### 5. Policy Profile Display

**Decision**: Display "—" for all files initially; policy tracking is out of scope for this feature

**Rationale**:
- The spec mentions "Policy Profile" as a column
- Current database schema has `policy_name` on Jobs table, not Files table
- Files don't currently track which policy has been applied to them
- Adding policy tracking to files requires schema changes beyond this feature's scope

**Implementation**:
- Column header: "Policy"
- All cells display "—" initially
- Future enhancement: Add `last_applied_policy` column to files table

**Note**: This is documented as an assumption in the spec ("if no policy has been applied, this shows as '—'"). All files will show "—" until policy application tracking is implemented separately.

### 6. Table Layout Consistency with Jobs

**Decision**: Match Jobs dashboard table structure exactly for visual consistency

**Components to match**:
- Filter bar layout (dropdowns, reset link)
- Table column sizing and alignment
- Empty state styling
- Pagination controls (Previous/Next buttons, "Showing X-Y of Z")
- Loading state (spinner)
- Status badges (for scan status: ok, error)

**CSS Classes to reuse**:
- `.jobs-filters` → `.library-filters`
- `.jobs-table` → `.library-table`
- `.jobs-empty` → `.library-empty`
- `.jobs-pagination` → `.library-pagination`
- `.status-badge` (reuse directly for scan status)

### 7. Polling Strategy

**Decision**: No automatic polling for Library page initially

**Rationale**:
- Jobs page polls because job status changes in real-time
- Library files change only during scans, which are infrequent
- Polling would waste bandwidth for minimal benefit
- User can manually refresh if needed

**Future Enhancement**: Add optional polling during active scan jobs (detect via `/api/jobs?status=running&type=scan`)

## Summary of Decisions

| Topic | Decision |
|-------|----------|
| Query pattern | `get_files_filtered()` with JOIN, GROUP BY, pagination |
| Resolution labels | Python-side mapping from (width, height) |
| Audio languages | First 3 + "+N more" overflow |
| Time formatting | Client-side relative time (existing pattern) |
| Policy column | Show "—" for all (policy tracking out of scope) |
| UI consistency | Match Jobs dashboard layout exactly |
| Polling | None initially (files rarely change) |

## Dependencies Identified

1. **Existing**: `db/models.py` - Add `get_files_filtered()` function
2. **Existing**: `server/ui/models.py` - Add Library models
3. **Existing**: `server/ui/routes.py` - Add handlers
4. **Existing**: `server/static/css/main.css` - Add library styles
5. **New**: `server/static/js/library.js` - Page JavaScript
6. **Existing**: `server/ui/templates/sections/library.html` - Update placeholder

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Slow query for large libraries | Medium | High | Use indexed `scanned_at` column; test with 10k files |
| JOIN performance with many tracks | Low | Medium | Optimize GROUP BY; consider subquery if needed |
| Policy column confusion | Low | Low | Clear "—" placeholder; document in UI if needed |
