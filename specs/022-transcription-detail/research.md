# Research: Transcription Detail View

**Feature**: 022-transcription-detail
**Date**: 2025-11-24

## Overview

This document captures research findings for implementing the transcription detail view. The feature is straightforward as it builds on existing patterns - no major unknowns required resolution.

## Existing Patterns Analysis

### Detail View Pattern (from 016-job-detail-view, 020-file-detail-view)

**Decision**: Follow established detail view pattern

**Rationale**: The codebase has two well-established detail view implementations that provide a consistent pattern:
- Route: `/{resource}/{id}` for HTML, `/api/{resource}/{id}` for JSON
- Handler pattern: async handler with `connection_pool.transaction()` for DB access
- Context pattern: `*DetailItem` dataclass for data, `*DetailContext` for template context
- Template pattern: Jinja2 template in `templates/sections/{resource}_detail.html`

**Components to implement**:
1. `TranscriptionDetailItem` - dataclass with full transcription + track data
2. `TranscriptionDetailContext` - template context with back_url
3. `get_transcription_detail()` - DB query joining transcription_results with tracks
4. `transcription_detail_handler` - HTML page handler
5. `api_transcription_detail_handler` - JSON API handler

**Alternatives considered**: None - existing pattern is well-suited

### Commentary Detection Logic (from transcription/models.py)

**Decision**: Reuse existing `COMMENTARY_KEYWORDS` and `COMMENTARY_TRANSCRIPT_PATTERNS`

**Rationale**: The commentary detection logic already exists and is well-defined:

**Metadata keywords** (COMMENTARY_KEYWORDS):
- commentary, director, cast, crew, behind the scenes, making of, bts, isolated, alternate, composer

**Transcript patterns** (COMMENTARY_TRANSCRIPT_PATTERNS):
- `\bthis scene\b.*\bwe\b` - Director/cast phrases
- `\bwhen we (shot|filmed|made)\b`
- `\bI (remember|think|wanted)\b`
- `\bthe (actor|actress|director)\b`
- `\bon set\b`, `\bthe script\b`, `\bthe original\b.*\bversion\b`
- Interview patterns: `\bwhat (made|inspired)\b.*\byou\b`, `\btell us about\b`

**Classification display**:
- Check if track was classified via metadata: `is_commentary_by_metadata(title)`
- Check if classified via patterns: scan `transcript_sample` for `COMMENTARY_TRANSCRIPT_PATTERNS`
- Display which method triggered the classification

**Alternatives considered**: Building new detection logic - rejected as duplicate effort

### Text Chunking Strategy

**Decision**: CSS-based line wrapping with optional "Show more" JavaScript

**Rationale**:
- Transcription text is plain text, not structured
- Long text (> 10,000 chars) should truncate with "Show more" option
- Use CSS `word-break: break-word` and `overflow-wrap: break-word` for display
- Initial display shows first ~500 characters with expansion option

**Implementation approach**:
1. Server returns full transcript_sample (already limited at source during transcription)
2. Template applies CSS for proper text wrapping
3. JavaScript adds "Show more/less" toggle for text > 500 chars
4. No server-side chunking needed

**Alternatives considered**:
- Server-side pagination - rejected (unnecessary complexity for single-page view)
- Virtual scrolling - rejected (overkill for transcript display)

### URL Routing Pattern

**Decision**: Use `/transcriptions/{id}` pattern with integer ID

**Rationale**:
- Consistent with `/library/{file_id}` and `/jobs/{job_id}` patterns
- Use `transcription_results.id` (integer primary key) as identifier
- Simpler than compound key (track_id) and stable

**Routes to add**:
- `GET /transcriptions/{transcription_id}` - HTML detail page
- `GET /api/transcriptions/{transcription_id}` - JSON API

**Alternatives considered**:
- Using track_id: rejected (transcription_results.id is more direct)
- Nested route `/library/{file_id}/tracks/{track_id}/transcription`: rejected (too deep, harder to link to directly)

### Keyword Highlighting Approach

**Decision**: Server-side HTML generation with CSS classes

**Rationale**:
- For FR-009 (highlight commentary keywords in transcript)
- Generate HTML with `<mark class="keyword-match">` tags around matches
- Apply CSS styling for visual highlighting
- Safer than client-side text manipulation (XSS concerns)

**Implementation**:
1. Create helper function `highlight_keywords(text, patterns)` in models.py
2. Escape HTML in transcript text first
3. Apply `<mark>` tags around pattern matches
4. Return as safe HTML for Jinja2 template

**Alternatives considered**:
- Client-side JS highlighting: rejected (security concern with innerHTML)
- No highlighting: rejected (explicit in FR-009)

## Database Query Design

### get_transcription_detail() Function

```sql
SELECT
    tr.id,
    tr.track_id,
    tr.detected_language,
    tr.confidence_score,
    tr.track_type,
    tr.transcript_sample,
    tr.plugin_name,
    tr.created_at,
    tr.updated_at,
    t.track_index,
    t.track_type AS track_media_type,
    t.codec,
    t.language AS original_language,
    t.title,
    t.channels,
    t.channel_layout,
    t.is_default,
    t.is_forced,
    f.id AS file_id,
    f.filename,
    f.path
FROM transcription_results tr
JOIN tracks t ON tr.track_id = t.id
JOIN files f ON t.file_id = f.id
WHERE tr.id = ?
```

**Rationale**: Single query retrieves all needed data for the detail view - transcription result, track metadata, and parent file info for navigation.

## Summary

No major research unknowns were found. The feature follows existing patterns:
1. Detail view pattern from job/file detail views
2. Commentary detection from transcription/models.py
3. Standard route/handler/template structure

All design decisions align with existing codebase conventions.
