"""CLI commands for job queue management."""

import logging
from pathlib import Path

import click

from video_policy_orchestrator.config import get_config
from video_policy_orchestrator.db.models import (
    Job,
    JobStatus,
    delete_job,
    get_all_jobs,
    get_jobs_by_status,
)
from video_policy_orchestrator.jobs.queue import (
    cancel_job,
    get_queue_stats,
    recover_stale_jobs,
    requeue_job,
)
from video_policy_orchestrator.jobs.worker import JobWorker

logger = logging.getLogger(__name__)


def _format_job_row(job: Job) -> tuple[str, str, str, str, str, str]:
    """Format a job for table display."""
    status_colors = {
        JobStatus.QUEUED: "yellow",
        JobStatus.RUNNING: "blue",
        JobStatus.COMPLETED: "green",
        JobStatus.FAILED: "red",
        JobStatus.CANCELLED: "bright_black",
    }

    status = click.style(job.status.value, fg=status_colors.get(job.status, "white"))
    job_id = job.id[:8]
    file_name = Path(job.file_path).name
    if len(file_name) > 40:
        file_name = file_name[:37] + "..."

    progress = (
        f"{job.progress_percent:.0f}%" if job.status == JobStatus.RUNNING else "-"
    )
    created = job.created_at[:19].replace("T", " ")

    return (job_id, status, job.job_type.value, file_name, progress, created)


@click.group("jobs")
def jobs_group() -> None:
    """Manage job queue for transcoding and file operations."""
    pass


@jobs_group.command("list")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["queued", "running", "completed", "failed", "cancelled", "all"]),
    default="all",
    help="Filter by job status.",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=50,
    help="Maximum number of jobs to show.",
)
@click.pass_context
def list_jobs(ctx: click.Context, status: str, limit: int) -> None:
    """List jobs in the queue."""
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    if status == "all":
        jobs = get_all_jobs(conn, limit=limit)
    else:
        jobs = get_jobs_by_status(conn, JobStatus(status), limit=limit)

    if not jobs:
        click.echo("No jobs found.")
        return

    # Print header
    click.echo(
        f"{'ID':<10} {'STATUS':<12} {'TYPE':<10} "
        f"{'FILE':<42} {'PROG':<6} {'CREATED':<20}"
    )
    click.echo("-" * 100)

    # Print jobs
    for job in jobs:
        row = _format_job_row(job)
        line = f"{row[0]:<10} {row[1]:<12} {row[2]:<10} "
        line += f"{row[3]:<42} {row[4]:<6} {row[5]:<20}"
        click.echo(line)


@jobs_group.command("status")
@click.pass_context
def show_status(ctx: click.Context) -> None:
    """Show queue statistics."""
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    stats = get_queue_stats(conn)

    click.echo("Job Queue Status")
    click.echo("-" * 30)
    click.echo(f"  Queued:    {stats['queued']:>5}")
    click.echo(f"  Running:   {stats['running']:>5}")
    click.echo(f"  Completed: {stats['completed']:>5}")
    click.echo(f"  Failed:    {stats['failed']:>5}")
    click.echo(f"  Cancelled: {stats['cancelled']:>5}")
    click.echo("-" * 30)
    click.echo(f"  Total:     {stats['total']:>5}")


@jobs_group.command("start")
@click.option(
    "--max-files",
    "-n",
    type=int,
    help="Maximum number of files to process.",
)
@click.option(
    "--max-duration",
    "-d",
    type=int,
    help="Maximum duration in seconds.",
)
@click.option(
    "--end-by",
    "-e",
    help="End time (HH:MM format, 24h).",
)
@click.option(
    "--cpu-cores",
    "-c",
    type=int,
    help="Number of CPU cores for transcoding.",
)
@click.option(
    "--no-purge",
    is_flag=True,
    help="Don't purge old completed jobs.",
)
@click.pass_context
def start_worker(
    ctx: click.Context,
    max_files: int | None,
    max_duration: int | None,
    end_by: str | None,
    cpu_cores: int | None,
    no_purge: bool,
) -> None:
    """Start processing jobs from the queue.

    The worker will process jobs until:
    - Queue is empty
    - --max-files limit reached
    - --max-duration limit reached
    - --end-by time reached
    - SIGTERM/SIGINT received

    Examples:

        # Process all queued jobs
        vpo jobs start

        # Process max 5 files
        vpo jobs start --max-files 5

        # Run for max 1 hour
        vpo jobs start --max-duration 3600

        # Stop at 6:00 AM
        vpo jobs start --end-by 06:00
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Get config defaults
    config = get_config()

    worker = JobWorker(
        conn=conn,
        max_files=max_files or config.worker.max_files,
        max_duration=max_duration or config.worker.max_duration,
        end_by=end_by or config.worker.end_by,
        cpu_cores=cpu_cores or config.worker.cpu_cores,
        auto_purge=not no_purge and config.jobs.auto_purge,
        retention_days=config.jobs.retention_days,
    )

    processed = worker.run()
    click.echo(f"Processed {processed} job(s).")


@jobs_group.command("cancel")
@click.argument("job_id")
@click.pass_context
def cancel_job_cmd(ctx: click.Context, job_id: str) -> None:
    """Cancel a queued job.

    JOB_ID can be the full UUID or just the first 8 characters.
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Find job by prefix
    jobs = get_all_jobs(conn)
    matching = [j for j in jobs if j.id.startswith(job_id)]

    if len(matching) == 0:
        raise click.ClickException(f"Job not found: {job_id}")
    if len(matching) > 1:
        raise click.ClickException(f"Multiple jobs match '{job_id}'. Be more specific.")

    job = matching[0]

    if job.status != JobStatus.QUEUED:
        raise click.ClickException(
            f"Can only cancel queued jobs. Job is {job.status.value}."
        )

    if cancel_job(conn, job.id):
        click.echo(f"Cancelled job {job.id[:8]}")
    else:
        raise click.ClickException("Failed to cancel job.")


@jobs_group.command("retry")
@click.argument("job_id")
@click.pass_context
def retry_job_cmd(ctx: click.Context, job_id: str) -> None:
    """Retry a failed or cancelled job.

    JOB_ID can be the full UUID or just the first 8 characters.
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Find job by prefix
    jobs = get_all_jobs(conn)
    matching = [j for j in jobs if j.id.startswith(job_id)]

    if len(matching) == 0:
        raise click.ClickException(f"Job not found: {job_id}")
    if len(matching) > 1:
        raise click.ClickException(f"Multiple jobs match '{job_id}'. Be more specific.")

    job = matching[0]

    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
        raise click.ClickException(
            f"Can only retry failed or cancelled jobs. Job is {job.status.value}."
        )

    if requeue_job(conn, job.id):
        click.echo(f"Requeued job {job.id[:8]}")
    else:
        raise click.ClickException("Failed to requeue job.")


@jobs_group.command("clear")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["completed", "failed", "cancelled", "all"]),
    default="completed",
    help="Which jobs to clear.",
)
@click.option("--force", "-f", is_flag=True, help="Don't ask for confirmation.")
@click.pass_context
def clear_jobs(ctx: click.Context, status: str, force: bool) -> None:
    """Clear old jobs from the queue.

    By default only clears completed jobs. Use --status to clear
    failed or cancelled jobs, or --status all for everything
    (except queued and running).
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    if status == "all":
        statuses = [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
    else:
        statuses = [JobStatus(status)]

    # Count matching jobs
    total = 0
    for s in statuses:
        jobs = get_jobs_by_status(conn, s)
        total += len(jobs)

    if total == 0:
        click.echo("No jobs to clear.")
        return

    if not force:
        if not click.confirm(f"Clear {total} {status} job(s)?"):
            click.echo("Cancelled.")
            return

    # Delete jobs
    deleted = 0
    for s in statuses:
        jobs = get_jobs_by_status(conn, s)
        for job in jobs:
            if delete_job(conn, job.id):
                deleted += 1

    click.echo(f"Cleared {deleted} job(s).")


@jobs_group.command("recover")
@click.pass_context
def recover_jobs(ctx: click.Context) -> None:
    """Recover stale jobs from dead workers.

    Jobs that have been running for too long without heartbeat
    updates are reset to queued status.
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    count = recover_stale_jobs(conn)
    if count > 0:
        click.echo(f"Recovered {count} stale job(s).")
    else:
        click.echo("No stale jobs found.")


@jobs_group.command("cleanup")
@click.option(
    "--older-than",
    "-o",
    type=int,
    default=30,
    help="Remove jobs older than N days (default: 30).",
)
@click.option(
    "--include-backups",
    is_flag=True,
    help="Also remove .original backup files for cleaned jobs.",
)
@click.option(
    "--remove-temp",
    is_flag=True,
    help="Remove orphaned temp files (.vpo_temp_*).",
)
@click.option(
    "--temp-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory to scan for temp files (default: ~/.vpo/).",
)
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be removed.")
@click.option("--force", "-f", is_flag=True, help="Don't ask for confirmation.")
@click.pass_context
def cleanup_jobs(
    ctx: click.Context,
    older_than: int,
    include_backups: bool,
    remove_temp: bool,
    temp_dir: Path | None,
    dry_run: bool,
    force: bool,
) -> None:
    """Clean up old jobs, backups, and temp files.

    Removes completed/failed/cancelled jobs older than --older-than days.
    Optionally removes associated backup files and orphaned temp files.

    Examples:

        # Preview what would be cleaned
        vpo jobs cleanup --dry-run

        # Clean jobs older than 7 days
        vpo jobs cleanup --older-than 7

        # Also remove backup files
        vpo jobs cleanup --include-backups

        # Clean up orphaned temp files
        vpo jobs cleanup --remove-temp
    """
    from datetime import datetime, timedelta, timezone

    from video_policy_orchestrator.db.models import delete_old_jobs

    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Calculate cutoff date
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than)).isoformat()

    # Count jobs to be removed
    jobs = get_all_jobs(conn)
    old_jobs = [
        j
        for j in jobs
        if j.created_at < cutoff
        and j.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
    ]

    click.echo(f"Cleanup summary (older than {older_than} days):")
    click.echo("-" * 40)
    click.echo(f"  Jobs to remove: {len(old_jobs)}")

    # Find backup files if requested
    backup_files: list[Path] = []
    if include_backups:
        for job in old_jobs:
            output_path = job.output_path
            if output_path:
                original = Path(output_path).with_suffix(
                    Path(output_path).suffix + ".original"
                )
                if original.exists():
                    backup_files.append(original)
        click.echo(f"  Backup files: {len(backup_files)}")

    # Find orphaned temp files if requested
    temp_files: list[Path] = []
    if remove_temp:
        search_dir = temp_dir or Path.home() / ".vpo"
        if search_dir.exists():
            # Search for .vpo_temp_* files
            for temp_file in search_dir.glob(".vpo_temp_*"):
                if temp_file.is_file():
                    temp_files.append(temp_file)
            # Also search in common video directories
            for temp_file in search_dir.rglob(".vpo_temp_*"):
                if temp_file.is_file() and temp_file not in temp_files:
                    temp_files.append(temp_file)
        click.echo(f"  Temp files: {len(temp_files)}")

    total = len(old_jobs) + len(backup_files) + len(temp_files)
    if total == 0:
        click.echo("\nNothing to clean up.")
        return

    if dry_run:
        click.echo("\n[DRY RUN] Would remove:")
        for job in old_jobs[:10]:
            click.echo(f"  Job: {job.id[:8]} ({job.status.value})")
        if len(old_jobs) > 10:
            click.echo(f"  ... and {len(old_jobs) - 10} more jobs")
        for bf in backup_files[:5]:
            click.echo(f"  Backup: {bf}")
        if len(backup_files) > 5:
            click.echo(f"  ... and {len(backup_files) - 5} more backups")
        for tf in temp_files[:5]:
            click.echo(f"  Temp: {tf}")
        if len(temp_files) > 5:
            click.echo(f"  ... and {len(temp_files) - 5} more temp files")
        return

    if not force:
        if not click.confirm(f"Remove {total} item(s)?"):
            click.echo("Cancelled.")
            return

    # Delete old jobs
    deleted_jobs = delete_old_jobs(conn, cutoff)

    # Delete backup files
    deleted_backups = 0
    for bf in backup_files:
        try:
            bf.unlink()
            deleted_backups += 1
        except OSError as e:
            click.echo(f"  Warning: Could not remove {bf}: {e}")

    # Delete temp files
    deleted_temp = 0
    for tf in temp_files:
        try:
            tf.unlink()
            deleted_temp += 1
        except OSError as e:
            click.echo(f"  Warning: Could not remove {tf}: {e}")

    click.echo("\nCleaned up:")
    click.echo(f"  Jobs: {deleted_jobs}")
    if include_backups:
        click.echo(f"  Backups: {deleted_backups}")
    if remove_temp:
        click.echo(f"  Temp files: {deleted_temp}")
