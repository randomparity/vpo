"""CLI commands for managing the video library.

This module provides commands for listing and managing files in the
VPO library database.
"""

import json
import sqlite3
import sys

import click

from vpo.cli.exit_codes import ExitCode
from vpo.core import format_file_size, truncate_filename
from vpo.db.views import get_missing_files


def _get_conn(ctx: click.Context) -> sqlite3.Connection:
    """Extract the database connection from the Click context.

    Raises:
        click.ClickException: If no connection is available.
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")
    return conn


@click.group("library")
def library_group() -> None:
    """Manage video library.

    Commands for listing, filtering, and managing files tracked
    in the VPO library database.

    Examples:

        # Show library summary
        vpo library info

        # List files missing from the filesystem
        vpo library missing

        # Remove DB records for missing files
        vpo library prune --dry-run

        # Check database integrity
        vpo library verify

        # Compact the database
        vpo library optimize --dry-run

        # Find duplicate files
        vpo library duplicates
    """
    pass


@library_group.command("missing")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.option(
    "--limit",
    default=100,
    type=int,
    help="Maximum files to return (default: 100).",
)
@click.pass_context
def missing_command(
    ctx: click.Context,
    json_output: bool,
    limit: int,
) -> None:
    """List files missing from the filesystem.

    Shows files that were previously scanned but are no longer found
    on disk (scan_status='missing'). These files can be pruned with
    'vpo library prune'.

    Examples:

        # List missing files
        vpo library missing

        # List up to 500 missing files as JSON
        vpo library missing --json --limit 500
    """
    conn = _get_conn(ctx)

    files = get_missing_files(conn, limit=limit)

    if json_output:
        output = {
            "total": len(files),
            "files": [
                {
                    "id": f["id"],
                    "path": f["path"],
                    "size_bytes": f["size_bytes"],
                    "scanned_at": f["scanned_at"],
                }
                for f in files
            ],
        }
        click.echo(json.dumps(output, indent=2))
        return

    if not files:
        click.echo("No missing files found.")
        return

    click.echo(f"Missing files: {len(files)}")
    click.echo()

    # Table header
    path_width = 50
    date_width = 20
    size_width = 10
    header = (
        f"{'Filename':<{path_width}}  "
        f"{'Last Scanned':<{date_width}}  "
        f"{'Size':>{size_width}}"
    )
    click.echo(header)
    click.echo("\u2500" * len(header))

    for f in files:
        path = truncate_filename(f["filename"] or f["path"] or "", path_width)

        scanned = (f["scanned_at"] or "")[:19].replace("T", " ")
        size = format_file_size(f["size_bytes"]) if f["size_bytes"] else "\u2014"

        click.echo(
            f"{path:<{path_width}}  {scanned:<{date_width}}  {size:>{size_width}}"
        )


@library_group.command("prune")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be pruned without making changes.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def prune_command(
    ctx: click.Context,
    dry_run: bool,
    yes: bool,
    json_output: bool,
) -> None:
    """Remove database records for missing files.

    Deletes records for files with scan_status='missing' from the
    library database. Use --dry-run to preview what would be removed.

    Examples:

        # Preview what would be pruned
        vpo library prune --dry-run

        # Prune without confirmation
        vpo library prune --yes

        # Prune with JSON output
        vpo library prune --yes --json
    """
    conn = _get_conn(ctx)

    from vpo.db.views import get_missing_files_count

    # Get exact count for confirmation prompt (unlimited)
    missing_count = get_missing_files_count(conn)

    if missing_count == 0:
        if json_output:
            click.echo(json.dumps({"files_pruned": 0, "dry_run": dry_run}))
        else:
            click.echo("No missing files to prune.")
        return

    if dry_run:
        # Fetch limited preview of paths
        missing = get_missing_files(conn, limit=1000)
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "files_pruned": missing_count,
                        "dry_run": True,
                        "files": [{"id": f["id"], "path": f["path"]} for f in missing],
                    },
                    indent=2,
                )
            )
        else:
            click.echo(f"Would prune {missing_count} missing file(s):")
            for f in missing:
                click.echo(f"  {f['path']}")
            if missing_count > len(missing):
                click.echo(f"  ... and {missing_count - len(missing)} more")
        return

    # Confirm unless --yes
    if not yes:
        click.confirm(
            f"Prune {missing_count} missing file(s) from the database?",
            abort=True,
        )

    # Use PruneJobService for atomic deletion with job tracking
    from vpo.jobs.services.prune import PruneJobService
    from vpo.jobs.tracking import complete_prune_job, create_prune_job

    try:
        job = create_prune_job(conn)
        service = PruneJobService(conn)
        result = service.process()
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            raise click.ClickException(
                "Database is locked by another process. "
                "Close other VPO instances and try again."
            ) from e
        raise

    summary = {"files_pruned": result.files_pruned}
    complete_prune_job(conn, job.id, summary, error_message=result.error_message)

    if not result.success:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "files_pruned": 0,
                        "dry_run": False,
                        "error": result.error_message,
                    }
                )
            )
        else:
            click.echo(f"Prune failed: {result.error_message}", err=True)
        sys.exit(ExitCode.OPERATION_FAILED)

    if json_output:
        click.echo(json.dumps({"files_pruned": result.files_pruned, "dry_run": False}))
    else:
        click.echo(f"Pruned {result.files_pruned} missing file(s).")


@library_group.command("info")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def info_command(
    ctx: click.Context,
    json_output: bool,
) -> None:
    """Show library summary statistics.

    Displays file counts by scan status, track counts by type,
    database size, and schema version.

    Examples:

        vpo library info

        vpo library info --json
    """
    from vpo.db.views import get_library_info

    conn = _get_conn(ctx)

    info = get_library_info(conn)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "files": {
                        "total": info.total_files,
                        "ok": info.files_ok,
                        "missing": info.files_missing,
                        "error": info.files_error,
                        "pending": info.files_pending,
                    },
                    "total_size_bytes": info.total_size_bytes,
                    "tracks": {
                        "video": info.video_tracks,
                        "audio": info.audio_tracks,
                        "subtitle": info.subtitle_tracks,
                        "attachment": info.attachment_tracks,
                    },
                    "database": {
                        "size_bytes": info.db_size_bytes,
                        "page_size": info.db_page_size,
                        "page_count": info.db_page_count,
                        "freelist_count": info.db_freelist_count,
                        "schema_version": info.schema_version,
                    },
                },
                indent=2,
            )
        )
        return

    click.echo("Library Summary")
    click.echo("=" * 40)

    click.echo(f"\nFiles: {info.total_files:,}")
    click.echo(f"  OK:      {info.files_ok:,}")
    click.echo(f"  Missing: {info.files_missing:,}")
    click.echo(f"  Error:   {info.files_error:,}")
    if info.files_pending > 0:
        click.echo(f"  Pending: {info.files_pending:,}")
    click.echo(f"  Total size: {format_file_size(info.total_size_bytes)}")

    total_tracks = (
        info.video_tracks
        + info.audio_tracks
        + info.subtitle_tracks
        + info.attachment_tracks
    )
    click.echo(f"\nTracks: {total_tracks:,}")
    click.echo(f"  Video:      {info.video_tracks:,}")
    click.echo(f"  Audio:      {info.audio_tracks:,}")
    click.echo(f"  Subtitle:   {info.subtitle_tracks:,}")
    click.echo(f"  Attachment: {info.attachment_tracks:,}")

    click.echo("\nDatabase")
    click.echo(f"  Size:    {format_file_size(info.db_size_bytes)}")
    click.echo(f"  Schema:  v{info.schema_version}")
    if info.db_freelist_count > 0:
        free_bytes = info.db_freelist_count * info.db_page_size
        click.echo(f"  Free:    {format_file_size(free_bytes)} (reclaimable)")


@library_group.command("optimize")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show estimated savings without making changes.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def optimize_command(
    ctx: click.Context,
    dry_run: bool,
    yes: bool,
    json_output: bool,
) -> None:
    """Compact and optimize the database.

    Runs VACUUM to reclaim unused space and ANALYZE to update
    query planner statistics. Requires exclusive database access.

    Examples:

        # Preview estimated savings
        vpo library optimize --dry-run

        # Optimize without confirmation
        vpo library optimize --yes
    """
    from vpo.db.views import run_optimize

    conn = _get_conn(ctx)

    if dry_run:
        result = run_optimize(conn, dry_run=True)
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "size_before": result.size_before,
                        "size_after": result.size_after,
                        "space_saved": result.space_saved,
                        "freelist_pages": result.freelist_pages,
                        "dry_run": True,
                    },
                    indent=2,
                )
            )
        else:
            click.echo(f"Current DB size: {format_file_size(result.size_before)}")
            click.echo(f"Free pages:      {result.freelist_pages}")
            click.echo(f"Estimated savings: {format_file_size(result.space_saved)}")
        return

    # Confirm unless --yes
    if not yes:
        click.confirm(
            "Optimize the database? This requires exclusive access.",
            abort=True,
        )

    try:
        result = run_optimize(conn, dry_run=False)
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            raise click.ClickException(
                "Database is locked by another process. "
                "Close other VPO instances and try again."
            ) from e
        raise

    if json_output:
        click.echo(
            json.dumps(
                {
                    "size_before": result.size_before,
                    "size_after": result.size_after,
                    "space_saved": result.space_saved,
                    "freelist_pages": result.freelist_pages,
                    "dry_run": False,
                },
                indent=2,
            )
        )
    else:
        click.echo(f"Before: {format_file_size(result.size_before)}")
        click.echo(f"After:  {format_file_size(result.size_after)}")
        click.echo(f"Saved:  {format_file_size(result.space_saved)}")


@library_group.command("verify")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def verify_command(
    ctx: click.Context,
    json_output: bool,
) -> None:
    """Check database integrity.

    Runs SQLite integrity_check and foreign_key_check to verify
    database consistency. Exits with code 1 if errors are found.

    Examples:

        vpo library verify

        vpo library verify --json
    """
    from vpo.db.views import run_integrity_check

    conn = _get_conn(ctx)

    try:
        result = run_integrity_check(conn)
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            raise click.ClickException(
                "Database is locked by another process. "
                "Close other VPO instances and try again."
            ) from e
        raise

    if json_output:
        click.echo(
            json.dumps(
                {
                    "integrity_ok": result.integrity_ok,
                    "integrity_errors": result.integrity_errors,
                    "foreign_key_ok": result.foreign_key_ok,
                    "foreign_key_errors": [
                        {
                            "table": e.table,
                            "rowid": e.rowid,
                            "parent": e.parent,
                            "fkid": e.fkid,
                        }
                        for e in result.foreign_key_errors
                    ],
                },
                indent=2,
            )
        )
    else:
        if result.integrity_ok:
            click.echo("Integrity check: OK")
        else:
            click.echo("Integrity check: FAILED")
            for err in result.integrity_errors:
                click.echo(f"  {err}")

        if result.foreign_key_ok:
            click.echo("Foreign key check: OK")
        else:
            click.echo("Foreign key check: FAILED")
            for e in result.foreign_key_errors:
                click.echo(f"  {e.table} rowid={e.rowid} -> {e.parent} (fk={e.fkid})")

    if not result.integrity_ok or not result.foreign_key_ok:
        sys.exit(ExitCode.DATABASE_ERROR)


@library_group.command("duplicates")
@click.option(
    "--limit",
    default=50,
    type=int,
    help="Maximum duplicate groups to show (default: 50).",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def duplicates_command(
    ctx: click.Context,
    limit: int,
    json_output: bool,
) -> None:
    """Find files with duplicate content hashes.

    Groups files by content_hash and shows groups with 2 or more
    matching files. Only files scanned with --verify-hash are
    included (files without a content hash are excluded).

    Examples:

        vpo library duplicates

        vpo library duplicates --limit 10 --json
    """
    from vpo.db.views import get_duplicate_files

    conn = _get_conn(ctx)

    groups = get_duplicate_files(conn, limit=limit)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "total_groups": len(groups),
                    "groups": [
                        {
                            "content_hash": g.content_hash,
                            "file_count": g.file_count,
                            "total_size_bytes": g.total_size_bytes,
                            "paths": g.paths,
                        }
                        for g in groups
                    ],
                },
                indent=2,
            )
        )
        return

    if not groups:
        click.echo("No duplicate files found.")
        return

    click.echo(f"Duplicate groups: {len(groups)}")
    click.echo()

    for g in groups:
        hash_short = g.content_hash[:12]
        size = format_file_size(g.total_size_bytes)
        click.echo(f"Hash: {hash_short}...  Files: {g.file_count}  Size: {size}")
        for path in g.paths:
            click.echo(f"  {path}")
        click.echo()


def _get_db_path(ctx: click.Context):
    """Extract the database path from the Click context.

    Returns:
        Path object for the database path.

    Raises:
        click.ClickException: If no database path is available.
    """
    from pathlib import Path

    db_path = ctx.obj.get("db_path")
    if db_path is None:
        raise click.ClickException("No database path configured.")
    return Path(db_path)


@library_group.command("backup")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True),
    help="Output path for backup file (default: ~/.vpo/backups/).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be backed up without creating archive.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def backup_command(
    ctx: click.Context,
    output: str | None,
    dry_run: bool,
    json_output: bool,
) -> None:
    """Create a compressed backup of the library database.

    Creates a tar.gz archive containing the SQLite database and
    metadata JSON. Uses the SQLite online backup API to safely
    copy the database even if it's in use.

    Examples:

        # Create backup in default location
        vpo library backup

        # Create backup at custom path
        vpo library backup --output /path/to/backup.tar.gz

        # Preview without creating
        vpo library backup --dry-run
    """
    from pathlib import Path

    from vpo.db.backup import (
        ESTIMATED_COMPRESSION_RATIO,
        BackupIOError,
        BackupLockError,
        InsufficientSpaceError,
        _generate_backup_filename,
        _get_default_backup_dir,
        _get_library_stats,
        create_backup,
    )
    from vpo.db.schema import SCHEMA_VERSION

    conn = _get_conn(ctx)
    db_path = _get_db_path(ctx)

    # Determine output path
    if output:
        output_path = Path(output).resolve()
    else:
        output_path = _get_default_backup_dir() / _generate_backup_filename()

    if dry_run:
        # Show what would be backed up
        try:
            db_size = db_path.stat().st_size
        except OSError as e:
            raise click.ClickException(f"Failed to read database: {e}") from e

        file_count, total_library_size = _get_library_stats(conn)
        estimated_archive = int(db_size * ESTIMATED_COMPRESSION_RATIO)
        estimated_min = int(estimated_archive * 0.7)
        estimated_max = int(estimated_archive * 1.3)

        if json_output:
            click.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "database_path": str(db_path),
                        "database_size_bytes": db_size,
                        "output_path": str(output_path),
                        "estimated_archive_min_bytes": estimated_min,
                        "estimated_archive_max_bytes": estimated_max,
                        "file_count": file_count,
                        "schema_version": SCHEMA_VERSION,
                    },
                    indent=2,
                )
            )
        else:
            click.echo("Would create backup:")
            click.echo(f"  Database: {db_path} ({format_file_size(db_size)})")
            click.echo(f"  Output: {output_path}")
            min_size = format_file_size(estimated_min)
            max_size = format_file_size(estimated_max)
            click.echo(f"  Estimated archive size: ~{min_size}-{max_size}")
            click.echo(f"  Files in library: {file_count:,}")
            click.echo(f"  Schema version: {SCHEMA_VERSION}")
        return

    # Create backup
    try:
        result = create_backup(
            db_path=db_path,
            output_path=output_path if output else None,
            conn=conn,
        )
    except BackupLockError as e:
        if json_output:
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(ExitCode.DATABASE_LOCKED)
    except InsufficientSpaceError as e:
        if json_output:
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(ExitCode.INSUFFICIENT_SPACE)
    except BackupIOError as e:
        if json_output:
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(ExitCode.OPERATION_FAILED)

    # Output result
    if json_output:
        compression_ratio = (
            result.metadata.database_size_bytes - result.archive_size_bytes
        ) / result.metadata.database_size_bytes
        click.echo(
            json.dumps(
                {
                    "success": True,
                    "path": str(result.path),
                    "archive_size_bytes": result.archive_size_bytes,
                    "database_size_bytes": result.metadata.database_size_bytes,
                    "compression_ratio": round(compression_ratio, 3),
                    "file_count": result.metadata.file_count,
                    "schema_version": result.metadata.schema_version,
                    "created_at": result.metadata.created_at,
                },
                indent=2,
            )
        )
    else:
        compression_pct = int(
            100
            * (result.metadata.database_size_bytes - result.archive_size_bytes)
            / result.metadata.database_size_bytes
        )
        click.echo(f"Backup created: {result.path}")
        db_size = format_file_size(result.metadata.database_size_bytes)
        archive_size = format_file_size(result.archive_size_bytes)
        click.echo(f"  Database size: {db_size}")
        click.echo(f"  Archive size:  {archive_size} ({compression_pct}% compression)")
        click.echo(f"  Files in library: {result.metadata.file_count:,}")
