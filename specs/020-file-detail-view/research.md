# Research: File Detail View

**Feature**: 020-file-detail-view
**Date**: 2025-11-23

## Overview

This research document consolidates findings from analyzing the existing codebase to inform the file detail view implementation. Since the feature follows established patterns, no external research was needed.

## Research Tasks

### 1. Existing Detail View Patterns (016-job-detail-view)

**Decision**: Follow the job detail view architecture pattern

**Rationale**: The existing `016-job-detail-view` implementation provides a proven pattern for:
- Route structure (`/jobs/{job_id}` HTML + `/api/jobs/{job_id}` JSON)
- Model design (`JobDetailItem` with `to_dict()` method)
- Handler structure (`job_detail_handler` + `api_job_detail_handler`)
- Template organization (`sections/job_detail.html`)
- Error handling (404 for not found, 400 for invalid ID format)
- Back navigation with referer preservation

**Alternatives considered**:
- Custom architecture: Rejected because consistency with existing patterns reduces cognitive load and maintenance burden

### 2. Database Query Patterns

**Decision**: Create `get_file_by_id()` function in `db/models.py`, use existing `get_tracks_for_file()`

**Rationale**:
- Existing `get_file_by_path()` shows the pattern for file queries
- `get_tracks_for_file()` already exists and returns `TrackRecord` objects
- Job linkage: Files have `job_id` column linking to scan job
- Need to also query `transcription_results` table by track_id

**Alternatives considered**:
- Single query with JOINs: Rejected for simplicity; separate queries are clearer and the data volume per file is small (typically < 20 tracks)

### 3. Track Display Organization

**Decision**: Group tracks by type (video, audio, subtitle, other), display in collapsible sections

**Rationale**:
- Video tracks: Show codec, resolution (width x height), frame rate
- Audio tracks: Show codec, language, channels, channel_layout, title, flags (default/forced)
- Subtitle tracks: Show codec, language, title, flags (default/forced)
- Collapsible sections for 5+ total tracks to maintain readability
- Follows existing CSS patterns (`.section-header`, `.section-content`)

**Alternatives considered**:
- Flat list of all tracks: Rejected because harder to scan visually
- Tabs per track type: Rejected for complexity; collapsible sections are simpler

### 4. File Size Formatting

**Decision**: Use existing humanize patterns or inline formatting function

**Rationale**:
- Job detail view has size formatting in `generate_summary_text()`
- Pattern: bytes → KB/MB/GB with 1 decimal place
- Example: `4294967296` → `"4.0 GB"`

**Alternatives considered**:
- External humanize library: Rejected; simple inline function is sufficient

### 5. Transcription Data Display

**Decision**: Show transcription results per audio track when available

**Rationale**:
- `transcription_results` table links via `track_id`
- Display: detected_language, confidence_score (as percentage), track_type (main/commentary/alternate)
- If no transcription data, hide section or show "No transcription data"

**Alternatives considered**:
- Separate transcription section: Considered but rejected; inline display per audio track is more contextual

### 6. Library List Click Navigation

**Decision**: Make file rows clickable in library list, linking to `/library/{file_id}`

**Rationale**:
- Follows existing job list → job detail navigation pattern
- Uses file `id` (integer primary key) as URL parameter
- JavaScript enhancement to make entire row clickable (existing pattern from jobs list)

**Alternatives considered**:
- Modal/overlay: Rejected for complexity; separate page is simpler
- Query parameter instead of path: Rejected; path parameter is cleaner (`/library/123` vs `/library?id=123`)

## Resolved Unknowns

All technical context items were resolved using existing codebase patterns:

| Item | Resolution |
|------|------------|
| Route pattern | `/library/{file_id}` (HTML) + `/api/library/{file_id}` (JSON) |
| Model pattern | `FileDetailItem` dataclass with `to_dict()` |
| Handler pattern | Async handlers with connection pool transaction |
| Template pattern | `sections/file_detail.html` extending base layout |
| Error handling | 404/400/503 matching job detail patterns |
| Track grouping | By type with collapsible sections |
| Back navigation | Preserve referer to `/library` with filters |

## Dependencies

No new dependencies required. Feature uses existing:
- aiohttp (web framework)
- Jinja2 + aiohttp-jinja2 (templating)
- SQLite (database via existing connection pool)

## Next Steps

Proceed to Phase 1: Generate data-model.md and API contracts.
