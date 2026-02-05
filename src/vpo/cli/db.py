"""CLI commands for managing the VPO database.

This module provides commands for database operations including:
- Library statistics and integrity checks
- File tracking (missing, prune, duplicates)
- Database maintenance (optimize, backup, restore)
- Log file maintenance

Renamed from library.py for clearer scope - these are database operations.
"""

import json
import logging
import sqlite3
import sys

import click

from vpo.cli.exit_codes import ExitCode
from vpo.config import get_config
from vpo.core import format_file_size, truncate_filename
from vpo.db.views import get_missing_files
from vpo.jobs.logs import (
    LogMaintenanceStats,
    compress_old_logs,
    delete_old_logs,
    get_log_stats,
)

logger = logging.getLogger(__name__)


def _get_conn(ctx: click.Context) -> sqlite3.Connection:
    """Extract the database connection from the Click context.

    Raises:
        click.ClickException: If no connection is available.
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")
    return conn


@click.group("db")
def db_group() -> None:
    """Manage VPO database.

    Commands for viewing statistics, checking integrity, and managing
    files tracked in the VPO database.

    Examples:

        # Show database summary
        vpo db info

        # List files missing from the filesystem
        vpo db missing

        # Remove DB records for missing files
        vpo db prune --dry-run

        # Check database integrity
        vpo db verify

        # Compact the database
        vpo db optimize --dry-run

        # Find duplicate files
        vpo db duplicates

        # Create a database backup
        vpo db backup

        # Restore from a backup
        vpo db restore backup.tar.gz

        # List available backups
        vpo db backups

        # Manage log files
        vpo db logs --compress-days 7
    """
    pass


@db_group.command("missing")
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
    'vpo db prune'.

    Examples:

        # List missing files
        vpo db missing

        # List up to 500 missing files as JSON
        vpo db missing --json --limit 500
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


@db_group.command("prune")
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
    database. Use --dry-run to preview what would be removed.

    Examples:

        # Preview what would be pruned
        vpo db prune --dry-run

        # Prune without confirmation
        vpo db prune --yes

        # Prune with JSON output
        vpo db prune --yes --json
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


@db_group.command("info")
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
    """Show database summary statistics.

    Displays file counts by scan status, track counts by type,
    database size, and schema version.

    Examples:

        vpo db info

        vpo db info --json
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

    click.echo("Database Summary")
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


@db_group.command("optimize")
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
        vpo db optimize --dry-run

        # Optimize without confirmation
        vpo db optimize --yes
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


@db_group.command("verify")
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

        vpo db verify

        vpo db verify --json
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


@db_group.command("duplicates")
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

        vpo db duplicates

        vpo db duplicates --limit 10 --json
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
    """Extract the database path from the Click context or use default.

    Returns:
        Path object for the database path.
    """
    from vpo.db.connection import get_default_db_path

    db_path = ctx.obj.get("db_path")
    if db_path is not None:
        from pathlib import Path

        return Path(db_path)
    return get_default_db_path()


@db_group.command("backup")
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
    """Create a compressed backup of the database.

    Creates a tar.gz archive containing the SQLite database and
    metadata JSON. Uses the SQLite online backup API to safely
    copy the database even if it's in use.

    Examples:

        # Create backup in default location
        vpo db backup

        # Create backup at custom path
        vpo db backup --output /path/to/backup.tar.gz

        # Preview without creating
        vpo db backup --dry-run
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
    db_size_bytes = result.metadata.database_size_bytes
    if json_output:
        compression_ratio = (
            (db_size_bytes - result.archive_size_bytes) / db_size_bytes
            if db_size_bytes > 0
            else 0.0
        )
        click.echo(
            json.dumps(
                {
                    "success": True,
                    "path": str(result.path),
                    "archive_size_bytes": result.archive_size_bytes,
                    "database_size_bytes": db_size_bytes,
                    "compression_ratio": round(compression_ratio, 3),
                    "file_count": result.metadata.file_count,
                    "schema_version": result.metadata.schema_version,
                    "created_at": result.metadata.created_at,
                },
                indent=2,
            )
        )
    else:
        compression_pct = (
            int(100 * (db_size_bytes - result.archive_size_bytes) / db_size_bytes)
            if db_size_bytes > 0
            else 0
        )
        click.echo(f"Backup created: {result.path}")
        click.echo(f"  Database size: {format_file_size(db_size_bytes)}")
        click.echo(
            f"  Archive size:  {format_file_size(result.archive_size_bytes)} "
            f"({compression_pct}% compression)"
        )
        click.echo(f"  Files in library: {result.metadata.file_count:,}")


@db_group.command("restore")
@click.argument(
    "backup_file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate archive without restoring.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def restore_command(
    ctx: click.Context,
    backup_file: str,
    yes: bool,
    dry_run: bool,
    json_output: bool,
) -> None:
    """Restore the database from a backup archive.

    Validates the backup archive and replaces the current database
    with the backup contents. Uses atomic operations to prevent
    corruption.

    Examples:

        # Restore with confirmation prompt
        vpo db restore backup.tar.gz

        # Restore without prompt
        vpo db restore --yes backup.tar.gz

        # Validate only (don't restore)
        vpo db restore --dry-run backup.tar.gz
    """
    from pathlib import Path

    from vpo.db.backup import (
        BackupIOError,
        BackupLockError,
        BackupValidationError,
        InsufficientSpaceError,
        restore_backup,
        validate_backup,
    )
    from vpo.db.schema import SCHEMA_VERSION

    db_path = _get_db_path(ctx)
    backup_path = Path(backup_file).resolve()

    # Validate backup first
    try:
        metadata = validate_backup(backup_path)
    except BackupValidationError as e:
        if json_output:
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            click.echo(f"Error: Invalid backup archive - {e}", err=True)
        sys.exit(ExitCode.INVALID_ARCHIVE)
    except BackupIOError as e:
        if json_output:
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(ExitCode.OPERATION_FAILED)

    # Check schema version
    schema_mismatch = metadata.schema_version != SCHEMA_VERSION

    if dry_run:
        # Just validate and show info
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "valid": True,
                        "backup_path": str(backup_path),
                        "created_at": metadata.created_at,
                        "vpo_version": metadata.vpo_version,
                        "schema_version": metadata.schema_version,
                        "current_schema_version": SCHEMA_VERSION,
                        "schema_mismatch": schema_mismatch,
                        "database_size_bytes": metadata.database_size_bytes,
                        "file_count": metadata.file_count,
                    },
                    indent=2,
                )
            )
        else:
            click.echo(f"Validating backup: {backup_path}")
            click.echo()
            click.echo("Archive valid:")
            created_str = metadata.created_at.replace("T", " ").replace("Z", " UTC")
            click.echo(f"  Created: {created_str}")
            click.echo(f"  VPO version: {metadata.vpo_version}")
            schema_status = f"{metadata.schema_version} (current: {SCHEMA_VERSION})"
            click.echo(f"  Schema version: {schema_status}")
            db_size_str = format_file_size(metadata.database_size_bytes)
            click.echo(f"  Database size: {db_size_str}")
            click.echo(f"  Files in backup: {metadata.file_count:,}")
            click.echo()
            click.echo("No changes made (dry run).")
        return

    # Reject backups from newer schema versions
    if metadata.schema_version > SCHEMA_VERSION:
        error_msg = (
            f"Backup schema version ({metadata.schema_version}) is newer "
            f"than current VPO schema ({SCHEMA_VERSION}). "
            "Update VPO before restoring this backup."
        )
        if json_output:
            click.echo(json.dumps({"success": False, "error": error_msg}))
        else:
            click.echo(f"Error: {error_msg}", err=True)
        sys.exit(ExitCode.SCHEMA_INCOMPATIBLE)

    # Show restore info
    if not json_output:
        click.echo(f"Restoring from: {backup_path}")
        created_display = metadata.created_at.replace("T", " ").replace("Z", " UTC")
        click.echo(f"  Created: {created_display}")
        click.echo(f"  Files: {metadata.file_count:,}")
        click.echo(f"  Schema: v{metadata.schema_version}")
        click.echo()

        if schema_mismatch:
            click.echo(
                f"Warning: Backup schema version ({metadata.schema_version}) differs "
                f"from current VPO schema ({SCHEMA_VERSION})."
            )
            click.echo("  The database will be migrated after restore.")
            click.echo()

    # Confirm unless --yes
    if not yes and not json_output:
        click.confirm(
            "This will replace your current library database. Continue?",
            abort=True,
        )

    # Perform restore
    try:
        result = restore_backup(
            backup_path=backup_path,
            db_path=db_path,
            force=False,
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
    except (BackupValidationError, BackupIOError) as e:
        if json_output:
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(ExitCode.OPERATION_FAILED)

    # Output result
    if json_output:
        click.echo(
            json.dumps(
                {
                    "success": True,
                    "source_path": str(result.source_path),
                    "database_path": str(result.database_path),
                    "duration_seconds": round(result.duration_seconds, 2),
                    "schema_mismatch": result.schema_mismatch,
                    "file_count": result.metadata.file_count,
                },
                indent=2,
            )
        )
    else:
        click.echo()
        click.echo("Restore complete.")
        click.echo(f"  Database restored to: {result.database_path}")
        click.echo(f"  Duration: {result.duration_seconds:.1f} seconds")


@db_group.command("backups")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, readable=True),
    help="Directory to scan for backups (default: ~/.vpo/backups/).",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def backups_command(
    ctx: click.Context,
    path: str | None,
    json_output: bool,
) -> None:
    """List available backups in the backup directory.

    Scans for vpo-library-*.tar.gz files and displays metadata
    including creation date, size, and file count.

    Examples:

        # List backups in default location
        vpo db backups

        # List backups in custom directory
        vpo db backups --path /mnt/external/vpo-backups/
    """
    from pathlib import Path

    from vpo.db.backup import BackupIOError, _get_default_backup_dir, list_backups

    backup_dir = Path(path) if path else _get_default_backup_dir()

    try:
        backups = list_backups(backup_dir)
    except BackupIOError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(ExitCode.OPERATION_FAILED)

    if json_output:
        total_size = sum(b.archive_size_bytes for b in backups)
        click.echo(
            json.dumps(
                {
                    "directory": str(backup_dir),
                    "total_count": len(backups),
                    "total_size_bytes": total_size,
                    "backups": [
                        {
                            "filename": b.filename,
                            "path": str(b.path),
                            "created_at": b.created_at,
                            "archive_size_bytes": b.archive_size_bytes,
                            "database_size_bytes": (
                                b.metadata.database_size_bytes if b.metadata else None
                            ),
                            "file_count": b.metadata.file_count if b.metadata else None,
                            "schema_version": (
                                b.metadata.schema_version if b.metadata else None
                            ),
                        }
                        for b in backups
                    ],
                },
                indent=2,
            )
        )
        return

    if not backups:
        click.echo(f"No backups found in {backup_dir}")
        click.echo()
        click.echo("Create a backup with: vpo db backup")
        return

    click.echo(f"Backups in {backup_dir}:")
    click.echo()

    # Table header
    name_width = 44
    date_width = 18
    size_width = 10
    files_width = 8
    header = (
        f"{'Filename':<{name_width}}  "
        f"{'Created':<{date_width}}  "
        f"{'Size':>{size_width}}  "
        f"{'Files':>{files_width}}"
    )
    click.echo(header)
    click.echo("\u2500" * len(header))

    for b in backups:
        # Format filename
        filename = b.filename
        if len(filename) > name_width:
            filename = filename[: name_width - 3] + "..."

        # Format date (remove T and Z, truncate seconds)
        created = b.created_at.replace("T", " ").replace("Z", "")[:16]

        # Format size
        size = format_file_size(b.archive_size_bytes)

        # Format file count
        if b.metadata:
            files = f"{b.metadata.file_count:,}"
        else:
            files = "\u2014"

        click.echo(
            f"{filename:<{name_width}}  "
            f"{created:<{date_width}}  "
            f"{size:>{size_width}}  "
            f"{files:>{files_width}}"
        )

    click.echo()
    total_size = sum(b.archive_size_bytes for b in backups)
    click.echo(f"Total: {len(backups)} backup(s) ({format_file_size(total_size)})")


# =============================================================================
# Log Maintenance (absorbed from maintain.py)
# =============================================================================


def _stats_to_dict(stats: LogMaintenanceStats) -> dict:
    """Convert LogMaintenanceStats to dict for JSON output."""
    return {
        "compressed_count": stats.compressed_count,
        "compressed_bytes_before": stats.compressed_bytes_before,
        "compressed_bytes_after": stats.compressed_bytes_after,
        "compression_ratio": stats.compression_ratio,
        "deleted_count": stats.deleted_count,
        "deleted_bytes": stats.deleted_bytes,
        "errors": stats.errors or [],
    }


@db_group.command(name="logs")
@click.option(
    "--compress-days",
    type=int,
    default=None,
    help="Compress logs older than N days (default: from config, 7 days).",
)
@click.option(
    "--delete-days",
    type=int,
    default=None,
    help="Delete logs older than N days (default: from config, 90 days).",
)
@click.option(
    "--compress-only",
    is_flag=True,
    help="Only compress logs, don't delete.",
)
@click.option(
    "--delete-only",
    is_flag=True,
    help="Only delete logs, don't compress.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON.",
)
def logs_command(
    compress_days: int | None,
    delete_days: int | None,
    compress_only: bool,
    delete_only: bool,
    dry_run: bool,
    output_json: bool,
) -> None:
    """Compress and delete old job log files.

    By default, logs are:
    - Compressed (gzip) after 7 days
    - Deleted after 90 days

    These defaults can be changed in config.toml under [jobs]:

    \b
        [jobs]
        log_compression_days = 7
        log_deletion_days = 90

    Or via environment variables:

    \b
        VPO_LOG_COMPRESSION_DAYS=7
        VPO_LOG_DELETION_DAYS=90

    Examples:

    \b
        # Run with defaults from config
        vpo db logs

    \b
        # Preview what would happen
        vpo db logs --dry-run

    \b
        # Compress logs older than 3 days
        vpo db logs --compress-days 3 --compress-only

    \b
        # Delete logs older than 30 days
        vpo db logs --delete-days 30 --delete-only
    """
    if compress_only and delete_only:
        raise click.UsageError("Cannot use both --compress-only and --delete-only")

    # Get defaults from config
    config = get_config()
    if compress_days is None:
        compress_days = config.jobs.log_compression_days
    if delete_days is None:
        delete_days = config.jobs.log_deletion_days

    # Get current stats
    before_stats = get_log_stats()

    results: dict = {
        "dry_run": dry_run,
        "before": before_stats,
        "compression": None,
        "deletion": None,
    }

    compression_stats: LogMaintenanceStats | None = None
    deletion_stats: LogMaintenanceStats | None = None

    # Run operations
    if not delete_only:
        compression_stats = compress_old_logs(compress_days, dry_run=dry_run)
        results["compression"] = _stats_to_dict(compression_stats)

    if not compress_only:
        deletion_stats = delete_old_logs(delete_days, dry_run=dry_run)
        results["deletion"] = _stats_to_dict(deletion_stats)

    # Get after stats
    if not dry_run:
        after_stats = get_log_stats()
        results["after"] = after_stats
    else:
        results["after"] = before_stats

    # Output
    if output_json:
        click.echo(json.dumps(results, indent=2))
        return

    # Human-readable output
    action = "Would" if dry_run else "Did"

    if dry_run:
        click.echo("Dry run mode - no changes made\n")

    click.echo(
        f"Log directory: {before_stats['total_count']} files, "
        f"{format_file_size(before_stats['total_bytes'])}"
    )
    click.echo()

    if compression_stats:
        click.echo(f"Compression (logs older than {compress_days} days):")
        if compression_stats.compressed_count > 0:
            count = compression_stats.compressed_count
            click.echo(f"  {action} compress {count} file(s)")
            before = format_file_size(compression_stats.compressed_bytes_before)
            after = format_file_size(compression_stats.compressed_bytes_after)
            click.echo(f"  Before: {before}")
            click.echo(f"  After:  {after}")
            if compression_stats.compressed_bytes_before > 0:
                ratio = compression_stats.compression_ratio * 100
                click.echo(f"  Ratio:  {ratio:.1f}% of original")
        else:
            click.echo("  No logs to compress")

        if compression_stats.errors:
            click.echo(f"  Errors: {len(compression_stats.errors)}")
            for err in compression_stats.errors[:5]:
                click.echo(f"    - {err}")

        click.echo()

    if deletion_stats:
        click.echo(f"Deletion (logs older than {delete_days} days):")
        if deletion_stats.deleted_count > 0:
            click.echo(f"  {action} delete {deletion_stats.deleted_count} file(s)")
            click.echo(f"  Freed: {format_file_size(deletion_stats.deleted_bytes)}")
        else:
            click.echo("  No logs to delete")

        if deletion_stats.errors:
            click.echo(f"  Errors: {len(deletion_stats.errors)}")
            for err in deletion_stats.errors[:5]:
                click.echo(f"    - {err}")
