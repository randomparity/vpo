"""Tests for server UI middleware."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web

from vpo.server.middleware import (
    JOBS_ALLOWED_PARAMS,
    validate_query_params,
)
from vpo.server.ui.routes import (
    database_required_middleware,
    shutdown_check_middleware,
)


class FakeQuery:
    """Fake query dict that supports .keys() method."""

    def __init__(self, params: dict | None = None):
        self._params = params or {}

    def keys(self):
        return self._params.keys()

    def get(self, key: str, default=None):
        return self._params.get(key, default)


class FakeRequest:
    """Fake request for testing middleware without full aiohttp setup."""

    def __init__(self, app_dict: dict | None = None, query: dict | None = None):
        self._app_dict = app_dict or {}
        self._data: dict = {}
        self._query = FakeQuery(query)
        self.path = "/test"

    @property
    def app(self) -> dict:
        return self._app_dict

    @property
    def query(self) -> FakeQuery:
        return self._query

    def __setitem__(self, key: str, value) -> None:
        self._data[key] = value

    def __getitem__(self, key: str):
        return self._data[key]


class TestShutdownCheckMiddleware:
    """Tests for shutdown_check_middleware decorator."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock async handler."""
        handler = AsyncMock()
        handler.return_value = web.json_response({"success": True})
        return handler

    @pytest.mark.asyncio
    async def test_allows_request_when_no_lifecycle(self, mock_handler):
        """Calls handler when no lifecycle object exists."""
        request = FakeRequest({"lifecycle": None})

        wrapped = shutdown_check_middleware(mock_handler)
        response = await wrapped(request)

        mock_handler.assert_called_once_with(request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_allows_request_when_lifecycle_not_shutting_down(self, mock_handler):
        """Calls handler when lifecycle exists but not shutting down."""
        lifecycle = MagicMock()
        lifecycle.is_shutting_down = False
        request = FakeRequest({"lifecycle": lifecycle})

        wrapped = shutdown_check_middleware(mock_handler)
        response = await wrapped(request)

        mock_handler.assert_called_once_with(request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_returns_503_when_shutting_down(self, mock_handler):
        """Returns 503 when server is shutting down."""
        lifecycle = MagicMock()
        lifecycle.is_shutting_down = True
        request = FakeRequest({"lifecycle": lifecycle})

        wrapped = shutdown_check_middleware(mock_handler)
        response = await wrapped(request)

        mock_handler.assert_not_called()
        assert response.status == 503

    @pytest.mark.asyncio
    async def test_503_response_has_error_message(self, mock_handler):
        """503 response contains error message."""
        lifecycle = MagicMock()
        lifecycle.is_shutting_down = True
        request = FakeRequest({"lifecycle": lifecycle})

        wrapped = shutdown_check_middleware(mock_handler)
        response = await wrapped(request)

        body = response.body.decode("utf-8")
        data = json.loads(body)
        assert data["error"] == "Service is shutting down"


class TestDatabaseRequiredMiddleware:
    """Tests for database_required_middleware decorator."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock async handler."""
        handler = AsyncMock()
        handler.return_value = web.json_response({"success": True})
        return handler

    @pytest.fixture
    def mock_pool(self):
        """Create a mock connection pool."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_returns_503_when_no_connection_pool(self, mock_handler):
        """Returns 503 when connection pool is not available."""
        request = FakeRequest({"connection_pool": None})

        wrapped = database_required_middleware(mock_handler)
        response = await wrapped(request)

        mock_handler.assert_not_called()
        assert response.status == 503

    @pytest.mark.asyncio
    async def test_503_response_has_error_message(self, mock_handler):
        """503 response contains database unavailable message."""
        request = FakeRequest({"connection_pool": None})

        wrapped = database_required_middleware(mock_handler)
        response = await wrapped(request)

        body = response.body.decode("utf-8")
        data = json.loads(body)
        assert data["error"] == "Database not available"

    @pytest.mark.asyncio
    async def test_calls_handler_when_pool_available(self, mock_handler, mock_pool):
        """Calls handler when connection pool is available."""
        request = FakeRequest({"connection_pool": mock_pool})

        wrapped = database_required_middleware(mock_handler)
        response = await wrapped(request)

        mock_handler.assert_called_once_with(request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_stores_pool_in_request(self, mock_pool):
        """Stores connection pool in request for handler access."""
        request = FakeRequest({"connection_pool": mock_pool})

        # Capture the request passed to handler
        captured_request = None

        async def capture_handler(req):
            nonlocal captured_request
            captured_request = req
            return web.json_response({"success": True})

        wrapped = database_required_middleware(capture_handler)
        await wrapped(request)

        assert captured_request is not None
        assert captured_request["connection_pool"] is mock_pool


class TestMiddlewareComposition:
    """Tests for combining multiple middleware decorators."""

    @pytest.fixture
    def mock_pool(self):
        """Create a mock connection pool."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_shutdown_check_runs_first(self, mock_pool):
        """shutdown_check_middleware runs before database_required_middleware."""
        lifecycle = MagicMock()
        lifecycle.is_shutting_down = True

        request = FakeRequest(
            {
                "lifecycle": lifecycle,
                "connection_pool": mock_pool,
            }
        )

        async def handler(req):
            return web.json_response({"success": True})

        # Apply decorators in order (shutdown first, then database)
        wrapped = shutdown_check_middleware(database_required_middleware(handler))
        response = await wrapped(request)

        # Should return 503 from shutdown check, not from database check
        assert response.status == 503
        body = response.body.decode("utf-8")
        data = json.loads(body)
        assert data["error"] == "Service is shutting down"

    @pytest.mark.asyncio
    async def test_database_check_runs_after_shutdown(self):
        """database_required_middleware runs after shutdown check passes."""
        lifecycle = MagicMock()
        lifecycle.is_shutting_down = False

        request = FakeRequest(
            {
                "lifecycle": lifecycle,
                "connection_pool": None,  # No database
            }
        )

        async def handler(req):
            return web.json_response({"success": True})

        wrapped = shutdown_check_middleware(database_required_middleware(handler))
        response = await wrapped(request)

        # Should return 503 from database check
        assert response.status == 503
        body = response.body.decode("utf-8")
        data = json.loads(body)
        assert data["error"] == "Database not available"

    @pytest.mark.asyncio
    async def test_handler_called_when_all_checks_pass(self, mock_pool):
        """Handler called when both shutdown and database checks pass."""
        lifecycle = MagicMock()
        lifecycle.is_shutting_down = False

        request = FakeRequest(
            {
                "lifecycle": lifecycle,
                "connection_pool": mock_pool,
            }
        )

        handler_called = False

        async def handler(req):
            nonlocal handler_called
            handler_called = True
            # Verify pool is accessible
            assert req["connection_pool"] is mock_pool
            return web.json_response({"success": True})

        wrapped = shutdown_check_middleware(database_required_middleware(handler))
        response = await wrapped(request)

        assert handler_called
        assert response.status == 200


class TestValidateQueryParams:
    """Tests for validate_query_params decorator."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock async handler."""
        handler = AsyncMock()
        handler.return_value = web.json_response({"success": True})
        return handler

    @pytest.mark.asyncio
    async def test_allows_valid_params(self, mock_handler):
        """Handler called when all query params are in allowlist."""
        allowed = frozenset({"status", "limit", "offset"})
        request = FakeRequest(query={"status": "running", "limit": "10"})

        wrapped = validate_query_params(allowed)(mock_handler)
        response = await wrapped(request)

        mock_handler.assert_called_once_with(request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_allows_empty_params(self, mock_handler):
        """Handler called when no query params provided."""
        allowed = frozenset({"status", "limit", "offset"})
        request = FakeRequest(query={})

        wrapped = validate_query_params(allowed)(mock_handler)
        response = await wrapped(request)

        mock_handler.assert_called_once_with(request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_lenient_mode_logs_unknown_params(self, mock_handler, caplog):
        """In lenient mode (default), unknown params are logged but allowed."""
        allowed = frozenset({"status", "limit"})
        request = FakeRequest(query={"status": "running", "unknown": "value"})

        wrapped = validate_query_params(allowed)(mock_handler)
        response = await wrapped(request)

        # Handler should still be called
        mock_handler.assert_called_once_with(request)
        assert response.status == 200

        # Warning should be logged
        assert "unknown" in caplog.text.lower() or mock_handler.called

    @pytest.mark.asyncio
    async def test_strict_mode_rejects_unknown_params(self, mock_handler):
        """In strict mode, unknown params return 400 error."""
        allowed = frozenset({"status", "limit"})
        request = FakeRequest(query={"status": "running", "unknown": "value"})

        wrapped = validate_query_params(allowed, strict=True)(mock_handler)
        response = await wrapped(request)

        # Handler should NOT be called
        mock_handler.assert_not_called()
        assert response.status == 400

        body = response.body.decode("utf-8")
        data = json.loads(body)
        assert "Unknown query parameters" in data["error"]
        assert "unknown" in data["error"]

    @pytest.mark.asyncio
    async def test_strict_mode_allows_valid_params(self, mock_handler):
        """In strict mode, valid params are allowed."""
        allowed = frozenset({"status", "limit"})
        request = FakeRequest(query={"status": "running"})

        wrapped = validate_query_params(allowed, strict=True)(mock_handler)
        response = await wrapped(request)

        mock_handler.assert_called_once_with(request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_jobs_allowed_params_defined(self):
        """JOBS_ALLOWED_PARAMS contains expected parameters."""
        assert "status" in JOBS_ALLOWED_PARAMS
        assert "type" in JOBS_ALLOWED_PARAMS
        assert "since" in JOBS_ALLOWED_PARAMS
        assert "limit" in JOBS_ALLOWED_PARAMS
        assert "offset" in JOBS_ALLOWED_PARAMS
