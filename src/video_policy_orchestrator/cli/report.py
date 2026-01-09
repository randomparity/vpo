"""CLI commands for generating reports from the VPO database."""

import logging
from pathlib import Path

import click

from video_policy_orchestrator.reports import (
    ReportFormat,
    TimeFilter,
    render_csv,
    render_json,
    render_text_table,
    write_report_to_file,
)

logger = logging.getLogger(__name__)


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

    from video_policy_orchestrator.reports.queries import get_jobs_report

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

    from video_policy_orchestrator.reports.queries import get_library_report

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

    from video_policy_orchestrator.reports.queries import get_scans_report

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

    from video_policy_orchestrator.reports.queries import get_transcodes_report

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

    from video_policy_orchestrator.reports.queries import get_policy_apply_report

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
