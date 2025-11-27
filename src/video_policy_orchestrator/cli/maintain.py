"""Maintenance commands for VPO.

This module provides commands for periodic maintenance tasks such as:
- Log file compression and cleanup
- Future: database vacuuming, temp file cleanup, etc.
"""

import json
import logging

import click

from video_policy_orchestrator.config import get_config
from video_policy_orchestrator.jobs.logs import (
    LogMaintenanceStats,
    compress_old_logs,
    delete_old_logs,
    get_log_stats,
    run_log_maintenance,
)

logger = logging.getLogger(__name__)


def _format_bytes(num_bytes: int) -> str:
    """Format bytes as human-readable string."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


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


@click.group(name="maintain")
def maintain_group() -> None:
    """Run maintenance tasks.

    VPO periodically needs maintenance to manage log files, clean up
    temporary data, and optimize storage. These commands can be run
    manually or scheduled via cron/systemd timer.

    The daemon also runs log maintenance automatically (daily by default).
    """
    pass


@maintain_group.command(name="logs")
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
        vpo maintain logs

    \b
        # Preview what would happen
        vpo maintain logs --dry-run

    \b
        # Compress logs older than 3 days
        vpo maintain logs --compress-days 3 --compress-only

    \b
        # Delete logs older than 30 days
        vpo maintain logs --delete-days 30 --delete-only
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
        f"{_format_bytes(before_stats['total_bytes'])}"
    )
    click.echo()

    if compression_stats:
        click.echo(f"Compression (logs older than {compress_days} days):")
        if compression_stats.compressed_count > 0:
            count = compression_stats.compressed_count
            click.echo(f"  {action} compress {count} file(s)")
            before = _format_bytes(compression_stats.compressed_bytes_before)
            after = _format_bytes(compression_stats.compressed_bytes_after)
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
            click.echo(f"  Freed: {_format_bytes(deletion_stats.deleted_bytes)}")
        else:
            click.echo("  No logs to delete")

        if deletion_stats.errors:
            click.echo(f"  Errors: {len(deletion_stats.errors)}")
            for err in deletion_stats.errors[:5]:
                click.echo(f"    - {err}")


@maintain_group.command(name="all")
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
def all_command(dry_run: bool, output_json: bool) -> None:
    """Run all maintenance tasks.

    Currently runs:
    - Log compression and deletion

    Future tasks may include:
    - Database vacuuming
    - Temp file cleanup
    - Orphaned backup removal
    """
    config = get_config()

    compression_stats, deletion_stats = run_log_maintenance(
        compression_days=config.jobs.log_compression_days,
        deletion_days=config.jobs.log_deletion_days,
        dry_run=dry_run,
    )

    results = {
        "dry_run": dry_run,
        "logs": {
            "compression": _stats_to_dict(compression_stats),
            "deletion": _stats_to_dict(deletion_stats),
        },
    }

    if output_json:
        click.echo(json.dumps(results, indent=2))
        return

    action = "Would" if dry_run else "Did"

    if dry_run:
        click.echo("Dry run mode - no changes made\n")

    click.echo("Log maintenance:")
    if compression_stats.compressed_count > 0:
        click.echo(
            f"  {action} compress {compression_stats.compressed_count} file(s) "
            f"({_format_bytes(compression_stats.compressed_bytes_before)} -> "
            f"{_format_bytes(compression_stats.compressed_bytes_after)})"
        )
    else:
        click.echo("  No logs to compress")

    if deletion_stats.deleted_count > 0:
        click.echo(
            f"  {action} delete {deletion_stats.deleted_count} file(s) "
            f"(freed {_format_bytes(deletion_stats.deleted_bytes)})"
        )
    else:
        click.echo("  No logs to delete")

    all_errors = (compression_stats.errors or []) + (deletion_stats.errors or [])
    if all_errors:
        click.echo(f"\nErrors: {len(all_errors)}")
        for err in all_errors[:10]:
            click.echo(f"  - {err}")


@maintain_group.command(name="status")
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON.",
)
def status_command(output_json: bool) -> None:
    """Show maintenance status and statistics.

    Displays current state of:
    - Log files (counts, sizes, compression status)
    - Configuration settings
    """
    config = get_config()
    log_stats = get_log_stats()

    results = {
        "logs": {
            **log_stats,
            "compression_days": config.jobs.log_compression_days,
            "deletion_days": config.jobs.log_deletion_days,
        },
    }

    if output_json:
        click.echo(json.dumps(results, indent=2))
        return

    click.echo("Log Files:")
    click.echo(f"  Total:        {log_stats['total_count']} files")
    click.echo(
        f"  Uncompressed: {log_stats['uncompressed_count']} files "
        f"({_format_bytes(log_stats['uncompressed_bytes'])})"
    )
    click.echo(
        f"  Compressed:   {log_stats['compressed_count']} files "
        f"({_format_bytes(log_stats['compressed_bytes'])})"
    )
    click.echo(f"  Total size:   {_format_bytes(log_stats['total_bytes'])}")
    click.echo()
    click.echo("Configuration:")
    click.echo(f"  Compress after: {config.jobs.log_compression_days} days")
    click.echo(f"  Delete after:   {config.jobs.log_deletion_days} days")
