"""HTTP application for daemon mode.

This module provides the aiohttp Application with health check endpoint,
Web UI routes, and runtime state management.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.web import RequestHandler
from aiohttp_session import setup as setup_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet

from vpo import __version__
from vpo.server.ui import setup_ui_routes

if TYPE_CHECKING:
    from vpo.db.connection import DaemonConnectionPool

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

    # Job queue metrics
    jobs_queued: int = 0
    """Number of jobs waiting in queue."""

    jobs_running: int = 0
    """Number of jobs currently being processed."""

    active_workers: int = 0
    """Number of distinct workers processing jobs."""

    recent_errors: int = 0
    """Number of failed jobs in last 24 hours."""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


HEALTH_CHECK_TIMEOUT = 5.0  # seconds


async def check_database_health(connection_pool: DaemonConnectionPool | None) -> bool:
    """Check database connectivity using connection pool.

    Runs SELECT 1 query in a thread pool to avoid blocking the event loop.
    Uses the daemon's connection pool for thread-safe access.
    Times out after HEALTH_CHECK_TIMEOUT seconds to prevent hanging.

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
        except sqlite3.OperationalError as e:
            logger.warning("Database locked or inaccessible: %s", e)
            return False
        except sqlite3.DatabaseError as e:
            logger.warning("Database error during health check: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error during health check: %s", e)
            return False

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_sync_check),
            timeout=HEALTH_CHECK_TIMEOUT,
        )
    except asyncio.TimeoutError:
        timeout = HEALTH_CHECK_TIMEOUT
        logger.warning("Database health check timed out after %.1fs", timeout)
        return False
    except Exception as e:
        logger.error("Failed to run health check: %s", e)
        return False


async def _cleanup_connection_pool(app: web.Application) -> None:
    """Cleanup handler to close the connection pool on shutdown."""
    pool: DaemonConnectionPool | None = app.get("connection_pool")
    if pool is not None:
        logger.debug("Closing database connection pool")
        pool.close()


def create_app(
    db_path: Path | None = None, auth_token: str | None = None
) -> web.Application:
    """Create and configure the aiohttp Application.

    Args:
        db_path: Path to database file for connection pooling.
            If provided and exists, a connection pool will be created.
        auth_token: Optional authentication token for HTTP Basic Auth.
            If provided (non-empty), all endpoints except /health require auth.

    Returns:
        Configured aiohttp Application instance.
    """
    from vpo.db.connection import DaemonConnectionPool
    from vpo.server.auth import (
        create_auth_middleware,
        is_auth_enabled,
    )

    app = web.Application()

    # Setup auth middleware if token is configured
    if is_auth_enabled(auth_token):
        auth_middleware = create_auth_middleware(auth_token)  # type: ignore[arg-type]
        app.middlewares.append(auth_middleware)
        logger.info("Authentication enabled for web UI and API endpoints")
    else:
        logger.warning(
            "Authentication is disabled. Set VPO_AUTH_TOKEN to protect the web UI."
        )

    # Setup session middleware with encrypted cookie storage
    # Use environment variable for secret key, or generate one for development
    secret_key_str = os.environ.get("VPO_SESSION_SECRET")
    if not secret_key_str:
        # Generate a random 32-byte key for development/testing
        # In production, VPO_SESSION_SECRET should be set
        # Note: We use Fernet.generate_key() and decode it to get raw 32 bytes
        # EncryptedCookieStorage expects raw bytes, not base64-encoded
        import base64

        encoded_key = fernet.Fernet.generate_key()
        secret_key = base64.urlsafe_b64decode(encoded_key)
        logger.warning(
            "VPO_SESSION_SECRET not set, using randomly generated session key. "
            "Sessions will not persist across restarts."
        )
    else:
        # Environment variable is a string, encode it to bytes
        # Assume it's a Fernet-compatible base64-encoded key
        import base64

        secret_key = base64.urlsafe_b64decode(secret_key_str)

    setup_session(app, EncryptedCookieStorage(secret_key))

    # Store runtime state in app dict
    app["lifecycle"] = None  # Will be set by serve command

    # Create connection pool if database path provided
    if db_path is not None and db_path.exists():
        from vpo.db.schema import initialize_database

        pool_timeout = float(os.environ.get("VPO_DB_TIMEOUT", "30.0"))
        pool = DaemonConnectionPool(db_path, timeout=pool_timeout)
        app["connection_pool"] = pool

        # Run database migrations if needed
        # Note: initialize_database is NOT wrapped in transaction() because:
        # - create_schema uses executescript() which commits implicitly
        # - Migrations are idempotent and safe to re-run on failure
        conn = pool.get_connection()
        initialize_database(conn)

        logger.debug(
            "Created database connection pool for %s with timeout %.1fs",
            db_path,
            pool_timeout,
        )
    else:
        app["connection_pool"] = None

    # Initialize maintenance task (will be started on server startup)
    app["maintenance_task"] = None
    app["maintenance_task_handle"] = None

    # Register API routes
    app.router.add_get("/health", health_handler)
    app.router.add_get("/api/about", api_about_handler)
    # Setup UI routes and templates (includes API routes via setup_api_routes)
    setup_ui_routes(app)

    # Setup static file serving with cache headers
    static_path = Path(__file__).parent / "static"
    app.router.add_static(
        "/static",
        static_path,
        name="static",
        append_version=True,  # Adds ?v=hash for cache busting
    )

    # Add middleware for static file cache headers
    @web.middleware
    async def static_cache_middleware(
        request: web.Request, handler: RequestHandler
    ) -> web.StreamResponse:
        """Add Cache-Control headers to static file responses."""
        response = await handler(request)
        if request.path.startswith("/static/"):
            # Cache static files for 1 hour
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    # Insert at beginning so it runs after static handler
    app.middlewares.insert(0, static_cache_middleware)

    # Register startup and cleanup handlers
    app.on_startup.append(_start_maintenance_task)
    app.on_cleanup.append(_stop_maintenance_task)
    app.on_cleanup.append(_cleanup_connection_pool)

    return app


async def _start_maintenance_task(app: web.Application) -> None:
    """Start the background maintenance task."""
    from vpo.server.maintenance import MaintenanceTask

    maintenance = MaintenanceTask()
    app["maintenance_task"] = maintenance
    app["maintenance_task_handle"] = asyncio.create_task(maintenance.run())
    logger.debug("Started background maintenance task")


async def _stop_maintenance_task(app: web.Application) -> None:
    """Stop the background maintenance task."""
    maintenance = app.get("maintenance_task")
    task_handle = app.get("maintenance_task_handle")

    if maintenance:
        maintenance.stop()

    if task_handle and not task_handle.done():
        # Wait for task to finish (with timeout)
        try:
            await asyncio.wait_for(task_handle, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Maintenance task did not stop in time, cancelling")
            task_handle.cancel()
            try:
                await task_handle
            except asyncio.CancelledError:
                pass

    logger.debug("Stopped background maintenance task")


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
    from vpo.jobs.queue import get_job_health_metrics
    from vpo.server.lifecycle import DaemonLifecycle

    lifecycle: DaemonLifecycle | None = request.app.get("lifecycle")
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")

    # Check database connectivity using connection pool
    db_connected = await check_database_health(connection_pool)

    # Determine shutdown state
    shutting_down = lifecycle.is_shutting_down if lifecycle else False
    uptime = lifecycle.uptime_seconds if lifecycle else 0.0

    # Get job metrics from database
    job_metrics = {
        "jobs_queued": 0,
        "jobs_running": 0,
        "active_workers": 0,
        "recent_errors": 0,
    }
    if db_connected and connection_pool is not None:
        try:

            def _get_metrics() -> dict[str, int]:
                conn = connection_pool.get_connection()
                return get_job_health_metrics(conn)

            job_metrics = await asyncio.to_thread(_get_metrics)
        except Exception as e:
            logger.warning("Failed to get job metrics for health check: %s", e)

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
        # Job metrics
        jobs_queued=job_metrics["jobs_queued"],
        jobs_running=job_metrics["jobs_running"],
        active_workers=job_metrics["active_workers"],
        recent_errors=job_metrics["recent_errors"],
    )

    # Return 503 for degraded/unhealthy, 200 for healthy
    http_status = 200 if status == "healthy" else 503

    return web.json_response(health.to_dict(), status=http_status)


async def api_about_handler(request: web.Request) -> web.Response:
    """Handle GET /api/about requests.

    Returns JSON with application information for programmatic access.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with AboutInfo payload.
    """
    from vpo.server.ui.routes import get_about_info

    about_info = get_about_info(request)
    return web.json_response(about_info.to_dict())
