"""CLI commands for language analysis management.

This module provides commands for running language analysis on audio tracks,
viewing analysis status, and managing cached results independently of the
scan workflow.
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import click

from vpo.db import (
    FileRecord,
    get_file_by_id,
    get_file_by_path,
    get_tracks_for_file,
)
from vpo.db.queries.helpers import _escape_like_pattern
from vpo.plugin import get_default_registry

logger = logging.getLogger(__name__)


@dataclass
class AnalysisRunResult:
    """Result of running analysis on a single file."""

    file_path: str
    success: bool
    track_count: int
    analyzed_count: int
    cached_count: int
    error: str | None = None
    duration_ms: int = 0


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


def _check_plugin_available() -> bool:
    """Check if transcription plugin is available.

    Returns:
        True if plugin is available, False otherwise.
    """
    try:
        registry = get_default_registry()
        # Check if any transcription plugin is registered
        from vpo.transcription.coordinator import (
            TranscriptionCoordinator,
        )

        coordinator = TranscriptionCoordinator(registry)
        return coordinator.is_available()
    except Exception:
        return False


def _resolve_files_from_paths(
    conn,
    paths: tuple[str, ...],
    recursive: bool,
) -> tuple[list[FileRecord], list[str]]:
    """Resolve paths to FileRecords from the database.

    Args:
        conn: Database connection.
        paths: Paths to files or directories.
        recursive: Whether to include files from subdirectories.

    Returns:
        Tuple of (valid files, paths not found).
    """
    files: list[FileRecord] = []
    not_found: list[str] = []

    for path_str in paths:
        path = Path(path_str).resolve()

        if path.is_file():
            # Single file - look up in database
            record = get_file_by_path(conn, str(path))
            if record:
                files.append(record)
            else:
                not_found.append(str(path))
        elif path.is_dir():
            # Directory - find all files with matching path prefix
            from vpo.db.queries import get_file_ids_by_path_prefix

            file_ids = get_file_ids_by_path_prefix(
                conn, str(path), include_subdirs=recursive
            )
            for file_id in file_ids:
                record = get_file_by_id(conn, file_id)
                if record:
                    files.append(record)
            if not file_ids:
                not_found.append(str(path))
        else:
            not_found.append(str(path))

    return files, not_found


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

    Examples:

        # Analyze a single file
        vpo analyze-language run movie.mkv

        # Analyze with force re-analysis
        vpo analyze-language run movie.mkv --force

        # Analyze a directory recursively
        vpo analyze-language run /media/movies/ -R

        # Output as JSON
        vpo analyze-language run movie.mkv --json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        click.echo("Error: Database connection unavailable.", err=True)
        raise SystemExit(1)

    # Check plugin availability
    if not _check_plugin_available():
        click.echo(
            "Error: Whisper transcription plugin not installed or not configured.",
            err=True,
        )
        click.echo(
            "Install with: pip install vpo-whisper-transcriber",
            err=True,
        )
        raise SystemExit(1)

    # Resolve files from paths
    files, not_found = _resolve_files_from_paths(conn, paths, recursive)

    # Warn about not-found paths
    for path in not_found:
        click.echo(
            f"Warning: '{path}' not found in database. Run 'vpo scan' first.", err=True
        )

    if not files:
        click.echo("Error: No valid files found to analyze.", err=True)
        raise SystemExit(2)

    # Run analysis on each file
    results: list[AnalysisRunResult] = []
    total_files = len(files)
    successful = 0
    failed = 0
    cached = 0
    tracks_analyzed = 0
    errors: list[tuple[str, str]] = []

    def process_files(file_iter):
        """Process files from iterator, accumulating results."""
        nonlocal successful, failed, cached, tracks_analyzed
        for file_record in file_iter:
            result = _run_analysis_for_file(conn, file_record, force)
            results.append(result)

            if result.success:
                successful += 1
                tracks_analyzed += result.analyzed_count
                cached += result.cached_count
            else:
                failed += 1
                if result.error:
                    errors.append((result.file_path, result.error))

    # Use progress bar only when not in JSON mode
    if output_json:
        process_files(files)
    else:
        with click.progressbar(
            files,
            label="Analyzing files",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda f: f.filename if f else "",
        ) as progress_files:
            process_files(progress_files)

    # Output results
    if output_json:
        output = {
            "total_files": total_files,
            "successful": successful,
            "failed": failed,
            "cached": cached,
            "tracks_analyzed": tracks_analyzed,
            "results": [asdict(r) for r in results],
            "errors": [{"path": p, "error": e} for p, e in errors],
        }
        click.echo(json.dumps(output, indent=2))
    else:
        _format_run_results(
            results, total_files, successful, failed, cached, tracks_analyzed, errors
        )

    # Exit code based on results
    if failed == total_files:
        raise SystemExit(2)  # Complete failure
    elif failed > 0:
        raise SystemExit(1)  # Partial failure


def _run_analysis_for_file(
    conn,
    file_record: FileRecord,
    force: bool,
) -> AnalysisRunResult:
    """Run language analysis on a single file.

    Args:
        conn: Database connection.
        file_record: File to analyze.
        force: Whether to re-analyze even if cached.

    Returns:
        AnalysisRunResult with analysis outcome.
    """
    import time

    from vpo.language_analysis import (
        LanguageAnalysisError,
        analyze_track_languages,
        get_cached_analysis,
        persist_analysis_result,
    )
    from vpo.transcription.coordinator import (
        TranscriptionCoordinator,
    )

    start_time = time.monotonic()
    file_path = Path(file_record.path)
    tracks = get_tracks_for_file(conn, file_record.id)

    # Filter to audio tracks
    audio_tracks = [t for t in tracks if t.track_type == "audio"]

    if not audio_tracks:
        return AnalysisRunResult(
            file_path=str(file_path),
            success=True,  # Not an error, just no audio
            track_count=0,
            analyzed_count=0,
            cached_count=0,
            error="No audio tracks found",
            duration_ms=int((time.monotonic() - start_time) * 1000),
        )

    analyzed = 0
    cached_count = 0
    errors: list[str] = []

    # Get transcription coordinator
    try:
        registry = get_default_registry()
        coordinator = TranscriptionCoordinator(registry)
        transcriber_plugin = coordinator.get_default_plugin()
        if not transcriber_plugin:
            return AnalysisRunResult(
                file_path=str(file_path),
                success=False,
                track_count=len(audio_tracks),
                analyzed_count=0,
                cached_count=0,
                error="Transcription plugin not available",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
        transcriber = transcriber_plugin.instance
    except Exception as e:
        return AnalysisRunResult(
            file_path=str(file_path),
            success=False,
            track_count=len(audio_tracks),
            analyzed_count=0,
            cached_count=0,
            error=f"Failed to get transcription plugin: {e}",
            duration_ms=int((time.monotonic() - start_time) * 1000),
        )

    for track in audio_tracks:
        if track.id is None:
            continue

        file_hash = file_record.content_hash

        # Check cache unless force is set or hash is unavailable
        if not force and file_hash is not None:
            cached_result = get_cached_analysis(conn, track.id, file_hash)
            if cached_result is not None:
                cached_count += 1
                continue

        # Run analysis
        try:
            if track.duration_seconds is None:
                errors.append(f"Track {track.track_index}: missing duration")
                continue

            result = analyze_track_languages(
                file_path=file_path,
                track_index=track.track_index,
                track_id=track.id,
                track_duration=track.duration_seconds,
                file_hash=file_hash or "",
                transcriber=transcriber,
            )
            persist_analysis_result(conn, result)
            analyzed += 1

        except LanguageAnalysisError as e:
            errors.append(f"Track {track.track_index}: {e}")
        except Exception as e:
            errors.append(f"Track {track.track_index}: {type(e).__name__}: {e}")

    duration_ms = int((time.monotonic() - start_time) * 1000)

    if errors and analyzed == 0 and cached_count == 0:
        return AnalysisRunResult(
            file_path=str(file_path),
            success=False,
            track_count=len(audio_tracks),
            analyzed_count=analyzed,
            cached_count=cached_count,
            error="; ".join(errors),
            duration_ms=duration_ms,
        )

    return AnalysisRunResult(
        file_path=str(file_path),
        success=True,
        track_count=len(audio_tracks),
        analyzed_count=analyzed,
        cached_count=cached_count,
        error=None if not errors else "; ".join(errors),
        duration_ms=duration_ms,
    )


def _format_run_results(
    results: list[AnalysisRunResult],
    total_files: int,
    successful: int,
    failed: int,
    cached: int,
    tracks_analyzed: int,
    errors: list[tuple[str, str]],
) -> None:
    """Format and output run results in human-readable format."""
    click.echo("")

    # Individual file results
    for result in results:
        path = Path(result.file_path).name
        if result.success:
            if result.track_count == 0:
                click.echo(f"  {path}: no audio tracks")
            elif result.cached_count > 0 and result.analyzed_count == 0:
                cached_msg = f"{result.cached_count} tracks cached (use --force)"
                click.echo(f"  {path}: {cached_msg}")
            else:
                ac = result.analyzed_count
                cc = result.cached_count
                click.echo(f"  {path}: {ac} analyzed, {cc} cached")
        else:
            click.echo(f"  {path}: error - {result.error}")

    # Summary
    click.echo("")
    summary_msg = (
        f"Summary: {successful} files processed, {tracks_analyzed} tracks analyzed, "
        f"{cached} cached, {failed} failed"
    )
    click.echo(summary_msg)

    if errors:
        click.echo("")
        click.echo("Errors:")
        for path, error in errors[:5]:
            click.echo(f"  {Path(path).name}: {error}")
        if len(errors) > 5:
            click.echo(f"  ... and {len(errors) - 5} more errors")


@analyze_language_group.command("status")
@click.argument("path", required=False, type=click.Path())
@click.option(
    "--filter",
    "filter_type",
    type=click.Choice(["all", "multi-language", "single-language", "pending"]),
    default="all",
    help="Filter files by classification",
)
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

    Examples:

        # View library summary
        vpo analyze-language status

        # View details for a specific file
        vpo analyze-language status movie.mkv

        # Filter to multi-language files
        vpo analyze-language status --filter multi-language

        # Output as JSON
        vpo analyze-language status --json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        click.echo("Error: Database connection unavailable.", err=True)
        raise SystemExit(1)

    from vpo.db.views import (
        get_analysis_status_summary,
        get_file_analysis_detail,
        get_files_analysis_status,
    )

    if path is None:
        # Show library-wide summary
        summary = get_analysis_status_summary(conn)

        if filter_type != "all":
            # Get filtered file list
            files = get_files_analysis_status(
                conn,
                filter_classification=filter_type,
                limit=limit,
            )
            if output_json:
                output = {
                    "summary": asdict(summary),
                    "filter": filter_type,
                    "files": [asdict(f) for f in files],
                }
                click.echo(json.dumps(output, indent=2))
            else:
                _format_status_summary(summary)
                _format_file_list(files, filter_type, limit)
        else:
            if output_json:
                click.echo(json.dumps(asdict(summary), indent=2))
            else:
                _format_status_summary(summary)
    else:
        # Show detail for specific path
        resolved_path = str(Path(path).resolve())
        detail = get_file_analysis_detail(conn, resolved_path)

        if detail is None:
            click.echo(f"Error: No analysis found for '{path}'", err=True)
            raise SystemExit(1)

        if output_json:
            click.echo(json.dumps([asdict(d) for d in detail], indent=2))
        else:
            _format_file_detail(resolved_path, detail)


def _format_status_summary(summary) -> None:
    """Format and output status summary in human-readable format."""
    click.echo("")
    click.echo("Language Analysis Status")
    click.echo("=" * 50)
    click.echo("")
    click.echo("Library Summary:")
    click.echo(f"  Total files:      {summary.total_files:,}")
    click.echo(f"  Total tracks:     {summary.total_tracks:,}")

    if summary.total_tracks > 0:
        analyzed_pct = (summary.analyzed_tracks / summary.total_tracks) * 100
        pending_pct = (summary.pending_tracks / summary.total_tracks) * 100
        click.echo(
            f"  Analyzed:         {summary.analyzed_tracks:,} ({analyzed_pct:.1f}%)"
        )
        click.echo(
            f"  Pending:          {summary.pending_tracks:,} ({pending_pct:.1f}%)"
        )
    else:
        click.echo(f"  Analyzed:         {summary.analyzed_tracks:,}")
        click.echo(f"  Pending:          {summary.pending_tracks:,}")

    click.echo("")
    click.echo("Classification:")
    if summary.analyzed_tracks > 0:
        multi_pct = (summary.multi_language_count / summary.analyzed_tracks) * 100
        single_pct = (summary.single_language_count / summary.analyzed_tracks) * 100
        multi_count = summary.multi_language_count
        single_count = summary.single_language_count
        click.echo(f"  Multi-language:   {multi_count:,} tracks ({multi_pct:.1f}%)")
        click.echo(f"  Single-language:  {single_count:,} tracks ({single_pct:.1f}%)")
    else:
        click.echo(f"  Multi-language:   {summary.multi_language_count:,} tracks")
        click.echo(f"  Single-language:  {summary.single_language_count:,} tracks")

    click.echo("")


def _format_file_detail(file_path: str, details: list) -> None:
    """Format and output file detail in human-readable format."""
    click.echo("")
    click.echo(f"Language Analysis: {file_path}")
    click.echo("=" * 60)
    click.echo("")

    if not details:
        click.echo("No analysis results found for this file.")
        return

    for detail in details:
        lang = detail.language or "unknown"
        click.echo(f"Track {detail.track_index} (Audio - {lang}):")
        click.echo(f"  Classification: {detail.classification}")
        pct = detail.primary_percentage * 100
        click.echo(f"  Primary: {detail.primary_language} ({pct:.1f}%)")
        if detail.secondary_languages:
            click.echo(f"  Secondary: {detail.secondary_languages}")
        click.echo(f"  Analyzed: {detail.analyzed_at}")
        click.echo("")


def _format_file_list(files: list, filter_type: str, limit: int) -> None:
    """Format and output filtered file list."""
    if not files:
        click.echo(f"No files match filter: {filter_type}")
        return

    label_map = {
        "multi-language": "Multi-language files",
        "single-language": "Single-language files",
        "pending": "Files pending analysis",
    }
    click.echo(f"{label_map.get(filter_type, 'Files')} (--filter {filter_type}):")
    click.echo("")

    for f in files:
        click.echo(f"  {f.file_path}")
        click.echo(f"    {f.track_count} tracks, {f.analyzed_count} analyzed")

    if len(files) >= limit:
        click.echo(f"\nShowing {limit} files (use --limit to show more)")


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

    Examples:

        # Clear results for a specific file
        vpo analyze-language clear movie.mkv --yes

        # Clear results for a directory
        vpo analyze-language clear /media/movies/ -R --yes

        # Preview what would be cleared
        vpo analyze-language clear --all --dry-run

        # Clear all results
        vpo analyze-language clear --all --yes
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        click.echo("Error: Database connection unavailable.", err=True)
        raise SystemExit(1)

    if not path and not clear_all:
        click.echo("Error: Specify a PATH or use --all to clear all results.", err=True)
        raise SystemExit(2)

    from vpo.db.queries import (
        delete_all_analysis,
        delete_analysis_by_path_prefix,
        delete_analysis_for_file,
    )

    # Count affected results
    files_affected = 0
    tracks_affected = 0

    if clear_all:
        files_affected, tracks_affected = _count_affected_results(
            conn, None, recursive=True
        )
    elif path:
        resolved_path = str(Path(path).resolve())
        files_affected, tracks_affected = _count_affected_results(
            conn, resolved_path, recursive
        )

    if tracks_affected == 0:
        if output_json:
            click.echo(
                json.dumps(
                    {
                        "dry_run": dry_run,
                        "files_affected": 0,
                        "tracks_cleared": 0,
                        "success": True,
                    }
                )
            )
        else:
            click.echo("No analysis results to clear.")
        return

    # Dry run output
    if dry_run:
        if output_json:
            click.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "files_affected": files_affected,
                        "tracks_cleared": tracks_affected,
                        "success": True,
                    }
                )
            )
        else:
            click.echo("Would clear analysis results:")
            click.echo(f"  Files affected: {files_affected}")
            click.echo(f"  Tracks affected: {tracks_affected}")
            click.echo("")
            click.echo("Use without --dry-run to proceed.")
        return

    # Confirmation
    if not yes:
        click.echo("This will clear language analysis results for:")
        click.echo(f"  Files: {files_affected}")
        click.echo(f"  Tracks: {tracks_affected}")
        click.echo("")
        if not click.confirm("Continue?"):
            click.echo("Operation cancelled.")
            raise SystemExit(2)

    # Execute deletion
    if clear_all:
        deleted = delete_all_analysis(conn)
    elif path:
        resolved_path = str(Path(path).resolve())
        if Path(resolved_path).is_file():
            # Single file
            file_record = get_file_by_path(conn, resolved_path)
            if file_record:
                deleted = delete_analysis_for_file(conn, file_record.id)
            else:
                deleted = 0
        else:
            # Directory
            deleted = delete_analysis_by_path_prefix(conn, resolved_path)
    else:
        deleted = 0

    if output_json:
        click.echo(
            json.dumps(
                {
                    "dry_run": False,
                    "files_affected": files_affected,
                    "tracks_cleared": deleted,
                    "success": True,
                }
            )
        )
    else:
        click.echo(f"Cleared {deleted} analysis results from {files_affected} files.")


def _count_affected_results(
    conn,
    path: str | None,
    recursive: bool,
) -> tuple[int, int]:
    """Count files and tracks that would be affected by a clear operation.

    Args:
        conn: Database connection.
        path: Path to file or directory, or None for all.
        recursive: Whether to include subdirectories.

    Returns:
        Tuple of (files_affected, tracks_affected).
    """
    base_query = """
        SELECT
            COUNT(DISTINCT f.id) as files,
            COUNT(DISTINCT lar.id) as tracks
        FROM files f
        JOIN tracks t ON f.id = t.file_id
        JOIN language_analysis_results lar ON t.id = lar.track_id
    """

    if path is None:
        # Count all
        cursor = conn.execute(base_query)
    elif Path(path).is_file():
        # Single file
        cursor = conn.execute(base_query + " WHERE f.path = ?", (path,))
    elif recursive:
        # Directory recursive
        escaped_path = _escape_like_pattern(path)
        pattern = escaped_path + "%"
        cursor = conn.execute(
            base_query + " WHERE f.path LIKE ? ESCAPE '\\'", (pattern,)
        )
    else:
        # Directory non-recursive: exclude subdirectories
        escaped_path = _escape_like_pattern(path)
        pattern = escaped_path + "/%"
        where_clause = (
            " WHERE f.path LIKE ? ESCAPE '\\' AND f.path NOT LIKE ? ESCAPE '\\'"
        )
        cursor = conn.execute(
            base_query + where_clause,
            (pattern, pattern + "/%"),
        )

    row = cursor.fetchone()
    return row[0] or 0, row[1] or 0
