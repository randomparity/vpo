"""CLI commands for viewing processing statistics.

This module provides commands for viewing disk space savings, track removal
statistics, policy effectiveness, and processing performance metrics.
"""

import json
import logging
from dataclasses import asdict

import click

from video_policy_orchestrator.db.views import (
    get_policy_stats,
    get_recent_stats,
    get_stats_summary,
)

logger = logging.getLogger(__name__)


def _format_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string (e.g., "1.5 GB", "256 MB").
    """
    if size_bytes == 0:
        return "0 B"

    abs_bytes = abs(size_bytes)
    sign = "-" if size_bytes < 0 else ""

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs_bytes < 1024:
            return f"{sign}{abs_bytes:.1f} {unit}"
        abs_bytes /= 1024

    return f"{sign}{abs_bytes:.1f} PB"


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


@click.group("stats")
def stats_group() -> None:
    """View processing statistics and metrics.

    Processing statistics are automatically collected during non-dry-run
    workflow execution. Use these commands to analyze disk space savings,
    track removal, policy effectiveness, and performance.

    Examples:

        # View overall summary
        vpo stats summary

        # View stats for a specific policy
        vpo stats summary --policy my-policy.yaml

        # View stats from last week as JSON
        vpo stats summary --since 7d --format json

        # View recent processing history
        vpo stats recent

        # View policy comparison
        vpo stats policies
    """
    pass


@stats_group.command("summary")
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
def stats_summary(
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
        vpo stats summary

        # Stats from last week
        vpo stats summary --since 7d

        # Stats for specific policy
        vpo stats summary --policy normalize.yaml

        # Export as JSON
        vpo stats summary --format json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Parse time filters
    since_ts = _parse_time_filter(since) if since else None
    until_ts = _parse_time_filter(until) if until else None

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
    click.echo(f"  Size Before:        {_format_bytes(summary.total_size_before)}")
    click.echo(f"  Size After:         {_format_bytes(summary.total_size_after)}")
    if summary.total_size_saved >= 0:
        click.echo(f"  Space Saved:        {_format_bytes(summary.total_size_saved)}")
    else:
        click.echo(
            f"  Space Added:        {_format_bytes(abs(summary.total_size_saved))}"
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
    """Output summary in CSV format."""
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
    click.echo(",".join(headers))

    values = [
        str(summary.total_files_processed),
        str(summary.total_successful),
        str(summary.total_failed),
        f"{summary.success_rate:.4f}",
        str(summary.total_size_before),
        str(summary.total_size_after),
        str(summary.total_size_saved),
        f"{summary.avg_savings_percent:.2f}",
        str(summary.total_audio_removed),
        str(summary.total_subtitles_removed),
        str(summary.total_attachments_removed),
        str(summary.total_videos_transcoded),
        str(summary.total_videos_skipped),
        str(summary.total_audio_transcoded),
        f"{summary.avg_processing_time:.2f}",
        summary.earliest_processing or "",
        summary.latest_processing or "",
    ]
    click.echo(",".join(values))


@stats_group.command("recent")
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
def stats_recent(
    ctx: click.Context,
    limit: int,
    policy_name: str | None,
    output_format: str,
) -> None:
    """Show recent processing history.

    Lists recent processing runs with size changes and track removals.

    Examples:

        # Show last 10 processing runs
        vpo stats recent

        # Show last 25 runs
        vpo stats recent -n 25

        # Show recent runs for specific policy
        vpo stats recent --policy my-policy.yaml

        # Export as JSON
        vpo stats recent --format json
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
        _output_recent_csv(entries)
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
        saved = _format_bytes(entry.size_change)
        audio = str(entry.audio_removed)
        subs = str(entry.subtitle_removed)
        duration = _format_duration(entry.duration_seconds)
        status = "OK" if entry.success else "FAIL"

        click.echo(
            f"{date:<20} {policy:<25} {saved:<12} "
            f"{audio:<6} {subs:<6} {duration:<10} {status:<8}"
        )

    click.echo("")


def _output_recent_csv(entries) -> None:
    """Output recent entries in CSV format."""
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
    click.echo(",".join(headers))

    for entry in entries:
        values = [
            entry.stats_id,
            entry.processed_at,
            entry.policy_name,
            str(entry.size_before),
            str(entry.size_after),
            str(entry.size_change),
            str(entry.audio_removed),
            str(entry.subtitle_removed),
            str(entry.attachments_removed),
            f"{entry.duration_seconds:.2f}",
            "true" if entry.success else "false",
            entry.error_message or "",
        ]
        click.echo(",".join(values))


@stats_group.command("policies")
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
def stats_policies(
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
        vpo stats policies

        # Compare policies from last week
        vpo stats policies --since 7d

        # Export as JSON
        vpo stats policies --format json
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Parse time filters
    since_ts = _parse_time_filter(since) if since else None
    until_ts = _parse_time_filter(until) if until else None

    policies = get_policy_stats(
        conn,
        since=since_ts,
        until=until_ts,
    )

    if output_format == "json":
        click.echo(json.dumps([asdict(p) for p in policies], indent=2))
        return

    if output_format == "csv":
        _output_policies_csv(policies)
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
        saved = _format_bytes(policy.total_size_saved)
        audio = str(policy.audio_tracks_removed)
        subs = str(policy.subtitle_tracks_removed)
        avg_time = _format_duration(policy.avg_processing_time)
        last_used = policy.last_used[:19] if policy.last_used else ""

        click.echo(
            f"{name:<30} {files:>8} {success:>8} {saved:>12} "
            f"{audio:>6} {subs:>6} {avg_time:>10} {last_used:<20}"
        )

    click.echo("")


def _output_policies_csv(policies) -> None:
    """Output policies in CSV format."""
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
    click.echo(",".join(headers))

    for policy in policies:
        values = [
            policy.policy_name,
            str(policy.files_processed),
            f"{policy.success_rate:.4f}",
            str(policy.total_size_saved),
            f"{policy.avg_savings_percent:.2f}",
            str(policy.audio_tracks_removed),
            str(policy.subtitle_tracks_removed),
            str(policy.attachments_removed),
            str(policy.videos_transcoded),
            str(policy.audio_transcoded),
            f"{policy.avg_processing_time:.2f}",
            policy.last_used or "",
        ]
        click.echo(",".join(values))


def _parse_time_filter(value: str) -> str:
    """Parse a time filter value to ISO-8601 timestamp.

    Accepts relative times (7d, 1w, 2h) or ISO-8601 timestamps.

    Args:
        value: Time filter value.

    Returns:
        ISO-8601 timestamp string.

    Raises:
        click.ClickException: If format is invalid.
    """
    from datetime import datetime, timedelta, timezone

    # Check if it's already an ISO-8601 timestamp
    if "T" in value or len(value) >= 10:
        return value

    # Parse relative time
    try:
        if value.endswith("d"):
            days = int(value[:-1])
            delta = timedelta(days=days)
        elif value.endswith("w"):
            weeks = int(value[:-1])
            delta = timedelta(weeks=weeks)
        elif value.endswith("h"):
            hours = int(value[:-1])
            delta = timedelta(hours=hours)
        elif value.endswith("m"):
            minutes = int(value[:-1])
            delta = timedelta(minutes=minutes)
        else:
            raise click.ClickException(
                f"Invalid time format: {value}. "
                "Use relative time (7d, 1w, 2h) or ISO-8601."
            )

        result = datetime.now(timezone.utc) - delta
        return result.isoformat()

    except ValueError:
        raise click.ClickException(
            f"Invalid time format: {value}. Use relative time (7d, 1w, 2h) or ISO-8601."
        )
