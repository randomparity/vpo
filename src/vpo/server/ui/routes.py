"""UI route handlers for Web UI Shell.

This module provides server-rendered HTML routes for the VPO web interface.
JSON API handlers have been moved to vpo.server.api package.
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

from vpo import __version__
from vpo.core.validation import is_valid_uuid
from vpo.db.connection import DaemonConnectionPool
from vpo.server.ui.models import (
    DEFAULT_SECTION,
    NAVIGATION_ITEMS,
    AboutInfo,
    FileDetailContext,
    JobDetailContext,
    JobListContext,
    LibraryContext,
    NavigationState,
    PlanDetailContext,
    PlanDetailItem,
    PlansContext,
    PoliciesContext,
    TemplateContext,
    TranscriptionDetailContext,
    build_file_detail_item,
    build_job_detail_item,
    build_transcription_detail_item,
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
        # Allow CDN for Ajv and Highlight.js
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
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
# HTML Route handlers
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
        Authentication is applied globally via auth middleware when
        `auth_token` is configured in settings. VPO is designed as a
        local tool but can be secured for network exposure.
    """
    from vpo.jobs.logs import log_file_exists

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
        from vpo.db import get_job

        with connection_pool.transaction() as conn:
            return get_job(conn, job_id)

    job = await asyncio.to_thread(_query_job)

    if job is None:
        raise web.HTTPNotFound(reason="Job not found")

    # Check if log file exists
    has_logs = log_file_exists(job_id)

    # Convert to detail item
    detail_item = build_job_detail_item(job, has_logs)

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


# ==========================================================================
# File Detail View Handlers (020-file-detail-view)
# ==========================================================================


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
    from vpo.db import (
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
    detail_item = build_file_detail_item(file_record, tracks, transcriptions)

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


async def transcriptions_handler(request: web.Request) -> dict:
    """Handle GET /transcriptions - Transcriptions section page."""
    return _create_template_context(
        active_id="transcriptions",
        section_title="Transcriptions",
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
    from vpo.db import get_transcription_detail

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
    detail_item = build_transcription_detail_item(data)

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


async def policies_handler(request: web.Request) -> dict:
    """Handle GET /policies - Policies section page.

    Renders the Policies list page with all policy files discovered
    from ~/.vpo/policies/ directory.
    """
    from vpo.policy.services import list_policies

    response = await asyncio.to_thread(list_policies)

    context = _create_template_context(
        active_id="policies",
        section_title="Policies",
    )
    context["policies_context"] = PoliciesContext.default()
    context["policies_response"] = response

    return context


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
    from vpo.policy.discovery import DEFAULT_POLICIES_DIR
    from vpo.policy.editor import KNOWN_POLICY_FIELDS, PolicyRoundTripEditor
    from vpo.policy.loader import PolicyValidationError
    from vpo.server.ui.models import PolicyEditorContext

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
        "preferred_audio_codec": None,
    }

    # Get unknown fields for warning banner (T076)
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
        # Phased policy fields (user-defined phases)
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


async def plan_detail_handler(request: web.Request) -> dict:
    """Handle GET /plans/{plan_id} - Plan detail HTML page.

    Args:
        request: aiohttp Request object.

    Returns:
        Template context dict for rendering.

    Raises:
        HTTPNotFound: If plan not found.
        HTTPBadRequest: If plan ID format is invalid.
        HTTPServiceUnavailable: If database not available.
    """
    from vpo.core.validation import is_valid_uuid
    from vpo.db.operations import get_plan_by_id

    plan_id = request.match_info["plan_id"]

    # Validate UUID format
    if not is_valid_uuid(plan_id):
        raise web.HTTPBadRequest(reason="Invalid plan ID format")

    # Get connection pool
    connection_pool: DaemonConnectionPool | None = request.app.get("connection_pool")
    if connection_pool is None:
        raise web.HTTPServiceUnavailable(reason="Database not available")

    # Query plan from database
    def _query_plan():
        with connection_pool.transaction() as conn:
            return get_plan_by_id(conn, plan_id)

    plan = await asyncio.to_thread(_query_plan)

    if plan is None:
        raise web.HTTPNotFound(reason="Plan not found")

    # Convert to detail item with deserialized actions
    detail_item = PlanDetailItem.from_plan_record(plan)

    # Get referer for back navigation
    referer = request.headers.get("Referer")

    # Create context
    detail_context = PlanDetailContext.from_plan_and_request(detail_item, referer)

    context = _create_template_context(
        active_id="plans",
        section_title=f"Plan {detail_item.id_short}",
    )
    context["plan"] = detail_item
    context["back_url"] = detail_context.back_url
    # CSRF token is injected by csrf_middleware into request context
    context["csrf_token"] = request.get("csrf_token", "")

    return context


async def approvals_handler(request: web.Request) -> dict:
    """Handle GET /approvals - Approvals section page.

    Shows only pending plans with bulk approve/reject functionality.
    """
    context = _create_template_context(
        active_id="approvals",
        section_title="Approvals",
    )
    # CSRF token is injected by csrf_middleware into request context
    context["csrf_token"] = request.get("csrf_token", "")
    return context


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


# ==========================================================================
# Plugin Data Browser View Handlers (236-generic-plugin-data-browser)
# ==========================================================================


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
    from vpo.db import get_file_by_id
    from vpo.db.views import get_plugin_data_for_file
    from vpo.server.ui.models import PluginDataContext

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
    # Setup API routes from separate modules
    from vpo.server.api import setup_api_routes

    setup_api_routes(app)

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
    app.router.add_get(
        "/library",
        aiohttp_jinja2.template("sections/library.html")(library_handler),
    )
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
    # NOTE: Transcription routes removed in 236-generic-plugin-data-browser
    # Transcription data is now accessed via generic plugin data browser
    app.router.add_get(
        "/policies",
        aiohttp_jinja2.template("sections/policies.html")(policies_handler),
    )
    # Policy editor routes (024-policy-editor)
    app.router.add_get(
        "/policies/{name}/edit",
        aiohttp_jinja2.template("sections/policy_editor.html")(policy_editor_handler),
    )
    # Plans list routes (026-plans-list-view)
    app.router.add_get(
        "/plans",
        aiohttp_jinja2.template("sections/plans.html")(plans_handler),
    )
    # Plan detail route
    app.router.add_get(
        "/plans/{plan_id}",
        aiohttp_jinja2.template("sections/plan_detail.html")(plan_detail_handler),
    )
    app.router.add_get(
        "/approvals",
        aiohttp_jinja2.template("sections/approvals.html")(approvals_handler),
    )
    # Processing statistics routes (040-processing-stats)
    app.router.add_get(
        "/stats",
        aiohttp_jinja2.template("sections/stats.html")(stats_handler),
    )
    app.router.add_get(
        "/about",
        aiohttp_jinja2.template("sections/about.html")(about_handler),
    )

    # Add middleware (order matters: logging -> csrf -> security -> error handling)
    from vpo.server.csrf import csrf_middleware

    app.middlewares.append(request_logging_middleware)
    app.middlewares.append(csrf_middleware)
    app.middlewares.append(security_headers_middleware)
    app.middlewares.append(error_middleware)

    logger.debug("UI routes configured with Jinja2 templating and CSRF protection")
