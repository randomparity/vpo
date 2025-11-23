# Research: Operational UX

**Feature**: 008-operational-ux
**Date**: 2025-11-22

## Overview

This document consolidates research findings for the Operational UX feature. All NEEDS CLARIFICATION items from the technical context have been resolved.

---

## R1: Incremental Scan Change Detection

**Question**: What is the most reliable and performant approach for detecting file changes during incremental scans?

**Decision**: Use mtime + size comparison as primary detection method, with optional content hash verification.

**Rationale**:
- The existing `files` table already stores `modified_at` (mtime) and `size_bytes` - no schema changes needed for basic detection
- mtime + size comparison is the industry standard for incremental tools (rsync, make, git status)
- ~99.9% reliable on local filesystems; edge cases (NFS clock skew, same-second modifications) are rare
- Content hash (`--verify-hash`) provides 100% reliability for paranoid mode but requires reading entire file

**Alternatives Considered**:
1. **Content hash only**: Too slow for large libraries (must read every file on every scan)
2. **inotify/FSEvents watch**: Complex, doesn't persist across restarts, not portable
3. **Database-stored checksums with lazy refresh**: Overcomplicated for the benefit

**Implementation Notes**:
- Compare stored `modified_at` and `size_bytes` against `os.stat()` results
- Use `Path.stat()` for cross-platform compatibility
- Consider timezone handling: mtime is stored as ISO-8601 UTC, stat returns local time

---

## R2: Job Type Expansion for Unified History

**Question**: How should the existing jobs table be extended to support scan and apply operations?

**Decision**: Extend the `job_type` CHECK constraint to include `'scan'` and `'apply'` values. Add a `files_affected` JSON column for multi-file operations.

**Rationale**:
- Existing `jobs` table has the right structure (id, status, timing, error tracking)
- Single table for all job types enables unified `vpo jobs list` without JOINs
- JSON column for affected files avoids many-to-many junction table complexity

**Alternatives Considered**:
1. **Separate tables per job type**: Fragments history, complicates queries
2. **Polymorphic operations table**: Already exists but designed for per-file audit, not job-level tracking
3. **Redis/external queue**: Overkill for single-user CLI tool

**Schema Changes**:
```sql
-- Extend job_type constraint (migration v6→v7)
ALTER TABLE jobs DROP CONSTRAINT valid_job_type;
ALTER TABLE jobs ADD CONSTRAINT valid_job_type CHECK (
    job_type IN ('transcode', 'move', 'scan', 'apply')
);

-- Add files_affected for multi-file jobs
ALTER TABLE jobs ADD COLUMN files_affected_json TEXT;
```

---

## R3: Profile Configuration Structure

**Question**: What format and location should configuration profiles use?

**Decision**: YAML files in `~/.vpo/profiles/<name>.yaml` with structure mirroring `VPOConfig` dataclass.

**Rationale**:
- YAML is already used for VPO configuration (consistency)
- File-per-profile enables easy backup, sharing, version control
- Mirroring `VPOConfig` structure avoids translation layer

**Profile Schema**:
```yaml
# ~/.vpo/profiles/movies.yaml
name: movies
description: "Settings for movie library"

# Policy to use by default
default_policy: ~/policies/movies-policy.yaml

# Override any VPOConfig fields
behavior:
  warn_on_missing_features: false

logging:
  level: info
  file: ~/.vpo/logs/movies.log
```

**Precedence Order** (highest wins):
1. Explicit CLI flags (`--policy`, `--verbose`)
2. Profile settings (`--profile movies`)
3. Global config (`~/.vpo/config.yaml`)
4. Built-in defaults

**Alternatives Considered**:
1. **Single config file with profiles section**: Harder to share individual profiles
2. **JSON format**: Less human-readable, no comments
3. **TOML format**: Would introduce new dependency

---

## R4: Structured Logging Implementation

**Question**: What logging library and configuration approach should be used?

**Decision**: Use Python's standard `logging` module with custom JSON formatter and `RotatingFileHandler`.

**Rationale**:
- Standard library = no new dependencies
- `logging` module is well-tested and thread-safe
- `RotatingFileHandler` provides built-in size-based rotation
- Custom formatter can output JSON without external libraries

**Configuration Model**:
```python
@dataclass
class LoggingConfig:
    level: str = "info"  # debug, info, warning, error
    file: Path | None = None  # None = stderr only
    format: str = "text"  # text, json
    max_bytes: int = 10_485_760  # 10MB
    backup_count: int = 5
```

**JSON Format**:
```json
{"timestamp": "2025-11-22T10:30:00Z", "level": "INFO", "message": "Scan started", "context": {"path": "/media/movies", "files": 1000}}
```

**Alternatives Considered**:
1. **structlog**: Excellent library but adds dependency
2. **loguru**: Popular but non-standard API
3. **python-json-logger**: Dependency for something achievable with stdlib

---

## R5: Deleted File Handling Strategy

**Question**: How should incremental scan handle files that no longer exist on disk?

**Decision**: Default behavior marks files with `scan_status = 'missing'`. Optional `--prune` flag deletes records entirely.

**Rationale**:
- Marking preserves history and enables recovery if file was temporarily unavailable
- Explicit `--prune` prevents accidental data loss from network mount hiccups
- Aligns with "safe by default" principle (Constitution XVI)

**Implementation**:
```python
# During incremental scan
for db_file in existing_db_records:
    if not Path(db_file.path).exists():
        if prune_missing:
            delete_file(conn, db_file.id)
        else:
            update_scan_status(conn, db_file.id, "missing")
```

**Alternatives Considered**:
1. **Always delete**: Risky if mount is temporarily unavailable
2. **Separate "stale" table**: Overcomplicated
3. **Soft delete with timestamp**: Similar to status approach but less queryable

---

## R6: Job Purge Timing

**Question**: When should automatic job purge run?

**Decision**: Purge runs at the start of any job-creating command (scan, apply, transcode) if `auto_purge` is enabled.

**Rationale**:
- Piggybacks on existing database connection
- Avoids need for separate daemon or cron job
- Bounded execution time (DELETE with LIMIT)
- Already matches existing `JobsConfig.auto_purge` pattern

**Implementation**:
```python
def maybe_purge_old_jobs(conn: Connection, config: JobsConfig) -> int:
    if not config.auto_purge:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=config.retention_days)
    return delete_old_jobs(conn, cutoff.isoformat())
```

---

## Summary

| Topic | Decision | Key Rationale |
|-------|----------|---------------|
| Change detection | mtime + size | Already in schema, industry standard |
| Job expansion | Extend job_type | Single unified history table |
| Profile format | YAML files | Consistent with existing config |
| Logging | stdlib logging | No new dependencies |
| Missing files | Mark status, opt-in prune | Safe by default |
| Job purge | On command start | No daemon needed |

All research items resolved. Ready for Phase 1 design.
