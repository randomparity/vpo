"""Unit tests for HTTP Basic Auth middleware.

Tests authentication functions and middleware behavior for web UI protection.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from video_policy_orchestrator.server.auth import (
    create_auth_middleware,
    is_auth_enabled,
    parse_basic_auth,
    validate_token,
)


class TestParseBasicAuth:
    """Tests for parse_basic_auth() function."""

    def test_valid_basic_auth_simple(self) -> None:
        """Parse valid Basic auth header with simple credentials."""
        # "user:password" base64-encoded
        header = "Basic " + base64.b64encode(b"user:password").decode()
        result = parse_basic_auth(header)
        assert result == ("user", "password")

    def test_valid_basic_auth_with_colon_in_password(self) -> None:
        """Parse Basic auth where password contains colons."""
        # Password is "pass:word:with:colons"
        header = "Basic " + base64.b64encode(b"user:pass:word:with:colons").decode()
        result = parse_basic_auth(header)
        assert result == ("user", "pass:word:with:colons")

    def test_valid_basic_auth_special_characters(self) -> None:
        """Parse Basic auth with special characters in password (!, @, #, spaces)."""
        special_password = "p@ss! w#rd 123"  # pragma: allowlist secret
        header = (
            "Basic " + base64.b64encode(f"user:{special_password}".encode()).decode()
        )
        result = parse_basic_auth(header)
        assert result == ("user", special_password)

    def test_valid_basic_auth_unicode_password(self) -> None:
        """Parse Basic auth with Unicode characters in password."""
        unicode_password = "пароль密码"
        header = (
            "Basic " + base64.b64encode(f"user:{unicode_password}".encode()).decode()
        )
        result = parse_basic_auth(header)
        assert result == ("user", unicode_password)

    def test_valid_basic_auth_empty_username(self) -> None:
        """Parse Basic auth with empty username (only password)."""
        header = "Basic " + base64.b64encode(b":password").decode()
        result = parse_basic_auth(header)
        assert result == ("", "password")

    def test_none_header(self) -> None:
        """Return None for missing Authorization header."""
        result = parse_basic_auth(None)
        assert result is None

    def test_empty_header(self) -> None:
        """Return None for empty Authorization header."""
        result = parse_basic_auth("")
        assert result is None

    def test_bearer_auth_header(self) -> None:
        """Return None for Bearer auth (not Basic)."""
        result = parse_basic_auth("Bearer token123")
        assert result is None

    def test_invalid_scheme(self) -> None:
        """Return None for unknown auth scheme."""
        result = parse_basic_auth("Digest username=test")
        assert result is None

    def test_invalid_base64(self) -> None:
        """Return None for invalid base64 encoding."""
        result = parse_basic_auth("Basic not-valid-base64!!!")
        assert result is None

    def test_missing_colon(self) -> None:
        """Return None when decoded value has no colon separator."""
        # "userpassword" without colon
        header = "Basic " + base64.b64encode(b"userpassword").decode()
        result = parse_basic_auth(header)
        assert result is None

    def test_invalid_utf8(self) -> None:
        """Return None for invalid UTF-8 in decoded credentials."""
        # Invalid UTF-8 sequence
        header = "Basic " + base64.b64encode(b"\xff\xfe:password").decode()
        result = parse_basic_auth(header)
        assert result is None


class TestValidateToken:
    """Tests for validate_token() function with constant-time comparison."""

    def test_matching_tokens(self) -> None:
        """Return True when tokens match exactly."""
        assert validate_token("secret123", "secret123") is True

    def test_non_matching_tokens(self) -> None:
        """Return False when tokens don't match."""
        assert validate_token("wrong", "secret123") is False

    def test_empty_provided_token(self) -> None:
        """Return False when provided token is empty."""
        assert validate_token("", "secret123") is False

    def test_case_sensitive(self) -> None:
        """Token comparison is case-sensitive."""
        assert validate_token("Secret123", "secret123") is False

    def test_whitespace_matters(self) -> None:
        """Whitespace in tokens matters."""
        assert validate_token("secret 123", "secret123") is False
        assert validate_token("secret123 ", "secret123") is False

    def test_special_characters(self) -> None:
        """Tokens with special characters compared correctly."""
        token = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        assert validate_token(token, token) is True

    def test_unicode_tokens(self) -> None:
        """Unicode tokens compared correctly."""
        token = "密码пароль🔐"
        assert validate_token(token, token) is True


class TestIsAuthEnabled:
    """Tests for is_auth_enabled() helper function."""

    def test_none_token(self) -> None:
        """Return False for None token."""
        assert is_auth_enabled(None) is False

    def test_empty_string_token(self) -> None:
        """Return False for empty string token."""
        assert is_auth_enabled("") is False

    def test_whitespace_only_token(self) -> None:
        """Return False for whitespace-only token."""
        assert is_auth_enabled("   ") is False
        assert is_auth_enabled("\t\n") is False

    def test_valid_token(self) -> None:
        """Return True for non-empty token."""
        assert is_auth_enabled("secret123") is True

    def test_token_with_surrounding_whitespace(self) -> None:
        """Return True for token with surrounding whitespace (has content)."""
        assert is_auth_enabled("  secret  ") is True


class TestAuthMiddleware:
    """Tests for create_auth_middleware() factory and middleware behavior."""

    @pytest.fixture
    def mock_handler(self) -> AsyncMock:
        """Create mock request handler that returns 200 OK."""
        handler = AsyncMock()
        handler.return_value = web.Response(text="OK")
        return handler

    @pytest.fixture
    def valid_auth_header(self) -> str:
        """Create valid Basic auth header for token 'secret123'."""
        return "Basic " + base64.b64encode(b"user:secret123").decode()

    @pytest.mark.asyncio
    async def test_rejects_missing_credentials(self, mock_handler: AsyncMock) -> None:
        """Return 401 when Authorization header is missing."""
        middleware = create_auth_middleware("secret123")
        request = make_mocked_request("GET", "/api/jobs")

        response = await middleware(request, mock_handler)

        assert response.status == 401
        assert response.headers.get("WWW-Authenticate") == 'Basic realm="VPO"'
        mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_invalid_credentials(self, mock_handler: AsyncMock) -> None:
        """Return 401 when credentials are invalid."""
        middleware = create_auth_middleware("secret123")
        # Wrong password
        wrong_auth = "Basic " + base64.b64encode(b"user:wrongpassword").decode()
        request = make_mocked_request(
            "GET", "/api/jobs", headers={"Authorization": wrong_auth}
        )

        response = await middleware(request, mock_handler)

        assert response.status == 401
        assert response.headers.get("WWW-Authenticate") == 'Basic realm="VPO"'
        mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_allows_valid_credentials(
        self, mock_handler: AsyncMock, valid_auth_header: str
    ) -> None:
        """Allow request when credentials are valid."""
        middleware = create_auth_middleware("secret123")
        request = make_mocked_request(
            "GET", "/api/jobs", headers={"Authorization": valid_auth_header}
        )

        response = await middleware(request, mock_handler)

        assert response.status == 200
        mock_handler.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_health_endpoint_bypasses_auth(self, mock_handler: AsyncMock) -> None:
        """Allow /health requests without authentication."""
        middleware = create_auth_middleware("secret123")
        request = make_mocked_request("GET", "/health")

        response = await middleware(request, mock_handler)

        assert response.status == 200
        mock_handler.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_health_endpoint_no_auth_header_needed(
        self, mock_handler: AsyncMock
    ) -> None:
        """Confirm /health works without any Authorization header."""
        middleware = create_auth_middleware("secret123")
        # Explicitly no Authorization header
        request = make_mocked_request("GET", "/health")

        response = await middleware(request, mock_handler)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_www_authenticate_header_format(
        self, mock_handler: AsyncMock
    ) -> None:
        """Verify WWW-Authenticate header format for browser dialog."""
        middleware = create_auth_middleware("secret123")
        request = make_mocked_request("GET", "/api/jobs")

        response = await middleware(request, mock_handler)

        # This exact format triggers browser's native login dialog
        assert response.headers.get("WWW-Authenticate") == 'Basic realm="VPO"'

    @pytest.mark.asyncio
    async def test_protects_static_files(
        self, mock_handler: AsyncMock, valid_auth_header: str
    ) -> None:
        """Require auth for static file requests."""
        middleware = create_auth_middleware("secret123")
        request = make_mocked_request("GET", "/static/js/app.js")

        # Without auth
        response = await middleware(request, mock_handler)
        assert response.status == 401

        # With auth
        request_with_auth = make_mocked_request(
            "GET", "/static/js/app.js", headers={"Authorization": valid_auth_header}
        )
        response = await middleware(request_with_auth, mock_handler)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_protects_root_path(
        self, mock_handler: AsyncMock, valid_auth_header: str
    ) -> None:
        """Require auth for root path request."""
        middleware = create_auth_middleware("secret123")
        request = make_mocked_request("GET", "/")

        response = await middleware(request, mock_handler)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_special_character_token(self, mock_handler: AsyncMock) -> None:
        """Handle tokens with special characters correctly."""
        special_token = "p@ss! w#rd 123"
        middleware = create_auth_middleware(special_token)
        auth_header = (
            "Basic " + base64.b64encode(f"user:{special_token}".encode()).decode()
        )
        request = make_mocked_request(
            "GET", "/api/jobs", headers={"Authorization": auth_header}
        )

        response = await middleware(request, mock_handler)

        assert response.status == 200
        mock_handler.assert_called_once()
