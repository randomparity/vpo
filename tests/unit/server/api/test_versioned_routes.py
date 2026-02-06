"""Tests for API v1 versioned route registration.

Verifies that every /api/v1/* route resolves to the same handler as its
/api/* counterpart, and that /health stays unversioned.
"""

from __future__ import annotations

from aiohttp import web

from vpo.server.api import _ROUTE_GETTERS, setup_api_routes


def _build_app() -> web.Application:
    """Create a minimal app with all API routes registered."""
    app = web.Application()
    setup_api_routes(app)

    # Also register /api/about and /api/v1/about as app.py does
    async def about_handler(request: web.Request) -> web.Response:
        return web.json_response({})

    app.router.add_get("/api/about", about_handler)
    app.router.add_get("/api/v1/about", about_handler)
    return app


class TestVersionedRoutes:
    """Tests that /api/v1/ routes mirror /api/ routes."""

    def test_every_api_route_has_v1_counterpart(self):
        """All routes from get_*_routes() are registered under /api/v1/."""
        app = _build_app()

        # Collect all expected v1 paths
        expected_v1_paths = set()
        for get_routes in _ROUTE_GETTERS:
            for method, suffix, _handler in get_routes():
                expected_v1_paths.add((method, f"/api/v1{suffix}"))

        # Collect actual registered routes
        registered = set()
        for resource in app.router.resources():
            info = resource.get_info()
            # formatter is the path pattern for dynamic routes
            path = info.get("formatter") or info.get("path", "")
            if path.startswith("/api/v1"):
                for route in resource:
                    registered.add((route.method, path))

        for method, path in expected_v1_paths:
            assert (method, path) in registered, f"Missing v1 route: {method} {path}"

    def test_v1_routes_use_same_handler_as_api_routes(self):
        """Each /api/v1/X handler is the same function as /api/X."""
        app = _build_app()

        # Build lookup of path -> handler for /api/ routes
        api_handlers: dict[tuple[str, str], object] = {}
        v1_handlers: dict[tuple[str, str], object] = {}

        for resource in app.router.resources():
            info = resource.get_info()
            path = info.get("formatter") or info.get("path", "")
            for route in resource:
                key = (route.method, path)
                if path.startswith("/api/v1/"):
                    # Strip /api/v1 → keep the suffix
                    suffix = path[len("/api/v1") :]
                    v1_handlers[(route.method, suffix)] = route.handler
                elif path.startswith("/api/") and not path.startswith("/api/v1"):
                    suffix = path[len("/api") :]
                    api_handlers[(route.method, suffix)] = route.handler

        # Every v1 handler should match the corresponding api handler
        for key, handler in v1_handlers.items():
            assert key in api_handlers, f"v1 route {key} has no /api/ counterpart"
            assert handler is api_handlers[key], (
                f"Handler mismatch for {key}: "
                f"v1={handler!r} vs api={api_handlers[key]!r}"
            )

    def test_health_stays_unversioned(self):
        """The /health endpoint should not appear under /api/v1/."""
        app = _build_app()

        for resource in app.router.resources():
            info = resource.get_info()
            path = info.get("formatter") or info.get("path", "")
            assert path != "/api/v1/health", "/health should not be versioned"
