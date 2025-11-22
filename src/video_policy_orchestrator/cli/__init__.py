"""CLI module for Video Policy Orchestrator."""

import sqlite3

import click

from video_policy_orchestrator.db.connection import (
    ensure_db_directory,
    get_default_db_path,
)
from video_policy_orchestrator.db.schema import create_schema


def _get_db_connection() -> sqlite3.Connection | None:
    """Get a database connection for CLI context.

    Creates a persistent connection (not context-managed) for use across
    subcommands. The connection is created with the same settings as
    get_connection() but without the context manager wrapper.

    Returns:
        Database connection or None if connection fails.
    """
    try:
        db_path = get_default_db_path()
        ensure_db_directory(db_path)

        conn = sqlite3.connect(str(db_path), timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row

        # Ensure schema exists
        create_schema(conn)

        return conn
    except Exception:
        return None


@click.group()
@click.version_option(package_name="video-policy-orchestrator")
@click.option(
    "--force-load-plugins",
    is_flag=True,
    help="Force load plugins even if version incompatible or unacknowledged",
)
@click.pass_context
def main(ctx: click.Context, force_load_plugins: bool) -> None:
    """Video Policy Orchestrator - Scan, organize, and transform video libraries."""
    ctx.ensure_object(dict)
    ctx.obj["force_load_plugins"] = force_load_plugins

    # Initialize database connection for subcommands
    ctx.obj["db_conn"] = _get_db_connection()


# Defer import to avoid circular dependency
def _register_commands():
    from video_policy_orchestrator.cli import scan  # noqa: F401
    from video_policy_orchestrator.cli.apply import apply_command
    from video_policy_orchestrator.cli.doctor import doctor_command
    from video_policy_orchestrator.cli.inspect import inspect_command
    from video_policy_orchestrator.cli.jobs import jobs_group
    from video_policy_orchestrator.cli.plugins import plugins
    from video_policy_orchestrator.cli.transcode import transcode_command
    from video_policy_orchestrator.cli.transcribe import transcribe_group

    main.add_command(inspect_command)
    main.add_command(apply_command)
    main.add_command(doctor_command)
    main.add_command(plugins)
    main.add_command(transcode_command)
    main.add_command(jobs_group)
    main.add_command(transcribe_group)


_register_commands()
