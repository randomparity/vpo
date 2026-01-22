"""Daemon lifecycle management.

This module provides classes for managing daemon startup, running state,
graceful shutdown coordination, and configuration reload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.config.models import VPOConfig
    from vpo.server.config_reload import ReloadResult, ReloadState


@dataclass
class ShutdownState:
    """Tracks shutdown progress for graceful termination."""

    initiated: datetime | None = None
    """UTC timestamp when shutdown was initiated, None if not shutting down."""

    timeout_deadline: datetime | None = None
    """UTC timestamp after which remaining tasks will be cancelled."""

    tasks_remaining: int = 0
    """Count of in-flight tasks awaiting completion."""

    @property
    def is_shutting_down(self) -> bool:
        """Returns True if shutdown has been initiated."""
        return self.initiated is not None

    @property
    def is_timed_out(self) -> bool:
        """Returns True if shutdown timeout has been exceeded."""
        if self.timeout_deadline is None:
            return False
        return datetime.now(timezone.utc) >= self.timeout_deadline


@dataclass
class DaemonLifecycle:
    """Manages daemon startup and shutdown state.

    Coordinates graceful shutdown across HTTP server and background tasks.
    Uses asyncio.Event for cross-task shutdown signaling.
    """

    shutdown_timeout: float = 30.0
    """Seconds to wait for graceful shutdown before cancelling tasks."""

    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """UTC timestamp when daemon started."""

    shutdown_state: ShutdownState = field(default_factory=ShutdownState)
    """Current shutdown state."""

    config_path: Path | None = None
    """Path to configuration file for reload."""

    @property
    def uptime_seconds(self) -> float:
        """Returns seconds since daemon startup."""
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()

    @property
    def is_shutting_down(self) -> bool:
        """Returns True if shutdown has been initiated."""
        return self.shutdown_state.is_shutting_down

    def initiate_shutdown(self) -> None:
        """Begin graceful shutdown process.

        Sets shutdown timestamps and deadline. Idempotent - calling multiple
        times has no additional effect after first call.
        """
        if self.shutdown_state.initiated is not None:
            return  # Already shutting down

        from datetime import timedelta

        now = datetime.now(timezone.utc)
        self.shutdown_state.initiated = now
        self.shutdown_state.timeout_deadline = now + timedelta(
            seconds=self.shutdown_timeout
        )

    def init_reload_support(self, config: VPOConfig) -> None:
        """Initialize configuration reload support.

        Sets up the config reloader with the current configuration snapshot.
        Must be called after daemon startup to enable SIGHUP reload.

        Args:
            config: Current configuration to use as baseline for reload comparison.
        """
        from vpo.server.config_reload import ConfigReloader, ReloadState

        self._reload_state = ReloadState()
        self._config_reloader = ConfigReloader(
            state=self._reload_state,
            config_path=self.config_path,
        )
        self._config_reloader.set_current_config(config)

    @property
    def reload_state(self) -> ReloadState | None:
        """Get the current reload state, or None if not initialized."""
        return getattr(self, "_reload_state", None)

    async def reload_config(self) -> ReloadResult:
        """Reload configuration from file.

        Compares new configuration with current snapshot, logs changes,
        and updates internal state. On failure, keeps old configuration.

        Returns:
            ReloadResult with success status and change details.
        """
        from vpo.server.config_reload import ReloadResult

        if not hasattr(self, "_config_reloader"):
            return ReloadResult(
                success=False,
                changes=[],
                error="Reload support not initialized",
            )

        return await self._config_reloader.reload()
