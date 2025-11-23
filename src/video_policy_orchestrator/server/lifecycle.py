"""Daemon lifecycle management.

This module provides classes for managing daemon startup, running state,
and graceful shutdown coordination.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


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
        return datetime.now(UTC) >= self.timeout_deadline


@dataclass
class DaemonLifecycle:
    """Manages daemon startup and shutdown state.

    Coordinates graceful shutdown across HTTP server and background tasks.
    Uses asyncio.Event for cross-task shutdown signaling.
    """

    shutdown_timeout: float = 30.0
    """Seconds to wait for graceful shutdown before cancelling tasks."""

    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    """UTC timestamp when daemon started."""

    shutdown_state: ShutdownState = field(default_factory=ShutdownState)
    """Current shutdown state."""

    @property
    def uptime_seconds(self) -> float:
        """Returns seconds since daemon startup."""
        return (datetime.now(UTC) - self.start_time).total_seconds()

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

        now = datetime.now(UTC)
        self.shutdown_state.initiated = now
        self.shutdown_state.timeout_deadline = now + timedelta(
            seconds=self.shutdown_timeout
        )
