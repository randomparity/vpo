"""CLI commands for track classification operations.

Provides commands for classifying audio tracks as original/dubbed/commentary:
- classify run: Run classification on files
- classify status: View classification status for files
- classify clear: Clear classification data

Exit codes:
- 0: Success
- 2: File not found
- 3: No audio tracks found
- 4: Classification failed
"""

import logging
import sqlite3
from pathlib import Path

import click

from video_policy_orchestrator.db.models import get_file_by_path
from video_policy_orchestrator.db.queries import (
    delete_track_classification,
    get_classifications_for_file,
)
from video_policy_orchestrator.track_classification.service import (
    classify_file_tracks,
)

logger = logging.getLogger(__name__)

# Exit codes specific to classify command
EXIT_SUCCESS = 0
EXIT_FILE_NOT_FOUND = 2
EXIT_NO_TRACKS = 3
EXIT_CLASSIFICATION_FAILED = 4


def _get_db_conn(ctx: click.Context) -> sqlite3.Connection:
    """Get database connection from context.

    Args:
        ctx: Click context.

    Returns:
        Database connection.

    Raises:
        click.ClickException: If database connection not available.
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Database connection not available")
    return conn


def _format_classification_row(
    track_index: int,
    language: str | None,
    original_dubbed: str,
    commentary: str,
    confidence: float,
    method: str,
) -> tuple[str, str, str, str, str, str]:
    """Format classification for table display."""
    return (
        str(track_index),
        language or "und",
        original_dubbed,
        commentary,
        f"{confidence:.0%}",
        method,
    )


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


@click.group(name="classify")
def classify_group() -> None:
    """Track classification commands.

    Commands for classifying audio tracks as original, dubbed, or commentary.
    Classification results are stored in the database and can be used in
    policy conditions with is_original and is_dubbed.
    """
    pass


@classify_group.command(name="run")
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
def classify_run(
    ctx: click.Context,
    path: Path,
    force: bool,
    output_json: bool,
) -> None:
    """Run classification on a media file.

    Analyzes audio tracks to determine:
    - Original vs dubbed status (using metadata and language analysis)
    - Commentary vs main audio (using metadata and acoustic analysis)

    Results are stored in the database for use in policy conditions.

    Examples:
        vpo classify run movie.mkv
        vpo classify run --force movie.mkv
        vpo classify run --json movie.mkv
    """
    conn = _get_db_conn(ctx)

    # Look up file in database
    file_record = get_file_by_path(conn, str(path))
    if file_record is None:
        click.echo(f"Error: File not found in database: {path}", err=True)
        click.echo("Run 'vpo scan' first to add the file to the library.", err=True)
        ctx.exit(EXIT_FILE_NOT_FOUND)

    # Get audio tracks
    from video_policy_orchestrator.db.models import get_tracks_for_file

    tracks = get_tracks_for_file(conn, file_record.id)
    audio_tracks = [t for t in tracks if t.track_type.casefold() == "audio"]

    if not audio_tracks:
        click.echo(f"Error: No audio tracks found in file: {path}", err=True)
        ctx.exit(EXIT_NO_TRACKS)

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
            import json

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

    except Exception as e:
        logger.exception("Classification failed")
        click.echo(f"Error: Classification failed: {e}", err=True)
        ctx.exit(EXIT_CLASSIFICATION_FAILED)

    ctx.exit(EXIT_SUCCESS)


@classify_group.command(name="status")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.pass_context
def classify_status(
    ctx: click.Context,
    path: Path,
    output_json: bool,
) -> None:
    """View classification status for a media file.

    Shows existing classification results without running new classification.

    Examples:
        vpo classify status movie.mkv
        vpo classify status --json movie.mkv
    """
    conn = _get_db_conn(ctx)

    # Look up file in database
    file_record = get_file_by_path(conn, str(path))
    if file_record is None:
        click.echo(f"Error: File not found in database: {path}", err=True)
        ctx.exit(EXIT_FILE_NOT_FOUND)

    # Get existing classifications
    classifications = get_classifications_for_file(conn, file_record.id)

    if output_json:
        import json

        output = {
            "file": str(path),
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
            click.echo(f"No classification data for: {path.name}")
            click.echo("Run 'vpo classify run' to classify tracks.")
            ctx.exit(EXIT_SUCCESS)

        click.echo(f"\nClassification status for: {path.name}")
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

    ctx.exit(EXIT_SUCCESS)


@classify_group.command(name="clear")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.pass_context
def classify_clear(
    ctx: click.Context,
    path: Path,
    yes: bool,
) -> None:
    """Clear classification data for a media file.

    Removes all classification results for the specified file.
    This allows re-running classification with fresh analysis.

    Examples:
        vpo classify clear movie.mkv
        vpo classify clear --yes movie.mkv
    """
    conn = _get_db_conn(ctx)

    # Look up file in database
    file_record = get_file_by_path(conn, str(path))
    if file_record is None:
        click.echo(f"Error: File not found in database: {path}", err=True)
        ctx.exit(EXIT_FILE_NOT_FOUND)

    # Get existing classifications to show what will be deleted
    classifications = get_classifications_for_file(conn, file_record.id)

    if not classifications:
        click.echo(f"No classification data to clear for: {path.name}")
        ctx.exit(EXIT_SUCCESS)

    if not yes:
        click.echo(f"\nWill delete {len(classifications)} classification record(s)")
        click.echo(f"File: {path.name}")
        if not click.confirm("Continue?"):
            click.echo("Cancelled.")
            ctx.exit(EXIT_SUCCESS)

    # Delete classifications
    deleted_count = 0
    for c in classifications:
        if delete_track_classification(conn, c.track_id):
            deleted_count += 1

    conn.commit()

    click.echo(f"Cleared {deleted_count} classification record(s)")
    ctx.exit(EXIT_SUCCESS)
