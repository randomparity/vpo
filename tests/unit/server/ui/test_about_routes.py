"""Unit tests for About page route handlers."""

import os
from unittest.mock import MagicMock, patch

from aiohttp import web

from video_policy_orchestrator.server.ui.models import AboutInfo
from video_policy_orchestrator.server.ui.routes import (
    DOCS_URL,
    get_about_info,
)


class TestAboutInfo:
    """Tests for AboutInfo dataclass."""

    def test_about_info_to_dict(self) -> None:
        """Test AboutInfo serializes correctly to dictionary."""
        info = AboutInfo(
            version="0.1.0",
            git_hash="abc123",
            profile_name="production",
            api_url="http://localhost:8080",
            docs_url="https://example.com/docs",
            is_read_only=True,
        )

        data = info.to_dict()

        assert data["version"] == "0.1.0"
        assert data["git_hash"] == "abc123"
        assert data["profile_name"] == "production"
        assert data["api_url"] == "http://localhost:8080"
        assert data["docs_url"] == "https://example.com/docs"
        assert data["is_read_only"] is True

    def test_about_info_default_read_only(self) -> None:
        """Test that is_read_only defaults to True."""
        info = AboutInfo(
            version="0.1.0",
            git_hash=None,
            profile_name="Default",
            api_url="http://localhost:8080",
            docs_url="https://example.com/docs",
        )

        assert info.is_read_only is True

    def test_about_info_with_none_git_hash(self) -> None:
        """Test AboutInfo handles None git_hash."""
        info = AboutInfo(
            version="0.1.0",
            git_hash=None,
            profile_name="Default",
            api_url="http://localhost:8080",
            docs_url="https://example.com/docs",
        )

        data = info.to_dict()
        assert data["git_hash"] is None


class TestGetAboutInfo:
    """Tests for get_about_info helper function."""

    def test_get_about_info_returns_version(self) -> None:
        """Test that get_about_info returns the package version."""
        # Create mock request
        mock_app = {"profile_name": "Default"}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        # Version should be from __version__
        assert info.version == "0.1.0"

    def test_get_about_info_uses_profile_from_app_context(self) -> None:
        """Test that get_about_info reads profile from app context."""
        mock_app = {"profile_name": "custom-profile"}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        assert info.profile_name == "custom-profile"

    def test_get_about_info_defaults_profile_to_default(self) -> None:
        """Test that get_about_info defaults profile to 'Default'."""
        mock_app = {}  # No profile_name set
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        assert info.profile_name == "Default"

    def test_get_about_info_uses_request_url(self) -> None:
        """Test that get_about_info builds api_url from request."""
        mock_app = {}
        mock_url = MagicMock()
        mock_url.origin.return_value = "https://vpo.example.com:9000"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        assert info.api_url == "https://vpo.example.com:9000"

    def test_get_about_info_includes_docs_url(self) -> None:
        """Test that get_about_info includes documentation URL."""
        mock_app = {}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        assert info.docs_url == DOCS_URL

    @patch.dict(os.environ, {"VPO_GIT_HASH": "abc123def456"})
    def test_get_about_info_reads_git_hash_from_env(self) -> None:
        """Test that get_about_info reads git hash from environment."""
        mock_app = {}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        assert info.git_hash == "abc123def456"

    @patch.dict(os.environ, {}, clear=True)
    def test_get_about_info_handles_missing_git_hash(self) -> None:
        """Test that get_about_info handles missing git hash gracefully."""
        mock_app = {}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        assert info.git_hash is None

    @patch.dict(os.environ, {"VPO_GIT_HASH": "not-a-valid-hash!"})
    def test_get_about_info_rejects_invalid_git_hash(self) -> None:
        """Test that get_about_info rejects invalid git hash format."""
        mock_app = {}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        # Invalid hash should be treated as None
        assert info.git_hash is None

    @patch.dict(os.environ, {"VPO_GIT_HASH": "abc"})
    def test_get_about_info_rejects_too_short_git_hash(self) -> None:
        """Test that get_about_info rejects git hash that is too short."""
        mock_app = {}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        # Hash shorter than 7 chars should be rejected
        assert info.git_hash is None

    def test_get_about_info_is_read_only(self) -> None:
        """Test that get_about_info always sets is_read_only to True."""
        mock_app = {}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        info = get_about_info(mock_request)

        assert info.is_read_only is True


class TestApiAboutHandler:
    """Tests for /api/about endpoint handler."""

    def test_api_about_returns_json_response(self) -> None:
        """Test that api_about_handler returns a JSON response."""
        import asyncio

        from video_policy_orchestrator.server.app import api_about_handler

        mock_app = {"profile_name": "test-profile"}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:8080"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        response = asyncio.run(api_about_handler(mock_request))

        assert response.status == 200
        assert response.content_type == "application/json"

    def test_api_about_includes_all_fields(self) -> None:
        """Test that api_about_handler response includes all expected fields."""
        import asyncio
        import json

        from video_policy_orchestrator.server.app import api_about_handler

        mock_app = {"profile_name": "my-profile"}
        mock_url = MagicMock()
        mock_url.origin.return_value = "http://localhost:9000"

        mock_request = MagicMock(spec=web.Request)
        mock_request.app = mock_app
        mock_request.url = mock_url

        response = asyncio.run(api_about_handler(mock_request))

        # Parse the response body
        body = json.loads(response.body)

        assert "version" in body
        assert "git_hash" in body
        assert "profile_name" in body
        assert body["profile_name"] == "my-profile"
        assert "api_url" in body
        assert body["api_url"] == "http://localhost:9000"
        assert "docs_url" in body
        assert "is_read_only" in body
        assert body["is_read_only"] is True
