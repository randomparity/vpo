"""Signal handler setup for daemon mode.

This module provides signal handler registration for graceful shutdown
on SIGTERM (from systemd) and SIGINT (from Ctrl+C).
"""

import asyncio
import logging
import signal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.server.lifecycle import DaemonLifecycle

logger = logging.getLogger(__name__)


def setup_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    lifecycle: "DaemonLifecycle",
    shutdown_event: asyncio.Event,
) -> None:
    """Register signal handlers for graceful shutdown.

    Registers handlers for SIGTERM and SIGINT that initiate graceful
    shutdown through the lifecycle object and signal the shutdown event.

    Args:
        loop: The asyncio event loop to register handlers on.
        lifecycle: DaemonLifecycle instance for shutdown coordination.
        shutdown_event: Event to signal when shutdown is initiated.
    """

    def handle_signal(sig: signal.Signals) -> None:
        """Handle shutdown signal."""
        sig_name = sig.name
        logger.info("Received %s, initiating graceful shutdown", sig_name)
        lifecycle.initiate_shutdown()
        shutdown_event.set()

    # Register handlers for both SIGTERM (systemd) and SIGINT (Ctrl+C)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, handle_signal, sig)
            logger.debug("Registered handler for %s", sig.name)
        except (ValueError, RuntimeError) as e:
            # ValueError: not in main thread
            # RuntimeError: event loop not running
            logger.warning("Failed to register handler for %s: %s", sig.name, e)


def remove_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Remove signal handlers during cleanup.

    Args:
        loop: The asyncio event loop to remove handlers from.
    """
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.remove_signal_handler(sig)
            logger.debug("Removed handler for %s", sig.name)
        except (ValueError, RuntimeError):
            pass  # Handler may not have been registered
