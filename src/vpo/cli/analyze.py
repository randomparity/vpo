"""CLI commands for analysis operations.

This module provides commands for analyzing audio tracks:
- analyze classify: Classify tracks as original/dubbed/commentary
- analyze language: Detect multi-language content
- analyze status: View analysis status
- analyze clear: Clear cached analysis results

Merged from classify.py and analyze_language.py.
"""

import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import click

from vpo.cli import get_db_conn_from_context
from vpo.cli.exit_codes import ExitCode
from vpo.db import (
    FileRecord,
    get_file_by_id,
    get_file_by_path,
    get_tracks_for_file,
)
from vpo.db.queries import (
    delete_track_classification,
    get_classifications_for_file,
)
from vpo.db.queries.helpers import _escape_like_pattern
from vpo.plugin import get_default_registry
from vpo.track_classification.models import ClassificationError
from vpo.track_classification.service import classify_file_tracks

logger = logging.getLogger(__name__)


# =============================================================================
# Shared Utilities
# =============================================================================


def _check_plugin_available() -> bool:
    """Check if transcription plugin is available.

    Returns:
        True if plugin is available, False otherwise.
    """
    try:
        registry = get_default_registry()
        from vpo.transcription.coordinator import TranscriptionCoordinator

        coordinator = TranscriptionCoordinator(registry)
        return coordinator.is_available()
    except Exception as e:
        logger.debug("Transcription plugin check failed: %s", e, exc_info=True)
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
            record = get_file_by_path(conn, str(path))
            if record:
                files.append(record)
            else:
                not_found.append(str(path))
        elif path.is_dir():
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


# =============================================================================
# Classify Utilities
# =============================================================================


def _color_for_status(status: str) -> str:
    """Get color for status value."""
    colors = {
        "original": "green",
        "dubbed": "yellow",
        "commentary": "cyan",
        "main": "white",
        "unknown": "bright_black",
    }
    return colors.get(status.casefold(), "white")


# =============================================================================
# Language Analysis Utilities
# =============================================================================


@dataclass
class LanguageAnalysisRunResult:
    """Result of running language analysis on a single file."""

    file_path: str
    success: bool
    track_count: int
    analyzed_count: int
    cached_count: int
    error: str | None = None
    duration_ms: int = 0


def _run_language_analysis_for_file(
    conn,
    file_record: FileRecord,
    force: bool,
) -> LanguageAnalysisRunResult:
    """Run language analysis on a single file.

    Args:
        conn: Database connection.
        file_record: File to analyze.
        force: Whether to re-analyze even if cached.

    Returns:
        LanguageAnalysisRunResult with analysis outcome.
    """
    from vpo.language_analysis import (
        LanguageAnalysisError,
        analyze_track_languages,
        get_cached_analysis,
        persist_analysis_result,
    )
    from vpo.transcription.coordinator import TranscriptionCoordinator

    start_time = time.monotonic()
    file_path = Path(file_record.path)
    tracks = get_tracks_for_file(conn, file_record.id)

    # Filter to audio tracks
    audio_tracks = [t for t in tracks if t.track_type == "audio"]

    if not audio_tracks:
        return LanguageAnalysisRunResult(
            file_path=str(file_path),
            success=True,
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
            return LanguageAnalysisRunResult(
                file_path=str(file_path),
                success=False,
                track_count=len(audio_tracks),
                analyzed_count=0,
                cached_count=0,
                error="Transcription plugin not available",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
        transcriber = transcriber_plugin.instance
    except (ImportError, RuntimeError, AttributeError) as e:
        logger.debug("Failed to get transcription plugin: %s", e, exc_info=True)
        return LanguageAnalysisRunResult(
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
        except (OSError, sqlite3.Error) as e:
            # Transient errors - log and continue to next track
            logger.warning("Track %d analysis failed: %s", track.track_index, e)
            errors.append(f"Track {track.track_index}: {type(e).__name__}: {e}")
        except Exception as e:
            # Unexpected errors - log with traceback for debugging
            logger.debug(
                "Unexpected error analyzing track %d: %s",
                track.track_index,
                e,
                exc_info=True,
            )
            errors.append(f"Track {track.track_index}: {type(e).__name__}: {e}")

    duration_ms = int((time.monotonic() - start_time) * 1000)

    if errors and analyzed == 0 and cached_count == 0:
        return LanguageAnalysisRunResult(
            file_path=str(file_path),
            success=False,
            track_count=len(audio_tracks),
            analyzed_count=analyzed,
            cached_count=cached_count,
            error="; ".join(errors),
            duration_ms=duration_ms,
        )

    return LanguageAnalysisRunResult(
        file_path=str(file_path),
        success=True,
        track_count=len(audio_tracks),
        analyzed_count=analyzed,
        cached_count=cached_count,
        error=None if not errors else "; ".join(errors),
        duration_ms=duration_ms,
    )


# =============================================================================
# Analyze Command Group
# =============================================================================


@click.group(name="analyze")
def analyze_group() -> None:
    """Audio track analysis commands.

    Commands for classifying and analyzing audio tracks:

    - classify: Determine if tracks are original, dubbed, or commentary
    - language: Detect multi-language content in tracks
    - status: View analysis results
    - clear: Clear cached analysis data

    Examples:

        # Classify tracks in a file
        vpo analyze classify movie.mkv

        # Run language analysis
        vpo analyze language movie.mkv

        # View analysis status
        vpo analyze status

        # Clear all analysis for a file
        vpo analyze clear movie.mkv --yes
    """
    pass


# =============================================================================
# Classify Subcommand
# =============================================================================


@analyze_group.command(name="classify")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force reclassification even if results exist",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.pass_context
def classify_command(
    ctx: click.Context,
    path: Path,
    force: bool,
    output_json: bool,
) -> None:
    """Classify audio tracks as original/dubbed/commentary.

    Analyzes audio tracks to determine:
    - Original vs dubbed status (using metadata and language analysis)
    - Commentary vs main audio (using metadata and acoustic analysis)

    Results are stored in the database for use in policy conditions.

    Examples:
        vpo analyze classify movie.mkv
        vpo analyze classify --force movie.mkv
        vpo analyze classify --json movie.mkv
    """
    conn = get_db_conn_from_context(ctx)

    # Look up file in database
    file_record = get_file_by_path(conn, str(path))
    if file_record is None:
        click.echo(f"Error: File not found in database: {path}", err=True)
        click.echo("Run 'vpo scan' first to add the file to the library.", err=True)
        ctx.exit(ExitCode.TARGET_NOT_FOUND)

    # Get audio tracks
    tracks = get_tracks_for_file(conn, file_record.id)
    audio_tracks = [t for t in tracks if t.track_type.casefold() == "audio"]

    if not audio_tracks:
        click.echo(f"Error: No audio tracks found in file: {path}", err=True)
        ctx.exit(ExitCode.NO_TRACKS_FOUND)

    try:
        # Run classification
        results = classify_file_tracks(
            conn=conn,
            file_record=file_record,
            plugin_metadata=None,
            language_analysis=None,
            force_reclassify=force,
        )

        if output_json:
            output = {
                "file": str(path),
                "tracks": [
                    {
                        "track_id": r.track_id,
                        "language": r.language,
                        "original_dubbed": r.original_dubbed_status.value,
                        "commentary": r.commentary_status.value
                        if r.commentary_status
                        else "unknown",
                        "confidence": r.confidence,
                        "detection_method": r.detection_method.value,
                    }
                    for r in results
                ],
            }
            click.echo(json.dumps(output, indent=2))
        else:
            # Display results as table
            click.echo(f"\nClassification results for: {path.name}")
            click.echo("=" * 70)

            # Header
            click.echo(
                f"{'Track':<6} {'Lang':<6} {'Type':<10} {'Content':<12} "
                f"{'Conf':<6} {'Method'}"
            )
            click.echo("-" * 70)

            for result in results:
                original_dubbed = result.original_dubbed_status.value
                commentary = (
                    result.commentary_status.value
                    if result.commentary_status
                    else "unknown"
                )

                # Find track index from track_id
                track = next((t for t in audio_tracks if t.id == result.track_id), None)
                track_idx = track.track_index if track else "?"

                # Colorize status values
                od_color = _color_for_status(original_dubbed)
                cm_color = _color_for_status(commentary)

                conf_str = f"{result.confidence:.0%}"
                click.echo(
                    f"{track_idx:<6} "
                    f"{result.language or 'und':<6} "
                    f"{click.style(original_dubbed, fg=od_color):<10} "
                    f"{click.style(commentary, fg=cm_color):<12} "
                    f"{conf_str:<6} "
                    f"{result.detection_method.value}"
                )

            click.echo("")
            click.echo(f"Classified {len(results)} audio track(s)")

    except ClassificationError as e:
        logger.error("Classification failed: %s", e)
        click.echo(f"Error: Classification failed: {e}", err=True)
        ctx.exit(ExitCode.ANALYSIS_ERROR)
    except sqlite3.Error as e:
        logger.error("Classification failed due to database error: %s", e)
        click.echo(f"Error: Classification failed (database error): {e}", err=True)
        ctx.exit(ExitCode.DATABASE_ERROR)
    except Exception as e:
        logger.exception("Classification failed unexpectedly")
        click.echo(f"Error: Classification failed: {e}", err=True)
        ctx.exit(ExitCode.ANALYSIS_ERROR)

    ctx.exit(ExitCode.SUCCESS)


# =============================================================================
# Language Subcommand
# =============================================================================


@analyze_group.command(name="language")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, help="Re-analyze even if cached")
@click.option("--recursive", "-R", is_flag=True, help="Process directories recursively")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def language_command(
    ctx: click.Context,
    paths: tuple[str, ...],
    force: bool,
    recursive: bool,
    output_json: bool,
) -> None:
    """Run multi-language detection on audio tracks.

    PATHS can be files or directories. Files must exist in the VPO database
    (run 'vpo scan' first).

    Examples:

        # Analyze a single file
        vpo analyze language movie.mkv

        # Analyze with force re-analysis
        vpo analyze language movie.mkv --force

        # Analyze a directory recursively
        vpo analyze language /media/movies/ -R

        # Output as JSON
        vpo analyze language movie.mkv --json
    """
    conn = get_db_conn_from_context(ctx)

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
        raise SystemExit(ExitCode.PLUGIN_UNAVAILABLE)

    # Resolve files from paths
    files, not_found = _resolve_files_from_paths(conn, paths, recursive)

    # Warn about not-found paths
    for path in not_found:
        click.echo(
            f"Warning: '{path}' not found in database. Run 'vpo scan' first.", err=True
        )

    if not files:
        click.echo("Error: No valid files found to analyze.", err=True)
        raise SystemExit(ExitCode.TARGET_NOT_FOUND)

    # Run analysis on each file
    results: list[LanguageAnalysisRunResult] = []
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
            result = _run_language_analysis_for_file(conn, file_record, force)
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
        _format_language_run_results(
            results, total_files, successful, failed, cached, tracks_analyzed, errors
        )

    # Exit code based on results
    if failed == total_files:
        raise SystemExit(ExitCode.OPERATION_FAILED)
    elif failed > 0:
        raise SystemExit(ExitCode.GENERAL_ERROR)


def _format_language_run_results(
    results: list[LanguageAnalysisRunResult],
    total_files: int,
    successful: int,
    failed: int,
    cached: int,
    tracks_analyzed: int,
    errors: list[tuple[str, str]],
) -> None:
    """Format and output language analysis run results in human-readable format."""
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


# =============================================================================
# Status Subcommand
# =============================================================================


@analyze_group.command(name="status")
@click.argument("path", required=False, type=click.Path())
@click.option(
    "--type",
    "analysis_type",
    type=click.Choice(["all", "classify", "language"]),
    default="all",
    help="Type of analysis to show status for",
)
@click.option(
    "--filter",
    "filter_type",
    type=click.Choice(["all", "multi-language", "single-language", "pending"]),
    default="all",
    help="Filter files by classification (language analysis only)",
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--limit", "-n", default=50, help="Maximum files to show")
@click.pass_context
def status_command(
    ctx: click.Context,
    path: str | None,
    analysis_type: str,
    filter_type: str,
    output_json: bool,
    limit: int,
) -> None:
    """View analysis status for files.

    Without PATH, shows library summary. With PATH, shows detailed
    analysis for that file.

    Examples:

        # View library summary
        vpo analyze status

        # View classification status for a file
        vpo analyze status movie.mkv --type classify

        # View language analysis status
        vpo analyze status --type language

        # Filter to multi-language files
        vpo analyze status --type language --filter multi-language

        # Output as JSON
        vpo analyze status --json
    """
    conn = get_db_conn_from_context(ctx)

    # Handle specific file path
    if path:
        resolved_path = str(Path(path).resolve())

        if analysis_type in ("all", "classify"):
            _show_classification_status_for_file(ctx, conn, resolved_path, output_json)

        if analysis_type in ("all", "language"):
            _show_language_status_for_file(ctx, conn, resolved_path, output_json)
        return

    # Library-wide summary
    if analysis_type == "classify":
        _show_classification_summary(conn, output_json, limit)
    elif analysis_type == "language":
        _show_language_summary(conn, filter_type, output_json, limit)
    else:
        # Show both
        if output_json:
            # Combined JSON output
            from vpo.db.views import get_analysis_status_summary

            lang_summary = get_analysis_status_summary(conn)
            output = {
                "language_analysis": asdict(lang_summary),
            }
            click.echo(json.dumps(output, indent=2))
        else:
            _show_language_summary(conn, filter_type, output_json, limit)


def _show_classification_status_for_file(
    ctx: click.Context,
    conn,
    file_path: str,
    output_json: bool,
) -> None:
    """Show classification status for a specific file."""
    file_record = get_file_by_path(conn, file_path)
    if file_record is None:
        click.echo(f"Error: File not found in database: {file_path}", err=True)
        ctx.exit(ExitCode.TARGET_NOT_FOUND)

    classifications = get_classifications_for_file(conn, file_record.id)

    if output_json:
        output = {
            "file": file_path,
            "classifications": [
                {
                    "track_id": c.track_id,
                    "original_dubbed": c.original_dubbed_status,
                    "commentary": c.commentary_status,
                    "confidence": c.confidence,
                    "detection_method": c.detection_method,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                }
                for c in classifications
            ],
        }
        click.echo(json.dumps(output, indent=2))
    else:
        if not classifications:
            click.echo(f"No classification data for: {Path(file_path).name}")
            click.echo("Run 'vpo analyze classify' to classify tracks.")
            return

        click.echo(f"\nClassification status for: {Path(file_path).name}")
        click.echo("=" * 60)

        click.echo(
            f"{'Track ID':<10} {'Type':<10} {'Content':<12} "
            f"{'Confidence':<12} {'Method'}"
        )
        click.echo("-" * 60)

        for c in classifications:
            od_color = _color_for_status(c.original_dubbed_status)
            cm_color = _color_for_status(c.commentary_status)
            conf_str = f"{c.confidence:.0%}"

            click.echo(
                f"{c.track_id:<10} "
                f"{click.style(c.original_dubbed_status, fg=od_color):<10} "
                f"{click.style(c.commentary_status, fg=cm_color):<12} "
                f"{conf_str:<12} "
                f"{c.detection_method}"
            )

        click.echo("")
        click.echo(f"Found {len(classifications)} classification record(s)")


def _show_language_status_for_file(
    ctx: click.Context,
    conn,
    file_path: str,
    output_json: bool,
) -> None:
    """Show language analysis status for a specific file."""
    from vpo.db.views import get_file_analysis_detail

    detail = get_file_analysis_detail(conn, file_path)

    if detail is None:
        if not output_json:
            click.echo(f"No language analysis found for: {Path(file_path).name}")
        return

    if output_json:
        click.echo(json.dumps([asdict(d) for d in detail], indent=2))
    else:
        click.echo(f"\nLanguage Analysis: {file_path}")
        click.echo("=" * 60)
        click.echo("")

        if not detail:
            click.echo("No analysis results found for this file.")
            return

        for d in detail:
            lang = d.language or "unknown"
            click.echo(f"Track {d.track_index} (Audio - {lang}):")
            click.echo(f"  Classification: {d.classification}")
            pct = d.primary_percentage * 100
            click.echo(f"  Primary: {d.primary_language} ({pct:.1f}%)")
            if d.secondary_languages:
                click.echo(f"  Secondary: {d.secondary_languages}")
            click.echo(f"  Analyzed: {d.analyzed_at}")
            click.echo("")


def _show_classification_summary(conn, output_json: bool, limit: int) -> None:
    """Show library-wide classification summary."""
    # This would need a summary view in the DB; for now, show a simple message
    if output_json:
        msg = {"message": "Classification summary not yet implemented"}
        click.echo(json.dumps(msg))
    else:
        click.echo("\nClassification Summary")
        click.echo("=" * 50)
        click.echo("\nUse 'vpo analyze status <file>' to view classification.")
        click.echo("Use 'vpo analyze classify <file>' to classify tracks.")


def _show_language_summary(
    conn, filter_type: str, output_json: bool, limit: int
) -> None:
    """Show library-wide language analysis summary."""
    from vpo.db.views import (
        get_analysis_status_summary,
        get_files_analysis_status,
    )

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
            _format_language_status_summary(summary)
            _format_language_file_list(files, filter_type, limit)
    else:
        if output_json:
            click.echo(json.dumps(asdict(summary), indent=2))
        else:
            _format_language_status_summary(summary)


def _format_language_status_summary(summary) -> None:
    """Format and output language analysis status summary."""
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


def _format_language_file_list(files: list, filter_type: str, limit: int) -> None:
    """Format and output filtered file list for language analysis."""
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


# =============================================================================
# Clear Subcommand
# =============================================================================


@analyze_group.command(name="clear")
@click.argument("path", required=False, type=click.Path())
@click.option(
    "--type",
    "analysis_type",
    type=click.Choice(["all", "classify", "language"]),
    default="all",
    help="Type of analysis data to clear",
)
@click.option("--all", "clear_all", is_flag=True, help="Clear all results")
@click.option("--recursive", "-R", is_flag=True, help="Include subdirectories")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", "-n", is_flag=True, help="Preview without deleting")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def clear_command(
    ctx: click.Context,
    path: str | None,
    analysis_type: str,
    clear_all: bool,
    recursive: bool,
    yes: bool,
    dry_run: bool,
    output_json: bool,
) -> None:
    """Clear cached analysis results.

    Specify PATH for a file or directory, or use --all to clear everything.
    Use --type to clear only specific analysis types.

    Examples:

        # Clear all analysis for a file
        vpo analyze clear movie.mkv --yes

        # Clear only classification data
        vpo analyze clear movie.mkv --type classify --yes

        # Clear only language analysis data
        vpo analyze clear movie.mkv --type language --yes

        # Clear language analysis for a directory
        vpo analyze clear /media/movies/ -R --type language --yes

        # Preview what would be cleared
        vpo analyze clear --all --dry-run

        # Clear all analysis results
        vpo analyze clear --all --yes
    """
    conn = get_db_conn_from_context(ctx)

    if not path and not clear_all:
        click.echo("Error: Specify a PATH or use --all to clear all results.", err=True)
        raise SystemExit(ExitCode.INVALID_ARGUMENTS)

    # Track totals
    files_affected = 0
    classify_cleared = 0
    language_cleared = 0

    if path:
        resolved_path = str(Path(path).resolve())

        # Handle classification clearing
        if analysis_type in ("all", "classify"):
            if Path(resolved_path).is_file():
                file_record = get_file_by_path(conn, resolved_path)
                if file_record:
                    classifications = get_classifications_for_file(conn, file_record.id)
                    classify_cleared = len(classifications)
                    if classify_cleared > 0:
                        files_affected = 1

        # Handle language analysis clearing
        if analysis_type in ("all", "language"):
            lang_files, lang_tracks = _count_language_results(
                conn, resolved_path, recursive
            )
            language_cleared = lang_tracks
            if lang_files > files_affected:
                files_affected = lang_files
    else:
        # Clear all
        if analysis_type in ("all", "language"):
            lang_files, lang_tracks = _count_language_results(conn, None, True)
            language_cleared = lang_tracks
            files_affected = lang_files

    total_cleared = classify_cleared + language_cleared

    if total_cleared == 0:
        if output_json:
            click.echo(
                json.dumps(
                    {
                        "dry_run": dry_run,
                        "files_affected": 0,
                        "classify_cleared": 0,
                        "language_cleared": 0,
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
                        "classify_cleared": classify_cleared,
                        "language_cleared": language_cleared,
                        "success": True,
                    }
                )
            )
        else:
            click.echo("Would clear analysis results:")
            click.echo(f"  Files affected: {files_affected}")
            if analysis_type in ("all", "classify"):
                click.echo(f"  Classification records: {classify_cleared}")
            if analysis_type in ("all", "language"):
                click.echo(f"  Language analysis records: {language_cleared}")
            click.echo("")
            click.echo("Use without --dry-run to proceed.")
        return

    # Confirmation
    if not yes:
        click.echo("This will clear analysis results:")
        click.echo(f"  Files: {files_affected}")
        if analysis_type in ("all", "classify"):
            click.echo(f"  Classification records: {classify_cleared}")
        if analysis_type in ("all", "language"):
            click.echo(f"  Language analysis records: {language_cleared}")
        click.echo("")
        if not click.confirm("Continue?"):
            click.echo("Operation cancelled.")
            raise SystemExit(ExitCode.INTERRUPTED)

    # Execute deletion
    actual_classify = 0
    actual_language = 0

    if path:
        resolved_path = str(Path(path).resolve())

        # Clear classification
        if analysis_type in ("all", "classify") and classify_cleared > 0:
            file_record = get_file_by_path(conn, resolved_path)
            if file_record:
                classifications = get_classifications_for_file(conn, file_record.id)
                for c in classifications:
                    if delete_track_classification(conn, c.track_id):
                        actual_classify += 1
                conn.commit()

        # Clear language analysis
        if analysis_type in ("all", "language") and language_cleared > 0:
            actual_language = _clear_language_results(conn, resolved_path, recursive)
    else:
        # Clear all
        if analysis_type in ("all", "language"):
            actual_language = _clear_language_results(conn, None, True)

    if output_json:
        click.echo(
            json.dumps(
                {
                    "dry_run": False,
                    "files_affected": files_affected,
                    "classify_cleared": actual_classify,
                    "language_cleared": actual_language,
                    "success": True,
                }
            )
        )
    else:
        click.echo(f"Cleared analysis results from {files_affected} file(s):")
        if analysis_type in ("all", "classify") and actual_classify > 0:
            click.echo(f"  Classification records: {actual_classify}")
        if analysis_type in ("all", "language") and actual_language > 0:
            click.echo(f"  Language analysis records: {actual_language}")


def _count_language_results(
    conn,
    path: str | None,
    recursive: bool,
) -> tuple[int, int]:
    """Count files and tracks that would be affected by clearing language analysis.

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
        cursor = conn.execute(base_query)
    elif Path(path).is_file():
        cursor = conn.execute(base_query + " WHERE f.path = ?", (path,))
    elif recursive:
        escaped_path = _escape_like_pattern(path)
        pattern = escaped_path + "%"
        cursor = conn.execute(
            base_query + " WHERE f.path LIKE ? ESCAPE '\\'", (pattern,)
        )
    else:
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


def _clear_language_results(conn, path: str | None, recursive: bool) -> int:
    """Clear language analysis results.

    Args:
        conn: Database connection.
        path: Path to file or directory, or None for all.
        recursive: Whether to include subdirectories.

    Returns:
        Number of records deleted.
    """
    from vpo.db.queries import (
        delete_all_analysis,
        delete_analysis_by_path_prefix,
        delete_analysis_for_file,
    )

    if path is None:
        return delete_all_analysis(conn)
    elif Path(path).is_file():
        file_record = get_file_by_path(conn, path)
        if file_record:
            return delete_analysis_for_file(conn, file_record.id)
        return 0
    else:
        return delete_analysis_by_path_prefix(conn, path)
