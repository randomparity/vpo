"""API route modules for the VPO web server.

This package contains JSON API handlers extracted from server/ui/routes.py
for better organization. Each module handles a specific domain:

- jobs.py: Job listing, detail, logs, and errors endpoints
- files.py: Library files and transcription endpoints
- policies.py: Policy CRUD and validation endpoints
- plans.py: Plan listing, approval, and rejection endpoints
- stats.py: Processing statistics endpoints
- plugins.py: Plugin data browser endpoints
"""

from aiohttp import web

from vpo.server.api.files import setup_file_routes
from vpo.server.api.jobs import setup_job_routes
from vpo.server.api.plans import setup_plan_routes
from vpo.server.api.plugins import setup_plugin_routes
from vpo.server.api.policies import setup_policy_routes
from vpo.server.api.stats import setup_stats_routes

__all__ = [
    "setup_api_routes",
]


def setup_api_routes(app: web.Application) -> None:
    """Register all API routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    setup_job_routes(app)
    setup_file_routes(app)
    setup_policy_routes(app)
    setup_plan_routes(app)
    setup_stats_routes(app)
    setup_plugin_routes(app)
