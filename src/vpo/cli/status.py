"""VPO status dashboard command."""

import json
import logging

import click

from vpo.cli.output import format_option
from vpo.core.formatting import format_file_size

logger = logging.getLogger(__name__)


@click.command("status")
@format_option
@click.pass_context
def status_command(ctx: click.Context, output_format: str) -> None:
    """Show a summary of the VPO library, jobs, and tools.

    Displays library file counts, job queue statistics, and external
    tool availability in a single dashboard view.

    Examples:

    \b
        vpo status
        vpo status --format json
    """
    conn = ctx.obj.get("db_conn") if ctx.obj else None

    data: dict = {}

    # Library info
    if conn is not None:
        from vpo.db.views.library_info import get_library_info

        info = get_library_info(conn)
        data["library"] = {
            "total_files": info.total_files,
            "files_ok": info.files_ok,
            "files_missing": info.files_missing,
            "files_error": info.files_error,
            "files_pending": info.files_pending,
            "total_size_bytes": info.total_size_bytes,
            "schema_version": info.schema_version,
        }

        # Job queue stats
        from vpo.jobs.queue import get_queue_stats

        queue = get_queue_stats(conn)
        data["jobs"] = queue
    else:
        data["library"] = None
        data["jobs"] = None

    # Tool availability
    from vpo.tools.cache import get_tool_registry

    try:
        registry = get_tool_registry()
        data["tools"] = {
            tool.name: {
                "status": tool.status.value,
                "version": tool.version,
            }
            for tool in [
                registry.ffmpeg,
                registry.ffprobe,
                registry.mkvmerge,
                registry.mkvpropedit,
            ]
        }
    except Exception:
        logger.debug("Tool detection failed", exc_info=True)
        data["tools"] = None

    if output_format == "json":
        click.echo(json.dumps(data, indent=2))
        return

    _display_status(data)


def _display_status(data: dict) -> None:
    """Render the status dashboard in human-readable format."""
    lib = data.get("library")
    if lib is not None:
        click.echo("Library:")
        click.echo(f"  Files: {lib['total_files']} total", nl=False)
        parts = []
        if lib["files_ok"]:
            parts.append(f"{lib['files_ok']} ok")
        if lib["files_missing"]:
            parts.append(f"{lib['files_missing']} missing")
        if lib["files_error"]:
            parts.append(f"{lib['files_error']} error")
        if lib["files_pending"]:
            parts.append(f"{lib['files_pending']} pending")
        if parts:
            click.echo(f" ({', '.join(parts)})")
        else:
            click.echo()
        click.echo(f"  Size:  {format_file_size(lib['total_size_bytes'])}")
        click.echo(f"  Schema: v{lib['schema_version']}")
    else:
        click.echo("Library: (no database connection)")

    click.echo()

    jobs = data.get("jobs")
    if jobs is not None:
        click.echo("Jobs:")
        click.echo(
            f"  Queued: {jobs['queued']}  Running: {jobs['running']}  "
            f"Completed: {jobs['completed']}  Failed: {jobs['failed']}"
        )
    else:
        click.echo("Jobs: (no database connection)")

    click.echo()

    tools = data.get("tools")
    if tools is not None:
        click.echo("Tools:")
        for name, info in tools.items():
            status_mark = "ok" if info["status"] == "available" else info["status"]
            version = info["version"] or "-"
            click.echo(f"  {name:<14} {version:<12} {status_mark}")
    else:
        click.echo("Tools: (detection failed)")
