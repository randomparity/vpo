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
    PoliciesContext,
    PolicyListItem,
    PolicyListResponse,
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
    format_language_preferences,
    generate_summary_text,
    get_classification_reasoning,
    get_confidence_level,
    get_resolution_label,
    group_tracks_by_type,
    highlight_keywords_in_transcript,
)

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
        with pool.transaction() as conn:
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

            # Get files with errors for this specific job
            cursor = conn.execute(
                """
                SELECT path, filename, scan_error
                FROM files
                WHERE job_id = ?
                  AND scan_status = 'error'
                  AND scan_error IS NOT NULL
                ORDER BY filename
                """,
                (job_id,),
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


async def library_api_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library - JSON API for library files listing.

    Query parameters:
        status: Filter by scan status (ok, error)
        limit: Page size (1-100, default 50)
        offset: Pagination offset (default 0)

    Returns:
        JSON response with FileListResponse payload.
    """
    from video_policy_orchestrator.db.connection import DaemonConnectionPool
    from video_policy_orchestrator.db.models import get_files_filtered

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

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

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        return web.json_response(
            {"error": "Database not available"},
            status=503,
        )

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


async def api_library_languages_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library/languages - Get available audio languages.

    Returns list of distinct audio language codes present in the library
    for populating the language filter dropdown (019-library-filters-search).
    """
    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

    from video_policy_orchestrator.db.connection import DaemonConnectionPool

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        return web.json_response(
            {"error": "Database not available"},
            status=503,
        )

    # Query distinct languages from database
    from video_policy_orchestrator.db.models import get_distinct_audio_languages

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
    # Group tracks by type
    video_tracks, audio_tracks, subtitle_tracks, other_tracks = group_tracks_by_type(
        tracks, transcriptions
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
    from video_policy_orchestrator.db.connection import DaemonConnectionPool
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


async def api_file_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library/{file_id} - JSON API for file detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with FileDetailResponse payload or error.
    """
    from video_policy_orchestrator.db.connection import DaemonConnectionPool
    from video_policy_orchestrator.db.models import (
        get_file_by_id,
        get_tracks_for_file,
        get_transcriptions_for_tracks,
    )

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
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

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        return web.json_response(
            {"error": "Database not available"},
            status=503,
        )

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


async def api_transcriptions_handler(request: web.Request) -> web.Response:
    """Handle GET /api/transcriptions - JSON API for transcriptions listing.

    Query parameters:
        show_all: If true, show all files. Default: false (transcribed only).
        limit: Page size (1-100, default 50).
        offset: Pagination offset (default 0).

    Returns:
        JSON response with TranscriptionListResponse payload.
    """
    from video_policy_orchestrator.db.connection import DaemonConnectionPool
    from video_policy_orchestrator.db.models import get_files_with_transcriptions

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

    # Parse query parameters
    params = TranscriptionFilterParams.from_query(dict(request.query))

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        return web.json_response(
            {"error": "Database not available"},
            status=503,
        )

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
    from video_policy_orchestrator.db.connection import DaemonConnectionPool
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


async def api_transcription_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/transcriptions/{id} - JSON API for transcription detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with TranscriptionDetailResponse payload or error.
    """
    from video_policy_orchestrator.db.connection import DaemonConnectionPool
    from video_policy_orchestrator.db.models import get_transcription_detail

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

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

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        return web.json_response(
            {"error": "Database not available"},
            status=503,
        )

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
    from video_policy_orchestrator.policy.discovery import (
        DEFAULT_POLICIES_DIR,
        discover_policies,
    )

    # Get default policy from active profile
    default_policy_path = None
    try:
        from video_policy_orchestrator.config.profiles import get_active_profile

        profile = get_active_profile()
        if profile and profile.default_policy:
            default_policy_path = profile.default_policy
    except Exception:
        pass

    # Discover policies
    policies_dir = DEFAULT_POLICIES_DIR
    summaries, default_missing = await asyncio.to_thread(
        discover_policies,
        policies_dir,
        default_policy_path,
    )

    # Convert to PolicyListItem
    policies = [
        PolicyListItem(
            name=s.name,
            filename=s.filename,
            file_path=s.file_path,
            last_modified=s.last_modified,
            schema_version=s.schema_version,
            audio_languages=format_language_preferences(s.audio_languages),
            subtitle_languages=format_language_preferences(s.subtitle_languages),
            has_transcode=s.has_transcode,
            has_transcription=s.has_transcription,
            is_default=s.is_default,
            parse_error=s.parse_error,
        )
        for s in summaries
    ]

    response = PolicyListResponse(
        policies=policies,
        total=len(policies),
        policies_directory=str(policies_dir),
        default_policy_path=str(default_policy_path) if default_policy_path else None,
        default_policy_missing=default_missing,
        directory_exists=policies_dir.exists(),
    )

    context = _create_template_context(
        active_id="policies",
        section_title="Policies",
    )
    context["policies_context"] = PoliciesContext.default()
    context["policies_response"] = response

    return context


async def policies_api_handler(request: web.Request) -> web.Response:
    """Handle GET /api/policies - JSON API for policy files listing.

    Returns:
        JSON response with PolicyListResponse payload.
    """
    from video_policy_orchestrator.policy.discovery import (
        DEFAULT_POLICIES_DIR,
        discover_policies,
    )

    # Check if shutting down
    lifecycle = request.app.get("lifecycle")
    if lifecycle and lifecycle.is_shutting_down:
        return web.json_response(
            {"error": "Service is shutting down"},
            status=503,
        )

    # Get default policy from active profile
    default_policy_path = None
    try:
        from video_policy_orchestrator.config.profiles import get_active_profile

        profile = get_active_profile()
        if profile and profile.default_policy:
            default_policy_path = profile.default_policy
    except Exception:
        pass

    # Discover policies
    policies_dir = DEFAULT_POLICIES_DIR
    summaries, default_missing = await asyncio.to_thread(
        discover_policies,
        policies_dir,
        default_policy_path,
    )

    # Convert to PolicyListItem
    policies = [
        PolicyListItem(
            name=s.name,
            filename=s.filename,
            file_path=s.file_path,
            last_modified=s.last_modified,
            schema_version=s.schema_version,
            audio_languages=format_language_preferences(s.audio_languages),
            subtitle_languages=format_language_preferences(s.subtitle_languages),
            has_transcode=s.has_transcode,
            has_transcription=s.has_transcription,
            is_default=s.is_default,
            parse_error=s.parse_error,
        )
        for s in summaries
    ]

    response = PolicyListResponse(
        policies=policies,
        total=len(policies),
        policies_directory=str(policies_dir),
        default_policy_path=str(default_policy_path) if default_policy_path else None,
        default_policy_missing=default_missing,
        directory_exists=policies_dir.exists(),
    )

    return web.json_response(response.to_dict())


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
    # File detail routes (020-file-detail-view)
    app.router.add_get(
        "/library/{file_id}",
        aiohttp_jinja2.template("sections/file_detail.html")(file_detail_handler),
    )
    app.router.add_get("/api/library/{file_id}", api_file_detail_handler)
    app.router.add_get(
        "/transcriptions",
        aiohttp_jinja2.template("sections/transcriptions.html")(transcriptions_handler),
    )
    # Transcriptions API route (021-transcriptions-list)
    app.router.add_get("/api/transcriptions", api_transcriptions_handler)
    # Transcription detail routes (022-transcription-detail)
    app.router.add_get(
        "/transcriptions/{transcription_id}",
        aiohttp_jinja2.template("sections/transcription_detail.html")(
            transcription_detail_handler
        ),
    )
    app.router.add_get(
        "/api/transcriptions/{transcription_id}", api_transcription_detail_handler
    )
    app.router.add_get(
        "/policies",
        aiohttp_jinja2.template("sections/policies.html")(policies_handler),
    )
    # Policies API route (023-policies-list-view)
    app.router.add_get("/api/policies", policies_api_handler)
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
