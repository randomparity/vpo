"""Integration tests for HTTP Basic Auth middleware.

Tests end-to-end authentication flow with aiohttp test client.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

import pytest
from aiohttp.test_utils import AioHTTPTestCase

from video_policy_orchestrator.server.app import create_app

if TYPE_CHECKING:
    from aiohttp import web


class TestAuthEnabledIntegration(AioHTTPTestCase):
    """Integration tests for server with authentication enabled."""

    AUTH_TOKEN = "test-secret-token-123"

    async def get_application(self) -> web.Application:
        """Create application with auth enabled for testing."""
        return create_app(db_path=None, auth_token=self.AUTH_TOKEN)

    def _make_auth_header(self, token: str) -> str:
        """Create Basic auth header for given token."""
        encoded = base64.b64encode(f"user:{token}".encode()).decode()
        return f"Basic {encoded}"

    async def test_protected_endpoint_rejects_unauthenticated(self) -> None:
        """Protected endpoint returns 401 without credentials."""
        async with self.client.get("/api/about") as response:
            assert response.status == 401
            assert response.headers.get("WWW-Authenticate") == 'Basic realm="VPO"'

    async def test_protected_endpoint_accepts_valid_auth(self) -> None:
        """Protected endpoint returns 200 with valid credentials."""
        headers = {"Authorization": self._make_auth_header(self.AUTH_TOKEN)}
        async with self.client.get("/api/about", headers=headers) as response:
            assert response.status == 200

    async def test_protected_endpoint_rejects_invalid_auth(self) -> None:
        """Protected endpoint returns 401 with invalid credentials."""
        headers = {"Authorization": self._make_auth_header("wrong-token")}
        async with self.client.get("/api/about", headers=headers) as response:
            assert response.status == 401

    async def test_health_endpoint_allows_unauthenticated(self) -> None:
        """Health endpoint works without credentials (for load balancers)."""
        async with self.client.get("/health") as response:
            # Health returns 503 when no database, but should not be 401
            assert response.status != 401
            # Should be 503 (no db) or 200
            assert response.status in (200, 503)

    async def test_static_files_require_auth(self) -> None:
        """Static file requests require authentication."""
        # Without auth
        async with self.client.get("/static/css/style.css") as response:
            assert response.status == 401

        # With auth
        headers = {"Authorization": self._make_auth_header(self.AUTH_TOKEN)}
        async with self.client.get(
            "/static/css/style.css", headers=headers
        ) as response:
            # May be 404 if file doesn't exist, but should not be 401
            assert response.status != 401

    async def test_root_path_requires_auth(self) -> None:
        """Root path requires authentication."""
        async with self.client.get("/") as response:
            assert response.status == 401

    async def test_401_response_triggers_browser_dialog(self) -> None:
        """401 response includes proper WWW-Authenticate header for browser dialog."""
        async with self.client.get("/api/about") as response:
            assert response.status == 401
            # This exact format triggers browser's native login dialog
            www_auth = response.headers.get("WWW-Authenticate")
            assert www_auth == 'Basic realm="VPO"'


class TestAuthDisabledIntegration(AioHTTPTestCase):
    """Integration tests for server with authentication disabled."""

    async def get_application(self) -> web.Application:
        """Create application with auth disabled for testing."""
        return create_app(db_path=None, auth_token=None)

    async def test_all_endpoints_accessible(self) -> None:
        """All endpoints accessible when auth is disabled."""
        async with self.client.get("/api/about") as response:
            assert response.status == 200

        async with self.client.get("/health") as response:
            # 503 because no database, but not 401
            assert response.status in (200, 503)


class TestAuthDisabledWarning:
    """Test that warning is logged when auth is disabled."""

    @pytest.fixture
    def caplog_with_info(
        self, caplog: pytest.LogCaptureFixture
    ) -> pytest.LogCaptureFixture:
        """Configure caplog to capture INFO level logs."""
        caplog.set_level(logging.WARNING)
        return caplog

    def test_warning_logged_when_auth_disabled(
        self, caplog_with_info: pytest.LogCaptureFixture
    ) -> None:
        """Log warning when server starts without auth token."""
        create_app(db_path=None, auth_token=None)

        # Check that warning was logged
        assert any(
            "Authentication is disabled" in record.message
            for record in caplog_with_info.records
        )

    def test_no_warning_when_auth_enabled(
        self, caplog_with_info: pytest.LogCaptureFixture
    ) -> None:
        """No warning when server starts with auth token."""
        create_app(db_path=None, auth_token="secret123")

        # Check that no warning about disabled auth was logged
        assert not any(
            "Authentication is disabled" in record.message
            for record in caplog_with_info.records
        )
