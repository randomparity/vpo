"""UI route handlers for Web UI Shell.

This module provides server-rendered HTML routes for the VPO web interface.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import aiohttp_jinja2
import jinja2
from aiohttp import web

from video_policy_orchestrator import __version__
from video_policy_orchestrator.server.ui.models import (
    DEFAULT_SECTION,
    NAVIGATION_ITEMS,
    AboutInfo,
    JobDetailContext,
    JobDetailItem,
    JobFilterParams,
    JobListContext,
    JobListItem,
    JobListResponse,
    JobLogsResponse,
    NavigationState,
    ScanErrorItem,
    ScanErrorsResponse,
    TemplateContext,
    generate_summary_text,
)

logger = logging.getLogger(__name__)

# HTTP security headers for HTML responses
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# Template directory path
TEMPLATES_DIR = Path(__file__).parent / "templates"


def _create_navigation_state(active_id: str | None) -> NavigationState:
    """Create navigation state with the specified active section.

    Args:
        active_id: ID of the active section, or None for 404 pages.

    Returns:
        NavigationState with all items and active section set.
    """
    return NavigationState(items=list(NAVIGATION_ITEMS), active_id=active_id)


def _create_template_context(
    active_id: str | None,
    section_title: str,
    section_content: str | None = None,
    error_message: str | None = None,
) -> dict:
    """Create template context dictionary.

    Args:
        active_id: ID of the active navigation item.
        section_title: Title for the page/section.
        section_content: Optional HTML content for the section body.
        error_message: Optional error message for error pages.

    Returns:
        Dictionary suitable for Jinja2 template rendering.
    """
    context = TemplateContext(
        nav=_create_navigation_state(active_id),
        section_title=section_title,
        section_content=section_content,
        error_message=error_message,
    )
    return context.to_dict()


async def root_redirect(request: web.Request) -> web.Response:
    """Handle GET / - redirect to default section."""
    raise web.HTTPFound(location=f"/{DEFAULT_SECTION}")


async def jobs_handler(request: web.Request) -> dict:
    """Handle GET /jobs - Jobs section page."""
    context = _create_template_context(
        active_id="jobs",
        section_title="Jobs",
    )
    # Add jobs filter options for template
    context["jobs_context"] = JobListContext.default()
    return context


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
    from datetime import datetime, timedelta, timezone

    from video_policy_orchestrator.db.connection import DaemonConnectionPool
    from video_policy_orchestrator.db.models import JobStatus, JobType

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

    # Parse query parameters
    params = JobFilterParams.from_query(dict(request.query))

    # Validate status parameter
    status_enum = None
    if params.status:
        try:
            status_enum = JobStatus(params.status)
        except ValueError:
            return web.json_response(
                {"error": f"Invalid status value: '{params.status}'"},
                status=400,
            )

    # Validate job_type parameter
    job_type_enum = None
    if params.job_type:
        try:
            job_type_enum = JobType(params.job_type)
        except ValueError:
            return web.json_response(
                {"error": f"Invalid type value: '{params.job_type}'"},
                status=400,
            )

    # Calculate 'since' timestamp
    since_timestamp = None
    if params.since:
        if params.since == "24h":
            since_timestamp = (
                datetime.now(timezone.utc) - timedelta(hours=24)
            ).isoformat()
        elif params.since == "7d":
            since_timestamp = (
                datetime.now(timezone.utc) - timedelta(days=7)
            ).isoformat()
        elif params.since:
            return web.json_response(
                {"error": f"Invalid since value: '{params.since}'"},
                status=400,
            )

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        return web.json_response(
            {"error": "Database not available"},
            status=503,
        )

    # Query jobs from database using thread-safe connection access
    def _query_jobs() -> tuple[list, int]:
        from video_policy_orchestrator.db.models import get_jobs_filtered

        # Use transaction context manager to hold lock during entire operation
        with connection_pool.transaction() as conn:
            # Use SQL-level pagination for efficiency
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

    import asyncio

    jobs_data, total = await asyncio.to_thread(_query_jobs)

    # Helper to parse ISO-8601 timestamps (handles both Z and +00:00 suffixes)
    def _parse_iso_timestamp(timestamp: str) -> datetime:
        # Normalize Z suffix to +00:00 for fromisoformat compatibility (Python 3.10)
        # This is safe even if timestamp already has +00:00 (Z won't be present)
        normalized = timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    # Convert to JobListItem
    job_items = []
    for job in jobs_data:
        # Calculate duration if completed
        duration_seconds = None
        if job.completed_at and job.created_at:
            try:
                created = _parse_iso_timestamp(job.created_at)
                completed = _parse_iso_timestamp(job.completed_at)
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
            )
        )

    # Determine if any filters are active
    has_filters = bool(params.status or params.job_type or params.since)

    response = JobListResponse(
        jobs=job_items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=has_filters,
    )

    return web.json_response(response.to_dict())


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID v4 format.

    Args:
        value: String to validate.

    Returns:
        True if valid UUID format, False otherwise.
    """
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    return bool(uuid_pattern.match(value))


def _parse_iso_timestamp(timestamp: str) -> datetime:
    """Parse ISO-8601 timestamp, handling both Z and +00:00 suffixes.

    Args:
        timestamp: ISO-8601 timestamp string.

    Returns:
        Parsed datetime object.
    """
    normalized = timestamp.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _job_to_detail_item(job, has_logs: bool) -> JobDetailItem:
    """Convert a Job database record to a JobDetailItem.

    Args:
        job: Job database record.
        has_logs: Whether log file exists for this job.

    Returns:
        JobDetailItem for API/template use.
    """
    import json

    # Calculate duration if completed
    duration_seconds = None
    if job.completed_at and job.created_at:
        try:
            created = _parse_iso_timestamp(job.created_at)
            completed = _parse_iso_timestamp(job.completed_at)
            duration_seconds = int((completed - created).total_seconds())
        except (ValueError, TypeError):
            pass

    # Parse summary_json if present
    summary_raw = None
    if job.summary_json:
        try:
            summary_raw = json.loads(job.summary_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # Generate human-readable summary from summary_raw
    summary_text = generate_summary_text(job.job_type.value, summary_raw)

    return JobDetailItem(
        id=job.id,
        id_short=job.id[:8],
        job_type=job.job_type.value,
        status=job.status.value,
        priority=job.priority,
        file_path=job.file_path,
        policy_name=job.policy_name,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=duration_seconds,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        output_path=job.output_path,
        summary=summary_text,
        summary_raw=summary_raw,
        has_logs=has_logs,
    )


async def api_job_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs/{job_id} - JSON API for job detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with job detail or error.
    """
    import asyncio

    from video_policy_orchestrator.db.connection import DaemonConnectionPool
    from video_policy_orchestrator.jobs.logs import log_file_exists

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not _is_valid_uuid(job_id):
        return web.json_response(
            {"error": "Invalid job ID format"},
            status=400,
        )

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        return web.json_response(
            {"error": "Database not available"},
            status=503,
        )

    # Query job from database
    def _query_job():
        from video_policy_orchestrator.db.models import get_job

        with connection_pool.transaction() as conn:
            return get_job(conn, job_id)

    job = await asyncio.to_thread(_query_job)

    if job is None:
        return web.json_response(
            {"error": "Job not found"},
            status=404,
        )

    # Check if log file exists
    has_logs = log_file_exists(job_id)

    # Convert to detail item
    detail_item = _job_to_detail_item(job, has_logs)

    return web.json_response(detail_item.to_dict())


async def job_detail_handler(request: web.Request) -> dict:
    """Handle GET /jobs/{job_id} - Job detail HTML page.

    Args:
        request: aiohttp Request object.

    Returns:
        Template context dict for rendering.

    Raises:
        HTTPNotFound: If job not found.
        HTTPBadRequest: If job ID format is invalid.

    Note:
        TODO: Add authentication when auth system is implemented.
        This endpoint currently exposes job details without access control.
        VPO is designed as a local tool, but authentication should be
        added before exposing the web UI to untrusted networks.
    """
    import asyncio

    from video_policy_orchestrator.db.connection import DaemonConnectionPool
    from video_policy_orchestrator.jobs.logs import log_file_exists

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not _is_valid_uuid(job_id):
        raise web.HTTPBadRequest(reason="Invalid job ID format")

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        raise web.HTTPServiceUnavailable(reason="Database not available")

    # Query job from database
    def _query_job():
        from video_policy_orchestrator.db.models import get_job

        with connection_pool.transaction() as conn:
            return get_job(conn, job_id)

    job = await asyncio.to_thread(_query_job)

    if job is None:
        raise web.HTTPNotFound(reason="Job not found")

    # Check if log file exists
    has_logs = log_file_exists(job_id)

    # Convert to detail item
    detail_item = _job_to_detail_item(job, has_logs)

    # Get referer for back navigation
    referer = request.headers.get("Referer")

    # Create context
    detail_context = JobDetailContext.from_job_and_request(detail_item, referer)

    context = _create_template_context(
        active_id="jobs",
        section_title=f"Job {detail_item.id_short}",
    )
    context["job"] = detail_item
    context["back_url"] = detail_context.back_url

    return context


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
        TODO: Add authentication when auth system is implemented.
        TODO: Add CSRF protection if state-changing operations (cancel/retry)
        are added to this endpoint in the future.
    """
    from video_policy_orchestrator.jobs.logs import DEFAULT_LOG_LINES, read_log_tail

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not _is_valid_uuid(job_id):
        return web.json_response(
            {"error": "Invalid job ID format"},
            status=400,
        )

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


async def api_job_errors_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs/{job_id}/errors - JSON API for scan errors.

    Returns files that failed during a scan job. Only applicable for
    scan jobs - returns empty list for other job types.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with ScanErrorsResponse payload.
    """
    from video_policy_orchestrator.db.connection import DaemonConnectionPool

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not _is_valid_uuid(job_id):
        return web.json_response(
            {"error": "Invalid job ID format"},
            status=400,
        )

    # Get connection pool
    pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if pool is None:
        return web.json_response(
            {"error": "Database not available"},
            status=503,
        )

    def _query_scan_errors() -> list[ScanErrorItem]:
        """Query files with scan errors (runs in thread pool)."""
        with pool.read() as conn:
            # First verify this is a scan job
            cursor = conn.execute(
                "SELECT job_type FROM jobs WHERE id = ?",
                (job_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return []
            if row["job_type"] != "scan":
                return []

            # Get files with errors
            # We can't directly link files to jobs, so we get all files with errors
            # In the future, could add a job_id column to files table
            cursor = conn.execute(
                """
                SELECT path, filename, scan_error
                FROM files
                WHERE scan_status = 'error' AND scan_error IS NOT NULL
                ORDER BY filename
                """,
            )
            return [
                ScanErrorItem(
                    path=row["path"],
                    filename=row["filename"],
                    error=row["scan_error"],
                )
                for row in cursor.fetchall()
            ]

    errors = await asyncio.to_thread(_query_scan_errors)

    response = ScanErrorsResponse(
        job_id=job_id,
        errors=errors,
        total_errors=len(errors),
    )

    return web.json_response(response.to_dict())


async def library_handler(request: web.Request) -> dict:
    """Handle GET /library - Library section page."""
    return _create_template_context(
        active_id="library",
        section_title="Library",
        section_content="<p>Library section - coming soon</p>",
    )


async def transcriptions_handler(request: web.Request) -> dict:
    """Handle GET /transcriptions - Transcriptions section page."""
    return _create_template_context(
        active_id="transcriptions",
        section_title="Transcriptions",
        section_content="<p>Transcriptions section - coming soon</p>",
    )


async def policies_handler(request: web.Request) -> dict:
    """Handle GET /policies - Policies section page."""
    return _create_template_context(
        active_id="policies",
        section_title="Policies",
        section_content="<p>Policies section - coming soon</p>",
    )


async def approvals_handler(request: web.Request) -> dict:
    """Handle GET /approvals - Approvals section page."""
    return _create_template_context(
        active_id="approvals",
        section_title="Approvals",
        section_content="<p>Approvals section - coming soon</p>",
    )


# Documentation URL constant
DOCS_URL = "https://github.com/randomparity/vpo/tree/main/docs"


def get_about_info(request: web.Request) -> AboutInfo:
    """Build AboutInfo from request context and environment.

    Args:
        request: aiohttp Request object.

    Returns:
        AboutInfo populated from app context, request, and package metadata.
    """
    # Get version from package
    version = __version__

    # Get git hash from environment (set during build/deployment)
    # Validate format: 7-64 hex characters (short SHA to SHA-256)
    git_hash_raw = os.environ.get("VPO_GIT_HASH")
    git_hash = None
    if git_hash_raw and re.match(r"^[a-fA-F0-9]{7,64}$", git_hash_raw):
        git_hash = git_hash_raw

    # Get profile name from app context (set at daemon startup)
    profile_name = request.app.get("profile_name", "Default")

    # Build API URL from request origin
    api_url = str(request.url.origin())

    return AboutInfo(
        version=version,
        git_hash=git_hash,
        profile_name=profile_name,
        api_url=api_url,
        docs_url=DOCS_URL,
        is_read_only=True,
    )


async def about_handler(request: web.Request) -> dict:
    """Handle GET /about - About section page."""
    about_info = get_about_info(request)

    context = _create_template_context(
        active_id="about",
        section_title="About",
    )
    # Add about info to context for template
    context["about"] = about_info

    return context


async def handle_404(request: web.Request) -> web.Response:
    """Handle 404 errors with a friendly HTML page."""
    context = _create_template_context(
        active_id=None,
        section_title="Page Not Found",
        error_message="The page you requested could not be found.",
    )
    response = aiohttp_jinja2.render_template(
        "errors/404.html",
        request,
        context,
        status=404,
    )
    return response


@web.middleware
async def security_headers_middleware(
    request: web.Request,
    handler: web.RequestHandler,
) -> web.StreamResponse:
    """Add security headers to all HTML responses."""
    response = await handler(request)

    # Only add security headers to HTML responses (not static files or API)
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

    return response


@web.middleware
async def request_logging_middleware(
    request: web.Request,
    handler: web.RequestHandler,
) -> web.StreamResponse:
    """Log request details with timing for UI routes."""
    start_time = time.monotonic()

    try:
        response = await handler(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        # Log UI routes (not static files or health checks)
        path = request.path
        if not path.startswith("/static/") and path != "/health":
            logger.info(
                "UI request: method=%s path=%s status=%d duration_ms=%.1f",
                request.method,
                path,
                response.status,
                duration_ms,
            )

        return response
    except web.HTTPException as exc:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "UI request: method=%s path=%s status=%d duration_ms=%.1f",
            request.method,
            request.path,
            exc.status,
            duration_ms,
        )
        raise


@web.middleware
async def error_middleware(
    request: web.Request,
    handler: web.RequestHandler,
) -> web.StreamResponse:
    """Middleware to handle 404 errors with custom HTML page."""
    try:
        response = await handler(request)
        if response.status == 404:
            return await handle_404(request)
        return response
    except web.HTTPNotFound:
        return await handle_404(request)


def setup_ui_routes(app: web.Application) -> None:
    """Setup UI routes and Jinja2 templating.

    Args:
        app: aiohttp Application to configure.
    """
    # Setup Jinja2 templating
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    )

    # Register routes
    app.router.add_get("/", root_redirect)

    # Section routes with Jinja2 template decorator
    app.router.add_get(
        "/jobs",
        aiohttp_jinja2.template("sections/jobs.html")(jobs_handler),
    )
    # Job detail routes (016-job-detail-view)
    app.router.add_get(
        "/jobs/{job_id}",
        aiohttp_jinja2.template("sections/job_detail.html")(job_detail_handler),
    )
    app.router.add_get("/api/jobs/{job_id}", api_job_detail_handler)
    app.router.add_get("/api/jobs/{job_id}/logs", api_job_logs_handler)
    app.router.add_get("/api/jobs/{job_id}/errors", api_job_errors_handler)
    app.router.add_get(
        "/library",
        aiohttp_jinja2.template("sections/library.html")(library_handler),
    )
    app.router.add_get(
        "/transcriptions",
        aiohttp_jinja2.template("sections/transcriptions.html")(transcriptions_handler),
    )
    app.router.add_get(
        "/policies",
        aiohttp_jinja2.template("sections/policies.html")(policies_handler),
    )
    app.router.add_get(
        "/approvals",
        aiohttp_jinja2.template("sections/approvals.html")(approvals_handler),
    )
    app.router.add_get(
        "/about",
        aiohttp_jinja2.template("sections/about.html")(about_handler),
    )

    # Add middleware (order matters: logging -> security -> error handling)
    app.middlewares.append(request_logging_middleware)
    app.middlewares.append(security_headers_middleware)
    app.middlewares.append(error_middleware)

    logger.debug("UI routes configured with Jinja2 templating")
