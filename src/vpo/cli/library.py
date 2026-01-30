"""CLI commands for managing the video library.

This module provides commands for listing and managing files in the
VPO library database.
"""

import json
import logging

import click

from vpo.core import format_file_size
from vpo.db.views import get_missing_files

logger = logging.getLogger(__name__)


@click.group("library")
def library_group() -> None:
    """Manage video library.

    Commands for listing, filtering, and managing files tracked
    in the VPO library database.

    Examples:

        # List files missing from the filesystem
        vpo library missing

        # List missing files as JSON
        vpo library missing --json
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
    a prune job.

    Examples:

        # List missing files
        vpo library missing

        # List up to 500 missing files as JSON
        vpo library missing --json --limit 500
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

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
        f"{'Path':<{path_width}}  "
        f"{'Last Scanned':<{date_width}}  "
        f"{'Size':>{size_width}}"
    )
    click.echo(header)
    click.echo("\u2500" * len(header))

    for f in files:
        path = f["path"] or ""
        if len(path) > path_width:
            path = "..." + path[-(path_width - 3) :]

        scanned = (f["scanned_at"] or "")[:19].replace("T", " ")
        size = format_file_size(f["size_bytes"]) if f["size_bytes"] else "\u2014"

        click.echo(
            f"{path:<{path_width}}  {scanned:<{date_width}}  {size:>{size_width}}"
        )
