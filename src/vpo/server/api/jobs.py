"""API handlers for jobs endpoints.

Endpoints:
    GET /api/jobs - List jobs with filtering
    GET /api/jobs/{job_id} - Get job detail
    GET /api/jobs/{job_id}/logs - Get job logs
    GET /api/jobs/{job_id}/errors - Get scan errors for job
"""

from __future__ import annotations

import asyncio

from aiohttp import web

from vpo.core.datetime_utils import (
    calculate_duration_seconds,
    parse_time_filter,
)
from vpo.core.validation import is_valid_uuid
from vpo.db.views import get_scan_errors_for_job
from vpo.server.api.errors import (
    INVALID_ID_FORMAT,
    INVALID_PARAMETER,
    NOT_FOUND,
    api_error,
)
from vpo.server.middleware import JOBS_ALLOWED_PARAMS, validate_query_params
from vpo.server.ui.models import (
    JobFilterParams,
    JobListItem,
    JobListResponse,
    JobLogsResponse,
    ScanErrorItem,
    ScanErrorsResponse,
    build_job_detail_item,
)
from vpo.server.ui.routes import (
    database_required_middleware,
    shutdown_check_middleware,
)


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(JOBS_ALLOWED_PARAMS)
async def api_jobs_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs - JSON API for jobs listing.

    Query parameters:
        status: Filter by job status (queued, running, completed, failed, cancelled)
        type: Filter by job type (scan, apply, transcode, move)
        since: Time filter (24h, 7d)
        limit: Page size (1-100, default 50)
        offset: Pagination offset (default 0)

    Returns:
        JSON response with JobListResponse payload.
    """
    from vpo.db import JobStatus, JobType

    # Parse query parameters
    params = JobFilterParams.from_query(dict(request.query))

    # Validate status parameter
    status_enum = None
    if params.status:
        try:
            status_enum = JobStatus(params.status)
        except ValueError:
            return api_error(
                f"Invalid status value: '{params.status}'",
                code=INVALID_PARAMETER,
            )

    # Validate job_type parameter
    job_type_enum = None
    if params.job_type:
        try:
            job_type_enum = JobType(params.job_type)
        except ValueError:
            return api_error(
                f"Invalid type value: '{params.job_type}'",
                code=INVALID_PARAMETER,
            )

    # Parse time filter (returns None for invalid values)
    since_timestamp = parse_time_filter(params.since)
    if params.since and since_timestamp is None:
        return api_error(
            f"Invalid since value: '{params.since}'",
            code=INVALID_PARAMETER,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query jobs from database using thread-safe connection access
    def _query_jobs() -> tuple[list, int]:
        from vpo.db import get_jobs_filtered

        # Use transaction context manager to hold lock during entire operation
        with connection_pool.transaction() as conn:
            # Use SQL-level pagination for efficiency
            jobs, total = get_jobs_filtered(
                conn,
                status=status_enum,
                job_type=job_type_enum,
                since=since_timestamp,
                search=params.search,
                sort_by=params.sort_by,
                sort_order=params.sort_order,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )
            return jobs, total

    jobs_data, total = await asyncio.to_thread(_query_jobs)

    # Convert to JobListItem
    job_items = []
    for job in jobs_data:
        # Calculate duration if completed
        duration_seconds = None
        if job.completed_at and job.created_at:
            duration_seconds = calculate_duration_seconds(
                job.created_at, job.completed_at
            )

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
            )
        )

    # Determine if any filters are active
    has_filters = bool(
        params.status or params.job_type or params.since or params.search
    )

    response = JobListResponse(
        jobs=job_items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=has_filters,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_job_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs/{job_id} - JSON API for job detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with job detail or error.
    """
    from vpo.jobs.logs import log_file_exists

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not is_valid_uuid(job_id):
        return api_error("Invalid job ID format", code=INVALID_ID_FORMAT)

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query job from database
    def _query_job():
        from vpo.db import get_job

        with connection_pool.transaction() as conn:
            return get_job(conn, job_id)

    job = await asyncio.to_thread(_query_job)

    if job is None:
        return api_error("Job not found", code=NOT_FOUND, status=404)

    # Check if log file exists
    has_logs = log_file_exists(job_id)

    # Convert to detail item
    detail_item = build_job_detail_item(job, has_logs)

    return web.json_response(detail_item.to_dict())


@shutdown_check_middleware
async def api_job_logs_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs/{job_id}/logs - JSON API for job logs.

    Query parameters:
        lines: Number of lines to return (default 500, max 1000)
        offset: Line offset from start (default 0)

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with JobLogsResponse payload.

    Note:
        Authentication is applied globally via auth middleware when
        `auth_token` is configured. CSRF protection would be needed if
        state-changing operations (cancel/retry) are added.
    """
    from vpo.jobs.logs import DEFAULT_LOG_LINES, read_log_tail

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not is_valid_uuid(job_id):
        return api_error("Invalid job ID format", code=INVALID_ID_FORMAT)

    # Parse query parameters
    try:
        lines = int(request.query.get("lines", DEFAULT_LOG_LINES))
        lines = max(1, min(1000, lines))  # Clamp to 1-1000
    except (ValueError, TypeError):
        lines = DEFAULT_LOG_LINES

    try:
        offset = int(request.query.get("offset", 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

    # Read logs
    log_lines, total_lines, has_more = read_log_tail(job_id, lines=lines, offset=offset)

    response = JobLogsResponse(
        job_id=job_id,
        lines=log_lines,
        total_lines=total_lines,
        offset=offset,
        has_more=has_more,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_job_errors_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs/{job_id}/errors - JSON API for scan errors.

    Returns files that failed during a scan job. Only applicable for
    scan jobs - returns empty list for other job types.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with ScanErrorsResponse payload.
    """
    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not is_valid_uuid(job_id):
        return api_error("Invalid job ID format", code=INVALID_ID_FORMAT)

    # Get connection pool from middleware
    pool = request["connection_pool"]

    def _query_scan_errors() -> list[ScanErrorItem]:
        """Query files with scan errors (runs in thread pool)."""
        with pool.transaction() as conn:
            result = get_scan_errors_for_job(conn, job_id)
            if result is None:
                return []
            return [
                ScanErrorItem(path=e.path, filename=e.filename, error=e.error)
                for e in result
            ]

    errors = await asyncio.to_thread(_query_scan_errors)

    response = ScanErrorsResponse(
        job_id=job_id,
        errors=errors,
        total_errors=len(errors),
    )

    return web.json_response(response.to_dict())


def setup_job_routes(app: web.Application) -> None:
    """Register job API routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    app.router.add_get("/api/jobs", api_jobs_handler)
    app.router.add_get("/api/jobs/{job_id}", api_job_detail_handler)
    app.router.add_get("/api/jobs/{job_id}/logs", api_job_logs_handler)
    app.router.add_get("/api/jobs/{job_id}/errors", api_job_errors_handler)
