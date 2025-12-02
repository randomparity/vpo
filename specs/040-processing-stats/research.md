# Research: Processing Statistics and Metrics Tracking

**Feature**: 040-processing-stats
**Date**: 2025-12-01

## Overview

This document captures research findings and design decisions for implementing comprehensive processing statistics and metrics tracking in VPO.

## Research Areas

### 1. Database Schema Design

**Decision**: Use three separate tables for statistics data (normalized design)

**Rationale**:
- `processing_stats`: Core statistics per processing run (size, track counts, timing)
- `action_results`: Per-action details linked to processing_stats
- `performance_metrics`: Per-phase performance data linked to processing_stats

This normalized approach follows Constitution Principle XIII (Database Design) and allows efficient querying for different use cases:
- Aggregate queries can use just `processing_stats`
- Detailed analysis can join to `action_results` and `performance_metrics`

**Alternatives Considered**:
- Single denormalized table: Rejected because action details and performance metrics are optional/variable in structure
- JSON columns for details: Rejected because structured queries are important for reporting

### 2. Statistics Capture Points

**Decision**: Capture statistics in the V11WorkflowProcessor after each phase completes

**Rationale**:
- The processor already has access to file info, policy context, and timing
- FileProcessingResult and PhaseResult already contain most needed data
- Minimal code changes - extend existing result types rather than adding new instrumentation

**Implementation Points**:
1. Before processing: Record file size, track counts, file hash
2. After each phase: Record phase duration, operations executed
3. After processing: Record final file size, track counts, success/failure

### 3. File Hash for Integrity

**Decision**: Use SHA-256 hash of first 1MB + last 1MB + file size

**Rationale**:
- Full file hashing is too slow for large video files (can be 20GB+)
- This approach catches most modifications while remaining fast
- Consistent with existing `content_hash` field in files table

**Alternatives Considered**:
- Full file SHA-256: Too slow for multi-GB files
- MD5: Deprecated for integrity verification
- CRC32: Too short for reliable integrity verification

### 4. Aggregate Query Performance

**Decision**: Use indexed columns and pre-computed aggregates where appropriate

**Rationale**:
- SC-001 requires <2 second aggregate queries
- Add indexes on `policy_name`, `processed_at`, `file_id`
- Consider materialized views for frequently-accessed aggregates (future optimization)

**Performance Approach**:
1. Standard indexes for common query patterns
2. Avoid full table scans in aggregate queries
3. Use SQLite's built-in aggregate functions (SUM, AVG, COUNT)

### 5. CLI Command Structure

**Decision**: New `vpo stats` command with subcommands

**Rationale**:
- Follows existing CLI patterns (e.g., `vpo jobs`, `vpo scan`)
- Subcommands allow focused functionality:
  - `vpo stats summary`: Overall statistics
  - `vpo stats policy <name>`: Per-policy breakdown
  - `vpo stats file <path>`: Per-file history
  - `vpo stats purge`: Manual cleanup

**Alternatives Considered**:
- Adding flags to existing commands: Would clutter existing command help
- Single stats command with many options: Less discoverable

### 6. Web UI Dashboard Design

**Decision**: Simple tabular display with optional time-range filtering

**Rationale**:
- Consistent with existing VPO web UI patterns (no complex JS frameworks)
- Server-rendered HTML with minimal JavaScript
- Focus on most common queries: total savings, per-policy breakdown

**Components**:
1. Summary cards: Total files processed, total space saved, success rate
2. Policy comparison table: Per-policy statistics
3. Recent processing table: Last N processing runs
4. Time range filter: All time, last 7 days, last 30 days, custom range

### 7. Per-Action State Tracking

**Decision**: Store before/after state as JSON for flexibility

**Rationale**:
- Track state varies by action type (codec changes vs flag changes vs removals)
- JSON provides flexibility without schema changes for new action types
- Keep action_type as indexed column for filtering

**Schema**:
```sql
action_results (
    id INTEGER PRIMARY KEY,
    stats_id INTEGER NOT NULL,  -- FK to processing_stats
    action_type TEXT NOT NULL,  -- indexed: set_default, set_language, remove, etc.
    track_type TEXT,            -- audio, video, subtitle, attachment
    track_index INTEGER,
    before_state TEXT,          -- JSON
    after_state TEXT,           -- JSON
    success INTEGER NOT NULL,
    duration_ms INTEGER,
    rule_reference TEXT,        -- Policy rule that triggered this action
    message TEXT,
    FOREIGN KEY (stats_id) REFERENCES processing_stats(id) ON DELETE CASCADE
)
```

### 8. FFmpeg Metrics Parsing

**Decision**: Parse stderr output for encoding metrics during transcode operations

**Rationale**:
- FFmpeg outputs progress to stderr in a parseable format
- Existing TranscodeExecutor already monitors FFmpeg output for progress
- Extend to capture: fps, bitrate, quality metrics

**Metrics to Capture**:
- `fps`: Current encoding speed
- `bitrate`: Current output bitrate
- `frame`: Current frame number
- `size`: Current output size
- `time`: Current output timestamp

### 9. Data Retention Strategy

**Decision**: Indefinite retention with manual purge capability (per clarification)

**Rationale**:
- Users want historical trend analysis
- Storage overhead is minimal (estimated <1KB per processing run)
- Purge commands allow users to manage their data

**Purge Options**:
- `vpo stats purge --before <date>`: Remove stats older than date
- `vpo stats purge --policy <name>`: Remove stats for specific policy
- `vpo stats purge --all`: Remove all statistics (with confirmation)

### 10. Transcode Skip Tracking

**Decision**: Record skip reason when transcoding is bypassed due to skip_if conditions

**Rationale**:
- Users need to understand why transcoding didn't occur
- Helps with policy debugging and optimization
- Store as a structured field in processing_stats

**Fields**:
```python
@dataclass
class TranscodeSkipInfo:
    skipped: bool
    reason: str | None  # "codec_matches", "resolution_within", "bitrate_under"
    details: str | None  # "codec=hevc matches [hevc, h265]"
```

## Dependencies

### Existing Code to Extend

1. **db/schema.py**: Add new tables and migration
2. **db/types.py**: Add new dataclass types
3. **db/queries.py**: Add CRUD operations
4. **workflow/v11_processor.py**: Capture statistics during processing
5. **executor/interface.py**: Extend ExecutorResult with optional metrics
6. **cli/__init__.py**: Register new stats command

### New Files to Create

1. **cli/stats.py**: Statistics CLI command
2. **server/ui/templates/stats.html**: Statistics dashboard
3. **db/stats.py**: (Optional) Dedicated statistics query module

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Performance impact on processing | Low | Medium | Lightweight capture, async writes |
| Large database growth | Low | Low | Minimal data per run, purge capability |
| Complex aggregate queries slow | Medium | Medium | Proper indexing, query optimization |
| Schema migration issues | Low | High | Thorough testing, rollback capability |

## Conclusion

The implementation approach is well-defined with no blocking unknowns. All decisions align with existing VPO patterns and constitution principles. Ready to proceed to Phase 1 design.
