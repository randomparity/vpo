"""CLI commands for generating reports from the VPO database.

This module provides commands for viewing and exporting data about:
- Processing statistics (summary, history, policies, detail)
- Job history
- Library metadata
- Scan operations
- Transcode operations
- Policy applications

The stats module has been merged into this module for a unified reporting interface.
"""

import csv
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

import click

from vpo.core import format_file_size, parse_relative_or_iso_time
from vpo.db.views import (
    get_policy_stats,
    get_policy_stats_by_name,
    get_recent_stats,
    get_stats_detail,
    get_stats_for_file,
    get_stats_summary,
)
from vpo.reports import (
    ReportFormat,
    TimeFilter,
    render_csv,
    render_json,
    render_text_table,
    write_report_to_file,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Formatting Helpers (from stats module)
# =============================================================================


def _format_duration(seconds: float) -> str:
    """Format duration as human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string (e.g., "1h 23m", "45s").
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def _format_percent(value: float) -> str:
    """Format percentage value.

    Args:
        value: Percentage value (0-100).

    Returns:
        Formatted string (e.g., "95.3%").
    """
    return f"{value:.1f}%"


def _parse_stats_time_filter(value: str) -> str:
    """Parse a time filter value to ISO-8601 timestamp.

    Args:
        value: Time filter value (relative: 7d, 1w, 2h, 30m, or ISO-8601).

    Returns:
        ISO-8601 timestamp string.

    Raises:
        click.ClickException: If format is invalid.
    """
    result = parse_relative_or_iso_time(value)
    if result is None:
        raise click.ClickException(
            f"Invalid time format: {value}. "
            "Use relative time (7d, 1w, 2h, 30m) or ISO-8601."
        )
    return result


# Common options for all report subcommands
def common_report_options(func):
    """Decorator to add common report options to a command."""
    func = click.option(
        "--format",
        "-f",
        "output_format",
        type=click.Choice(["text", "csv", "json"], case_sensitive=False),
        default="text",
        help="Output format (default: text).",
    )(func)
    func = click.option(
        "--output",
        "-o",
        "output_path",
        type=click.Path(path_type=Path),
        default=None,
        help="Write to file instead of stdout.",
    )(func)
    func = click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Overwrite existing output file.",
    )(func)
    func = click.option(
        "--limit",
        "-n",
        type=int,
        default=100,
        help="Maximum rows to return (default: 100).",
    )(func)
    func = click.option(
        "--no-limit",
        is_flag=True,
        default=False,
        help="Return all rows (no limit).",
    )(func)
    return func


def time_filter_options(func):
    """Decorator to add time filter options."""
    func = click.option(
        "--since",
        default=None,
        help="Show records since (relative: 7d, 1w, 2h or ISO-8601).",
    )(func)
    func = click.option(
        "--until",
        default=None,
        help="Show records until (relative: 7d, 1w, 2h or ISO-8601).",
    )(func)
    return func


def output_report(
    rows: list[dict],
    columns: list[tuple[str, str, int]],
    output_format: str,
    output_path: Path | None,
    force: bool,
    empty_message: str = "No records found.",
    filtered_message: str = "No records match the specified filters.",
    has_filters: bool = False,
) -> None:
    """Output report in requested format.

    Args:
        rows: List of row dictionaries.
        columns: List of (header, key, width) tuples for text format.
        output_format: Output format (text, csv, json).
        output_path: Output file path or None for stdout.
        force: Overwrite existing files.
        empty_message: Message when no records exist.
        filtered_message: Message when filters match nothing.
        has_filters: Whether filters were applied.
    """
    if not rows:
        msg = filtered_message if has_filters else empty_message
        click.echo(msg)
        return

    fmt = ReportFormat(output_format.casefold())
    column_keys = [col[1] for col in columns]

    if fmt == ReportFormat.TEXT:
        content = render_text_table(rows, columns)
    elif fmt == ReportFormat.CSV:
        content = render_csv(rows, column_keys)
    else:  # JSON
        content = render_json(rows)

    if output_path:
        try:
            write_report_to_file(content, output_path, force)
            click.echo(f"Report written to {output_path}")
        except FileExistsError as e:
            raise click.ClickException(str(e))
        except OSError as e:
            raise click.ClickException(f"Failed to write report: {e}")
    else:
        click.echo(content)


def get_effective_limit(limit: int, no_limit: bool) -> int | None:
    """Calculate effective limit from options.

    Args:
        limit: Limit value from --limit option.
        no_limit: Whether --no-limit flag was set.

    Returns:
        Effective limit or None for no limit.
    """
    return None if no_limit else limit


def parse_time_filter(since: str | None, until: str | None) -> TimeFilter:
    """Parse time filter options with error handling.

    Args:
        since: Since option value.
        until: Until option value.

    Returns:
        TimeFilter instance.

    Raises:
        click.ClickException: If time format is invalid.
    """
    try:
        return TimeFilter.from_strings(since, until)
    except ValueError as e:
        raise click.ClickException(str(e))


@click.group("report")
def report_group() -> None:
    """Generate reports from the VPO database.

    Reports are read-only views of job history, library metadata,
    scan operations, transcodes, and policy applications.

    Examples:

        # List recent jobs
        vpo report jobs

        # Export library to CSV
        vpo report library --format csv --output library.csv

        # View scan history from last week
        vpo report scans --since 7d
    """
    pass


@report_group.command("jobs")
@click.option(
    "--type",
    "-t",
    "job_type",
    type=click.Choice(
        ["scan", "apply", "transcode", "move", "all"], case_sensitive=False
    ),
    default="all",
    help="Filter by job type.",
)
@click.option(
    "--status",
    "-s",
    type=click.Choice(
        ["queued", "running", "completed", "failed", "cancelled", "all"],
        case_sensitive=False,
    ),
    default="all",
    help="Filter by job status.",
)
@time_filter_options
@common_report_options
@click.pass_context
def report_jobs(
    ctx: click.Context,
    job_type: str,
    status: str,
    since: str | None,
    until: str | None,
    output_format: str,
    output_path: Path | None,
    force: bool,
    limit: int,
    no_limit: bool,
) -> None:
    """List job history with filtering.

    Shows job ID, type, status, target file, start/end times, duration,
    and error messages (for failed jobs).

    Examples:

        # List all jobs (default: last 100)
        vpo report jobs

        # List failed jobs from last week
        vpo report jobs --status failed --since 7d

        # Export transcode jobs to CSV
        vpo report jobs --type transcode --format csv --output jobs.csv

        # Show all jobs without limit
        vpo report jobs --no-limit
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    from vpo.reports.queries import get_jobs_report

    time_filter = parse_time_filter(since, until)
    effective_limit = get_effective_limit(limit, no_limit)

    # Determine if filters are applied
    has_filters = bool(job_type != "all" or status != "all" or since or until)

    rows = get_jobs_report(
        conn,
        job_type=None if job_type == "all" else job_type,
        status=None if status == "all" else status,
        time_filter=time_filter,
        limit=effective_limit,
    )

    columns = [
        ("ID", "job_id", 10),
        ("TYPE", "type", 10),
        ("STATUS", "status", 12),
        ("TARGET", "target", 40),
        ("STARTED", "started_at", 20),
        ("COMPLETED", "completed_at", 20),
        ("DURATION", "duration", 12),
        ("ERROR", "error", 30),
    ]

    output_report(
        rows,
        columns,
        output_format,
        output_path,
        force,
        has_filters=has_filters,
    )


@report_group.command("library")
@click.option(
    "--resolution",
    "-r",
    type=click.Choice(["4K", "1080p", "720p", "480p", "SD"], case_sensitive=False),
    default=None,
    help="Filter by video resolution.",
)
@click.option(
    "--language",
    "-l",
    default=None,
    help="Filter by audio language (ISO 639-2, e.g., eng, jpn).",
)
@click.option(
    "--has-subtitles",
    is_flag=True,
    default=False,
    help="Only files with subtitle tracks.",
)
@click.option(
    "--no-subtitles",
    is_flag=True,
    default=False,
    help="Only files without subtitle tracks.",
)
@common_report_options
@click.pass_context
def report_library(
    ctx: click.Context,
    resolution: str | None,
    language: str | None,
    has_subtitles: bool,
    no_subtitles: bool,
    output_format: str,
    output_path: Path | None,
    force: bool,
    limit: int,
    no_limit: bool,
) -> None:
    """Export library file metadata.

    Shows file path, title, container format, resolution, audio languages,
    subtitle presence, and last scan time.

    Examples:

        # List all library files
        vpo report library

        # Export 4K files to CSV
        vpo report library --resolution 4K --format csv --output 4k.csv

        # Find files with Japanese audio
        vpo report library --language jpn

        # Files with subtitles
        vpo report library --has-subtitles
    """
    if has_subtitles and no_subtitles:
        raise click.ClickException(
            "Cannot use both --has-subtitles and --no-subtitles."
        )

    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    from vpo.reports.queries import get_library_report

    effective_limit = get_effective_limit(limit, no_limit)

    # Determine subtitle filter
    subtitle_filter = None
    if has_subtitles:
        subtitle_filter = True
    elif no_subtitles:
        subtitle_filter = False

    # Determine if filters are applied
    has_filters = bool(resolution or language or has_subtitles or no_subtitles)

    rows = get_library_report(
        conn,
        resolution=resolution.upper() if resolution else None,
        language=language,
        has_subtitles=subtitle_filter,
        limit=effective_limit,
    )

    columns = [
        ("PATH", "path", 50),
        ("TITLE", "title", 30),
        ("CONTAINER", "container", 10),
        ("RESOLUTION", "resolution", 10),
        ("AUDIO", "audio_languages", 15),
        ("SUBTITLES", "has_subtitles", 10),
        ("SCANNED", "scanned_at", 20),
    ]

    output_report(
        rows,
        columns,
        output_format,
        output_path,
        force,
        has_filters=has_filters,
    )


@report_group.command("scans")
@time_filter_options
@common_report_options
@click.pass_context
def report_scans(
    ctx: click.Context,
    since: str | None,
    until: str | None,
    output_format: str,
    output_path: Path | None,
    force: bool,
    limit: int,
    no_limit: bool,
) -> None:
    """List scan operation history.

    Shows scan ID, start/end times, duration, file counts (total, new, changed),
    and scan status.

    Examples:

        # List recent scans
        vpo report scans

        # Scans from last month
        vpo report scans --since 30d

        # Export to JSON
        vpo report scans --format json --output scans.json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    from vpo.reports.queries import get_scans_report

    time_filter = parse_time_filter(since, until)
    effective_limit = get_effective_limit(limit, no_limit)

    has_filters = bool(since or until)

    rows = get_scans_report(
        conn,
        time_filter=time_filter,
        limit=effective_limit,
    )

    columns = [
        ("SCAN_ID", "scan_id", 10),
        ("STARTED", "started_at", 20),
        ("COMPLETED", "completed_at", 20),
        ("DURATION", "duration", 12),
        ("TOTAL", "files_scanned", 8),
        ("NEW", "files_new", 8),
        ("CHANGED", "files_changed", 8),
        ("STATUS", "status", 12),
    ]

    output_report(
        rows,
        columns,
        output_format,
        output_path,
        force,
        has_filters=has_filters,
    )


@report_group.command("transcodes")
@click.option(
    "--codec",
    "-c",
    default=None,
    help="Filter by target codec (e.g., hevc, av1).",
)
@time_filter_options
@common_report_options
@click.pass_context
def report_transcodes(
    ctx: click.Context,
    codec: str | None,
    since: str | None,
    until: str | None,
    output_format: str,
    output_path: Path | None,
    force: bool,
    limit: int,
    no_limit: bool,
) -> None:
    """List transcode operation history.

    Shows job ID, file path, source/target codecs, start/end times,
    duration, status, and size change percentage.

    Examples:

        # List all transcodes
        vpo report transcodes

        # HEVC conversions for size analysis
        vpo report transcodes --codec hevc

        # Export to CSV
        vpo report transcodes --format csv --output transcodes.csv
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    from vpo.reports.queries import get_transcodes_report

    time_filter = parse_time_filter(since, until)
    effective_limit = get_effective_limit(limit, no_limit)

    has_filters = bool(codec or since or until)

    rows = get_transcodes_report(
        conn,
        codec=codec,
        time_filter=time_filter,
        limit=effective_limit,
    )

    columns = [
        ("JOB_ID", "job_id", 10),
        ("FILE", "file_path", 40),
        ("FROM", "source_codec", 10),
        ("TO", "target_codec", 10),
        ("STARTED", "started_at", 20),
        ("COMPLETED", "completed_at", 20),
        ("DURATION", "duration", 12),
        ("STATUS", "status", 12),
        ("SAVINGS", "size_change", 10),
    ]

    output_report(
        rows,
        columns,
        output_format,
        output_path,
        force,
        has_filters=has_filters,
    )


@report_group.command("policy-apply")
@click.option(
    "--policy",
    "-p",
    "policy_name",
    default=None,
    help="Filter by policy name.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show per-file details.",
)
@time_filter_options
@common_report_options
@click.pass_context
def report_policy_apply(
    ctx: click.Context,
    policy_name: str | None,
    verbose: bool,
    since: str | None,
    until: str | None,
    output_format: str,
    output_path: Path | None,
    force: bool,
    limit: int,
    no_limit: bool,
) -> None:
    """List policy application history.

    Shows operation ID, policy name, files affected, metadata/heavy change counts,
    status, and start time. Use --verbose for per-file details.

    Examples:

        # List policy applications
        vpo report policy-apply

        # Verbose output for specific policy
        vpo report policy-apply --policy normalize.yaml --verbose

        # Export to JSON
        vpo report policy-apply --format json --output policy-report.json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    from vpo.reports.queries import get_policy_apply_report

    time_filter = parse_time_filter(since, until)
    effective_limit = get_effective_limit(limit, no_limit)

    has_filters = bool(policy_name or since or until)

    rows = get_policy_apply_report(
        conn,
        policy_name=policy_name,
        verbose=verbose,
        time_filter=time_filter,
        limit=effective_limit,
    )

    if verbose:
        columns = [
            ("FILE", "file_path", 60),
            ("CHANGES", "changes", 50),
        ]
    else:
        columns = [
            ("OP_ID", "operation_id", 10),
            ("POLICY", "policy_name", 25),
            ("FILES", "files_affected", 8),
            ("METADATA", "metadata_changes", 10),
            ("HEAVY", "heavy_changes", 8),
            ("STATUS", "status", 12),
            ("STARTED", "started_at", 20),
        ]

    output_report(
        rows,
        columns,
        output_format,
        output_path,
        force,
        has_filters=has_filters,
    )


# =============================================================================
# Processing Statistics Commands (merged from stats module)
# =============================================================================


@report_group.command("summary")
@click.option(
    "--since",
    default=None,
    help="Show stats since (relative: 7d, 1w, 2h or ISO-8601).",
)
@click.option(
    "--until",
    default=None,
    help="Show stats until (relative: 7d, 1w, 2h or ISO-8601).",
)
@click.option(
    "--policy",
    "policy_name",
    default=None,
    help="Filter by policy name.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.pass_context
def report_summary(
    ctx: click.Context,
    since: str | None,
    until: str | None,
    policy_name: str | None,
    output_format: str,
) -> None:
    """Display aggregate processing statistics.

    Shows total files processed, success rate, disk space saved,
    tracks removed, and processing time.

    Examples:

        # Overall summary
        vpo report summary

        # Stats from last week
        vpo report summary --since 7d

        # Stats for specific policy
        vpo report summary --policy normalize.yaml

        # Export as JSON
        vpo report summary --format json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Parse time filters
    since_ts = _parse_stats_time_filter(since) if since else None
    until_ts = _parse_stats_time_filter(until) if until else None

    summary = get_stats_summary(
        conn,
        since=since_ts,
        until=until_ts,
        policy_name=policy_name,
    )

    if output_format == "json":
        click.echo(json.dumps(asdict(summary), indent=2))
        return

    if output_format == "csv":
        _output_summary_csv(summary)
        return

    # Table format
    _output_summary_table(summary, since, until, policy_name)


def _output_summary_table(summary, since, until, policy_name) -> None:
    """Output summary in table format."""
    # Header
    click.echo("")
    click.echo("Processing Statistics Summary")
    click.echo("=" * 50)

    if since or until or policy_name:
        filters = []
        if policy_name:
            filters.append(f"Policy: {policy_name}")
        if since:
            filters.append(f"Since: {since}")
        if until:
            filters.append(f"Until: {until}")
        click.echo(f"Filters: {', '.join(filters)}")
        click.echo("-" * 50)

    if summary.total_files_processed == 0:
        click.echo("")
        click.echo("No processing statistics recorded yet.")
        click.echo("Statistics are captured during 'vpo process' (non-dry-run).")
        click.echo("")
        return

    # Processing overview
    click.echo("")
    click.echo("Processing Overview")
    click.echo("-" * 30)
    click.echo(f"  Files Processed:    {summary.total_files_processed:,}")
    click.echo(f"  Successful:         {summary.total_successful:,}")
    click.echo(f"  Failed:             {summary.total_failed:,}")
    click.echo(f"  Success Rate:       {_format_percent(summary.success_rate * 100)}")

    # Disk space savings
    click.echo("")
    click.echo("Disk Space")
    click.echo("-" * 30)
    click.echo(f"  Size Before:        {format_file_size(summary.total_size_before)}")
    click.echo(f"  Size After:         {format_file_size(summary.total_size_after)}")
    if summary.total_size_saved >= 0:
        click.echo(
            f"  Space Saved:        {format_file_size(summary.total_size_saved)}"
        )
    else:
        click.echo(
            f"  Space Added:        {format_file_size(abs(summary.total_size_saved))}"
        )
    click.echo(f"  Avg Savings:        {_format_percent(summary.avg_savings_percent)}")

    # Track removal
    click.echo("")
    click.echo("Tracks Removed")
    click.echo("-" * 30)
    click.echo(f"  Audio Tracks:       {summary.total_audio_removed:,}")
    click.echo(f"  Subtitle Tracks:    {summary.total_subtitles_removed:,}")
    click.echo(f"  Attachments:        {summary.total_attachments_removed:,}")

    # Transcode stats
    click.echo("")
    click.echo("Transcoding")
    click.echo("-" * 30)
    click.echo(f"  Videos Transcoded:  {summary.total_videos_transcoded:,}")
    click.echo(f"  Videos Skipped:     {summary.total_videos_skipped:,}")
    click.echo(f"  Audio Transcoded:   {summary.total_audio_transcoded:,}")

    # Performance
    click.echo("")
    click.echo("Performance")
    click.echo("-" * 30)
    avg_time = _format_duration(summary.avg_processing_time)
    click.echo(f"  Avg Processing Time: {avg_time}")

    # Time range
    if summary.earliest_processing and summary.latest_processing:
        click.echo("")
        click.echo("Time Range")
        click.echo("-" * 30)
        click.echo(f"  First Processing:   {summary.earliest_processing[:19]}")
        click.echo(f"  Last Processing:    {summary.latest_processing[:19]}")

    click.echo("")


def _output_summary_csv(summary) -> None:
    """Output summary in CSV format with proper escaping."""
    writer = csv.writer(sys.stdout)
    headers = [
        "total_files_processed",
        "total_successful",
        "total_failed",
        "success_rate",
        "total_size_before",
        "total_size_after",
        "total_size_saved",
        "avg_savings_percent",
        "total_audio_removed",
        "total_subtitles_removed",
        "total_attachments_removed",
        "total_videos_transcoded",
        "total_videos_skipped",
        "total_audio_transcoded",
        "avg_processing_time",
        "earliest_processing",
        "latest_processing",
    ]
    writer.writerow(headers)

    values = [
        summary.total_files_processed,
        summary.total_successful,
        summary.total_failed,
        f"{summary.success_rate:.4f}",
        summary.total_size_before,
        summary.total_size_after,
        summary.total_size_saved,
        f"{summary.avg_savings_percent:.2f}",
        summary.total_audio_removed,
        summary.total_subtitles_removed,
        summary.total_attachments_removed,
        summary.total_videos_transcoded,
        summary.total_videos_skipped,
        summary.total_audio_transcoded,
        f"{summary.avg_processing_time:.2f}",
        summary.earliest_processing or "",
        summary.latest_processing or "",
    ]
    writer.writerow(values)


@report_group.command("history")
@click.option(
    "--limit",
    "-n",
    default=10,
    type=int,
    help="Number of entries to show (default: 10).",
)
@click.option(
    "--policy",
    "policy_name",
    default=None,
    help="Filter by policy name.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.pass_context
def report_history(
    ctx: click.Context,
    limit: int,
    policy_name: str | None,
    output_format: str,
) -> None:
    """Show recent processing history.

    Lists recent processing runs with size changes and track removals.

    Examples:

        # Show last 10 processing runs
        vpo report history

        # Show last 25 runs
        vpo report history -n 25

        # Show recent runs for specific policy
        vpo report history --policy my-policy.yaml

        # Export as JSON
        vpo report history --format json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    entries = get_recent_stats(
        conn,
        limit=limit,
        policy_name=policy_name,
    )

    if output_format == "json":
        click.echo(json.dumps([asdict(e) for e in entries], indent=2))
        return

    if output_format == "csv":
        _output_history_csv(entries)
        return

    # Table format
    if not entries:
        click.echo("No processing history found.")
        return

    click.echo("")
    click.echo("Recent Processing History")
    click.echo("=" * 100)

    # Header
    click.echo(
        f"{'DATE':<20} {'POLICY':<25} {'SAVED':<12} "
        f"{'AUDIO':<6} {'SUBS':<6} {'TIME':<10} {'STATUS':<8}"
    )
    click.echo("-" * 100)

    for entry in entries:
        date = entry.processed_at[:19] if entry.processed_at else ""
        policy = entry.policy_name[:24] if entry.policy_name else ""
        saved = format_file_size(entry.size_change)
        audio = str(entry.audio_removed)
        subs = str(entry.subtitle_removed)
        duration = _format_duration(entry.duration_seconds)
        status = "OK" if entry.success else "FAIL"

        click.echo(
            f"{date:<20} {policy:<25} {saved:<12} "
            f"{audio:<6} {subs:<6} {duration:<10} {status:<8}"
        )

    click.echo("")


def _output_history_csv(entries) -> None:
    """Output history entries in CSV format with proper escaping."""
    writer = csv.writer(sys.stdout)
    headers = [
        "stats_id",
        "processed_at",
        "policy_name",
        "size_before",
        "size_after",
        "size_change",
        "audio_removed",
        "subtitle_removed",
        "attachments_removed",
        "duration_seconds",
        "success",
        "error_message",
    ]
    writer.writerow(headers)

    for entry in entries:
        values = [
            entry.stats_id,
            entry.processed_at,
            entry.policy_name,
            entry.size_before,
            entry.size_after,
            entry.size_change,
            entry.audio_removed,
            entry.subtitle_removed,
            entry.attachments_removed,
            f"{entry.duration_seconds:.2f}",
            "true" if entry.success else "false",
            entry.error_message or "",
        ]
        writer.writerow(values)


@report_group.command("policies")
@click.option(
    "--since",
    default=None,
    help="Show stats since (relative: 7d, 1w, 2h or ISO-8601).",
)
@click.option(
    "--until",
    default=None,
    help="Show stats until (relative: 7d, 1w, 2h or ISO-8601).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.pass_context
def report_policies(
    ctx: click.Context,
    since: str | None,
    until: str | None,
    output_format: str,
) -> None:
    """Compare statistics across policies.

    Shows per-policy statistics including files processed, success rate,
    space saved, and tracks removed.

    Examples:

        # Compare all policies
        vpo report policies

        # Compare policies from last week
        vpo report policies --since 7d

        # Export as JSON
        vpo report policies --format json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Parse time filters
    since_ts = _parse_stats_time_filter(since) if since else None
    until_ts = _parse_stats_time_filter(until) if until else None

    policies = get_policy_stats(
        conn,
        since=since_ts,
        until=until_ts,
    )

    if output_format == "json":
        click.echo(json.dumps([asdict(p) for p in policies], indent=2))
        return

    if output_format == "csv":
        _output_policies_stats_csv(policies)
        return

    # Table format
    if not policies:
        click.echo("No policy statistics found.")
        return

    click.echo("")
    click.echo("Policy Statistics Comparison")
    click.echo("=" * 110)

    # Header
    click.echo(
        f"{'POLICY':<30} {'FILES':>8} {'SUCCESS':>8} {'SAVED':>12} "
        f"{'AUDIO':>6} {'SUBS':>6} {'AVG TIME':>10} {'LAST USED':<20}"
    )
    click.echo("-" * 110)

    for policy in policies:
        name = policy.policy_name[:29] if policy.policy_name else ""
        files = str(policy.files_processed)
        success = _format_percent(policy.success_rate * 100)
        saved = format_file_size(policy.total_size_saved)
        audio = str(policy.audio_tracks_removed)
        subs = str(policy.subtitle_tracks_removed)
        avg_time = _format_duration(policy.avg_processing_time)
        last_used = policy.last_used[:19] if policy.last_used else ""

        click.echo(
            f"{name:<30} {files:>8} {success:>8} {saved:>12} "
            f"{audio:>6} {subs:>6} {avg_time:>10} {last_used:<20}"
        )

    click.echo("")


def _output_policies_stats_csv(policies) -> None:
    """Output policies in CSV format with proper escaping."""
    writer = csv.writer(sys.stdout)
    headers = [
        "policy_name",
        "files_processed",
        "success_rate",
        "total_size_saved",
        "avg_savings_percent",
        "audio_tracks_removed",
        "subtitle_tracks_removed",
        "attachments_removed",
        "videos_transcoded",
        "audio_transcoded",
        "avg_processing_time",
        "last_used",
    ]
    writer.writerow(headers)

    for policy in policies:
        values = [
            policy.policy_name,
            policy.files_processed,
            f"{policy.success_rate:.4f}",
            policy.total_size_saved,
            f"{policy.avg_savings_percent:.2f}",
            policy.audio_tracks_removed,
            policy.subtitle_tracks_removed,
            policy.attachments_removed,
            policy.videos_transcoded,
            policy.audio_transcoded,
            f"{policy.avg_processing_time:.2f}",
            policy.last_used or "",
        ]
        writer.writerow(values)


@report_group.command("policy-stats")
@click.argument("name")
@click.option(
    "--since",
    default=None,
    help="Show stats since (relative: 7d, 1w, 2h or ISO-8601).",
)
@click.option(
    "--until",
    default=None,
    help="Show stats until (relative: 7d, 1w, 2h or ISO-8601).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.pass_context
def report_policy_stats(
    ctx: click.Context,
    name: str,
    since: str | None,
    until: str | None,
    output_format: str,
) -> None:
    """Show statistics for a specific policy.

    Displays detailed statistics for a single policy including files processed,
    success rate, space saved, tracks removed, and transcode info.

    Examples:

        # View stats for a specific policy
        vpo report policy-stats normalize.yaml

        # View policy stats from last week
        vpo report policy-stats normalize.yaml --since 7d

        # Export as JSON
        vpo report policy-stats normalize.yaml --format json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Parse time filters
    since_ts = _parse_stats_time_filter(since) if since else None
    until_ts = _parse_stats_time_filter(until) if until else None

    policy = get_policy_stats_by_name(
        conn,
        name,
        since=since_ts,
        until=until_ts,
    )

    if policy is None:
        raise click.ClickException(f"No statistics found for policy: {name}")

    if output_format == "json":
        click.echo(json.dumps(asdict(policy), indent=2))
        return

    # Table format
    click.echo("")
    click.echo(f"Policy Statistics: {name}")
    click.echo("=" * 50)

    if since or until:
        filters = []
        if since:
            filters.append(f"Since: {since}")
        if until:
            filters.append(f"Until: {until}")
        click.echo(f"Filters: {', '.join(filters)}")
        click.echo("-" * 50)

    click.echo("")
    click.echo("Processing Overview")
    click.echo("-" * 30)
    click.echo(f"  Files Processed:    {policy.files_processed:,}")
    click.echo(f"  Success Rate:       {_format_percent(policy.success_rate * 100)}")
    last_used = policy.last_used[:19] if policy.last_used else "N/A"
    click.echo(f"  Last Used:          {last_used}")

    click.echo("")
    click.echo("Disk Space")
    click.echo("-" * 30)
    click.echo(f"  Total Saved:        {format_file_size(policy.total_size_saved)}")
    click.echo(f"  Avg Savings:        {_format_percent(policy.avg_savings_percent)}")

    click.echo("")
    click.echo("Tracks Removed")
    click.echo("-" * 30)
    click.echo(f"  Audio Tracks:       {policy.audio_tracks_removed:,}")
    click.echo(f"  Subtitle Tracks:    {policy.subtitle_tracks_removed:,}")
    click.echo(f"  Attachments:        {policy.attachments_removed:,}")

    click.echo("")
    click.echo("Transcoding")
    click.echo("-" * 30)
    click.echo(f"  Videos Transcoded:  {policy.videos_transcoded:,}")
    click.echo(f"  Audio Transcoded:   {policy.audio_transcoded:,}")

    click.echo("")
    click.echo("Performance")
    click.echo("-" * 30)
    click.echo(f"  Avg Processing Time: {_format_duration(policy.avg_processing_time)}")

    click.echo("")


@report_group.command("file")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.pass_context
def report_file(
    ctx: click.Context,
    path: str,
    output_format: str,
) -> None:
    """Show processing history for a specific file.

    Displays all processing runs for the given file, including size changes,
    track removals, and status.

    Examples:

        # View history for a file
        vpo report file /path/to/video.mkv

        # Export as JSON
        vpo report file /path/to/video.mkv --format json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Resolve to absolute path
    file_path = str(Path(path).resolve())

    entries = get_stats_for_file(conn, file_path=file_path)

    if output_format == "json":
        click.echo(json.dumps([asdict(e) for e in entries], indent=2))
        return

    if output_format == "csv":
        _output_history_csv(entries)
        return

    # Table format
    if not entries:
        click.echo(f"No processing history found for: {path}")
        return

    click.echo("")
    click.echo(f"Processing History for: {path}")
    click.echo("=" * 100)

    # Header
    click.echo(
        f"{'DATE':<20} {'POLICY':<25} {'SAVED':<12} "
        f"{'AUDIO':<6} {'SUBS':<6} {'TIME':<10} {'STATUS':<8}"
    )
    click.echo("-" * 100)

    for entry in entries:
        date = entry.processed_at[:19] if entry.processed_at else ""
        policy = entry.policy_name[:24] if entry.policy_name else ""
        saved = format_file_size(entry.size_change)
        audio = str(entry.audio_removed)
        subs = str(entry.subtitle_removed)
        duration = _format_duration(entry.duration_seconds)
        status = "OK" if entry.success else "FAIL"

        click.echo(
            f"{date:<20} {policy:<25} {saved:<12} "
            f"{audio:<6} {subs:<6} {duration:<10} {status:<8}"
        )

    click.echo("")
    click.echo("Use 'vpo report detail <stats_id>' for detailed action breakdown.")
    click.echo("")


@report_group.command("detail")
@click.argument("stats_id")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.pass_context
def report_detail(
    ctx: click.Context,
    stats_id: str,
    output_format: str,
) -> None:
    """Show detailed statistics for a processing run.

    Displays full details including track counts before/after, all actions
    performed, transcode information, and performance metrics.

    Examples:

        # View detail for a processing run
        vpo report detail abc12345-6789-...

        # Export as JSON
        vpo report detail abc12345-6789-... --format json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    detail = get_stats_detail(conn, stats_id)

    if detail is None:
        raise click.ClickException(f"Processing stats not found: {stats_id}")

    if output_format == "json":
        click.echo(json.dumps(asdict(detail), indent=2))
        return

    # Table format
    _output_detail_table(detail)


def _output_detail_table(detail) -> None:
    """Output detailed stats in table format."""
    click.echo("")
    click.echo("Processing Details")
    click.echo("=" * 60)

    # File info
    click.echo("")
    click.echo("File Information")
    click.echo("-" * 40)
    click.echo(f"  Stats ID:       {detail.stats_id}")
    click.echo(f"  File:           {detail.filename or 'N/A'}")
    if detail.file_path:
        click.echo(f"  Path:           {detail.file_path}")
    click.echo(f"  Processed:      {detail.processed_at[:19]}")
    click.echo(f"  Policy:         {detail.policy_name}")
    click.echo(f"  Status:         {'SUCCESS' if detail.success else 'FAILED'}")
    if detail.error_message:
        click.echo(f"  Error:          {detail.error_message}")

    # Size changes
    click.echo("")
    click.echo("Size Changes")
    click.echo("-" * 40)
    click.echo(f"  Before:         {format_file_size(detail.size_before)}")
    click.echo(f"  After:          {format_file_size(detail.size_after)}")
    if detail.size_change >= 0:
        click.echo(f"  Saved:          {format_file_size(detail.size_change)}")
    else:
        click.echo(f"  Added:          {format_file_size(abs(detail.size_change))}")
    if detail.size_before > 0:
        pct = (detail.size_change / detail.size_before) * 100
        click.echo(f"  Savings:        {_format_percent(pct)}")

    # Track counts
    click.echo("")
    click.echo("Track Changes")
    click.echo("-" * 40)
    click.echo(
        f"  Audio:          {detail.audio_tracks_before} → "
        f"{detail.audio_tracks_after} (-{detail.audio_tracks_removed})"
    )
    click.echo(
        f"  Subtitle:       {detail.subtitle_tracks_before} → "
        f"{detail.subtitle_tracks_after} (-{detail.subtitle_tracks_removed})"
    )
    click.echo(
        f"  Attachments:    {detail.attachments_before} → "
        f"{detail.attachments_after} (-{detail.attachments_removed})"
    )

    # Transcode info
    if detail.video_source_codec or detail.video_target_codec:
        click.echo("")
        click.echo("Transcode Information")
        click.echo("-" * 40)
        if detail.video_source_codec:
            click.echo(f"  Video Codec:    {detail.video_source_codec}")
        if detail.video_target_codec:
            click.echo(f"  Target Codec:   {detail.video_target_codec}")
        if detail.video_transcode_skipped:
            click.echo(f"  Skipped:        Yes ({detail.video_skip_reason or 'N/A'})")
        else:
            click.echo("  Skipped:        No")
        click.echo(f"  Audio Transcoded: {detail.audio_tracks_transcoded}")
        click.echo(f"  Audio Preserved:  {detail.audio_tracks_preserved}")

    # Processing info
    click.echo("")
    click.echo("Processing Info")
    click.echo("-" * 40)
    click.echo(f"  Duration:       {_format_duration(detail.duration_seconds)}")
    click.echo(f"  Phases:         {detail.phases_completed}/{detail.phases_total}")
    click.echo(f"  Total Changes:  {detail.total_changes}")

    # File integrity
    if detail.hash_before or detail.hash_after:
        click.echo("")
        click.echo("File Integrity")
        click.echo("-" * 40)
        if detail.hash_before:
            click.echo(f"  Hash Before:    {detail.hash_before[:16]}...")
        if detail.hash_after:
            click.echo(f"  Hash After:     {detail.hash_after[:16]}...")

    # Actions
    if detail.actions:
        click.echo("")
        click.echo("Actions Performed")
        click.echo("-" * 40)
        for i, action in enumerate(detail.actions, 1):
            track_info = ""
            if action.track_type:
                track_info = f" ({action.track_type}"
                if action.track_index is not None:
                    track_info += f" #{action.track_index}"
                track_info += ")"
            status = "OK" if action.success else "FAIL"
            click.echo(f"  {i}. [{status}] {action.action_type}{track_info}")
            if action.message:
                click.echo(f"     {action.message}")

    click.echo("")


@report_group.command("purge")
@click.option(
    "--before",
    "before_date",
    default=None,
    help="Delete stats older than (relative: 30d, 90d or ISO-8601).",
)
@click.option(
    "--policy",
    "policy_name",
    default=None,
    help="Delete stats for a specific policy name.",
)
@click.option(
    "--all",
    "delete_all",
    is_flag=True,
    default=False,
    help="Delete ALL statistics (requires --yes to confirm).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be deleted without making changes.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
@click.pass_context
def report_purge(
    ctx: click.Context,
    before_date: str | None,
    policy_name: str | None,
    delete_all: bool,
    dry_run: bool,
    yes: bool,
) -> None:
    """Delete processing statistics.

    Remove old or unwanted statistics from the database. Use with caution
    as this operation cannot be undone.

    Examples:

        # Preview deletion of stats older than 30 days
        vpo report purge --before 30d --dry-run

        # Delete stats older than 90 days
        vpo report purge --before 90d

        # Delete stats for a specific policy
        vpo report purge --policy my-policy.yaml

        # Delete ALL stats (requires confirmation)
        vpo report purge --all --yes
    """
    from vpo.db.queries import (
        delete_all_processing_stats,
        delete_processing_stats_before,
        delete_processing_stats_by_policy,
    )

    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Validate options
    if not before_date and not policy_name and not delete_all:
        raise click.ClickException(
            "Must specify at least one of: --before, --policy, or --all"
        )

    if delete_all and (before_date or policy_name):
        raise click.ClickException("--all cannot be combined with --before or --policy")

    # Build operation description
    before_ts = None
    if delete_all:
        description = "ALL processing statistics"
    elif before_date and policy_name:
        # Parse the time filter
        _parse_stats_time_filter(before_date)
        raise click.ClickException(
            "Cannot combine --before and --policy. Use separate commands."
        )
    elif before_date:
        before_ts = _parse_stats_time_filter(before_date)
        description = f"stats older than {before_date}"
    else:
        description = f"stats for policy '{policy_name}'"

    # Dry run - show what would be deleted
    if dry_run:
        if delete_all:
            count = delete_all_processing_stats(conn, dry_run=True)
        elif before_date:
            count = delete_processing_stats_before(conn, before_ts, dry_run=True)
        else:
            count = delete_processing_stats_by_policy(
                conn,
                policy_name,
                dry_run=True,  # type: ignore
            )

        click.echo(f"[DRY-RUN] Would delete {count} processing stats records.")
        click.echo(f"Target: {description}")
        return

    # Confirmation for destructive operations
    if not yes:
        if delete_all:
            count = delete_all_processing_stats(conn, dry_run=True)
        elif before_date:
            count = delete_processing_stats_before(conn, before_ts, dry_run=True)
        else:
            count = delete_processing_stats_by_policy(
                conn,
                policy_name,
                dry_run=True,  # type: ignore
            )

        if count == 0:
            click.echo("No statistics match the specified criteria.")
            return

        click.echo(f"About to delete {count} processing stats records.")
        click.echo(f"Target: {description}")
        if not click.confirm("Are you sure you want to continue?"):
            click.echo("Operation cancelled.")
            return

    # Execute deletion
    if delete_all:
        deleted = delete_all_processing_stats(conn)
    elif before_date:
        deleted = delete_processing_stats_before(conn, before_ts)
    else:
        deleted = delete_processing_stats_by_policy(conn, policy_name)  # type: ignore

    click.echo(f"Deleted {deleted} processing stats records.")
