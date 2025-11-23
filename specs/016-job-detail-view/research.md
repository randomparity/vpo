# Research: Job Detail View with Logs

**Feature**: 016-job-detail-view
**Date**: 2025-11-23

## Research Summary

This document captures technical research and decisions made during the planning phase.

---

## 1. Log Storage Strategy

### Decision
File-based storage with database path reference (`log_path` field in jobs table).

### Rationale
- **Database bloat avoidance**: SQLite performance degrades when storing large TEXT blobs; logs can grow to megabytes
- **Streaming support**: File-based storage enables efficient tail reading and lazy loading without loading entire content
- **Existing pattern**: VPO already uses file-based approach for media files; logs follow same pattern
- **Cleanup simplicity**: Log files can be cleaned up independently via retention policy

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Database TEXT field | Bloats SQLite, hurts query performance for all tables |
| Hybrid (recent in DB, old in files) | Added complexity without significant benefit for single-user app |
| External log service | Overkill for desktop application, violates offline-first principle |

### Implementation Notes
- Log directory: `~/.vpo/logs/`
- File naming: `{job_id}.log` (UUID ensures uniqueness)
- Add `log_path` column to jobs table (nullable TEXT)
- Schema migration v7→v8 required

---

## 2. Log Lazy Loading Pattern

### Decision
Load last 500 lines initially, with "Load More" button to fetch additional chunks.

### Rationale
- **Performance**: Prevents browser freeze on large logs (10,000+ lines target)
- **User behavior**: Most debugging starts from recent output
- **Bandwidth**: Reduces initial page load time
- **Simplicity**: Chunk-based loading simpler than virtual scrolling

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Virtual scrolling | Complex implementation, browser compatibility concerns |
| Full load with truncation | Poor UX for troubleshooting (can't access older logs) |
| Pagination | Awkward UX for log viewing (logs are continuous stream) |

### Implementation Notes
- API: `GET /api/jobs/{id}/logs?lines=500&offset=0`
- Response includes `has_more` flag and `total_lines` count
- Frontend maintains loaded lines and appends on "Load More"
- Read from end of file for efficiency (`read_log_tail`)

---

## 3. Human-Readable Summary Generation

### Decision
Generate summary text from `summary_json` field based on job type.

### Rationale
- **Existing data**: `summary_json` already populated by 008-operational-ux
- **Type-specific**: Different job types have different meaningful metrics
- **Presentation layer**: Summary generation is a display concern, not business logic

### Summary Templates by Job Type
| Job Type | Summary Template |
|----------|------------------|
| scan | "Scanned {total_files} files in {target}, {new_files} new, {changed_files} changed" |
| apply | "Applied policy '{policy_name}' to {files_affected} files" |
| transcode | "Transcoded {input_path} → {output_path}" |
| move | "Moved {source_path} → {destination_path}" |

### Implementation Notes
- Summary generator function in UI models module
- Handle missing `summary_json` gracefully ("No summary available")
- Parse JSON safely with fallback for malformed data

---

## 4. URL Routing Pattern

### Decision
Use path parameter: `/jobs/{job_id}` (not query parameter).

### Rationale
- **RESTful**: Resource identification in path is REST convention
- **Shareable**: Clean URLs for bookmarking and sharing
- **Consistent**: Matches existing API patterns in codebase

### Implementation Notes
- Route: `GET /jobs/{job_id}` → `job_detail_handler`
- API: `GET /api/jobs/{id}` → `api_job_detail_handler`
- Logs API: `GET /api/jobs/{id}/logs` → `api_job_logs_handler`
- Handle invalid UUID format with 400 Bad Request
- Handle job not found with 404 Not Found

---

## 5. Filter State Preservation

### Decision
Use URL query parameters for filter state.

### Rationale
- **Browser navigation**: Back button naturally restores URL with params
- **No server-side state**: Stateless approach, no session storage needed
- **Existing pattern**: Jobs list already uses query params for filters

### Implementation Notes
- List URL: `/jobs?status=failed&type=scan&since=24h`
- Detail view links back to `/jobs` with preserved params
- JavaScript reads and preserves params on navigation
- No additional state management required

---

## 6. Timestamp Display Format

### Decision
Dual format: Relative time ("2 hours ago") with absolute time on hover.

### Rationale
- **Quick scanning**: Relative time easier to parse at a glance
- **Precision available**: Full timestamp available when needed
- **Existing pattern**: Common UX pattern (GitHub, etc.)

### Implementation Notes
- Use JavaScript for relative time calculation (browser timezone)
- Store `title` attribute with ISO-8601 for hover tooltip
- Update relative times periodically (every minute) for running jobs
- Format: "2 hours ago" / "5 minutes ago" / "just now"

---

## 7. Error Handling Strategy

### Decision
Graceful degradation with user-friendly error messages.

### Error Scenarios and Responses
| Scenario | HTTP Status | User Message |
|----------|-------------|--------------|
| Job not found | 404 | "Job not found. It may have been deleted." |
| Invalid job ID format | 400 | "Invalid job ID format." |
| Log file missing | 200 | Logs section shows "No logs available" |
| Log file read error | 200 | Logs section shows "Unable to load logs" |
| Database error | 503 | "Service temporarily unavailable" |

### Implementation Notes
- 404 page includes link back to jobs list
- Log errors don't fail the entire page (partial success)
- All error messages are user-friendly (no stack traces)
