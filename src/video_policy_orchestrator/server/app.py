"""HTTP application for daemon mode.

This module provides the aiohttp Application with health check endpoint
and runtime state management.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web

from video_policy_orchestrator import __version__

if TYPE_CHECKING:
    from video_policy_orchestrator.db.connection import DaemonConnectionPool

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health check response payload."""

    status: str
    """Overall status: 'healthy', 'degraded', or 'unhealthy'."""

    database: str
    """Database connectivity: 'connected' or 'disconnected'."""

    uptime_seconds: float
    """Seconds since daemon startup."""

    version: str
    """VPO version string."""

    shutting_down: bool = False
    """True if graceful shutdown is in progress."""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


async def check_database_health(connection_pool: DaemonConnectionPool | None) -> bool:
    """Check database connectivity using connection pool.

    Runs SELECT 1 query in a thread pool to avoid blocking the event loop.
    Uses the daemon's connection pool for thread-safe access.

    Args:
        connection_pool: DaemonConnectionPool instance or None.

    Returns:
        True if database is accessible, False otherwise.
    """
    if connection_pool is None:
        return False

    def _sync_check() -> bool:
        try:
            # Use pool's thread-safe execute method
            connection_pool.execute_read("SELECT 1")
            return True
        except Exception as e:
            logger.warning("Database health check failed: %s", e)
            return False

    try:
        return await asyncio.to_thread(_sync_check)
    except Exception as e:
        logger.error("Failed to run health check: %s", e)
        return False


async def _cleanup_connection_pool(app: web.Application) -> None:
    """Cleanup handler to close the connection pool on shutdown."""
    pool: DaemonConnectionPool | None = app.get("connection_pool")
    if pool is not None:
        logger.debug("Closing database connection pool")
        pool.close()


def create_app(db_path: Path | None = None) -> web.Application:
    """Create and configure the aiohttp Application.

    Args:
        db_path: Path to database file for connection pooling.
            If provided and exists, a connection pool will be created.

    Returns:
        Configured aiohttp Application instance.
    """
    from video_policy_orchestrator.db.connection import DaemonConnectionPool

    app = web.Application()

    # Store runtime state in app dict
    app["lifecycle"] = None  # Will be set by serve command

    # Create connection pool if database path provided
    if db_path is not None and db_path.exists():
        app["connection_pool"] = DaemonConnectionPool(db_path)
        logger.debug("Created database connection pool for %s", db_path)
    else:
        app["connection_pool"] = None

    # Register routes
    app.router.add_get("/health", health_handler)

    # Register cleanup handler
    app.on_cleanup.append(_cleanup_connection_pool)

    return app


async def health_handler(request: web.Request) -> web.Response:
    """Handle GET /health requests.

    Returns JSON health status with appropriate HTTP status code:
    - 200: healthy (database connected, not shutting down)
    - 503: degraded/unhealthy (database disconnected or shutting down)

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with HealthStatus payload.
    """
    from video_policy_orchestrator.server.lifecycle import DaemonLifecycle

    lifecycle: DaemonLifecycle | None = request.app.get("lifecycle")
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")

    # Check database connectivity using connection pool
    db_connected = await check_database_health(connection_pool)

    # Determine shutdown state
    shutting_down = lifecycle.is_shutting_down if lifecycle else False
    uptime = lifecycle.uptime_seconds if lifecycle else 0.0

    # Determine overall status
    if shutting_down:
        status = "unhealthy"
    elif not db_connected:
        status = "degraded"
    else:
        status = "healthy"

    health = HealthStatus(
        status=status,
        database="connected" if db_connected else "disconnected",
        uptime_seconds=round(uptime, 1),
        version=__version__,
        shutting_down=shutting_down,
    )

    # Return 503 for degraded/unhealthy, 200 for healthy
    http_status = 200 if status == "healthy" else 503

    return web.json_response(health.to_dict(), status=http_status)
