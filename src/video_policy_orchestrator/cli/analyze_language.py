"""CLI command for language analysis operations.

Provides commands to run, check status, and clear cached language analysis results.
"""

import json
import logging
import sqlite3
from pathlib import Path

import click

from video_policy_orchestrator.cli.exit_codes import ExitCode
from video_policy_orchestrator.cli.output import error_exit
from video_policy_orchestrator.db.connection import get_connection
from video_policy_orchestrator.db.models import (
    get_file_by_path,
    get_tracks_for_file,
)
from video_policy_orchestrator.language_analysis.models import LanguageClassification
from video_policy_orchestrator.language_analysis.orchestrator import (
    AnalysisProgress,
    LanguageAnalysisOrchestrator,
)
from video_policy_orchestrator.language_analysis.service import (
    get_cached_analysis,
    invalidate_analysis_cache,
)
from video_policy_orchestrator.plugin import get_default_registry

logger = logging.getLogger(__name__)


@click.group("analyze-language")
def analyze_language_group() -> None:
    """Analyze audio tracks for multi-language detection.

    This command group provides tools for detecting multiple languages
    in audio tracks, useful for identifying dubbed or multi-language content.

    Examples:

        vpo analyze-language run /media/movie.mkv

        vpo analyze-language status /media/movie.mkv

        vpo analyze-language clear /media/movie.mkv
    """
    pass


@analyze_language_group.command("run")
@click.argument(
    "target",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--track",
    "-t",
    "track_index",
    type=int,
    default=None,
    help="Analyze specific audio track index only.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Re-analyze even if cached result exists.",
)
@click.option(
    "--json",
    "-j",
    "json_output",
    is_flag=True,
    default=False,
    help="Output results in JSON format.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show detailed analysis output.",
)
def run_command(
    target: Path,
    track_index: int | None,
    force: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    """Run language analysis on audio tracks.

    TARGET is the path to a media file to analyze.

    Examples:

        vpo analyze-language run /media/movie.mkv

        vpo analyze-language run --track 1 /media/movie.mkv

        vpo analyze-language run --force --json /media/movie.mkv
    """
    target = target.expanduser().resolve()

    # Results collected from progress callback
    results: list[dict] = []

    def progress_callback(progress: AnalysisProgress) -> None:
        """Handle progress updates from orchestrator."""
        if progress.status == "cached" and progress.result:
            if not json_output:
                click.echo(
                    f"  Track {progress.track_index}: "
                    f"{progress.result.classification.value} (cached)"
                )
            results.append(
                {
                    "track_index": progress.track_index,
                    "classification": progress.result.classification.value,
                    "primary_language": progress.result.primary_language,
                    "primary_percentage": progress.result.primary_percentage,
                    "cached": True,
                }
            )
        elif progress.status == "analyzed" and progress.result:
            if not json_output:
                click.echo(
                    f"  Track {progress.track_index}: "
                    f"{progress.result.classification.value} "
                    f"({progress.result.primary_language} "
                    f"{progress.result.primary_percentage:.0%})"
                )
                if verbose and progress.result.secondary_languages:
                    for sec in progress.result.secondary_languages:
                        click.echo(
                            f"    Secondary: {sec.language_code} ({sec.percentage:.0%})"
                        )
            results.append(
                {
                    "track_index": progress.track_index,
                    "classification": progress.result.classification.value,
                    "primary_language": progress.result.primary_language,
                    "primary_percentage": progress.result.primary_percentage,
                    "secondary_languages": [
                        {
                            "language_code": s.language_code,
                            "percentage": s.percentage,
                        }
                        for s in progress.result.secondary_languages
                    ],
                    "cached": False,
                }
            )
        elif progress.status == "skipped":
            error_msg = progress.error or "unknown reason"
            if not json_output:
                click.echo(f"  Track {progress.track_index}: Skipped - {error_msg}")
            results.append(
                {
                    "track_index": progress.track_index,
                    "status": "skipped",
                    "reason": error_msg,
                }
            )
        elif progress.status == "error":
            error_msg = progress.error or "unknown error"
            if not json_output:
                click.echo(f"  Track {progress.track_index}: Error - {error_msg}")
            results.append(
                {
                    "track_index": progress.track_index,
                    "status": "error",
                    "error": error_msg,
                }
            )

    try:
        with get_connection() as conn:
            # Get file from database
            file_record = get_file_by_path(conn, str(target))
            if file_record is None:
                msg = f"File not found in database. Run 'vpo scan' first: {target}"
                if json_output:
                    click.echo(
                        json.dumps({"status": "error", "error": msg}),
                        err=True,
                    )
                else:
                    click.echo(f"Error: {msg}", err=True)
                raise SystemExit(1)

            # Get tracks from database
            track_records = get_tracks_for_file(conn, file_record.id)
            audio_tracks = [t for t in track_records if t.track_type == "audio"]

            # Filter to specific track if requested
            if track_index is not None:
                audio_tracks = [t for t in audio_tracks if t.track_index == track_index]
                if not audio_tracks:
                    msg = f"Audio track {track_index} not found."
                    if json_output:
                        click.echo(
                            json.dumps({"status": "error", "error": msg}),
                            err=True,
                        )
                    else:
                        click.echo(f"Error: {msg}", err=True)
                    raise SystemExit(1)

            if not audio_tracks:
                msg = "No audio tracks found in file."
                if json_output:
                    click.echo(
                        json.dumps({"status": "error", "error": msg}),
                        err=True,
                    )
                else:
                    click.echo(f"Error: {msg}", err=True)
                raise SystemExit(1)

            if not json_output:
                click.echo(f"Analyzing {len(audio_tracks)} audio track(s)...")

            # Use orchestrator for analysis with plugin registry
            registry = get_default_registry()
            orchestrator = LanguageAnalysisOrchestrator(plugin_registry=registry)
            batch_result = orchestrator.analyze_tracks_for_file(
                conn=conn,
                file_record=file_record,
                track_records=audio_tracks,
                file_path=target,
                force=force,
                progress_callback=progress_callback,
            )

            if not batch_result.transcriber_available:
                error_exit(
                    "Transcription plugin unavailable or lacks multi-language support.",
                    ExitCode.PLUGIN_UNAVAILABLE,
                    json_output=json_output,
                )

            conn.commit()

            if json_output:
                output = {
                    "status": "completed",
                    "file": str(target),
                    "tracks": results,
                }
                click.echo(json.dumps(output, indent=2))
            elif not verbose:
                click.echo(f"\nAnalysis complete for {len(results)} track(s).")

    except sqlite3.Error as e:
        msg = f"Database error: {e}"
        if json_output:
            click.echo(
                json.dumps({"status": "error", "error": msg}),
                err=True,
            )
        else:
            click.echo(f"Error: {msg}", err=True)
        raise SystemExit(1)


@analyze_language_group.command("status")
@click.argument(
    "target",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--json",
    "-j",
    "json_output",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
def status_command(
    target: Path,
    json_output: bool,
) -> None:
    """Show language analysis status for a file.

    TARGET is the path to a media file to check.

    Examples:

        vpo analyze-language status /media/movie.mkv

        vpo analyze-language status --json /media/movie.mkv
    """
    target = target.expanduser().resolve()

    try:
        with get_connection() as conn:
            # Get file from database
            file_record = get_file_by_path(conn, str(target))
            if file_record is None:
                msg = f"File not found in database. Run 'vpo scan' first: {target}"
                if json_output:
                    click.echo(
                        json.dumps({"status": "not_found", "error": msg}),
                        err=True,
                    )
                else:
                    click.echo(f"Error: {msg}", err=True)
                raise SystemExit(1)

            # Get tracks from database
            track_records = get_tracks_for_file(conn, file_record.id)
            audio_tracks = [t for t in track_records if t.track_type == "audio"]

            if not audio_tracks:
                if json_output:
                    click.echo(
                        json.dumps(
                            {
                                "status": "no_audio",
                                "file": str(target),
                                "tracks": [],
                            }
                        )
                    )
                else:
                    click.echo("No audio tracks found in file.")
                return

            file_hash = file_record.content_hash or ""
            results = []
            analyzed_count = 0
            multi_language_count = 0

            for track in audio_tracks:
                if track.id is None:
                    continue

                cached = get_cached_analysis(conn, track.id, file_hash)
                if cached is not None:
                    analyzed_count += 1
                    is_multi = (
                        cached.classification == LanguageClassification.MULTI_LANGUAGE
                    )
                    if is_multi:
                        multi_language_count += 1

                    results.append(
                        {
                            "track_index": track.track_index,
                            "analyzed": True,
                            "classification": cached.classification.value,
                            "primary_language": cached.primary_language,
                            "primary_percentage": cached.primary_percentage,
                            "analyzed_at": cached.updated_at.isoformat(),
                        }
                    )
                else:
                    results.append(
                        {
                            "track_index": track.track_index,
                            "analyzed": False,
                        }
                    )

            if json_output:
                output = {
                    "status": "ok",
                    "file": str(target),
                    "total_audio_tracks": len(audio_tracks),
                    "analyzed_tracks": analyzed_count,
                    "multi_language_tracks": multi_language_count,
                    "tracks": results,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                click.echo(f"File: {target}")
                click.echo(f"Audio tracks: {len(audio_tracks)}")
                click.echo(f"Analyzed: {analyzed_count}/{len(audio_tracks)}")
                if multi_language_count > 0:
                    click.echo(f"Multi-language: {multi_language_count}")
                click.echo()
                for r in results:
                    if r["analyzed"]:
                        click.echo(
                            f"  Track {r['track_index']}: "
                            f"{r['classification']} "
                            f"({r['primary_language']} {r['primary_percentage']:.0%})"
                        )
                    else:
                        click.echo(f"  Track {r['track_index']}: Not analyzed")

    except sqlite3.Error as e:
        msg = f"Database error: {e}"
        if json_output:
            click.echo(
                json.dumps({"status": "error", "error": msg}),
                err=True,
            )
        else:
            click.echo(f"Error: {msg}", err=True)
        raise SystemExit(1)


@analyze_language_group.command("clear")
@click.argument(
    "target",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--track",
    "-t",
    "track_index",
    type=int,
    default=None,
    help="Clear specific audio track only.",
)
@click.option(
    "--json",
    "-j",
    "json_output",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
def clear_command(
    target: Path,
    track_index: int | None,
    json_output: bool,
) -> None:
    """Clear cached language analysis results.

    TARGET is the path to a media file to clear analysis for.

    Examples:

        vpo analyze-language clear /media/movie.mkv

        vpo analyze-language clear --track 1 /media/movie.mkv
    """
    target = target.expanduser().resolve()

    try:
        with get_connection() as conn:
            # Get file from database
            file_record = get_file_by_path(conn, str(target))
            if file_record is None:
                msg = f"File not found in database: {target}"
                if json_output:
                    click.echo(
                        json.dumps({"status": "not_found", "error": msg}),
                        err=True,
                    )
                else:
                    click.echo(f"Error: {msg}", err=True)
                raise SystemExit(1)

            # Get tracks from database
            track_records = get_tracks_for_file(conn, file_record.id)
            audio_tracks = [t for t in track_records if t.track_type == "audio"]

            # Filter to specific track if requested
            if track_index is not None:
                audio_tracks = [t for t in audio_tracks if t.track_index == track_index]
                if not audio_tracks:
                    msg = f"Audio track {track_index} not found."
                    if json_output:
                        click.echo(
                            json.dumps({"status": "error", "error": msg}),
                            err=True,
                        )
                    else:
                        click.echo(f"Error: {msg}", err=True)
                    raise SystemExit(1)

            cleared_count = 0
            for track in audio_tracks:
                if track.id is None:
                    continue
                if invalidate_analysis_cache(conn, track.id):
                    cleared_count += 1

            conn.commit()

            if json_output:
                output = {
                    "status": "completed",
                    "file": str(target),
                    "cleared_count": cleared_count,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                if cleared_count > 0:
                    click.echo(f"Cleared {cleared_count} cached analysis result(s).")
                else:
                    click.echo("No cached results to clear.")

    except sqlite3.Error as e:
        msg = f"Database error: {e}"
        if json_output:
            click.echo(
                json.dumps({"status": "error", "error": msg}),
                err=True,
            )
        else:
            click.echo(f"Error: {msg}", err=True)
        raise SystemExit(1)
