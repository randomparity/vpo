"""API route modules for the VPO web server.

This package contains JSON API handlers extracted from server/ui/routes.py
for better organization. Each module handles a specific domain:

- jobs.py: Job listing, detail, logs, and errors endpoints
- files.py: Library files and transcription endpoints
- policies.py: Policy CRUD and validation endpoints
- plans.py: Plan listing, approval, and rejection endpoints
- stats.py: Processing statistics endpoints
- plugins.py: Plugin data browser endpoints
- events.py: Server-Sent Events (SSE) for real-time updates

API Versioning:
    All endpoints are available under both ``/api/`` (unversioned, backward
    compatible) and ``/api/v1/`` (versioned). Both prefixes resolve to the
    same handler.

Resource ID Schemes:
    - Jobs, plans, stats: UUIDv4 string (e.g. ``/api/jobs/{job_id}``)
    - Files, transcriptions: Auto-increment integer (e.g. ``/api/library/{file_id}``)
    - Policies: Filesystem name string (e.g. ``/api/policies/{name}``)
    - Plugins: Registry name string (e.g. ``/api/plugins/{name}``)
"""

from pathlib import Path

from aiohttp import web

from vpo.server.api.events import get_events_routes, setup_events_routes
from vpo.server.api.files import get_file_routes, setup_file_routes
from vpo.server.api.jobs import get_job_routes, setup_job_routes
from vpo.server.api.plans import get_plan_routes, setup_plan_routes
from vpo.server.api.plugins import get_plugin_routes, setup_plugin_routes
from vpo.server.api.policies import get_policy_routes, setup_policy_routes
from vpo.server.api.stats import get_stats_routes, setup_stats_routes

__all__ = [
    "setup_api_routes",
]

# All route getter functions for dual-prefix registration
_ROUTE_GETTERS = [
    get_job_routes,
    get_file_routes,
    get_policy_routes,
    get_plan_routes,
    get_stats_routes,
    get_plugin_routes,
    get_events_routes,
]


def setup_api_routes(app: web.Application) -> None:
    """Register all API routes with the application.

    Registers each route under both ``/api/`` (backward compatible) and
    ``/api/v1/`` (versioned) prefixes.

    Args:
        app: aiohttp Application to configure.
    """
    # Register under /api/ (backward compat)
    setup_job_routes(app)
    setup_file_routes(app)
    setup_policy_routes(app)
    setup_plan_routes(app)
    setup_stats_routes(app)
    setup_plugin_routes(app)
    setup_events_routes(app)

    # Register under /api/v1/ (versioned)
    for get_routes in _ROUTE_GETTERS:
        for method, suffix, handler in get_routes():
            app.router.add_route(method, f"/api/v1{suffix}", handler)

    # Serve OpenAPI spec under both prefixes
    app.router.add_get("/api/openapi.yaml", _openapi_handler)
    app.router.add_get("/api/v1/openapi.yaml", _openapi_handler)


_OPENAPI_PATH = Path(__file__).parent / "openapi.yaml"
_OPENAPI_TEXT = _OPENAPI_PATH.read_text()


async def _openapi_handler(request: web.Request) -> web.Response:
    """Serve the bundled OpenAPI specification."""
    return web.Response(text=_OPENAPI_TEXT, content_type="text/yaml")
