"""CLI commands for job queue management."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

from vpo.cli.formatting import get_status_color
from vpo.config import get_config
from vpo.core import parse_relative_time, truncate_filename
from vpo.db import (
    Job,
    JobStatus,
    JobType,
    delete_job,
    get_all_jobs,
    get_jobs_by_id_prefix,
    get_jobs_by_status,
    get_jobs_filtered,
)
from vpo.jobs.queue import (
    cancel_job,
    get_queue_stats,
    recover_stale_jobs,
    requeue_job,
)
from vpo.jobs.worker import JobWorker

logger = logging.getLogger(__name__)


def _format_job_row(job: Job) -> tuple[str, str, str, str, str, str, str]:
    """Format a job for table display.

    Returns:
        Tuple of (job_id, status_value, status_color, job_type,
        file_name, progress, created). Color is returned separately
        to allow proper column width formatting.
    """
    status_value = job.status.value
    status_color = get_status_color(job.status)
    job_id = job.id[:8]
    file_name = truncate_filename(Path(job.file_path).name, 40)

    progress = (
        f"{job.progress_percent:.0f}%" if job.status == JobStatus.RUNNING else "-"
    )
    created = job.created_at[:19].replace("T", " ")

    return (
        job_id,
        status_value,
        status_color,
        job.job_type.value,
        file_name,
        progress,
        created,
    )


@click.group("jobs")
def jobs_group() -> None:
    """Manage job queue for transcoding and file operations.

    Examples:

        # List all jobs
        vpo jobs list

        # List only running jobs
        vpo jobs list --status running

        # Show details for a specific job
        vpo jobs show <job-id>

        # Cancel a running job
        vpo jobs cancel <job-id>

        # Clean up old completed jobs
        vpo jobs clean --before 30d
    """
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
    "--type",
    "-t",
    "job_type",
    type=click.Choice(["scan", "apply", "transcode", "all"]),
    default="all",
    help="Filter by job type.",
)
@click.option(
    "--since",
    help="Show jobs since (relative: 1d, 1w, 2h or ISO-8601 date).",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=50,
    help="Maximum number of jobs to show.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format.",
)
@click.pass_context
def list_jobs(
    ctx: click.Context,
    status: str,
    job_type: str,
    since: str | None,
    limit: int,
    json_output: bool,
) -> None:
    """List jobs in the queue.

    Examples:

        # List all jobs
        vpo jobs list

        # List failed scan jobs
        vpo jobs list --status failed --type scan

        # List jobs from last 24 hours
        vpo jobs list --since 1d

        # List jobs from last week in JSON
        vpo jobs list --since 1w --json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Parse since parameter
    since_iso: str | None = None
    if since:
        try:
            # Try parsing as relative date first
            since_dt = parse_relative_time(since)
            since_iso = since_dt.isoformat()
        except ValueError:
            # Assume it's an ISO-8601 date
            since_iso = since

    # Get jobs with filters
    status_filter = None if status == "all" else JobStatus(status)
    type_filter = None if job_type == "all" else JobType(job_type)

    jobs = get_jobs_filtered(
        conn,
        status=status_filter,
        job_type=type_filter,
        since=since_iso,
        limit=limit,
    )

    if json_output:
        _output_jobs_json(jobs)
        return

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
        # Format width first, then apply color to avoid ANSI codes affecting alignment
        status_formatted = f"{row[1]:<12}"
        status_colored = click.style(status_formatted, fg=row[2])
        line = f"{row[0]:<10} {status_colored} {row[3]:<10} "
        line += f"{row[4]:<42} {row[5]:<6} {row[6]:<20}"
        click.echo(line)


def _output_jobs_json(jobs: list[Job]) -> None:
    """Output jobs list in JSON format."""
    data = []
    for job in jobs:
        job_data = {
            "id": job.id,
            "status": job.status.value,
            "type": job.job_type.value,
            "file_path": job.file_path,
            "progress_percent": job.progress_percent,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "policy_name": job.policy_name,
            "error_message": job.error_message,
        }
        data.append(job_data)
    click.echo(json.dumps(data, indent=2))


@jobs_group.command("show")
@click.argument("job_id")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format.",
)
@click.pass_context
def show_job(ctx: click.Context, job_id: str, json_output: bool) -> None:
    """Show detailed information about a job.

    JOB_ID can be the full UUID or a prefix (minimum 4 characters).

    Examples:

        # Show job by full ID
        vpo jobs show 12345678-1234-1234-1234-123456789abc

        # Show job by prefix
        vpo jobs show 1234

        # Output as JSON
        vpo jobs show 1234 --json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Find job by prefix
    matching = get_jobs_by_id_prefix(conn, job_id)

    if len(matching) == 0:
        raise click.ClickException(f"Job not found: {job_id}")
    if len(matching) > 1:
        click.echo(f"Multiple jobs match '{job_id}':", err=True)
        for job in matching[:5]:
            click.echo(f"  {job.id[:8]} - {job.status.value}", err=True)
        if len(matching) > 5:
            click.echo(f"  ... and {len(matching) - 5} more", err=True)
        raise click.ClickException("Be more specific.")

    job = matching[0]

    if json_output:
        _output_job_json(job)
    else:
        _output_job_human(job)


def _output_job_json(job: Job) -> None:
    """Output detailed job info in JSON format."""
    data = {
        "id": job.id,
        "file_id": job.file_id,
        "file_path": job.file_path,
        "job_type": job.job_type.value,
        "status": job.status.value,
        "priority": job.priority,
        "policy_name": job.policy_name,
        "policy_json": job.policy_json,
        "progress_percent": job.progress_percent,
        "progress_json": job.progress_json,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "worker_pid": job.worker_pid,
        "worker_heartbeat": job.worker_heartbeat,
        "output_path": job.output_path,
        "backup_path": job.backup_path,
        "error_message": job.error_message,
        "files_affected_json": job.files_affected_json,
        "summary_json": job.summary_json,
    }
    click.echo(json.dumps(data, indent=2))


def _output_job_human(job: Job) -> None:
    """Output detailed job info in human-readable format."""
    status_colored = click.style(
        job.status.value.upper(), fg=get_status_color(job.status)
    )

    click.echo(f"\nJob: {job.id}")
    click.echo("-" * 50)
    click.echo(f"  Status:      {status_colored}")
    click.echo(f"  Type:        {job.job_type.value}")
    click.echo(f"  File:        {job.file_path}")
    if job.policy_name:
        click.echo(f"  Policy:      {job.policy_name}")
    click.echo(f"  Priority:    {job.priority}")
    click.echo("")
    click.echo(f"  Created:     {job.created_at}")
    if job.started_at:
        click.echo(f"  Started:     {job.started_at}")
    if job.completed_at:
        click.echo(f"  Completed:   {job.completed_at}")

    if job.status == JobStatus.RUNNING:
        click.echo("")
        click.echo(f"  Progress:    {job.progress_percent:.1f}%")
        if job.worker_pid:
            click.echo(f"  Worker PID:  {job.worker_pid}")
        if job.worker_heartbeat:
            click.echo(f"  Heartbeat:   {job.worker_heartbeat}")

    if job.error_message:
        click.echo("")
        click.echo(f"  Error:       {click.style(job.error_message, fg='red')}")

    if job.output_path:
        click.echo("")
        click.echo(f"  Output:      {job.output_path}")
    if job.backup_path:
        click.echo(f"  Backup:      {job.backup_path}")

    # Parse and display summary if available
    if job.summary_json:
        try:
            summary = json.loads(job.summary_json)
            click.echo("")
            click.echo("  Summary:")
            for key, value in summary.items():
                click.echo(f"    {key}: {value}")
        except json.JSONDecodeError:
            pass

    click.echo("")


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

    # Find job by prefix using efficient SQL LIKE query
    matching = get_jobs_by_id_prefix(conn, job_id)

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

    # Find job by prefix using efficient SQL LIKE query
    matching = get_jobs_by_id_prefix(conn, job_id)

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
@click.option("--yes", "-y", is_flag=True, help="Don't ask for confirmation.")
@click.option("--force", is_flag=True, hidden=True)
@click.pass_context
def clear_jobs(ctx: click.Context, status: str, yes: bool, force: bool) -> None:
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

    # Collect matching jobs once
    jobs_to_delete = []
    for s in statuses:
        jobs_to_delete.extend(get_jobs_by_status(conn, s))

    total = len(jobs_to_delete)
    if total == 0:
        click.echo("No jobs to clear.")
        return

    if not (yes or force):
        if not click.confirm(f"Clear {total} {status} job(s)?"):
            click.echo("Cancelled.")
            return

    # Delete jobs
    deleted = 0
    for job in jobs_to_delete:
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
@click.option("--yes", "-y", is_flag=True, help="Don't ask for confirmation.")
@click.option("--force", is_flag=True, hidden=True)
@click.pass_context
def cleanup_jobs(
    ctx: click.Context,
    older_than: int,
    include_backups: bool,
    remove_temp: bool,
    temp_dir: Path | None,
    dry_run: bool,
    yes: bool,
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

    from vpo.db import delete_old_jobs

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

    if not (yes or force):
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
