"""Signal handler setup for daemon mode.

This module provides signal handler registration for graceful shutdown
on SIGTERM (from systemd) and SIGINT (from Ctrl+C), and configuration
reload on SIGHUP.
"""

import asyncio
import logging
import os
import signal
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.server.lifecycle import DaemonLifecycle

logger = logging.getLogger(__name__)

# Type alias for async reload callback
ReloadCallback = Callable[[], Awaitable[None]]


def _handle_reload_task_result(task: "asyncio.Task[None]") -> None:
    """Handle completion of reload task to capture any exceptions.

    This callback is added to the reload task to ensure exceptions
    are logged rather than silently swallowed.

    Args:
        task: The completed reload task.
    """
    try:
        task.result()
    except asyncio.CancelledError:
        logger.debug("Config reload task was cancelled")
    except Exception:
        logger.exception("Config reload callback failed unexpectedly")


def setup_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    lifecycle: "DaemonLifecycle",
    shutdown_event: asyncio.Event,
    reload_callback: ReloadCallback | None = None,
) -> None:
    """Register signal handlers for graceful shutdown and config reload.

    Registers handlers for:
    - SIGTERM and SIGINT: initiate graceful shutdown
    - SIGHUP: trigger configuration reload (if callback provided)

    Args:
        loop: The asyncio event loop to register handlers on.
        lifecycle: DaemonLifecycle instance for shutdown coordination.
        shutdown_event: Event to signal when shutdown is initiated.
        reload_callback: Optional async callback for SIGHUP config reload.
            If provided, SIGHUP will trigger config reload instead of shutdown.
    """

    def handle_shutdown_signal(sig: signal.Signals) -> None:
        """Handle shutdown signal (SIGTERM, SIGINT)."""
        sig_name = sig.name
        logger.info("Received %s, initiating graceful shutdown", sig_name)
        lifecycle.initiate_shutdown()
        shutdown_event.set()

    def handle_reload_signal(sig: signal.Signals) -> None:
        """Handle reload signal (SIGHUP)."""
        pid = os.getpid()
        if reload_callback is not None:
            logger.info("Received SIGHUP, scheduling config reload (pid=%d)", pid)
            # Schedule the async callback in the event loop
            task = asyncio.ensure_future(reload_callback())
            # Add done callback to capture exceptions
            task.add_done_callback(_handle_reload_task_result)
        else:
            logger.warning(
                "Received SIGHUP but no reload callback configured (pid=%d)", pid
            )

    # Register handlers for SIGTERM and SIGINT (shutdown)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, handle_shutdown_signal, sig)
            logger.debug("Registered handler for %s", sig.name)
        except (ValueError, RuntimeError) as e:
            # ValueError: not in main thread
            # RuntimeError: event loop not running
            logger.warning("Failed to register handler for %s: %s", sig.name, e)

    # Register handler for SIGHUP (reload) - only on Unix-like systems
    if hasattr(signal, "SIGHUP"):
        try:
            loop.add_signal_handler(signal.SIGHUP, handle_reload_signal, signal.SIGHUP)
            logger.debug("Registered handler for SIGHUP")
        except (ValueError, RuntimeError) as e:
            logger.warning("Failed to register handler for SIGHUP: %s", e)


def remove_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Remove signal handlers during cleanup.

    Args:
        loop: The asyncio event loop to remove handlers from.
    """
    signals_to_remove = [signal.SIGTERM, signal.SIGINT]

    # Also remove SIGHUP on Unix-like systems
    if hasattr(signal, "SIGHUP"):
        signals_to_remove.append(signal.SIGHUP)

    for sig in signals_to_remove:
        try:
            loop.remove_signal_handler(sig)
            logger.debug("Removed handler for %s", sig.name)
        except (ValueError, RuntimeError):
            pass  # Handler may not have been registered
