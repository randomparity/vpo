# Research: Reporting & Export CLI

**Feature**: 011-report-export-cli
**Date**: 2025-01-22

## Executive Summary

This feature adds read-only reporting capabilities to VPO. Research confirms the existing codebase provides all necessary patterns and infrastructure. No external dependencies required beyond what's already in use.

## Research Tasks & Findings

### 1. CLI Command Structure Patterns

**Decision**: Follow existing Click group pattern from `cli/jobs.py`

**Rationale**: The jobs command group provides an excellent template with:
- Group decorator with help text
- Subcommands with `@group.command()` decorator
- Consistent option naming (`--status`, `--type`, `--since`, `--limit`, `--json`)
- Context passing via `@click.pass_context` for database connection
- Error handling via `click.ClickException`

**Alternatives Considered**:
- Single command with `--type` flag: Rejected; subcommands provide better discoverability and help text
- Separate CLI entry point: Rejected; VPO already has established `vpo` entry point

**Reference**: `src/vpo/cli/jobs.py:108-112` shows group pattern

### 2. Time Filter Parsing

**Decision**: Reuse existing `_parse_relative_date()` from `cli/jobs.py`

**Rationale**: The function already supports required formats:
- `Nd` - N days ago (e.g., "7d")
- `Nw` - N weeks ago (e.g., "2w")
- `Nh` - N hours ago (e.g., "24h")
- Falls back to ISO-8601 parsing for absolute dates

**Alternatives Considered**:
- External library (dateparser): Rejected; overkill for simple relative dates, adds dependency
- New implementation: Rejected; existing code is tested and used in production

**Action**: Extract `_parse_relative_date()` to shared location (`reports/filters.py`) for reuse

**Reference**: `src/vpo/cli/jobs.py:33-66`

### 3. Database Query Patterns

**Decision**: Extend existing DAO pattern in `db/models.py`

**Rationale**: The codebase already has:
- `get_jobs_filtered()` with status, type, since filters - exact pattern we need
- Parameterized queries preventing SQL injection
- Consistent return types (dataclass instances)

**Alternatives Considered**:
- Raw SQL in CLI layer: Rejected; violates Constitution XIII (Database Design)
- ORM like SQLAlchemy: Rejected; project uses raw sqlite3 consistently

**Implementation Notes**:
- Add query functions for files with resolution/language filters
- Add aggregation for scan summary (new/changed counts from summary_json)
- Reuse existing model classes (Job, FileRecord, etc.)

**Reference**: `src/vpo/db/models.py:1107-1165` for filter pattern

### 4. Output Formatting Patterns

**Decision**: Create new `reports/formatters.py` module with three formatters

**Rationale**: Existing code has ad-hoc formatting; centralizing enables:
- Consistent column alignment across all reports
- Proper CSV escaping (Python stdlib `csv` module handles edge cases)
- Stable JSON key ordering (`sort_keys=True`)
- Single point for terminal width detection

**Text Format Design**:
```python
# Existing pattern from jobs.py:208-222
click.echo(f"{'ID':<10} {'STATUS':<12} ...")
click.echo("-" * 100)
for row in rows:
    click.echo(formatted_row)
```

**CSV Format Design**:
```python
import csv
import io

def render_csv(rows: list[dict], columns: list[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
```

**JSON Format Design**:
```python
import json

def render_json(rows: list[dict]) -> str:
    return json.dumps(rows, indent=2, sort_keys=True, default=str)
```

**Alternatives Considered**:
- External library (tabulate, rich): Rejected; stdlib sufficient, avoids dependency
- Per-command formatting: Rejected; DRY violation, inconsistent output

### 5. File Output with Overwrite Protection

**Decision**: Use pathlib + explicit check before write

**Rationale**: Simple and follows existing patterns:
```python
path = Path(output_path)
if path.exists() and not force:
    raise click.ClickException(f"File exists: {path}. Use --force to overwrite.")
path.write_text(content, encoding="utf-8")
```

**Alternatives Considered**:
- Atomic write with temp file: Considered; may add for large reports in future
- Append mode: Rejected; reports are complete snapshots, not logs

### 6. Timestamp Display (UTC to Local)

**Decision**: Convert at presentation layer per Constitution I

**Rationale**: All timestamps stored as ISO-8601 UTC strings. Display conversion:
```python
from datetime import datetime, timezone

def format_timestamp_local(utc_iso: str) -> str:
    """Convert UTC ISO timestamp to local time display."""
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    local_dt = dt.astimezone()  # Convert to local timezone
    return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
```

**Display Format**: `2025-01-22 14:30:00 EST` (includes timezone abbreviation)

### 7. Duration Formatting

**Decision**: Human-readable format following existing patterns

**Implementation**:
```python
def format_duration(seconds: float | None) -> str:
    """Format duration as human-readable string."""
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"
```

### 8. Library Report Resolution Detection

**Decision**: Derive resolution category from track dimensions

**Implementation**:
```python
def get_resolution_category(width: int | None, height: int | None) -> str:
    """Categorize resolution from dimensions."""
    if width is None or height is None:
        return "unknown"
    if height >= 2160:
        return "4K"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    if height >= 480:
        return "480p"
    return "SD"
```

**Filter Values**: `4K`, `1080p`, `720p`, `480p`, `SD`

### 9. Scan Summary Extraction

**Decision**: Parse `summary_json` field from scan jobs

**Rationale**: The jobs table stores scan summaries as JSON:
```json
{
  "files_scanned": 150,
  "files_new": 10,
  "files_changed": 5,
  "files_unchanged": 135
}
```

**Implementation**: Parse JSON, handle missing/malformed gracefully:
```python
def extract_scan_summary(job: Job) -> dict:
    if not job.summary_json:
        return {"files_scanned": 0, "files_new": 0, "files_changed": 0}
    try:
        return json.loads(job.summary_json)
    except json.JSONDecodeError:
        return {"files_scanned": 0, "files_new": 0, "files_changed": 0}
```

### 10. Result Limiting

**Decision**: Default 100 rows, `--limit N` override, `--no-limit` flag

**Implementation**:
```python
@click.option("--limit", "-n", type=int, default=100, help="Max rows (default: 100)")
@click.option("--no-limit", is_flag=True, help="Return all rows")
def report_cmd(limit: int, no_limit: bool):
    effective_limit = None if no_limit else limit
    rows = query_function(limit=effective_limit)
```

**Alternatives Considered**:
- No default limit: Rejected; could overwhelm terminal with large libraries
- Pagination: Deferred; CLI use case typically wants single output

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| click | Existing | CLI framework |
| sqlite3 | Stdlib | Database access |
| csv | Stdlib | CSV formatting |
| json | Stdlib | JSON formatting |
| pathlib | Stdlib | File output |
| datetime | Stdlib | Timestamp handling |

**No new dependencies required.**

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Large result sets slow performance | Medium | Low | Default 100-row limit; indexed queries |
| Missing scan summary data in older jobs | Medium | Low | Graceful fallback to zeros |
| Unicode in file paths breaks CSV | Low | Medium | Python csv module handles UTF-8 correctly |

## Open Questions

None - all clarifications resolved in specification phase.
