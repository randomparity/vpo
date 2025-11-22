"""Scan command for VPO CLI."""

import json
import sys
from pathlib import Path

import click

from video_policy_orchestrator.scanner.orchestrator import (
    DEFAULT_EXTENSIONS,
    ScannerOrchestrator,
)


def validate_directories(ctx, param, value):
    """Validate that all directories exist."""
    paths = []
    for path_str in value:
        path = Path(path_str)
        if not path.exists():
            raise click.BadParameter(f"Directory not found: {path}")
        if not path.is_dir():
            raise click.BadParameter(f"Not a directory: {path}")
        paths.append(path)
    return paths


@click.command()
@click.argument(
    "directories",
    nargs=-1,
    required=True,
    callback=validate_directories,
)
@click.option(
    "--extensions",
    "-e",
    default=None,
    help=(
        f"Comma-separated list of file extensions to scan. "
        f"Default: {','.join(DEFAULT_EXTENSIONS)}"
    ),
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Database path. Default: ~/.vpo/library.db",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Scan without writing to database.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show verbose output.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output results in JSON format.",
)
def scan(
    directories: list[Path],
    extensions: str | None,
    db_path: Path | None,
    dry_run: bool,
    verbose: bool,
    json_output: bool,
) -> None:
    """Scan directories for video files.

    Recursively discovers video files in the specified directories,
    computes content hashes, and stores results in the database.

    Examples:

        vpo scan /media/videos

        vpo scan --extensions mkv,mp4 /media/movies /media/tv

        vpo scan --dry-run --verbose /media/videos
    """
    from video_policy_orchestrator.db.connection import (
        get_connection,
        get_default_db_path,
    )
    from video_policy_orchestrator.db.schema import initialize_database

    # Parse extensions
    ext_list = None
    if extensions:
        ext_list = [e.strip().lower().lstrip(".") for e in extensions.split(",")]

    # Create scanner
    scanner = ScannerOrchestrator(extensions=ext_list)

    # Run scan
    if dry_run:
        # Dry run: just scan without database
        files, result = scanner.scan_directories(directories)
    else:
        # Normal run: scan and persist to database
        effective_db_path = db_path or get_default_db_path()
        with get_connection(effective_db_path) as conn:
            initialize_database(conn)
            files, result = scanner.scan_and_persist(directories, conn)

    # Output results
    if json_output:
        output_json(result, files, verbose, dry_run)
    else:
        output_human(result, files, verbose, dry_run)

    # Exit with error code if there were errors
    if result.errors:
        sys.exit(1) if not files else sys.exit(0)


def output_json(result, files, verbose: bool, dry_run: bool = False) -> None:
    """Output scan results in JSON format."""
    data = {
        "files_found": result.files_found,
        "elapsed_seconds": round(result.elapsed_seconds, 2),
        "directories_scanned": result.directories_scanned,
        "dry_run": dry_run,
    }

    if not dry_run:
        data["files_new"] = result.files_new
        data["files_updated"] = result.files_updated
        data["files_skipped"] = result.files_skipped

    if result.errors:
        data["errors"] = [{"path": p, "error": e} for p, e in result.errors]

    if verbose:
        data["files"] = [
            {
                "path": f.path,
                "size": f.size,
                "modified_at": f.modified_at.isoformat(),
                "content_hash": f.content_hash,
            }
            for f in files
        ]

    click.echo(json.dumps(data, indent=2))


def output_human(result, files, verbose: bool, dry_run: bool = False) -> None:
    """Output scan results in human-readable format."""
    dir_count = len(result.directories_scanned)
    dir_word = "directory" if dir_count == 1 else "directories"
    click.echo(f"\nScanned {dir_count} {dir_word}")
    file_word = "file" if result.files_found == 1 else "files"
    click.echo(f"Found {result.files_found} video {file_word}")

    if not dry_run:
        click.echo(f"  New: {result.files_new}")
        click.echo(f"  Updated: {result.files_updated}")
        click.echo(f"  Skipped: {result.files_skipped}")
    else:
        click.echo("  (dry run - no database changes)")

    click.echo(f"Elapsed time: {result.elapsed_seconds:.2f}s")

    if verbose and files:
        click.echo("\nFiles found:")
        for f in files:
            size_mb = f.size / (1024 * 1024)
            click.echo(f"  {f.path} ({size_mb:.2f} MB)")

    if result.errors:
        click.echo(f"\n{len(result.errors)} error(s):")
        for path, error in result.errors:
            click.echo(f"  {path}: {error}", err=True)


# Register with the CLI group
from video_policy_orchestrator.cli import main  # noqa: E402

main.add_command(scan)
