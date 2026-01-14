# Quickstart: Analyze-Language CLI Commands

**Feature**: 042-analyze-language-cli
**Date**: 2025-12-04

## Implementation Order

1. **Database queries** (db/views.py, db/queries.py)
2. **CLI module** (cli/analyze_language.py)
3. **Command registration** (cli/__init__.py)
4. **Unit tests** (tests/unit/cli/test_analyze_language.py)
5. **Integration tests** (tests/integration/test_analyze_language_cli.py)
6. **Documentation update** (docs/usage/multi-language-detection.md)

## Step 1: Add Database Queries

### views.py additions

```python
# src/vpo/db/views.py

@dataclass
class AnalysisStatusSummary:
    """Summary of language analysis status."""
    total_files: int
    total_tracks: int
    analyzed_tracks: int
    pending_tracks: int
    multi_language_count: int
    single_language_count: int


def get_analysis_status_summary(conn: sqlite3.Connection) -> AnalysisStatusSummary:
    """Get library-wide analysis status summary."""
    cursor = conn.execute("""
        SELECT
            (SELECT COUNT(DISTINCT file_id) FROM tracks WHERE type = 'audio') as total_files,
            (SELECT COUNT(*) FROM tracks WHERE type = 'audio') as total_tracks,
            (SELECT COUNT(*) FROM language_analysis_results) as analyzed_tracks,
            (SELECT COUNT(*) FROM language_analysis_results WHERE classification = 'MULTI_LANGUAGE') as multi_language_count,
            (SELECT COUNT(*) FROM language_analysis_results WHERE classification = 'SINGLE_LANGUAGE') as single_language_count
    """)
    row = cursor.fetchone()
    return AnalysisStatusSummary(
        total_files=row[0],
        total_tracks=row[1],
        analyzed_tracks=row[2],
        pending_tracks=row[1] - row[2],
        multi_language_count=row[3],
        single_language_count=row[4],
    )
```

### queries.py additions

```python
# src/vpo/db/queries.py

def delete_analysis_for_file(conn: sqlite3.Connection, file_id: int) -> int:
    """Delete all analysis results for a file's tracks."""
    cursor = conn.execute("""
        DELETE FROM language_analysis_results
        WHERE track_id IN (SELECT id FROM tracks WHERE file_id = ?)
    """, (file_id,))
    conn.commit()
    return cursor.rowcount


def delete_all_analysis(conn: sqlite3.Connection) -> int:
    """Delete all language analysis results."""
    cursor = conn.execute("DELETE FROM language_analysis_results")
    count = cursor.rowcount
    conn.execute("DELETE FROM language_segments")
    conn.commit()
    return count
```

## Step 2: Create CLI Module

```python
# src/vpo/cli/analyze_language.py

"""CLI commands for language analysis management."""

import logging
from pathlib import Path

import click

from vpo.db import get_file_by_path
from vpo.db.views import get_analysis_status_summary
from vpo.db.queries import delete_analysis_for_file, delete_all_analysis
from vpo.language_analysis import (
    analyze_track_languages,
    get_cached_analysis,
    format_human,
    format_json,
    LanguageAnalysisError,
)

logger = logging.getLogger(__name__)


@click.group("analyze-language")
def analyze_language_group() -> None:
    """Analyze and manage multi-language detection results.

    Run language analysis on files, view analysis status, and manage
    cached results.

    Examples:

        # Analyze a single file
        vpo analyze-language run movie.mkv

        # View library-wide status
        vpo analyze-language status

        # Clear results for a directory
        vpo analyze-language clear /media/movies/ --yes
    """
    pass


@analyze_language_group.command("run")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, help="Re-analyze even if cached")
@click.option("--recursive", "-R", is_flag=True, help="Process directories recursively")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def run_command(
    ctx: click.Context,
    paths: tuple[str, ...],
    force: bool,
    recursive: bool,
    output_json: bool,
) -> None:
    """Run language analysis on files.

    PATHS can be files or directories. Files must exist in the VPO database
    (run 'vpo scan' first).
    """
    conn = ctx.obj.get("db_conn")
    if not conn:
        click.echo("Error: Database connection unavailable.", err=True)
        raise SystemExit(1)

    # Check plugin availability
    try:
        from vpo.transcription.coordinator import get_transcription_plugin
        plugin = get_transcription_plugin()
        if not plugin:
            raise RuntimeError("No plugin")
    except Exception:
        click.echo("Error: Whisper transcription plugin not installed.", err=True)
        click.echo("Install with: pip install vpo-whisper-transcriber", err=True)
        raise SystemExit(1)

    # Resolve files from paths
    # ... implementation continues


@analyze_language_group.command("status")
@click.argument("path", required=False, type=click.Path())
@click.option("--filter", "filter_type", type=click.Choice(["all", "multi-language", "single-language", "pending"]), default="all")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--limit", "-n", default=50, help="Maximum files to show")
@click.pass_context
def status_command(
    ctx: click.Context,
    path: str | None,
    filter_type: str,
    output_json: bool,
    limit: int,
) -> None:
    """View language analysis status.

    Without PATH, shows library summary. With PATH, shows detailed
    analysis for that file or directory.
    """
    conn = ctx.obj.get("db_conn")
    if not conn:
        click.echo("Error: Database connection unavailable.", err=True)
        raise SystemExit(1)

    if path is None:
        # Show library summary
        summary = get_analysis_status_summary(conn)
        # ... format and display


@analyze_language_group.command("clear")
@click.argument("path", required=False, type=click.Path())
@click.option("--all", "clear_all", is_flag=True, help="Clear all results")
@click.option("--recursive", "-R", is_flag=True, help="Include subdirectories")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", "-n", is_flag=True, help="Preview without deleting")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def clear_command(
    ctx: click.Context,
    path: str | None,
    clear_all: bool,
    recursive: bool,
    yes: bool,
    dry_run: bool,
    output_json: bool,
) -> None:
    """Clear cached analysis results.

    Specify PATH for a file or directory, or use --all to clear everything.
    """
    conn = ctx.obj.get("db_conn")

    if not path and not clear_all:
        click.echo("Error: Specify PATH or use --all to clear all results.", err=True)
        raise SystemExit(2)

    # ... implementation continues
```

## Step 3: Register Command Group

```python
# src/vpo/cli/__init__.py

# Add to imports in _register_commands():
from vpo.cli.analyze_language import analyze_language_group

# Add to command registration:
main.add_command(analyze_language_group)
```

## Step 4: Unit Tests

```python
# tests/unit/cli/test_analyze_language.py

import pytest
from click.testing import CliRunner

from vpo.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestAnalyzeLanguageRun:
    def test_run_requires_paths(self, runner):
        result = runner.invoke(main, ["analyze-language", "run"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_run_file_not_in_database(self, runner, tmp_path):
        test_file = tmp_path / "test.mkv"
        test_file.touch()
        result = runner.invoke(main, ["analyze-language", "run", str(test_file)])
        assert "not found in database" in result.output


class TestAnalyzeLanguageStatus:
    def test_status_shows_summary(self, runner, mock_db):
        result = runner.invoke(main, ["analyze-language", "status"])
        assert result.exit_code == 0
        assert "Language Analysis Status" in result.output


class TestAnalyzeLanguageClear:
    def test_clear_requires_path_or_all(self, runner):
        result = runner.invoke(main, ["analyze-language", "clear"])
        assert result.exit_code == 2
        assert "Specify PATH or use --all" in result.output

    def test_clear_dry_run(self, runner, mock_db):
        result = runner.invoke(main, ["analyze-language", "clear", "--all", "--dry-run"])
        assert result.exit_code == 0
        assert "Would clear" in result.output
```

## Step 5: Integration Tests

```python
# tests/integration/test_analyze_language_cli.py

import pytest
from click.testing import CliRunner

from vpo.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def scanned_library(tmp_path, runner):
    """Create a library with scanned files."""
    # Setup test files and scan them
    ...


class TestAnalyzeLanguageIntegration:
    def test_full_workflow(self, runner, scanned_library):
        """Test run → status → clear workflow."""
        # Run analysis
        result = runner.invoke(main, [
            "analyze-language", "run",
            str(scanned_library / "test.mkv")
        ])
        assert result.exit_code == 0

        # Check status
        result = runner.invoke(main, ["analyze-language", "status"])
        assert "Analyzed:" in result.output

        # Clear results
        result = runner.invoke(main, [
            "analyze-language", "clear",
            "--all", "--yes"
        ])
        assert result.exit_code == 0
```

## Testing Strategy

1. **Unit tests**: Mock database, test CLI argument parsing and output formatting
2. **Integration tests**: Use real database with test fixtures from `tests/fixtures/audio/`
3. **Manual testing**: Verify against real media files

## Dependencies

No new dependencies. Uses existing:
- `click` (CLI framework)
- `language_analysis` module (analysis logic)
- `db` module (database queries)

## Estimated Effort

| Component | Complexity | Estimated Time |
|-----------|------------|----------------|
| Database queries | Low | 1 hour |
| CLI module | Medium | 3 hours |
| Unit tests | Low | 2 hours |
| Integration tests | Medium | 2 hours |
| Documentation | Low | 1 hour |
| **Total** | | **9 hours** |
