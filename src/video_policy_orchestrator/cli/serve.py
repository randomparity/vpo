"""CLI serve command for daemon mode.

This module provides the `vpo serve` command that runs VPO as a
long-lived background service suitable for systemd management.
"""

import asyncio
import logging
import sys
from pathlib import Path

import click

from video_policy_orchestrator.config import get_config
from video_policy_orchestrator.db.connection import (
    check_database_connectivity,
    get_default_db_path,
)

logger = logging.getLogger(__name__)


def _configure_daemon_logging(
    log_level: str | None,
    log_format: str | None,
    config_path: Path | None,
) -> None:
    """Configure logging for daemon mode.

    Uses the centralized logging configuration with daemon-specific defaults.

    Args:
        log_level: CLI override for log level.
        log_format: CLI override for log format.
        config_path: Path to config file for reading logging settings.
    """
    from video_policy_orchestrator.config import get_config
    from video_policy_orchestrator.config.models import LoggingConfig
    from video_policy_orchestrator.logging import configure_logging

    # Load base config
    config = get_config(config_path=config_path)
    base_logging = config.logging

    # Build logging config with CLI overrides
    # Daemon defaults to INFO level (not WARNING like some CLI commands)
    final_config = LoggingConfig(
        level=log_level or base_logging.level,
        file=base_logging.file,
        format=log_format or base_logging.format,
        include_stderr=True,  # Always include stderr for daemon (journald)
        max_bytes=base_logging.max_bytes,
        backup_count=base_logging.backup_count,
    )

    configure_logging(final_config)


async def run_server(
    bind: str,
    port: int,
    shutdown_timeout: float,
    db_path: Path,
) -> int:
    """Run the daemon server.

    Args:
        bind: Address to bind to.
        port: Port to bind to.
        shutdown_timeout: Seconds to wait for graceful shutdown.
        db_path: Path to database file.

    Returns:
        Exit code (0 for clean shutdown, non-zero for errors).
    """
    from aiohttp import web

    from video_policy_orchestrator.server.app import create_app
    from video_policy_orchestrator.server.lifecycle import DaemonLifecycle
    from video_policy_orchestrator.server.signals import (
        remove_signal_handlers,
        setup_signal_handlers,
    )

    # Create lifecycle manager
    lifecycle = DaemonLifecycle(shutdown_timeout=shutdown_timeout)

    # Create shutdown event for signal coordination
    shutdown_event = asyncio.Event()

    # Get the running event loop
    loop = asyncio.get_running_loop()

    # Set up signal handlers
    setup_signal_handlers(loop, lifecycle, shutdown_event)

    # Create the application with database path for connection pooling
    app = create_app(db_path=db_path)
    app["lifecycle"] = lifecycle

    # Create the runner and site
    runner = web.AppRunner(app)
    await runner.setup()

    try:
        site = web.TCPSite(runner, bind, port)
        await site.start()

        logger.info(
            "VPO daemon started on http://%s:%d (PID %d)",
            bind,
            port,
            __import__("os").getpid(),
        )
        logger.info("Health endpoint: http://%s:%d/health", bind, port)
        logger.info("Press Ctrl+C or send SIGTERM to stop")

        # Wait for shutdown signal
        await shutdown_event.wait()

        logger.info(
            "Shutdown initiated, waiting up to %.1fs for cleanup", shutdown_timeout
        )

        # Graceful shutdown - give time for in-flight requests
        await asyncio.sleep(0.5)  # Brief pause for in-flight requests

    except OSError as e:
        if "Address already in use" in str(e) or e.errno == 98:
            logger.error("Port %d is already in use", port)
            return 1
        if "Cannot assign requested address" in str(e) or e.errno == 99:
            logger.error("Cannot bind to address %s", bind)
            return 1
        logger.error("Server error: %s", e)
        return 1
    finally:
        # Clean up
        remove_signal_handlers(loop)
        await runner.cleanup()
        logger.info("VPO daemon stopped")

    return 0


@click.command("serve")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file (default: ~/.vpo/config.toml).",
)
@click.option(
    "--bind",
    type=str,
    default=None,
    help="Address to bind to (default: 127.0.0.1).",
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=None,
    help="Port to bind to (default: 8321).",
)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
    default=None,
    help="Override log level for daemon mode (default: info).",
)
@click.option(
    "--log-format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default=None,
    help="Log format: text or json (default: text).",
)
@click.pass_context
def serve_command(
    ctx: click.Context,
    config_path: Path | None,
    bind: str | None,
    port: int | None,
    log_level: str | None,
    log_format: str | None,
) -> None:
    """Run VPO as a background daemon.

    Starts a long-lived HTTP server with a health endpoint at /health.
    Handles graceful shutdown on SIGTERM (from systemd) or SIGINT (Ctrl+C).

    The daemon binds to localhost by default for security. Override with
    --bind to expose on other interfaces.

    Configuration precedence (highest to lowest):
      1. CLI flags (--bind, --port, --log-level, etc.)
      2. Config file (--config or ~/.vpo/config.toml)
      3. Environment variables (VPO_SERVER_*)
      4. Default values

    \b
    Examples:
        vpo serve                           # Start with defaults
        vpo serve --port 9000               # Custom port
        vpo serve --bind 0.0.0.0            # Listen on all interfaces
        vpo serve --config /etc/vpo/config.toml  # Custom config
        vpo serve --log-format json         # JSON logging for systemd
    """
    # Configure logging for daemon mode
    _configure_daemon_logging(log_level, log_format, config_path)

    # Load configuration with CLI overrides
    config = get_config(config_path=config_path)

    # Apply CLI overrides (CLI > config file > env vars > defaults)
    server_bind = bind if bind is not None else config.server.bind
    server_port = port if port is not None else config.server.port
    shutdown_timeout = config.server.shutdown_timeout

    # Get database path
    db_path = config.database_path or get_default_db_path()

    # Validate database accessibility at startup
    if not check_database_connectivity(db_path):
        logger.error("Database not accessible: %s", db_path)
        logger.error("Run 'vpo scan' first to initialize the database")
        sys.exit(1)

    # Validate port range
    if not 1 <= server_port <= 65535:
        logger.error("Port must be 1-65535, got %d", server_port)
        sys.exit(1)

    # Warn about privileged ports
    if server_port < 1024:
        logger.warning("Port %d is privileged and may require root", server_port)

    logger.info(
        "Starting VPO daemon (bind=%s, port=%d, timeout=%.1fs)",
        server_bind,
        server_port,
        shutdown_timeout,
    )

    # Run the async server
    try:
        exit_code = asyncio.run(
            run_server(server_bind, server_port, shutdown_timeout, db_path)
        )
        sys.exit(exit_code)
    except KeyboardInterrupt:
        # User pressed Ctrl+C before server started
        logger.info("Interrupted before server started")
        sys.exit(130)
