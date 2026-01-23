"""Server-Sent Events (SSE) API handlers.

Provides real-time updates to the web UI via SSE streams.
Falls back to polling automatically if SSE is not supported.

Endpoints:
    GET /api/events/jobs - SSE stream for job status changes
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from aiohttp import web

from vpo.server.ui.routes import shutdown_check_middleware

logger = logging.getLogger(__name__)

# SSE configuration
SSE_HEARTBEAT_INTERVAL = 15  # seconds
SSE_JOB_UPDATE_INTERVAL = 2  # seconds


async def _write_sse_event(
    response: web.StreamResponse,
    event_type: str,
    data: dict[str, Any],
) -> bool:
    """Write an SSE event to the response stream.

    Args:
        response: The streaming response object.
        event_type: Event type name (e.g., 'job_update', 'heartbeat').
        data: Event data to JSON-serialize.

    Returns:
        True if write succeeded, False if connection was closed.
    """
    try:
        lines = [
            f"event: {event_type}\n",
            f"data: {json.dumps(data)}\n",
            "\n",  # Empty line to signal end of event
        ]
        for line in lines:
            await response.write(line.encode("utf-8"))
        return True
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        logger.debug("SSE client disconnected")
        return False
    except Exception as e:
        logger.error("SSE write error: %s", e)
        return False


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

    logger.debug("SSE jobs connection established")

    # Track last update time for change detection
    last_update: dict[str, Any] = {}
    heartbeat_counter = 0

    try:
        while True:
            # Check if server is shutting down
            if request.app.get("_shutdown_event", asyncio.Event()).is_set():
                logger.debug("SSE closing due to shutdown")
                break

            # Fetch current jobs
            try:
                jobs_data = await _get_jobs_for_sse(request)
            except Exception as e:
                logger.error("Error fetching jobs for SSE: %s", e)
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
        logger.debug("SSE jobs connection cancelled")
    finally:
        logger.debug("SSE jobs connection closed")

    return response


async def _get_jobs_for_sse(request: web.Request) -> dict[str, Any]:
    """Fetch jobs data for SSE streaming.

    Args:
        request: aiohttp Request object.

    Returns:
        Dictionary with jobs list and total count.
    """
    from vpo.server.api.jobs import (
        _get_job_queue,
        _get_jobs_from_db,
    )

    # Get filters from query params (same as polling)
    status_filter = request.query.get("status")
    type_filter = request.query.get("type")
    since = request.query.get("since")
    limit = int(request.query.get("limit", "50"))
    offset = int(request.query.get("offset", "0"))

    # Get jobs from queue and database
    db_path = request.app.get("db_path")
    queue_jobs = await _get_job_queue(request.app)

    return await asyncio.to_thread(
        _get_jobs_from_db,
        db_path,
        queue_jobs,
        status_filter=status_filter,
        type_filter=type_filter,
        since=since,
        limit=limit,
        offset=offset,
    )


def _compute_jobs_hash(jobs_data: dict[str, Any]) -> str:
    """Compute a hash to detect changes in jobs data.

    Uses job IDs, statuses, and progress to detect meaningful changes.

    Args:
        jobs_data: Jobs data dictionary.

    Returns:
        Hash string for change detection.
    """
    jobs = jobs_data.get("jobs", [])
    parts = []
    for job in jobs:
        parts.append(
            f"{job.get('id')}:{job.get('status')}:{job.get('progress_percent')}"
        )
    return "|".join(parts)


def setup_events_routes(app: web.Application) -> None:
    """Register SSE event routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    app.router.add_get("/api/events/jobs", sse_jobs_handler)
