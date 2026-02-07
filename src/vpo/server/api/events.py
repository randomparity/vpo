"""Server-Sent Events (SSE) API handlers.

Provides real-time updates to the web UI via SSE streams.
Falls back to polling automatically if SSE is not supported.

Endpoints:
    GET /api/events/jobs - SSE stream for job status changes
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from aiohttp import web

from vpo.core.datetime_utils import parse_iso_timestamp, parse_time_filter
from vpo.server.api.errors import SERVICE_UNAVAILABLE, api_error
from vpo.server.ui.models import JobFilterParams, JobListItem
from vpo.server.ui.routes import shutdown_check_middleware

logger = logging.getLogger(__name__)

# SSE configuration
SSE_HEARTBEAT_INTERVAL = 15  # seconds
SSE_JOB_UPDATE_INTERVAL = 2  # seconds
SSE_WRITE_TIMEOUT = 5.0  # seconds - timeout for writing to slow clients
SSE_DB_TIMEOUT = 5.0  # seconds - timeout for database queries
MAX_SSE_CONNECTIONS = 100  # Maximum concurrent SSE connections


async def _write_sse_event(
    response: web.StreamResponse,
    event_type: str,
    data: dict[str, Any],
    timeout: float = SSE_WRITE_TIMEOUT,
) -> bool:
    """Write an SSE event to the response stream.

    Args:
        response: The streaming response object.
        event_type: Event type name (e.g., 'job_update', 'heartbeat').
        data: Event data to JSON-serialize.
        timeout: Write timeout in seconds.

    Returns:
        True if write succeeded, False if connection was closed or timed out.
    """
    try:
        lines = [
            f"event: {event_type}\n",
            f"data: {json.dumps(data)}\n",
            "\n",  # Empty line to signal end of event
        ]
        for line in lines:
            # Add timeout to protect against slow clients
            await asyncio.wait_for(
                response.write(line.encode("utf-8")),
                timeout=timeout,
            )
        return True
    except asyncio.TimeoutError:
        logger.warning("SSE write timeout - slow client")
        return False
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        logger.debug("SSE client disconnected")
        return False
    except Exception as e:
        logger.error("SSE write error: %s", e)
        return False


def _get_client_info(request: web.Request) -> tuple[str, str]:
    """Extract client identification from request for logging.

    Args:
        request: aiohttp Request object.

    Returns:
        Tuple of (client_ip, request_id).
    """
    client_ip = request.remote or "unknown"
    request_id = request.headers.get("X-Request-ID", "unknown")
    return client_ip, request_id


@shutdown_check_middleware
async def sse_jobs_handler(request: web.Request) -> web.StreamResponse:
    """Handle GET /api/events/jobs - SSE stream for job updates.

    Streams job status updates to connected clients in real-time.
    Sends heartbeat events to keep connection alive.

    Args:
        request: aiohttp Request object.

    Returns:
        StreamResponse with SSE content type.
    """
    client_ip, request_id = _get_client_info(request)

    # Track active connections and enforce limit
    sse_connections = request.app.setdefault("_sse_connections", {"count": 0})

    if sse_connections["count"] >= MAX_SSE_CONNECTIONS:
        logger.warning(
            "SSE connection limit reached (%d), rejecting client=%s request_id=%s",
            MAX_SSE_CONNECTIONS,
            client_ip,
            request_id,
        )
        resp = api_error(
            "Service temporarily unavailable - too many connections",
            code=SERVICE_UNAVAILABLE,
            status=503,
        )
        resp.headers["Retry-After"] = "10"
        return resp

    # Increment connection count
    sse_connections["count"] += 1
    logger.debug(
        "SSE jobs connection established client=%s request_id=%s (total: %d)",
        client_ip,
        request_id,
        sse_connections["count"],
    )

    # Set up SSE response headers
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
    await response.prepare(request)

    # Track last update time for change detection
    last_update: dict[str, Any] = {}
    heartbeat_counter = 0
    consecutive_db_errors = 0

    try:
        while True:
            # Check if server is shutting down
            if request.app.get("_shutdown_event", asyncio.Event()).is_set():
                logger.debug(
                    "SSE closing due to shutdown client=%s request_id=%s",
                    client_ip,
                    request_id,
                )
                # Best-effort close event
                await _write_sse_event(
                    response,
                    "close",
                    {"reason": "server_shutdown"},
                )
                break

            # Fetch current jobs with timeout
            try:
                jobs_data = await asyncio.wait_for(
                    _get_jobs_for_sse(request),
                    timeout=SSE_DB_TIMEOUT,
                )
                consecutive_db_errors = 0  # Reset on success
            except asyncio.TimeoutError:
                logger.warning(
                    "SSE database query timeout client=%s request_id=%s",
                    client_ip,
                    request_id,
                )
                consecutive_db_errors += 1
                # Send error event to client
                await _write_sse_event(
                    response,
                    "error",
                    {
                        "message": "Database query timeout",
                        "retry_after": min(5 * consecutive_db_errors, 30),
                    },
                )
                await asyncio.sleep(SSE_JOB_UPDATE_INTERVAL)
                continue
            except Exception as e:
                logger.error(
                    "Error fetching jobs for SSE client=%s request_id=%s: %s",
                    client_ip,
                    request_id,
                    e,
                )
                consecutive_db_errors += 1
                # Send error event to client
                await _write_sse_event(
                    response,
                    "error",
                    {
                        "message": "Database error",
                        "retry_after": min(5 * consecutive_db_errors, 30),
                    },
                )
                await asyncio.sleep(SSE_JOB_UPDATE_INTERVAL)
                continue

            # Check for changes
            current_hash = _compute_jobs_hash(jobs_data)
            if current_hash != last_update.get("hash"):
                # Send job update event
                success = await _write_sse_event(
                    response,
                    "jobs_update",
                    {
                        "jobs": jobs_data.get("jobs", []),
                        "total": jobs_data.get("total", 0),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                if not success:
                    break
                last_update["hash"] = current_hash
                heartbeat_counter = 0
            else:
                # Send heartbeat periodically to keep connection alive
                heartbeat_counter += SSE_JOB_UPDATE_INTERVAL
                if heartbeat_counter >= SSE_HEARTBEAT_INTERVAL:
                    success = await _write_sse_event(
                        response,
                        "heartbeat",
                        {"timestamp": datetime.now(timezone.utc).isoformat()},
                    )
                    if not success:
                        break
                    heartbeat_counter = 0

            await asyncio.sleep(SSE_JOB_UPDATE_INTERVAL)

    except asyncio.CancelledError:
        logger.debug(
            "SSE jobs connection cancelled client=%s request_id=%s",
            client_ip,
            request_id,
        )
        # Best-effort close event - ignore errors during teardown
        try:
            await _write_sse_event(
                response,
                "close",
                {"reason": "cancelled"},
                timeout=1.0,  # Short timeout for cleanup
            )
        except Exception:  # nosec B110 - intentional pass during cleanup
            pass
        raise  # Re-raise for proper aiohttp cleanup
    finally:
        # Decrement connection count
        sse_connections["count"] = max(0, sse_connections["count"] - 1)
        logger.debug(
            "SSE jobs connection closed client=%s request_id=%s (remaining: %d)",
            client_ip,
            request_id,
            sse_connections["count"],
        )

    return response


async def _get_jobs_for_sse(request: web.Request) -> dict[str, Any]:
    """Fetch jobs data for SSE streaming.

    Uses the same DB access pattern as the jobs API handler.

    Args:
        request: aiohttp Request object.

    Returns:
        Dictionary with jobs list and total count.

    Raises:
        ValueError: If query parameters are invalid.
        Exception: On database errors.
    """
    from vpo.db import JobStatus, JobType, get_jobs_filtered

    # Parse query parameters using existing JobFilterParams class
    try:
        params = JobFilterParams.from_query(dict(request.query))
    except Exception:
        # Default to sensible values on parse error
        params = JobFilterParams(
            status=None,
            job_type=None,
            since=None,
            limit=50,
            offset=0,
        )

    # Validate and convert status parameter
    status_enum = None
    if params.status:
        try:
            status_enum = JobStatus(params.status)
        except ValueError:
            pass  # Ignore invalid status, use None

    # Validate and convert job_type parameter
    job_type_enum = None
    if params.job_type:
        try:
            job_type_enum = JobType(params.job_type)
        except ValueError:
            pass  # Ignore invalid type, use None

    # Parse time filter
    since_timestamp = parse_time_filter(params.since) if params.since else None

    # Get connection pool from app (set by database_required_middleware)
    # For SSE we need to check if pool exists
    connection_pool = request.app.get("connection_pool")
    if connection_pool is None:
        # Return empty result if no database configured
        return {"jobs": [], "total": 0, "has_filters": False}

    def _query_jobs() -> tuple[list, int]:
        """Query jobs from database (runs in thread pool)."""
        with connection_pool.transaction() as conn:
            jobs, total = get_jobs_filtered(
                conn,
                status=status_enum,
                job_type=job_type_enum,
                since=since_timestamp,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )
            return jobs, total

    jobs_data, total = await asyncio.to_thread(_query_jobs)

    # Convert to JobListItem format (same as jobs API)
    job_items = []
    for job in jobs_data:
        duration_seconds = None
        if job.completed_at and job.created_at:
            try:
                created = parse_iso_timestamp(job.created_at)
                completed = parse_iso_timestamp(job.completed_at)
                duration_seconds = int((completed - created).total_seconds())
            except (ValueError, TypeError):
                pass

        job_items.append(
            JobListItem(
                id=job.id,
                job_type=job.job_type.value,
                status=job.status.value,
                file_path=job.file_path,
                progress_percent=job.progress_percent,
                created_at=job.created_at,
                completed_at=job.completed_at,
                duration_seconds=duration_seconds,
            ).to_dict()
        )

    has_filters = bool(params.status or params.job_type or params.since)

    return {
        "jobs": job_items,
        "total": total,
        "has_filters": has_filters,
    }


def _compute_jobs_hash(jobs_data: dict[str, Any]) -> str:
    """Compute a hash to detect changes in jobs data.

    Uses SHA256 for stable, collision-resistant hashing.

    Args:
        jobs_data: Jobs data dictionary.

    Returns:
        Hash string for change detection.
    """
    jobs = jobs_data.get("jobs", [])
    # Sort parts for stability
    parts = sorted(
        f"{job.get('id')}:{job.get('status')}:{job.get('progress_percent')}"
        for job in jobs
    )
    content = "|".join(parts)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_events_routes() -> list[tuple[str, str, object]]:
    """Return SSE event route definitions as (method, path_suffix, handler) tuples."""
    return [
        ("GET", "/events/jobs", sse_jobs_handler),
    ]
