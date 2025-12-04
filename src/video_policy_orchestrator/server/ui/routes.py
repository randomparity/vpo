"""UI route handlers for Web UI Shell.

This module provides server-rendered HTML routes for the VPO web interface.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

import aiohttp_jinja2
import jinja2
from aiohttp import web

from video_policy_orchestrator import __version__
from video_policy_orchestrator.core.datetime_utils import (
    parse_iso_timestamp,
    parse_time_filter,
)
from video_policy_orchestrator.core.validation import is_valid_uuid
from video_policy_orchestrator.db.connection import DaemonConnectionPool
from video_policy_orchestrator.db.views import (
    get_policy_stats,
    get_policy_stats_by_name,
    get_recent_stats,
    get_scan_errors_for_job,
    get_stats_detail,
    get_stats_for_file,
    get_stats_summary,
)
from video_policy_orchestrator.server.ui.models import (
    DEFAULT_SECTION,
    NAVIGATION_ITEMS,
    AboutInfo,
    FileDetailContext,
    FileDetailItem,
    FileDetailResponse,
    FileListItem,
    FileListResponse,
    JobDetailContext,
    JobDetailItem,
    JobFilterParams,
    JobListContext,
    JobListItem,
    JobListResponse,
    JobLogsResponse,
    LibraryContext,
    LibraryFilterParams,
    NavigationState,
    PlanActionResponse,
    PlanFilterParams,
    PlanListItem,
    PlanListResponse,
    PlansContext,
    PoliciesContext,
    ScanErrorItem,
    ScanErrorsResponse,
    TemplateContext,
    TranscriptionDetailContext,
    TranscriptionDetailItem,
    TranscriptionDetailResponse,
    TranscriptionFilterParams,
    TranscriptionListItem,
    TranscriptionListResponse,
    format_audio_languages,
    format_detected_languages,
    format_file_size,
    generate_summary_text,
    get_classification_reasoning,
    get_confidence_level,
    get_resolution_label,
    group_tracks_by_type,
    highlight_keywords_in_transcript,
)

# Type alias for handler functions (used in middleware decorators)
Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

logger = logging.getLogger(__name__)

# HTTP security headers for HTML responses
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'self'"
    ),
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
    result = context.to_dict()
    # Add polling configuration for client-side JavaScript
    result.update(_get_polling_config())
    return result


# Default polling configuration values
DEFAULT_POLLING_INTERVAL = 5000  # 5 seconds
DEFAULT_POLLING_LOG_INTERVAL = 15000  # 15 seconds


def _get_polling_config() -> dict:
    """Get polling configuration for templates.

    Returns:
        Dictionary with polling configuration values.
    """
    return {
        "polling_interval": DEFAULT_POLLING_INTERVAL,
        "polling_enabled": "true",
        "polling_log_interval": DEFAULT_POLLING_LOG_INTERVAL,
    }


# NOTE: parse_iso_timestamp moved to video_policy_orchestrator.core.datetime_utils
# Import parse_iso_timestamp at module level for use throughout this file


# ==========================================================================
# Decorator middleware for API handlers
# ==========================================================================


def shutdown_check_middleware(handler: Handler) -> Handler:
    """Decorator middleware that returns 503 if server is shutting down.

    Usage:
        @shutdown_check_middleware
        async def my_api_handler(request: web.Request) -> web.Response:
            ...

    Returns:
        JSON response with 503 status if shutting down, otherwise calls handler.
    """

    async def wrapper(request: web.Request) -> web.StreamResponse:
        lifecycle = request.app.get("lifecycle")
        if lifecycle and lifecycle.is_shutting_down:
            return web.json_response(
                {"error": "Service is shutting down"},
                status=503,
            )
        return await handler(request)

    return wrapper


def database_required_middleware(handler: Handler) -> Handler:
    """Decorator middleware that returns 503 if database is unavailable.

    Stores connection_pool in request for handler use via request["connection_pool"].

    Usage:
        @database_required_middleware
        async def my_api_handler(request: web.Request) -> web.Response:
            pool = request["connection_pool"]
            ...

    Returns:
        JSON response with 503 status if no connection pool, otherwise calls handler.
    """

    async def wrapper(request: web.Request) -> web.StreamResponse:
        pool: DaemonConnectionPool | None = request.app.get("connection_pool")
        if pool is None:
            return web.json_response(
                {"error": "Database not available"},
                status=503,
            )
        # Store in request for handler access
        request["connection_pool"] = pool
        return await handler(request)

    return wrapper


# ==========================================================================
# Route handlers
# ==========================================================================


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


@shutdown_check_middleware
@database_required_middleware
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
    from video_policy_orchestrator.db.models import JobStatus, JobType

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

    # Parse time filter (returns None for invalid values)
    since_timestamp = parse_time_filter(params.since)
    if params.since and since_timestamp is None:
        return web.json_response(
            {"error": f"Invalid since value: '{params.since}'"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

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

    jobs_data, total = await asyncio.to_thread(_query_jobs)

    # Convert to JobListItem
    job_items = []
    for job in jobs_data:
        # Calculate duration if completed
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


# NOTE: is_valid_uuid moved to video_policy_orchestrator.core.validation
# Import is_valid_uuid at module level for use throughout this file


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
            created = parse_iso_timestamp(job.created_at)
            completed = parse_iso_timestamp(job.completed_at)
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


@shutdown_check_middleware
@database_required_middleware
async def api_job_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/jobs/{job_id} - JSON API for job detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with job detail or error.
    """
    from video_policy_orchestrator.jobs.logs import log_file_exists

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not is_valid_uuid(job_id):
        return web.json_response(
            {"error": "Invalid job ID format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

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
    from video_policy_orchestrator.jobs.logs import log_file_exists

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not is_valid_uuid(job_id):
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
        TODO: Add authentication when auth system is implemented.
        TODO: Add CSRF protection if state-changing operations (cancel/retry)
        are added to this endpoint in the future.
    """
    from video_policy_orchestrator.jobs.logs import DEFAULT_LOG_LINES, read_log_tail

    job_id = request.match_info["job_id"]

    # Validate UUID format
    if not is_valid_uuid(job_id):
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
        return web.json_response(
            {"error": "Invalid job ID format"},
            status=400,
        )

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


async def library_handler(request: web.Request) -> dict:
    """Handle GET /library - Library section page.

    Renders the Library page HTML with filter options for client-side JavaScript.
    """
    context = _create_template_context(
        active_id="library",
        section_title="Library",
    )
    # Add library filter options for template
    context["library_context"] = LibraryContext.default()
    return context


@shutdown_check_middleware
@database_required_middleware
async def library_api_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library - JSON API for library files listing.

    Query parameters:
        status: Filter by scan status (ok, error)
        limit: Page size (1-100, default 50)
        offset: Pagination offset (default 0)

    Returns:
        JSON response with FileListResponse payload.
    """
    from video_policy_orchestrator.db.models import get_files_filtered

    # Parse query parameters
    # Handle audio_lang as a list (can appear multiple times in query)
    query_dict = dict(request.query)
    if "audio_lang" in request.query:
        query_dict["audio_lang"] = request.query.getall("audio_lang")
    params = LibraryFilterParams.from_query(query_dict)

    # Log filter request for debugging (019-library-filters-search)
    active_filters = []
    if params.status:
        active_filters.append(f"status={params.status}")
    if params.search:
        active_filters.append(f"search={params.search!r}")
    if params.resolution:
        active_filters.append(f"resolution={params.resolution}")
    if params.audio_lang:
        active_filters.append(f"audio_lang={params.audio_lang}")
    if params.subtitles:
        active_filters.append(f"subtitles={params.subtitles}")
    if active_filters:
        logger.debug("Library API filter request: %s", ", ".join(active_filters))

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query files from database using thread-safe connection access
    def _query_files() -> tuple[list[dict], int]:
        with connection_pool.transaction() as conn:
            result = get_files_filtered(
                conn,
                status=params.status,
                search=params.search,
                resolution=params.resolution,
                audio_lang=params.audio_lang,
                subtitles=params.subtitles,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )
            # Type narrowing: return_total=True always returns tuple
            return result  # type: ignore[return-value]

    files_data, total = await asyncio.to_thread(_query_files)

    # Transform to FileListItem
    files = [
        FileListItem(
            id=f["id"],
            filename=f["filename"],
            path=f["path"],
            title=f["video_title"],
            resolution=get_resolution_label(f["width"], f["height"]),
            audio_languages=format_audio_languages(f["audio_languages"]),
            scanned_at=f["scanned_at"],
            scan_status=f["scan_status"],
            scan_error=f["scan_error"],
        )
        for f in files_data
    ]

    # Determine if any filters are active (019-library-filters-search)
    has_filters = any(
        [
            params.status is not None,
            params.search is not None,
            params.resolution is not None,
            params.audio_lang is not None,
            params.subtitles is not None,
        ]
    )

    response = FileListResponse(
        files=files,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=has_filters,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_library_languages_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library/languages - Get available audio languages.

    Returns list of distinct audio language codes present in the library
    for populating the language filter dropdown (019-library-filters-search).
    """
    from video_policy_orchestrator.db.models import get_distinct_audio_languages

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query distinct languages from database
    def _query_languages() -> list[dict]:
        with connection_pool.transaction() as conn:
            return get_distinct_audio_languages(conn)

    languages = await asyncio.to_thread(_query_languages)

    return web.json_response({"languages": languages})


# ==========================================================================
# File Detail View Handlers (020-file-detail-view)
# ==========================================================================


def _build_file_detail_item(file_record, tracks, transcriptions) -> FileDetailItem:
    """Build FileDetailItem from database records.

    Args:
        file_record: FileRecord from database.
        tracks: List of TrackRecord from database.
        transcriptions: Dict mapping track_id to TranscriptionResultRecord.

    Returns:
        FileDetailItem ready for API/template use.
    """
    import json

    # Group tracks by type
    video_tracks, audio_tracks, subtitle_tracks, other_tracks = group_tracks_by_type(
        tracks, transcriptions
    )

    # Parse plugin_metadata JSON (236-generic-plugin-data-browser)
    plugin_metadata = None
    if file_record.plugin_metadata:
        try:
            plugin_metadata = json.loads(file_record.plugin_metadata)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failed to parse plugin_metadata for file %d: %s",
                file_record.id,
                e,
            )

    return FileDetailItem(
        id=file_record.id,
        path=file_record.path,
        filename=file_record.filename,
        directory=file_record.directory,
        extension=file_record.extension,
        container_format=file_record.container_format,
        size_bytes=file_record.size_bytes,
        size_human=format_file_size(file_record.size_bytes),
        modified_at=file_record.modified_at,
        scanned_at=file_record.scanned_at,
        scan_status=file_record.scan_status,
        scan_error=file_record.scan_error,
        scan_job_id=file_record.job_id,
        video_tracks=video_tracks,
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        other_tracks=other_tracks,
        plugin_metadata=plugin_metadata,
    )


async def file_detail_handler(request: web.Request) -> dict:
    """Handle GET /library/{file_id} - File detail HTML page.

    Args:
        request: aiohttp Request object.

    Returns:
        Template context dict for rendering.

    Raises:
        HTTPNotFound: If file not found.
        HTTPBadRequest: If file ID format is invalid.
        HTTPServiceUnavailable: If database not available.
    """
    from video_policy_orchestrator.db.models import (
        get_file_by_id,
        get_tracks_for_file,
        get_transcriptions_for_tracks,
    )

    file_id_str = request.match_info["file_id"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid file ID format")

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        raise web.HTTPServiceUnavailable(reason="Database not available")

    # Query file from database
    def _query_file():
        with connection_pool.transaction() as conn:
            file_record = get_file_by_id(conn, file_id)
            if file_record is None:
                return None, [], {}
            tracks = get_tracks_for_file(conn, file_record.id)
            # Get transcriptions for audio tracks
            audio_track_ids = [t.id for t in tracks if t.track_type == "audio"]
            transcriptions = get_transcriptions_for_tracks(conn, audio_track_ids)
            return file_record, tracks, transcriptions

    file_record, tracks, transcriptions = await asyncio.to_thread(_query_file)

    if file_record is None:
        raise web.HTTPNotFound(reason="File not found")

    # Build FileDetailItem
    detail_item = _build_file_detail_item(file_record, tracks, transcriptions)

    # Get referer for back navigation
    referer = request.headers.get("Referer")

    # Create context
    detail_context = FileDetailContext.from_file_and_request(detail_item, referer)

    context = _create_template_context(
        active_id="library",
        section_title=detail_item.filename,
    )
    context["file"] = detail_item
    context["back_url"] = detail_context.back_url

    return context


@shutdown_check_middleware
@database_required_middleware
async def api_file_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library/{file_id} - JSON API for file detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with FileDetailResponse payload or error.
    """
    from video_policy_orchestrator.db.models import (
        get_file_by_id,
        get_tracks_for_file,
        get_transcriptions_for_tracks,
    )

    file_id_str = request.match_info["file_id"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        return web.json_response(
            {"error": "Invalid file ID format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query file from database
    def _query_file():
        with connection_pool.transaction() as conn:
            file_record = get_file_by_id(conn, file_id)
            if file_record is None:
                return None, [], {}
            tracks = get_tracks_for_file(conn, file_record.id)
            # Get transcriptions for audio tracks
            audio_track_ids = [t.id for t in tracks if t.track_type == "audio"]
            transcriptions = get_transcriptions_for_tracks(conn, audio_track_ids)
            return file_record, tracks, transcriptions

    file_record, tracks, transcriptions = await asyncio.to_thread(_query_file)

    if file_record is None:
        return web.json_response(
            {"error": "File not found"},
            status=404,
        )

    # Build FileDetailItem
    detail_item = _build_file_detail_item(file_record, tracks, transcriptions)

    # Build response
    response = FileDetailResponse(file=detail_item)

    return web.json_response(response.to_dict())


async def transcriptions_handler(request: web.Request) -> dict:
    """Handle GET /transcriptions - Transcriptions section page."""
    return _create_template_context(
        active_id="transcriptions",
        section_title="Transcriptions",
    )


@shutdown_check_middleware
@database_required_middleware
async def api_transcriptions_handler(request: web.Request) -> web.Response:
    """Handle GET /api/transcriptions - JSON API for transcriptions listing.

    Query parameters:
        show_all: If true, show all files. Default: false (transcribed only).
        limit: Page size (1-100, default 50).
        offset: Pagination offset (default 0).

    Returns:
        JSON response with TranscriptionListResponse payload.
    """
    from video_policy_orchestrator.db.models import get_files_with_transcriptions

    # Parse query parameters
    params = TranscriptionFilterParams.from_query(dict(request.query))

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query files from database using thread-safe connection access
    def _query_files() -> tuple[list[dict], int]:
        with connection_pool.transaction() as conn:
            result = get_files_with_transcriptions(
                conn,
                show_all=params.show_all,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )
            # Type narrowing: return_total=True always returns tuple
            return result  # type: ignore[return-value]

    files_data, total = await asyncio.to_thread(_query_files)

    # Transform to TranscriptionListItem
    files = [
        TranscriptionListItem(
            id=f["id"],
            filename=f["filename"],
            path=f["path"],
            has_transcription=f["transcription_count"] > 0,
            detected_languages=format_detected_languages(f["detected_languages"]),
            confidence_level=get_confidence_level(f["avg_confidence"]),
            confidence_avg=f["avg_confidence"],
            transcription_count=f["transcription_count"],
            scan_status=f["scan_status"],
        )
        for f in files_data
    ]

    response = TranscriptionListResponse(
        files=files,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=params.show_all,
    )

    return web.json_response(response.to_dict())


# ==========================================================================
# Transcription Detail View Handlers (022-transcription-detail)
# ==========================================================================


def _build_transcription_detail_item(data: dict) -> TranscriptionDetailItem:
    """Build TranscriptionDetailItem from database query result.

    Args:
        data: Dictionary from get_transcription_detail() query.

    Returns:
        TranscriptionDetailItem ready for API/template use.
    """
    track_type = data["track_type"]
    transcript = data["transcript_sample"]

    # Get classification reasoning
    classification_source, matched_keywords = get_classification_reasoning(
        data["title"],
        transcript,
        track_type,
    )

    # Generate highlighted HTML
    transcript_html, transcript_truncated = highlight_keywords_in_transcript(
        transcript,
        track_type,
    )

    return TranscriptionDetailItem(
        id=data["id"],
        track_id=data["track_id"],
        detected_language=data["detected_language"],
        confidence_score=data["confidence_score"],
        confidence_level=get_confidence_level(data["confidence_score"]),
        track_classification=track_type,
        transcript_sample=transcript,
        transcript_html=transcript_html,
        transcript_truncated=transcript_truncated,
        plugin_name=data["plugin_name"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        track_index=data["track_index"],
        track_codec=data["codec"],
        original_language=data["original_language"],
        track_title=data["title"],
        channels=data["channels"],
        channel_layout=data["channel_layout"],
        is_default=bool(data["is_default"]),
        is_forced=bool(data["is_forced"]),
        is_commentary=track_type == "commentary",
        classification_source=classification_source,
        matched_keywords=matched_keywords,
        file_id=data["file_id"],
        filename=data["filename"],
        file_path=data["path"],
    )


async def transcription_detail_handler(request: web.Request) -> dict:
    """Handle GET /transcriptions/{id} - Transcription detail HTML page.

    Args:
        request: aiohttp Request object.

    Returns:
        Template context dict for rendering.

    Raises:
        HTTPNotFound: If transcription not found.
        HTTPBadRequest: If ID format is invalid.
        HTTPServiceUnavailable: If database not available.
    """
    from video_policy_orchestrator.db.models import get_transcription_detail

    transcription_id_str = request.match_info["transcription_id"]

    # Validate ID format (integer)
    try:
        transcription_id = int(transcription_id_str)
        if transcription_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid transcription ID format")

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        raise web.HTTPServiceUnavailable(reason="Database not available")

    # Query transcription from database
    def _query_transcription():
        with connection_pool.transaction() as conn:
            return get_transcription_detail(conn, transcription_id)

    data = await asyncio.to_thread(_query_transcription)

    if data is None:
        raise web.HTTPNotFound(reason="Transcription not found")

    # Build detail item
    detail_item = _build_transcription_detail_item(data)

    # Get referer for back navigation
    referer = request.headers.get("Referer")

    # Create context
    detail_context = TranscriptionDetailContext.from_transcription_and_request(
        detail_item, referer
    )

    context = _create_template_context(
        active_id="transcriptions",
        section_title=f"Track #{detail_item.track_index} - {detail_item.filename}",
    )
    context["transcription"] = detail_item
    context["back_url"] = detail_context.back_url
    context["back_label"] = detail_context.back_label

    return context


@shutdown_check_middleware
@database_required_middleware
async def api_transcription_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/transcriptions/{id} - JSON API for transcription detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with TranscriptionDetailResponse payload or error.
    """
    from video_policy_orchestrator.db.models import get_transcription_detail

    transcription_id_str = request.match_info["transcription_id"]

    # Validate ID format (integer)
    try:
        transcription_id = int(transcription_id_str)
        if transcription_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        return web.json_response(
            {"error": "Invalid transcription ID format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query transcription from database
    def _query_transcription():
        with connection_pool.transaction() as conn:
            return get_transcription_detail(conn, transcription_id)

    data = await asyncio.to_thread(_query_transcription)

    if data is None:
        return web.json_response(
            {"error": "Transcription not found"},
            status=404,
        )

    # Build detail item
    detail_item = _build_transcription_detail_item(data)

    # Build response
    response = TranscriptionDetailResponse(transcription=detail_item)

    return web.json_response(response.to_dict())


async def policies_handler(request: web.Request) -> dict:
    """Handle GET /policies - Policies section page.

    Renders the Policies list page with all policy files discovered
    from ~/.vpo/policies/ directory.
    """
    from video_policy_orchestrator.policy.services import list_policies

    response = await asyncio.to_thread(list_policies)

    context = _create_template_context(
        active_id="policies",
        section_title="Policies",
    )
    context["policies_context"] = PoliciesContext.default()
    context["policies_response"] = response

    return context


@shutdown_check_middleware
async def policies_api_handler(request: web.Request) -> web.Response:
    """Handle GET /api/policies - JSON API for policy files listing.

    Returns:
        JSON response with PolicyListResponse payload.
    """
    from video_policy_orchestrator.policy.services import list_policies

    response = await asyncio.to_thread(list_policies)

    return web.json_response(response.to_dict())


async def policy_editor_handler(request: web.Request) -> dict:
    """Handle GET /policies/{name}/edit - Policy editor HTML page.

    Args:
        request: aiohttp Request object.

    Returns:
        Template context dict for rendering.

    Raises:
        HTTPNotFound: If policy not found.
        HTTPBadRequest: If policy name format is invalid.
    """
    from video_policy_orchestrator.policy.discovery import DEFAULT_POLICIES_DIR
    from video_policy_orchestrator.policy.editor import PolicyRoundTripEditor
    from video_policy_orchestrator.policy.loader import PolicyValidationError

    policy_name = request.match_info["name"]

    # Validate policy name (alphanumeric, dash, underscore only)
    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        raise web.HTTPBadRequest(reason="Invalid policy name format")

    # Get policy directory (allow test override)
    policies_dir = request.app.get("policy_dir", DEFAULT_POLICIES_DIR)

    # Construct policy file path
    policy_path = policies_dir / f"{policy_name}.yaml"

    # Check for .yml extension if .yaml not found
    if not policy_path.exists():
        policy_path = policies_dir / f"{policy_name}.yml"

    if not policy_path.exists():
        raise web.HTTPNotFound(reason="Policy not found")

    # Verify resolved path is within allowed directory (prevent path traversal)
    try:
        resolved_path = policy_path.resolve()
        resolved_dir = policies_dir.resolve()
        resolved_path.relative_to(resolved_dir)
    except (ValueError, OSError):
        raise web.HTTPBadRequest(reason="Invalid policy path")

    # Load policy with round-trip editor
    def _load_policy():
        try:
            editor = PolicyRoundTripEditor(policy_path, allowed_dir=policies_dir)
            data = editor.load()
            return data, None
        except PolicyValidationError as e:
            return None, str(e)
        except Exception as e:
            logger.error(f"Failed to load policy {policy_name}: {e}")
            return None, f"Failed to load policy: {e}"

    policy_data, parse_error = await asyncio.to_thread(_load_policy)

    if policy_data is None and parse_error:
        # Show editor with error message
        policy_data = {}

    # Get file metadata
    stat = await asyncio.to_thread(policy_path.stat)
    last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    # Build context
    from video_policy_orchestrator.server.ui.models import PolicyEditorContext

    # Provide sensible defaults for policies that don't have track ordering configured
    default_track_order = [
        "video",
        "audio_main",
        "audio_alternate",
        "audio_commentary",
        "subtitle_main",
        "subtitle_forced",
        "subtitle_commentary",
        "attachment",
    ]
    default_audio_langs = ["eng"]
    default_subtitle_langs = ["eng"]
    default_flags = {
        "set_first_video_default": True,
        "set_preferred_audio_default": True,
        "set_preferred_subtitle_default": False,
        "clear_other_defaults": True,
    }

    # Get unknown fields for warning banner (T076)
    from video_policy_orchestrator.policy.editor import KNOWN_POLICY_FIELDS

    unknown_fields = [k for k in policy_data.keys() if k not in KNOWN_POLICY_FIELDS]

    editor_context = PolicyEditorContext(
        name=policy_name,
        filename=policy_path.name,
        file_path=str(policy_path),
        last_modified=last_modified,
        schema_version=policy_data.get("schema_version", 2),
        track_order=policy_data.get("track_order", default_track_order),
        audio_language_preference=policy_data.get(
            "audio_language_preference", default_audio_langs
        ),
        subtitle_language_preference=policy_data.get(
            "subtitle_language_preference", default_subtitle_langs
        ),
        commentary_patterns=policy_data.get("commentary_patterns", []),
        default_flags=policy_data.get("default_flags", default_flags),
        transcode=policy_data.get("transcode"),
        transcription=policy_data.get("transcription"),
        # V3+ fields (036-v9-policy-editor)
        audio_filter=policy_data.get("audio_filter"),
        subtitle_filter=policy_data.get("subtitle_filter"),
        attachment_filter=policy_data.get("attachment_filter"),
        container=policy_data.get("container"),
        # V4+ fields
        conditional=policy_data.get("conditional"),
        # V5+ fields
        audio_synthesis=policy_data.get("audio_synthesis"),
        # V9+ fields
        workflow=policy_data.get("workflow"),
        # V11+ fields (user-defined phases)
        phases=policy_data.get("phases"),
        config=policy_data.get("config"),
        # Meta
        unknown_fields=unknown_fields if unknown_fields else None,
        parse_error=parse_error,
    )

    context = _create_template_context(
        active_id="policies",
        section_title=f"Edit Policy: {policy_name}",
    )
    context["policy"] = editor_context
    # CSRF token is injected by csrf_middleware into request context
    context["csrf_token"] = request.get("csrf_token", "")

    return context


@shutdown_check_middleware
async def api_policy_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/policies/{name} - JSON API for policy detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with policy data or error.
    """
    from video_policy_orchestrator.policy.discovery import DEFAULT_POLICIES_DIR
    from video_policy_orchestrator.policy.editor import PolicyRoundTripEditor
    from video_policy_orchestrator.policy.loader import PolicyValidationError

    policy_name = request.match_info["name"]

    # Validate policy name
    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        return web.json_response(
            {"error": "Invalid policy name format"},
            status=400,
        )

    # Get policy directory (allow test override)
    policies_dir = request.app.get("policy_dir", DEFAULT_POLICIES_DIR)

    # Construct policy file path
    policy_path = policies_dir / f"{policy_name}.yaml"
    if not policy_path.exists():
        policy_path = policies_dir / f"{policy_name}.yml"

    if not policy_path.exists():
        return web.json_response(
            {"error": "Policy not found"},
            status=404,
        )

    # Verify resolved path is within allowed directory (prevent path traversal)
    try:
        resolved_path = policy_path.resolve()
        resolved_dir = policies_dir.resolve()
        resolved_path.relative_to(resolved_dir)
    except (ValueError, OSError):
        return web.json_response(
            {"error": "Invalid policy path"},
            status=400,
        )

    # Load policy
    def _load_policy():
        try:
            editor = PolicyRoundTripEditor(policy_path, allowed_dir=policies_dir)
            data = editor.load()
            stat = policy_path.stat()
            last_modified = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()
            return data, last_modified, None
        except PolicyValidationError as e:
            return None, None, str(e)
        except Exception as e:
            logger.error(f"Failed to load policy {policy_name}: {e}")
            return None, None, f"Failed to load policy: {e}"

    policy_data, last_modified, parse_error = await asyncio.to_thread(_load_policy)

    if policy_data is None and parse_error:
        return web.json_response(
            {"error": parse_error},
            status=400,
        )

    # Build response with V3-V10 fields (036-v9-policy-editor T010)
    from video_policy_orchestrator.policy.editor import KNOWN_POLICY_FIELDS
    from video_policy_orchestrator.server.ui.models import PolicyEditorContext

    # Get unknown fields for warning banner
    unknown_fields = [k for k in policy_data.keys() if k not in KNOWN_POLICY_FIELDS]

    response = PolicyEditorContext(
        name=policy_name,
        filename=policy_path.name,
        file_path=str(policy_path),
        last_modified=last_modified,
        schema_version=policy_data.get("schema_version", 2),
        track_order=policy_data.get("track_order", []),
        audio_language_preference=policy_data.get("audio_language_preference", []),
        subtitle_language_preference=policy_data.get(
            "subtitle_language_preference", []
        ),
        commentary_patterns=policy_data.get("commentary_patterns", []),
        default_flags=policy_data.get("default_flags", {}),
        transcode=policy_data.get("transcode"),
        transcription=policy_data.get("transcription"),
        # V3+ fields (036-v9-policy-editor)
        audio_filter=policy_data.get("audio_filter"),
        subtitle_filter=policy_data.get("subtitle_filter"),
        attachment_filter=policy_data.get("attachment_filter"),
        container=policy_data.get("container"),
        # V4+ fields
        conditional=policy_data.get("conditional"),
        # V5+ fields
        audio_synthesis=policy_data.get("audio_synthesis"),
        # V9+ fields
        workflow=policy_data.get("workflow"),
        # V11+ fields (user-defined phases)
        phases=policy_data.get("phases"),
        config=policy_data.get("config"),
        # Meta
        unknown_fields=unknown_fields if unknown_fields else None,
        parse_error=parse_error,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
async def api_policy_update_handler(request: web.Request) -> web.Response:
    """Handle PUT /api/policies/{name} - Save policy changes.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with updated policy data or structured validation errors.
    """
    from video_policy_orchestrator.policy.discovery import DEFAULT_POLICIES_DIR
    from video_policy_orchestrator.policy.editor import PolicyRoundTripEditor
    from video_policy_orchestrator.policy.validation import (
        DiffSummary,
        validate_policy_data,
    )
    from video_policy_orchestrator.server.ui.models import (
        ChangedFieldItem,
        PolicyEditorRequest,
        PolicySaveSuccessResponse,
        ValidationErrorItem,
        ValidationErrorResponse,
    )

    policy_name = request.match_info["name"]

    # Validate policy name
    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        return web.json_response(
            {"error": "Invalid policy name format"},
            status=400,
        )

    # Parse request body
    try:
        request_data = await request.json()
        editor_request = PolicyEditorRequest.from_dict(request_data)
    except ValueError as e:
        return web.json_response(
            {"error": f"Invalid request: {e}"},
            status=400,
        )
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    # Get policy directory (allow test override)
    policies_dir = request.app.get("policy_dir", DEFAULT_POLICIES_DIR)

    # Construct policy file path
    policy_path = policies_dir / f"{policy_name}.yaml"
    if not policy_path.exists():
        policy_path = policies_dir / f"{policy_name}.yml"

    if not policy_path.exists():
        return web.json_response(
            {"error": "Policy not found"},
            status=404,
        )

    # Verify resolved path is within allowed directory (prevent path traversal)
    try:
        resolved_path = policy_path.resolve()
        resolved_dir = policies_dir.resolve()
        resolved_path.relative_to(resolved_dir)
    except (ValueError, OSError):
        return web.json_response(
            {"error": "Invalid policy path"},
            status=400,
        )

    # Validate policy data BEFORE attempting save (T015)
    policy_dict = editor_request.to_policy_dict()
    validation_result = validate_policy_data(policy_dict)

    if not validation_result.success:
        # Return structured validation errors (T016)
        error_items = [
            ValidationErrorItem(
                field=err.field,
                message=err.message,
                code=err.code,
            )
            for err in validation_result.errors
        ]
        error_response = ValidationErrorResponse(
            error="Validation failed",
            errors=error_items,
            details=f"{len(error_items)} validation error(s) found",
        )
        return web.json_response(error_response.to_dict(), status=400)

    # Load original policy data for diff calculation
    def _load_original():
        try:
            editor = PolicyRoundTripEditor(policy_path, allowed_dir=policies_dir)
            return editor.load()
        except Exception:
            return None

    original_data = await asyncio.to_thread(_load_original)

    # Check concurrency and save (optimistic locking)
    def _check_and_save():
        try:
            stat = policy_path.stat()
            file_modified = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()

            # Compare timestamps
            if file_modified != editor_request.last_modified_timestamp:
                return None, None, "concurrent_modification"

            # Save (validation already passed above)
            editor = PolicyRoundTripEditor(policy_path, allowed_dir=policies_dir)
            editor.save(policy_dict)

            # Reload to get updated data
            data = editor.load()
            new_stat = policy_path.stat()
            new_modified = datetime.fromtimestamp(
                new_stat.st_mtime, tz=timezone.utc
            ).isoformat()

            return data, new_modified, None
        except Exception as e:
            logger.error(f"Failed to save policy {policy_name}: {e}")
            return None, None, f"Failed to save policy: {e}"

    policy_data, last_modified, error = await asyncio.to_thread(_check_and_save)

    if error == "concurrent_modification":
        return web.json_response(
            {
                "error": "Concurrent modification detected",
                "details": (
                    "Policy was modified since you loaded it. "
                    "Please reload and try again."
                ),
            },
            status=409,
        )

    if error:
        return web.json_response(
            {"error": "Save failed", "details": error},
            status=500,
        )

    # Calculate diff summary (T017)
    changed_fields: list[ChangedFieldItem] = []
    changed_fields_summary = "No changes"

    if original_data:
        diff = DiffSummary.compare_policies(original_data, policy_data)
        changed_fields = [
            ChangedFieldItem(
                field=change.field,
                change_type=change.change_type,
                details=change.details,
            )
            for change in diff.changes
        ]
        changed_fields_summary = diff.to_summary_text()

    # Build response with policy editor context (T011)
    from video_policy_orchestrator.policy.editor import KNOWN_POLICY_FIELDS
    from video_policy_orchestrator.server.ui.models import PolicyEditorContext

    # Get unknown fields
    unknown_fields = [k for k in policy_data.keys() if k not in KNOWN_POLICY_FIELDS]

    policy_context = PolicyEditorContext(
        name=policy_name,
        filename=policy_path.name,
        file_path=str(policy_path),
        last_modified=last_modified,
        schema_version=policy_data.get("schema_version", 2),
        track_order=policy_data.get("track_order", []),
        audio_language_preference=policy_data.get("audio_language_preference", []),
        subtitle_language_preference=policy_data.get(
            "subtitle_language_preference", []
        ),
        commentary_patterns=policy_data.get("commentary_patterns", []),
        default_flags=policy_data.get("default_flags", {}),
        transcode=policy_data.get("transcode"),
        transcription=policy_data.get("transcription"),
        # V3+ fields (036-v9-policy-editor)
        audio_filter=policy_data.get("audio_filter"),
        subtitle_filter=policy_data.get("subtitle_filter"),
        attachment_filter=policy_data.get("attachment_filter"),
        container=policy_data.get("container"),
        # V4+ fields
        conditional=policy_data.get("conditional"),
        # V5+ fields
        audio_synthesis=policy_data.get("audio_synthesis"),
        # V9+ fields
        workflow=policy_data.get("workflow"),
        # V11+ fields (user-defined phases)
        phases=policy_data.get("phases"),
        config=policy_data.get("config"),
        # Meta
        unknown_fields=unknown_fields if unknown_fields else None,
        parse_error=None,
    )

    response = PolicySaveSuccessResponse(
        success=True,
        changed_fields=changed_fields,
        changed_fields_summary=changed_fields_summary,
        policy=policy_context.to_dict(),
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
async def api_policy_validate_handler(request: web.Request) -> web.Response:
    """Handle POST /api/policies/{name}/validate - Validate without saving.

    Validates the policy data against the schema without persisting changes.
    This allows users to "test" their policy configuration before committing.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with validation result (valid/errors).
    """
    from video_policy_orchestrator.policy.validation import validate_policy_data
    from video_policy_orchestrator.server.ui.models import (
        PolicyEditorRequest,
        PolicyValidateResponse,
        ValidationErrorItem,
    )

    policy_name = request.match_info["name"]

    # Validate policy name format
    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        return web.json_response(
            {"error": "Invalid policy name format"},
            status=400,
        )

    # Parse request body
    try:
        request_data = await request.json()
        editor_request = PolicyEditorRequest.from_dict(request_data)
    except ValueError as e:
        return web.json_response(
            {"error": f"Invalid request: {e}"},
            status=400,
        )
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    # Validate policy data (does NOT save)
    policy_dict = editor_request.to_policy_dict()
    validation_result = validate_policy_data(policy_dict)

    if validation_result.success:
        response = PolicyValidateResponse(
            valid=True,
            errors=[],
            message="Policy configuration is valid",
        )
        return web.json_response(response.to_dict())
    else:
        error_items = [
            ValidationErrorItem(
                field=err.field,
                message=err.message,
                code=err.code,
            )
            for err in validation_result.errors
        ]
        response = PolicyValidateResponse(
            valid=False,
            errors=error_items,
            message=f"{len(error_items)} validation error(s) found",
        )
        return web.json_response(response.to_dict())


@shutdown_check_middleware
async def api_policy_create_handler(request: web.Request) -> web.Response:
    """Handle POST /api/policies - Create a new policy file.

    Creates a new policy file with the given name and default settings.
    Returns 409 Conflict if a policy with that name already exists.

    Request body:
        {
            "name": "policy-name",  // Required: alphanumeric, dash, underscore
            "description": "..."    // Optional: policy description
        }

    Returns:
        JSON response with created policy data or error.
    """
    from ruamel.yaml import YAML

    from video_policy_orchestrator.policy.discovery import DEFAULT_POLICIES_DIR
    from video_policy_orchestrator.policy.editor import KNOWN_POLICY_FIELDS
    from video_policy_orchestrator.policy.loader import MAX_SCHEMA_VERSION
    from video_policy_orchestrator.server.ui.models import PolicyEditorContext

    # Parse request body
    try:
        request_data = await request.json()
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    # Extract and validate policy name
    policy_name = request_data.get("name", "").strip()
    if not policy_name:
        return web.json_response(
            {"error": "Policy name is required"},
            status=400,
        )

    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        return web.json_response(
            {
                "error": (
                    "Invalid policy name format. "
                    "Use only letters, numbers, dashes, and underscores."
                )
            },
            status=400,
        )

    # Get policy directory (allow test override)
    policies_dir = request.app.get("policy_dir", DEFAULT_POLICIES_DIR)

    # Ensure policies directory exists
    policies_dir.mkdir(parents=True, exist_ok=True)

    # Check if policy already exists (409 Conflict)
    policy_path = policies_dir / f"{policy_name}.yaml"
    alt_path = policies_dir / f"{policy_name}.yml"

    if policy_path.exists() or alt_path.exists():
        return web.json_response(
            {"error": f"Policy '{policy_name}' already exists"},
            status=409,
        )

    # Verify resolved path is within allowed directory (prevent path traversal)
    try:
        resolved_path = policy_path.resolve()
        resolved_dir = policies_dir.resolve()
        resolved_path.relative_to(resolved_dir)
    except (ValueError, OSError):
        return web.json_response(
            {"error": "Invalid policy path"},
            status=400,
        )

    # Create default policy data with current schema version
    policy_data = {
        "schema_version": MAX_SCHEMA_VERSION,
        "track_order": ["video", "audio", "subtitle"],
        "audio_language_preference": ["eng"],
        "subtitle_language_preference": ["eng"],
    }

    # Add optional description if provided
    description = request_data.get("description", "").strip()
    if description:
        policy_data["description"] = description

    # Write new policy file
    def _create_policy():
        try:
            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.default_flow_style = False
            yaml.indent(mapping=2, sequence=4, offset=2)

            with open(policy_path, "w") as f:
                yaml.dump(policy_data, f)

            # Get file timestamp
            stat = policy_path.stat()
            last_modified = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()

            return policy_data, last_modified, None
        except Exception as e:
            logger.error(f"Failed to create policy {policy_name}: {e}")
            return None, None, str(e)

    created_data, last_modified, error = await asyncio.to_thread(_create_policy)

    if error:
        return web.json_response(
            {"error": "Failed to create policy", "details": error},
            status=500,
        )

    # Build response with policy editor context
    unknown_fields = [k for k in created_data.keys() if k not in KNOWN_POLICY_FIELDS]

    policy_context = PolicyEditorContext(
        name=policy_name,
        filename=policy_path.name,
        file_path=str(policy_path),
        last_modified=last_modified,
        schema_version=created_data.get("schema_version", MAX_SCHEMA_VERSION),
        track_order=created_data.get("track_order", []),
        audio_language_preference=created_data.get("audio_language_preference", []),
        subtitle_language_preference=created_data.get(
            "subtitle_language_preference", []
        ),
        commentary_patterns=created_data.get("commentary_patterns", []),
        default_flags=created_data.get("default_flags", {}),
        transcode=created_data.get("transcode"),
        transcription=created_data.get("transcription"),
        audio_filter=created_data.get("audio_filter"),
        subtitle_filter=created_data.get("subtitle_filter"),
        attachment_filter=created_data.get("attachment_filter"),
        container=created_data.get("container"),
        conditional=created_data.get("conditional"),
        audio_synthesis=created_data.get("audio_synthesis"),
        workflow=created_data.get("workflow"),
        # V11+ fields
        phases=created_data.get("phases"),
        config=created_data.get("config"),
        unknown_fields=unknown_fields if unknown_fields else None,
        parse_error=None,
    )

    logger.info(
        "Policy created",
        extra={
            "policy_name": policy_name,
            "policy_path": str(policy_path),
        },
    )

    return web.json_response(
        {
            "success": True,
            "message": f"Policy '{policy_name}' created successfully",
            "policy": policy_context.to_dict(),
        },
        status=201,
    )


# ==========================================================================
# Plans List View Handlers (026-plans-list-view)
# ==========================================================================


async def plans_handler(request: web.Request) -> dict:
    """Handle GET /plans - Plans list section page.

    Renders the Plans page HTML with filter options for client-side JavaScript.
    """
    context = _create_template_context(
        active_id="plans",
        section_title="Plans",
    )
    # Add plans filter options for template
    context["plans_context"] = PlansContext.default()
    # CSRF token is injected by csrf_middleware into request context
    context["csrf_token"] = request.get("csrf_token", "")
    return context


@shutdown_check_middleware
@database_required_middleware
async def api_plans_handler(request: web.Request) -> web.Response:
    """Handle GET /api/plans - JSON API for plans listing.

    Query parameters:
        status: Filter by plan status (pending, approved, rejected, applied, canceled)
        since: Time filter (24h, 7d, 30d)
        policy_name: Filter by policy name
        limit: Page size (1-100, default 50)
        offset: Pagination offset (default 0)

    Returns:
        JSON response with PlanListResponse payload.
    """
    from video_policy_orchestrator.db.models import PlanStatus
    from video_policy_orchestrator.db.operations import get_plans_filtered

    # Parse query parameters
    params = PlanFilterParams.from_query(dict(request.query))

    # Validate status parameter
    status_enum = None
    if params.status:
        try:
            status_enum = PlanStatus(params.status)
        except ValueError:
            return web.json_response(
                {"error": f"Invalid status value: '{params.status}'"},
                status=400,
            )

    # Parse time filter (returns None for invalid values)
    since_timestamp = parse_time_filter(params.since)
    if params.since and since_timestamp is None:
        return web.json_response(
            {"error": f"Invalid since value: '{params.since}'"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query plans from database using thread-safe connection access
    def _query_plans() -> tuple[list, int]:
        with connection_pool.transaction() as conn:
            plans, total = get_plans_filtered(
                conn,
                status=status_enum,
                since=since_timestamp,
                policy_name=params.policy_name,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )
            return plans, total

    plans_data, total = await asyncio.to_thread(_query_plans)

    # Convert to PlanListItem
    plan_items = [PlanListItem.from_plan_record(p) for p in plans_data]

    # Determine if any filters are active
    has_filters = bool(params.status or params.since or params.policy_name)

    response = PlanListResponse(
        plans=plan_items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=has_filters,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_plan_approve_handler(request: web.Request) -> web.Response:
    """Handle POST /api/plans/{plan_id}/approve - Approve a pending plan.

    Creates an APPLY job with priority=10 to execute the plan's actions.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with PlanActionResponse payload including job_id and job_url.
    """
    from video_policy_orchestrator.jobs.services import PlanApprovalService

    plan_id = request.match_info["plan_id"]

    # Validate UUID format
    if not is_valid_uuid(plan_id):
        return web.json_response(
            PlanActionResponse(success=False, error="Invalid plan ID format").to_dict(),
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Use service to approve plan
    service = PlanApprovalService()

    def _approve():
        with connection_pool.transaction() as conn:
            return service.approve(conn, plan_id)

    result = await asyncio.to_thread(_approve)

    if not result.success:
        status_code = 404 if result.error == "Plan not found" else 409
        return web.json_response(
            PlanActionResponse(success=False, error=result.error).to_dict(),
            status=status_code,
        )

    # Build job URL
    job_url = f"/jobs/{result.job_id}"

    response = PlanActionResponse(
        success=True,
        plan=PlanListItem.from_plan_record(result.plan),
        job_id=result.job_id,
        job_url=job_url,
        warning=result.warning,
    )
    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_plan_reject_handler(request: web.Request) -> web.Response:
    """Handle POST /api/plans/{plan_id}/reject - Reject a pending plan.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with PlanActionResponse payload.
    """
    from video_policy_orchestrator.jobs.services import PlanApprovalService

    plan_id = request.match_info["plan_id"]

    # Validate UUID format
    if not is_valid_uuid(plan_id):
        return web.json_response(
            PlanActionResponse(success=False, error="Invalid plan ID format").to_dict(),
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Use service to reject plan
    service = PlanApprovalService()

    def _reject():
        with connection_pool.transaction() as conn:
            return service.reject(conn, plan_id)

    result = await asyncio.to_thread(_reject)

    if not result.success:
        status_code = 404 if result.error == "Plan not found" else 409
        return web.json_response(
            PlanActionResponse(success=False, error=result.error).to_dict(),
            status=status_code,
        )

    response = PlanActionResponse(
        success=True,
        plan=PlanListItem.from_plan_record(result.plan),
    )
    return web.json_response(response.to_dict())


async def approvals_handler(request: web.Request) -> dict:
    """Handle GET /approvals - Approvals section page."""
    return _create_template_context(
        active_id="approvals",
        section_title="Approvals",
        section_content="<p>Approvals section - coming soon</p>",
    )


# ==========================================================================
# Processing Statistics View Handlers (040-processing-stats)
# ==========================================================================


async def stats_handler(request: web.Request) -> dict:
    """Handle GET /stats - Statistics dashboard page.

    Renders the Statistics page with overview of processing metrics.
    """
    context = _create_template_context(
        active_id="stats",
        section_title="Statistics",
    )
    return context


@shutdown_check_middleware
@database_required_middleware
async def api_stats_summary_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/summary - JSON API for statistics summary.

    Query parameters:
        since: Time filter (24h, 7d, 30d, or ISO-8601)
        until: Time filter end (ISO-8601)
        policy_name: Filter by policy name

    Returns:
        JSON response with StatsSummary payload.
    """
    from dataclasses import asdict

    # Parse query parameters
    since_str = request.query.get("since")
    until_str = request.query.get("until")
    policy_name = request.query.get("policy")

    # Parse time filters
    since_ts = None
    if since_str:
        since_ts = parse_time_filter(since_str)
        if since_ts is None:
            return web.json_response(
                {"error": f"Invalid since value: '{since_str}'"},
                status=400,
            )

    until_ts = None
    if until_str:
        until_ts = parse_time_filter(until_str)
        if until_ts is None:
            return web.json_response(
                {"error": f"Invalid until value: '{until_str}'"},
                status=400,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query stats summary
    def _query_summary():
        with connection_pool.transaction() as conn:
            return get_stats_summary(
                conn,
                since=since_ts,
                until=until_ts,
                policy_name=policy_name,
            )

    summary = await asyncio.to_thread(_query_summary)

    return web.json_response(asdict(summary))


@shutdown_check_middleware
@database_required_middleware
async def api_stats_recent_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/recent - JSON API for recent processing history.

    Query parameters:
        limit: Maximum entries to return (1-100, default 10)
        policy_name: Filter by policy name

    Returns:
        JSON response with list of FileProcessingHistory items.
    """
    from dataclasses import asdict

    # Parse query parameters
    try:
        limit = int(request.query.get("limit", 10))
        limit = max(1, min(100, limit))
    except (ValueError, TypeError):
        limit = 10

    policy_name = request.query.get("policy")

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query recent stats
    def _query_recent():
        with connection_pool.transaction() as conn:
            return get_recent_stats(
                conn,
                limit=limit,
                policy_name=policy_name,
            )

    entries = await asyncio.to_thread(_query_recent)

    return web.json_response([asdict(e) for e in entries])


@shutdown_check_middleware
@database_required_middleware
async def api_stats_policies_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/policies - JSON API for per-policy statistics.

    Query parameters:
        since: Time filter (24h, 7d, 30d, or ISO-8601)
        until: Time filter end (ISO-8601)

    Returns:
        JSON response with list of PolicyStats items.
    """
    from dataclasses import asdict

    # Parse query parameters
    since_str = request.query.get("since")
    until_str = request.query.get("until")

    # Parse time filters
    since_ts = None
    if since_str:
        since_ts = parse_time_filter(since_str)
        if since_ts is None:
            return web.json_response(
                {"error": f"Invalid since value: '{since_str}'"},
                status=400,
            )

    until_ts = None
    if until_str:
        until_ts = parse_time_filter(until_str)
        if until_ts is None:
            return web.json_response(
                {"error": f"Invalid until value: '{until_str}'"},
                status=400,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query policy stats
    def _query_policies():
        with connection_pool.transaction() as conn:
            return get_policy_stats(
                conn,
                since=since_ts,
                until=until_ts,
            )

    policies = await asyncio.to_thread(_query_policies)

    return web.json_response([asdict(p) for p in policies])


@database_required_middleware
async def api_stats_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/{stats_id} - JSON API for single stats record detail.

    Path parameters:
        stats_id: UUID of the processing_stats record.

    Returns:
        JSON response with full StatsDetailView including actions.
    """
    from dataclasses import asdict

    stats_id = request.match_info.get("stats_id")
    if not stats_id or not is_valid_uuid(stats_id):
        return web.json_response(
            {"error": "Invalid stats_id"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    def _query_detail():
        with connection_pool.transaction() as conn:
            return get_stats_detail(conn, stats_id)

    detail = await asyncio.to_thread(_query_detail)

    if detail is None:
        return web.json_response(
            {"error": f"Stats record not found: {stats_id}"},
            status=404,
        )

    return web.json_response(asdict(detail))


@database_required_middleware
async def api_stats_file_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/files/{file_id} - JSON API for file processing history.

    Path parameters:
        file_id: ID of the file to get history for.

    Returns:
        JSON response with list of FileProcessingHistory items.
    """
    from dataclasses import asdict

    file_id_str = request.match_info.get("file_id")
    if not file_id_str:
        return web.json_response(
            {"error": "file_id is required"},
            status=400,
        )

    try:
        file_id = int(file_id_str)
    except ValueError:
        return web.json_response(
            {"error": "file_id must be an integer"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    def _query_file_stats():
        with connection_pool.transaction() as conn:
            return get_stats_for_file(conn, file_id=file_id)

    history = await asyncio.to_thread(_query_file_stats)

    return web.json_response([asdict(h) for h in history])


@shutdown_check_middleware
@database_required_middleware
async def api_stats_purge_handler(request: web.Request) -> web.Response:
    """Handle DELETE /api/stats/purge - Delete processing statistics.

    Query parameters:
        before: Delete stats older than (relative: 30d, 90d or ISO-8601)
        policy: Delete stats for a specific policy name
        all: Delete ALL statistics (requires confirmation)
        dry_run: Preview what would be deleted without making changes

    Returns:
        JSON response with purge result (deleted count or error).
    """
    from video_policy_orchestrator.db.queries import (
        delete_all_processing_stats,
        delete_processing_stats_before,
        delete_processing_stats_by_policy,
    )

    # Parse query parameters
    before_str = request.query.get("before")
    policy_name = request.query.get("policy")
    delete_all = request.query.get("all", "").lower() in ("true", "1", "yes")
    dry_run = request.query.get("dry_run", "").lower() in ("true", "1", "yes")

    # Validate options
    if not before_str and not policy_name and not delete_all:
        return web.json_response(
            {"error": "Must specify at least one of: before, policy, or all"},
            status=400,
        )

    if delete_all and (before_str or policy_name):
        return web.json_response(
            {"error": "all cannot be combined with before or policy"},
            status=400,
        )

    if before_str and policy_name:
        return web.json_response(
            {"error": "before and policy cannot be combined. Use separate requests."},
            status=400,
        )

    # Parse time filter if provided
    before_ts = None
    if before_str:
        before_ts = parse_time_filter(before_str)
        if before_ts is None:
            return web.json_response(
                {"error": f"Invalid before value: '{before_str}'"},
                status=400,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Execute purge
    def _execute_purge() -> int:
        with connection_pool.transaction() as conn:
            if delete_all:
                return delete_all_processing_stats(conn, dry_run=dry_run)
            elif before_ts:
                return delete_processing_stats_before(conn, before_ts, dry_run=dry_run)
            else:
                return delete_processing_stats_by_policy(
                    conn,
                    policy_name,
                    dry_run=dry_run,  # type: ignore
                )

    deleted = await asyncio.to_thread(_execute_purge)

    # Build description
    if delete_all:
        target = "all processing statistics"
    elif before_ts:
        target = f"stats older than {before_str}"
    else:
        target = f"stats for policy '{policy_name}'"

    if dry_run:
        return web.json_response(
            {
                "dry_run": True,
                "would_delete": deleted,
                "target": target,
            }
        )
    else:
        return web.json_response(
            {
                "deleted": deleted,
                "target": target,
            }
        )


@database_required_middleware
async def api_stats_policy_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/policies/{name} - JSON API for single policy stats.

    Path parameters:
        name: Name of the policy to get stats for.

    Query parameters:
        since: Time filter (24h, 7d, 30d, or ISO-8601)
        until: Time filter end (ISO-8601)

    Returns:
        JSON response with PolicyStats for the policy.
    """
    from dataclasses import asdict

    policy_name = request.match_info.get("name")
    if not policy_name:
        return web.json_response(
            {"error": "Policy name is required"},
            status=400,
        )

    # Parse query parameters
    since_str = request.query.get("since")
    until_str = request.query.get("until")

    # Parse time filters
    since_ts = None
    if since_str:
        since_ts = parse_time_filter(since_str)
        if since_ts is None:
            return web.json_response(
                {"error": f"Invalid since value: '{since_str}'"},
                status=400,
            )

    until_ts = None
    if until_str:
        until_ts = parse_time_filter(until_str)
        if until_ts is None:
            return web.json_response(
                {"error": f"Invalid until value: '{until_str}'"},
                status=400,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    def _query_policy():
        with connection_pool.transaction() as conn:
            return get_policy_stats_by_name(
                conn,
                policy_name,
                since=since_ts,
                until=until_ts,
            )

    policy = await asyncio.to_thread(_query_policy)

    if policy is None:
        return web.json_response(
            {"error": f"No statistics found for policy: {policy_name}"},
            status=404,
        )

    return web.json_response(asdict(policy))


# ==========================================================================
# Plugin Data Browser View Handlers (236-generic-plugin-data-browser)
# ==========================================================================


@shutdown_check_middleware
async def api_plugins_list_handler(request: web.Request) -> web.Response:
    """Handle GET /api/plugins - JSON API for registered plugins list.

    Returns:
        JSON response with PluginListResponse payload.
    """
    from video_policy_orchestrator.plugin.manifest import PluginSource
    from video_policy_orchestrator.server.ui.models import (
        PluginInfo,
        PluginListResponse,
    )

    # Get plugin registry from app context
    registry = request.app.get("plugin_registry")
    if registry is None:
        # No registry configured - return empty list
        response = PluginListResponse(plugins=[], total=0)
        return web.json_response(response.to_dict())

    # Get all loaded plugins
    loaded_plugins = registry.get_all()

    # Build plugin info with defensive error handling
    plugins = []
    for p in loaded_plugins:
        try:
            plugins.append(
                PluginInfo(
                    name=p.name,
                    version=p.version,
                    enabled=p.enabled,
                    is_builtin=p.source == PluginSource.BUILTIN,
                    events=p.events,
                )
            )
        except AttributeError as e:
            logger.warning("Skipping malformed plugin: %s", e)

    response = PluginListResponse(plugins=plugins, total=len(plugins))
    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_plugin_files_handler(request: web.Request) -> web.Response:
    """Handle GET /api/plugins/{name}/files - Files with data from plugin.

    Path parameters:
        name: Plugin identifier (e.g., "whisper-transcriber").

    Query parameters:
        limit: Page size (1-100, default 50).
        offset: Pagination offset (default 0).

    Returns:
        JSON response with PluginFilesResponse payload.
    """
    from video_policy_orchestrator.db.views import get_files_with_plugin_data
    from video_policy_orchestrator.server.ui.models import (
        PluginFileItem,
        PluginFilesResponse,
    )

    plugin_name = request.match_info["name"]

    # Validate plugin name (alphanumeric, dash, underscore only)
    if not re.match(r"^[a-zA-Z0-9_-]+$", plugin_name):
        return web.json_response(
            {"error": "Invalid plugin name format"},
            status=400,
        )

    # Parse pagination parameters
    try:
        limit = int(request.query.get("limit", 50))
        limit = max(1, min(100, limit))
    except (ValueError, TypeError):
        limit = 50

    try:
        offset = int(request.query.get("offset", 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query files from database
    def _query_files() -> tuple[list[dict], int]:
        with connection_pool.transaction() as conn:
            result = get_files_with_plugin_data(
                conn,
                plugin_name,
                limit=limit,
                offset=offset,
                return_total=True,
            )
            return result  # type: ignore[return-value]

    files_data, total = await asyncio.to_thread(_query_files)

    # Convert to PluginFileItem
    files = [
        PluginFileItem(
            id=f["id"],
            filename=f["filename"],
            path=f["path"],
            scan_status=f["scan_status"],
            plugin_data=f["plugin_data"],
        )
        for f in files_data
    ]

    response = PluginFilesResponse(
        plugin_name=plugin_name,
        files=files,
        total=total,
        limit=limit,
        offset=offset,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_file_plugin_data_handler(request: web.Request) -> web.Response:
    """Handle GET /api/files/{file_id}/plugin-data - All plugin data for file.

    Path parameters:
        file_id: ID of file to get plugin data for.

    Returns:
        JSON response with FilePluginDataResponse payload.
    """
    from video_policy_orchestrator.db import get_file_by_id
    from video_policy_orchestrator.db.views import get_plugin_data_for_file
    from video_policy_orchestrator.server.ui.models import FilePluginDataResponse

    file_id_str = request.match_info["file_id"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        return web.json_response(
            {"error": "Invalid file ID format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query file and plugin data
    def _query_data():
        with connection_pool.transaction() as conn:
            file_record = get_file_by_id(conn, file_id)
            if file_record is None:
                return None, {}
            plugin_data = get_plugin_data_for_file(conn, file_id)
            return file_record, plugin_data

    file_record, plugin_data = await asyncio.to_thread(_query_data)

    if file_record is None:
        return web.json_response(
            {"error": "File not found"},
            status=404,
        )

    response = FilePluginDataResponse(
        file_id=file_id,
        filename=file_record.filename,
        plugin_data=plugin_data,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_file_plugin_data_single_handler(request: web.Request) -> web.Response:
    """Handle GET /api/files/{file_id}/plugin-data/{plugin} - Single plugin's data.

    Path parameters:
        file_id: ID of file to get plugin data for.
        plugin: Plugin identifier.

    Returns:
        JSON response with plugin-specific data.
    """
    from video_policy_orchestrator.db import get_file_by_id
    from video_policy_orchestrator.db.views import get_plugin_data_for_file

    file_id_str = request.match_info["file_id"]
    plugin_name = request.match_info["plugin"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        return web.json_response(
            {"error": "Invalid file ID format"},
            status=400,
        )

    # Validate plugin name
    if not re.match(r"^[a-zA-Z0-9_-]+$", plugin_name):
        return web.json_response(
            {"error": "Invalid plugin name format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query file and plugin data
    def _query_data():
        with connection_pool.transaction() as conn:
            file_record = get_file_by_id(conn, file_id)
            if file_record is None:
                return None, {}
            plugin_data = get_plugin_data_for_file(conn, file_id)
            return file_record, plugin_data

    file_record, plugin_data = await asyncio.to_thread(_query_data)

    if file_record is None:
        return web.json_response(
            {"error": "File not found"},
            status=404,
        )

    # Get specific plugin's data
    specific_data = plugin_data.get(plugin_name)
    if specific_data is None:
        return web.json_response(
            {"error": f"No data from plugin '{plugin_name}' for this file"},
            status=404,
        )

    return web.json_response(
        {
            "file_id": file_id,
            "filename": file_record.filename,
            "plugin_name": plugin_name,
            "data": specific_data,
        }
    )


async def file_plugin_data_handler(request: web.Request) -> dict:
    """Handle GET /library/{file_id}/plugins - Plugin data page for file.

    Args:
        request: aiohttp Request object.

    Returns:
        Template context dict for rendering.

    Raises:
        HTTPNotFound: If file not found.
        HTTPBadRequest: If file ID format is invalid.
        HTTPServiceUnavailable: If database not available.
    """
    from video_policy_orchestrator.db import get_file_by_id
    from video_policy_orchestrator.db.views import get_plugin_data_for_file
    from video_policy_orchestrator.server.ui.models import PluginDataContext

    file_id_str = request.match_info["file_id"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid file ID format")

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        raise web.HTTPServiceUnavailable(reason="Database not available")

    # Query file and plugin data
    def _query_data():
        with connection_pool.transaction() as conn:
            file_record = get_file_by_id(conn, file_id)
            if file_record is None:
                return None, {}
            plugin_data = get_plugin_data_for_file(conn, file_id)
            return file_record, plugin_data

    file_record, plugin_data = await asyncio.to_thread(_query_data)

    if file_record is None:
        raise web.HTTPNotFound(reason="File not found")

    # Build context
    plugin_context = PluginDataContext(
        file_id=file_id,
        filename=file_record.filename,
        file_path=file_record.path,
        plugin_data=plugin_data,
        plugin_count=len(plugin_data),
    )

    context = _create_template_context(
        active_id="library",
        section_title=f"Plugin Data: {file_record.filename}",
    )
    context["plugin_context"] = plugin_context
    context["back_url"] = f"/library/{file_id}"

    return context


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
    env = aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    )

    # Add custom Jinja2 filters (020-file-detail-view)
    def format_number(value: int | str) -> str:
        """Format a number with thousand separators."""
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return str(value)

    env.filters["format_number"] = format_number

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
    # Library API routes (018-library-list-view, 019-library-filters-search)
    app.router.add_get("/api/library", library_api_handler)
    app.router.add_get("/api/library/languages", api_library_languages_handler)
    # Plugin data route (register before /library/{file_id} for correct matching)
    app.router.add_get(
        "/library/{file_id}/plugins",
        aiohttp_jinja2.template("sections/plugin_data.html")(file_plugin_data_handler),
    )
    # File detail routes (020-file-detail-view)
    app.router.add_get(
        "/library/{file_id}",
        aiohttp_jinja2.template("sections/file_detail.html")(file_detail_handler),
    )
    app.router.add_get("/api/library/{file_id}", api_file_detail_handler)
    # NOTE: Transcription routes removed in 236-generic-plugin-data-browser
    # Transcription data is now accessed via generic plugin data browser
    app.router.add_get(
        "/policies",
        aiohttp_jinja2.template("sections/policies.html")(policies_handler),
    )
    # Policies API route (023-policies-list-view)
    app.router.add_get("/api/policies", policies_api_handler)
    # Create new policy endpoint (036-v9-policy-editor T068)
    app.router.add_post("/api/policies", api_policy_create_handler)
    # Policy editor routes (024-policy-editor)
    app.router.add_get(
        "/policies/{name}/edit",
        aiohttp_jinja2.template("sections/policy_editor.html")(policy_editor_handler),
    )
    app.router.add_get("/api/policies/{name}", api_policy_detail_handler)
    app.router.add_put("/api/policies/{name}", api_policy_update_handler)
    # Policy validation endpoint (025-policy-validation T029)
    app.router.add_post("/api/policies/{name}/validate", api_policy_validate_handler)
    # Plans list routes (026-plans-list-view)
    app.router.add_get(
        "/plans",
        aiohttp_jinja2.template("sections/plans.html")(plans_handler),
    )
    app.router.add_get("/api/plans", api_plans_handler)
    app.router.add_post("/api/plans/{plan_id}/approve", api_plan_approve_handler)
    app.router.add_post("/api/plans/{plan_id}/reject", api_plan_reject_handler)
    app.router.add_get(
        "/approvals",
        aiohttp_jinja2.template("sections/approvals.html")(approvals_handler),
    )
    # Processing statistics routes (040-processing-stats)
    app.router.add_get(
        "/stats",
        aiohttp_jinja2.template("sections/stats.html")(stats_handler),
    )
    app.router.add_get("/api/stats/summary", api_stats_summary_handler)
    app.router.add_get("/api/stats/recent", api_stats_recent_handler)
    app.router.add_get("/api/stats/policies", api_stats_policies_handler)
    app.router.add_get("/api/stats/policies/{name}", api_stats_policy_handler)
    app.router.add_get("/api/stats/files/{file_id}", api_stats_file_handler)
    app.router.add_get("/api/stats/{stats_id}", api_stats_detail_handler)
    app.router.add_delete("/api/stats/purge", api_stats_purge_handler)
    # Plugin data browser API routes (236-generic-plugin-data-browser)
    app.router.add_get("/api/plugins", api_plugins_list_handler)
    app.router.add_get("/api/plugins/{name}/files", api_plugin_files_handler)
    app.router.add_get("/api/files/{file_id}/plugin-data", api_file_plugin_data_handler)
    app.router.add_get(
        "/api/files/{file_id}/plugin-data/{plugin}", api_file_plugin_data_single_handler
    )
    app.router.add_get(
        "/about",
        aiohttp_jinja2.template("sections/about.html")(about_handler),
    )

    # Add middleware (order matters: logging -> csrf -> security -> error handling)
    from video_policy_orchestrator.server.csrf import csrf_middleware

    app.middlewares.append(request_logging_middleware)
    app.middlewares.append(csrf_middleware)
    app.middlewares.append(security_headers_middleware)
    app.middlewares.append(error_middleware)

    logger.debug("UI routes configured with Jinja2 templating and CSRF protection")
