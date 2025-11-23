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
    "--full",
    is_flag=True,
    default=False,
    help="Force full scan, bypass incremental detection.",
)
@click.option(
    "--prune",
    is_flag=True,
    default=False,
    help="Delete database records for missing files.",
)
@click.option(
    "--verify-hash",
    is_flag=True,
    default=False,
    help="Use content hash for change detection (slower).",
)
@click.option(
    "--profile",
    default=None,
    help="Use named configuration profile from ~/.vpo/profiles/.",
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
    full: bool,
    prune: bool,
    verify_hash: bool,
    profile: str | None,
    dry_run: bool,
    verbose: bool,
    json_output: bool,
) -> None:
    """Scan directories for video files.

    Recursively discovers video files in the specified directories,
    computes content hashes, and stores results in the database.

    By default, scans are incremental - only files that have changed since
    the last scan are introspected. Use --full to force a complete rescan.

    Examples:

        vpo scan /media/videos

        vpo scan --extensions mkv,mp4 /media/movies /media/tv

        vpo scan --dry-run --verbose /media/videos

        vpo scan --profile movies /media/movies
    """
    from video_policy_orchestrator.db.connection import (
        DatabaseLockedError,
        get_connection,
        get_default_db_path,
    )
    from video_policy_orchestrator.db.schema import initialize_database

    # Load profile if specified
    if profile:
        from video_policy_orchestrator.config.profiles import (
            ProfileError,
            list_profiles,
            load_profile,
        )

        try:
            loaded_profile = load_profile(profile)
            if verbose and not json_output:
                click.echo(f"Using profile: {loaded_profile.name}")
        except ProfileError as e:
            available = list_profiles()
            click.echo(f"Error: {e}", err=True)
            if available:
                click.echo("\nAvailable profiles:", err=True)
                for name in sorted(available):
                    click.echo(f"  - {name}", err=True)
            sys.exit(1)

    # Parse extensions
    ext_list = None
    if extensions:
        ext_list = [e.strip().lower().lstrip(".") for e in extensions.split(",")]

    # Create scanner
    scanner = ScannerOrchestrator(extensions=ext_list)

    # Progress callback for verbose mode
    def progress_callback(processed: int, total: int) -> None:
        if verbose and not json_output:
            click.echo(f"  Progress: {processed}/{total} files processed...")

    # Run scan
    try:
        if dry_run:
            # Dry run: just scan without database
            files, result = scanner.scan_directories(directories)
        else:
            # Normal run: scan and persist to database
            from video_policy_orchestrator.jobs.tracking import (
                complete_scan_job,
                create_scan_job,
            )

            effective_db_path = db_path or get_default_db_path()
            with get_connection(effective_db_path) as conn:
                initialize_database(conn)

                # Create job record
                if len(directories) == 1:
                    directory_str = str(directories[0])
                else:
                    directory_str = ",".join(str(d) for d in directories)
                job = create_scan_job(
                    conn,
                    directory_str,
                    incremental=not full,
                    prune=prune,
                    verify_hash=verify_hash,
                )

                files, result = scanner.scan_and_persist(
                    directories,
                    conn,
                    progress_callback=progress_callback,
                    full=full,
                    prune=prune,
                    verify_hash=verify_hash,
                )

                # Update job record with results
                result.job_id = job.id
                summary = {
                    "total_discovered": result.files_found,
                    "scanned": result.files_new + result.files_updated,
                    "skipped": result.files_skipped,
                    "added": result.files_new,
                    "removed": result.files_removed,
                    "errors": result.files_errored,
                }
                error_msg = None
                if result.interrupted:
                    error_msg = "Scan interrupted by user"
                complete_scan_job(conn, job.id, summary, error_message=error_msg)

    except DatabaseLockedError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo(
            "Hint: Close other VPO instances or use a different --db path.", err=True
        )
        sys.exit(1)

    # Output results
    if json_output:
        output_json(result, files, verbose, dry_run)
    else:
        output_human(result, files, verbose, dry_run)

    # Exit with appropriate code
    if getattr(result, "interrupted", False):
        click.echo("\nScan interrupted. Partial results saved.", err=True)
        sys.exit(130)  # Standard exit code for Ctrl+C
    elif result.errors:
        # Exit 1 only if errors occurred AND no files were found (complete
        # failure). Exit 0 if some files were processed despite errors
        # (partial success).
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
        data["files_removed"] = getattr(result, "files_removed", 0)
        data["incremental"] = getattr(result, "incremental", True)
        if hasattr(result, "job_id") and result.job_id:
            data["job_id"] = result.job_id

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

    # Build header
    if dir_count == 1:
        scan_target = result.directories_scanned[0]
    else:
        scan_target = f"{dir_count} {dir_word}"

    click.echo(f"\nScanning {scan_target}...")
    click.echo(f"  Discovered: {result.files_found:,} files")

    if not dry_run:
        click.echo(f"  Skipped (unchanged): {result.files_skipped:,}")
        click.echo(f"  Scanned (changed): {result.files_new + result.files_updated:,}")
        click.echo(f"  Added (new): {result.files_new:,}")
        if result.files_errored > 0:
            click.echo(f"  Scanned (error): {result.files_errored:,}")
        files_removed = getattr(result, "files_removed", 0)
        if files_removed > 0:
            click.echo(f"  Removed (missing): {files_removed:,}")
    else:
        click.echo("  (dry run - no database changes)")

    # Show job ID if available
    job_id = getattr(result, "job_id", None)
    if job_id:
        job_short = job_id[:8]
        elapsed = result.elapsed_seconds
        click.echo(f"\nScan complete in {elapsed:.1f}s (job: {job_short})")
    else:
        click.echo(f"\nScan complete in {result.elapsed_seconds:.1f}s")

    if verbose and files:
        click.echo("\nFiles found:")
        for f in files:
            size_mb = f.size / (1024 * 1024)
            click.echo(f"  {f.path} ({size_mb:.2f} MB)")

    if result.errors:
        error_count = len(result.errors)
        click.echo(f"\n{error_count} error(s):", err=True)
        if verbose:
            # In verbose mode, show all errors
            for path, error in result.errors:
                click.echo(f"  {path}: {error}", err=True)
        else:
            # In non-verbose mode, show first 5 errors with hint
            for path, error in result.errors[:5]:
                click.echo(f"  {path}: {error}", err=True)
            if error_count > 5:
                click.echo(
                    f"  ... and {error_count - 5} more (use --verbose to see all)",
                    err=True,
                )


# Register with the CLI group
from video_policy_orchestrator.cli import main  # noqa: E402

main.add_command(scan)
