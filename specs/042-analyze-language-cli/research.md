# Research: Analyze-Language CLI Commands

**Feature**: 042-analyze-language-cli
**Date**: 2025-12-04

## Overview

This document captures research findings for implementing the `vpo analyze-language` CLI command group. Since this feature builds entirely on existing VPO infrastructure, research focuses on established patterns rather than technology choices.

## CLI Group Pattern

### Decision: Follow `stats_group` pattern

**Rationale**: The `stats_group` in `cli/stats.py` provides the closest analogue - a command group with multiple subcommands (`summary`, `recent`, `policies`, `purge`) that query and manage database records.

**Alternatives Considered**:
- `jobs_group` pattern: More complex, includes background job management not needed here
- `plugins` pattern: Different use case (discovery and registration)
- Standalone commands: Would clutter top-level `vpo --help`

### Implementation Pattern

```python
@click.group("analyze-language")
def analyze_language_group() -> None:
    """Analyze and manage multi-language detection results."""
    pass

@analyze_language_group.command("run")
def run_command(...) -> None:
    """Run language analysis on files."""
    pass

@analyze_language_group.command("status")
def status_command(...) -> None:
    """View language analysis status."""
    pass

@analyze_language_group.command("clear")
def clear_command(...) -> None:
    """Clear cached analysis results."""
    pass
```

## Database Query Patterns

### Decision: Add queries to existing modules

**Rationale**: VPO separates queries by purpose:
- `db/queries.py`: CRUD operations (insert, update, delete, get by key)
- `db/views.py`: Aggregated/complex queries for UI/CLI display

New queries follow this pattern:
- `get_analysis_summary()` → `views.py` (aggregation)
- `get_files_with_analysis()` → `views.py` (filtered list)
- `delete_analysis_for_file()` → `queries.py` (CRUD)
- `delete_all_analysis()` → `queries.py` (CRUD)

**Alternatives Considered**:
- New `db/language_analysis_queries.py`: Would fragment the query layer
- Put all in service.py: Violates separation of concerns

## Existing Service Functions

### Available from `language_analysis` module:

| Function | Purpose | Used By |
|----------|---------|---------|
| `analyze_track_languages()` | Run analysis on a track | `run` command |
| `get_cached_analysis()` | Check cache | `run` command (skip if cached) |
| `invalidate_analysis_cache()` | Clear cache for track | `clear` command |
| `persist_analysis_result()` | Store results | `run` command |
| `format_human()` | Human-readable output | `status` command |
| `format_json()` | JSON output | `status --json` |

### Gap Analysis

**Missing functions needed**:
1. `get_analysis_status_summary(conn)` - Count total/analyzed/pending files
2. `get_files_with_analysis(conn, filter)` - List files by analysis state
3. `delete_analysis_for_files(conn, file_ids)` - Bulk delete by file
4. `get_file_ids_in_directory(conn, path)` - Support directory-based clear

## Progress Reporting

### Decision: Use `click.progressbar` for multi-file operations

**Rationale**: Consistent with existing VPO commands (`scan`, `process`).

```python
with click.progressbar(files, label="Analyzing") as bar:
    for file in bar:
        analyze_track_languages(...)
```

**Alternatives Considered**:
- Rich progress bars: Would add dependency
- Custom progress: Inconsistent UX

## Error Handling

### Decision: Fail-fast with user-friendly messages

**Rationale**: CLI users expect immediate feedback. Analysis errors should be reported per-file without stopping batch operations.

```python
for file in files:
    try:
        analyze_track_languages(file, ...)
    except LanguageAnalysisError as e:
        click.echo(f"Error analyzing {file}: {e}", err=True)
        failed_count += 1
        continue
```

**Plugin Unavailable Check**:
```python
try:
    plugin = get_transcription_plugin()
except TranscriptionPluginError:
    click.echo("Error: Whisper transcription plugin not installed.", err=True)
    click.echo("Install with: pip install vpo-whisper-transcriber", err=True)
    raise SystemExit(1)
```

## Output Formatting

### Decision: Human-readable default, JSON optional

**Rationale**: Follows VPO convention (e.g., `vpo stats summary` vs `vpo stats summary --format json`).

| Command | Default | JSON Flag |
|---------|---------|-----------|
| `run` | Progress + summary | `--json` for structured results |
| `status` | Table/summary | `--json` for programmatic use |
| `clear` | Confirmation + count | `--json` for scripting |

## Confirmation Pattern

### Decision: Use `click.confirm()` for destructive operations

**Rationale**: Follows `vpo stats purge` pattern.

```python
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without deleting")
def clear_command(yes: bool, dry_run: bool, ...):
    if dry_run:
        click.echo(f"Would delete {count} analysis results")
        return

    if not yes:
        if not click.confirm(f"Delete {count} analysis results?"):
            return

    # Proceed with deletion
```

## File Resolution

### Decision: Resolve paths via database lookup

**Rationale**: Spec requires files to exist in database. Use `get_file_by_path()` pattern.

```python
def resolve_file(conn, path: Path) -> FileRecord | None:
    """Resolve path to database record."""
    if path.is_file():
        return get_file_by_path(conn, str(path))
    return None

def resolve_directory(conn, path: Path, recursive: bool) -> list[FileRecord]:
    """Get all files in directory from database."""
    pattern = f"{path}%" if recursive else f"{path}/*"
    return get_files_by_path_pattern(conn, pattern)
```

## Summary

No NEEDS CLARIFICATION items remain. All design decisions leverage existing VPO patterns:

1. **CLI structure**: `click.group` with subcommands (stats_group pattern)
2. **Database queries**: Split between views.py and queries.py
3. **Service layer**: Reuse existing language_analysis functions
4. **Progress**: `click.progressbar` for multi-file ops
5. **Output**: Human default, JSON optional
6. **Confirmation**: `--yes`/`--dry-run` for destructive ops
