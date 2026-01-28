"""CLI module for Video Policy Orchestrator."""

import atexit
import logging
import os
import sqlite3
import sys
from pathlib import Path

import click

from vpo.db.connection import (
    ensure_db_directory,
    get_default_db_path,
)
from vpo.db.schema import create_schema

_db_conn: sqlite3.Connection | None = None
_logging_configured: bool = False
_atexit_registered: bool = False
_startup_logged: bool = False

logger = logging.getLogger(__name__)


def _cleanup_db_connection() -> None:
    """Clean up database connection on exit."""
    global _db_conn
    if _db_conn is not None:
        try:
            _db_conn.close()
        except Exception:  # nosec B110
            # Swallowing exception is intentional during cleanup - we can't
            # meaningfully handle errors when closing on exit
            pass
        _db_conn = None


def _get_db_connection() -> sqlite3.Connection | None:
    """Get a database connection for CLI context.

    Creates a persistent connection (not context-managed) for use across
    subcommands. The connection is created with the same settings as
    get_connection() but without the context manager wrapper.

    Connection Lifecycle:
        This uses a module-level singleton pattern with atexit cleanup.
        This is appropriate for CLI usage where the process runs a single
        command and exits. The atexit handler ensures the connection is
        closed on normal process termination. If the process is killed
        (SIGKILL), SQLite's WAL mode handles recovery safely.

    Returns:
        Database connection or None if connection fails.
    """
    global _db_conn

    if _db_conn is not None:
        return _db_conn

    try:
        db_path = get_default_db_path()
        ensure_db_directory(db_path)

        conn = sqlite3.connect(str(db_path), timeout=30.0)

        # Enable same PRAGMAs as get_connection() for consistency
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA temp_store = MEMORY")

        conn.row_factory = sqlite3.Row

        # Ensure schema exists
        create_schema(conn)

        _db_conn = conn

        # Register cleanup on exit (only once)
        global _atexit_registered
        if not _atexit_registered:
            atexit.register(_cleanup_db_connection)
            _atexit_registered = True

        return conn
    except (sqlite3.Error, OSError) as e:
        logger.warning("Failed to create database connection: %s", e)
        return None


def _configure_logging(
    log_level: str | None,
    log_file: Path | None,
    log_json: bool,
) -> None:
    """Configure logging from CLI options.

    Args:
        log_level: Override log level (debug, info, warning, error).
        log_file: Override log file path.
        log_json: Use JSON log format.
    """
    global _logging_configured
    if _logging_configured:
        return

    from vpo.config.logging_factory import (
        configure_logging_from_cli,
    )

    configure_logging_from_cli(
        level=log_level,
        file=log_file,
        format="json" if log_json else None,
    )
    _logging_configured = True


def _log_startup_settings(
    cli_log_level: str | None,
    cli_log_file: Path | None,
) -> None:
    """Log key settings with their sources at startup.

    This logs a summary of important configuration settings,
    showing where each value came from (default, config, env, cli).

    Args:
        cli_log_level: Log level from CLI option (or None).
        cli_log_file: Log file from CLI option (or None).
    """
    global _startup_logged
    if _startup_logged:
        return
    _startup_logged = True

    from vpo.config import get_config
    from vpo.config.loader import (
        get_data_dir,
        load_config_file,
    )

    # Get the effective configuration
    config = get_config()
    file_config = load_config_file()
    file_logging = file_config.get("logging", {})

    # Determine data_dir source
    data_dir = get_data_dir()
    if os.environ.get("VPO_DATA_DIR"):
        data_dir_source = "env"
    else:
        data_dir_source = "default"

    # Determine log_level source
    if cli_log_level:
        log_level_source = "cli"
        log_level = cli_log_level
    elif file_logging.get("level"):
        log_level_source = "config"
        log_level = config.logging.level
    else:
        log_level_source = "default"
        log_level = config.logging.level

    # Determine log_file source
    if cli_log_file:
        log_file_source = "cli"
        log_file = str(cli_log_file)
    elif file_logging.get("file"):
        log_file_source = "config"
        log_file = str(config.logging.file) if config.logging.file else "stderr"
    else:
        log_file_source = "default"
        log_file = str(config.logging.file) if config.logging.file else "stderr"

    # Compact the data_dir for display
    data_dir_display = str(data_dir).replace(str(Path.home()), "~")
    log_file_display = log_file.replace(str(Path.home()), "~") if log_file else "stderr"

    logger.info(
        "VPO starting: data_dir=%s (%s), log_level=%s (%s), log_file=%s (%s)",
        data_dir_display,
        data_dir_source,
        log_level,
        log_level_source,
        log_file_display,
        log_file_source,
    )


def _is_interactive() -> bool:
    """Check if running in interactive mode (TTY).

    This is extracted as a function to allow easier mocking in tests.

    Returns:
        True if stdin is a TTY, False otherwise.
    """
    return sys.stdin.isatty()


def _check_initialization(ctx: click.Context) -> None:
    """Check if VPO is initialized and prompt to initialize if not.

    This check runs before any subcommand except 'init'. If VPO is not
    initialized (config.toml missing), it prompts the user to initialize
    interactively, or exits with an error in non-interactive mode.

    Args:
        ctx: Click context with invoked_subcommand.
    """
    # Skip check for init command
    if ctx.invoked_subcommand == "init":
        return

    from vpo.config.loader import get_data_dir

    data_dir = get_data_dir()
    config_path = data_dir / "config.toml"

    if config_path.exists():
        return  # Already initialized

    # Check if running interactively
    if not _is_interactive():
        click.echo("Error: VPO is not initialized.", err=True)
        click.echo(
            "Run 'vpo init' to set up configuration and data directories.", err=True
        )
        raise SystemExit(1)

    # Prompt user
    click.echo("")
    if click.confirm(
        "VPO is not initialized. Would you like to initialize now?", default=True
    ):
        # Run init
        from vpo.cli.init import _display_result
        from vpo.config.templates import run_init

        result = run_init(data_dir)
        _display_result(result, force=False)

        if not result.success:
            raise SystemExit(1)

        click.echo("")
        click.echo(f"Continuing with {ctx.invoked_subcommand}...")
        click.echo("")
    else:
        click.echo("")
        click.echo("VPO requires initialization before use.")
        click.echo("Run 'vpo init' to set up configuration and data directories.")
        raise SystemExit(1)


@click.group()
@click.version_option(package_name="vpo")
@click.option(
    "--force-load-plugins",
    is_flag=True,
    help="Force load plugins even if version incompatible or unacknowledged",
)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
    default=None,
    help="Override log level (default: info).",
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Override log file path.",
)
@click.option(
    "--log-json",
    is_flag=True,
    default=False,
    help="Use JSON log format.",
)
@click.pass_context
def main(
    ctx: click.Context,
    force_load_plugins: bool,
    log_level: str | None,
    log_file: Path | None,
    log_json: bool,
) -> None:
    """Video Policy Orchestrator - Scan, organize, and transform video libraries."""
    ctx.ensure_object(dict)
    ctx.obj["force_load_plugins"] = force_load_plugins

    # Check initialization before any other setup (except for init command)
    _check_initialization(ctx)

    # Configure logging from CLI options
    _configure_logging(log_level, log_file, log_json)

    # Log startup settings (skip for init command - it should be silent)
    # ctx.invoked_subcommand is the name of the subcommand being invoked
    if ctx.invoked_subcommand != "init":
        _log_startup_settings(log_level, log_file)

    # Initialize database connection for subcommands (preserve mock if passed by tests)
    if "db_conn" not in ctx.obj:
        ctx.obj["db_conn"] = _get_db_connection()


# Defer import to avoid circular dependency
def _register_commands():
    from vpo.cli import scan  # noqa: F401
    from vpo.cli.analyze_language import analyze_language_group
    from vpo.cli.classify import classify_group
    from vpo.cli.doctor import doctor_command
    from vpo.cli.init import init_command
    from vpo.cli.inspect import inspect_command
    from vpo.cli.jobs import jobs_group
    from vpo.cli.maintain import maintain_group
    from vpo.cli.plugins import plugins
    from vpo.cli.process import process_command
    from vpo.cli.profiles import profiles_group
    from vpo.cli.report import report_group
    from vpo.cli.serve import serve_command
    from vpo.cli.stats import stats_group

    main.add_command(analyze_language_group)
    main.add_command(classify_group)
    main.add_command(init_command)
    main.add_command(inspect_command)
    main.add_command(doctor_command)
    main.add_command(plugins)
    main.add_command(process_command)
    main.add_command(jobs_group)
    main.add_command(stats_group)
    main.add_command(profiles_group)
    main.add_command(report_group)
    main.add_command(serve_command)
    main.add_command(maintain_group)


_register_commands()
