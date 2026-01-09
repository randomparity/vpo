"""Unit tests for Sonarr API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from vpo.config.models import PluginConnectionConfig
from vpo.plugins.sonarr_metadata.client import (
    SonarrAuthError,
    SonarrClient,
    SonarrConnectionError,
)
from vpo.plugins.sonarr_metadata.models import (
    SonarrLanguage,
)


@pytest.fixture
def config() -> PluginConnectionConfig:
    """Create a test connection config."""
    return PluginConnectionConfig(
        url="http://localhost:8989",
        api_key="test-api-key-12345",  # pragma: allowlist secret
        enabled=True,
        timeout_seconds=30,
    )


@pytest.fixture
def client(config: PluginConnectionConfig) -> SonarrClient:
    """Create a SonarrClient instance."""
    return SonarrClient(config)


class TestSonarrClientInit:
    """Tests for SonarrClient initialization."""

    def test_init_strips_trailing_slash(self, config: PluginConnectionConfig):
        """Test that trailing slashes are stripped from URL."""
        config_with_slash = PluginConnectionConfig(
            url="http://localhost:8989/",
            api_key="test-key",  # pragma: allowlist secret
            enabled=True,
            timeout_seconds=30,
        )
        client = SonarrClient(config_with_slash)
        assert client._base_url == "http://localhost:8989"

    def test_init_stores_config_values(self, config: PluginConnectionConfig):
        """Test that config values are stored correctly."""
        client = SonarrClient(config)
        assert client._base_url == "http://localhost:8989"
        assert client._api_key == "test-api-key-12345"  # pragma: allowlist secret
        assert client._timeout == 30

    def test_init_client_is_none(self, client: SonarrClient):
        """Test that HTTP client is not created until needed."""
        assert client._client is None


class TestSonarrClientHeaders:
    """Tests for API header generation."""

    def test_headers_include_api_key(self, client: SonarrClient):
        """Test that headers include X-Api-Key."""
        headers = client._headers()
        assert headers == {"X-Api-Key": "test-api-key-12345"}


class TestSonarrClientGetClient:
    """Tests for lazy HTTP client creation."""

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_creates_client_on_first_call(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test that HTTP client is created lazily."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        result = client._get_client()

        assert result == mock_http_client
        mock_client_class.assert_called_once_with(
            base_url="http://localhost:8989",
            timeout=30,
            headers={"X-Api-Key": "test-api-key-12345"},
        )

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_reuses_existing_client(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test that existing client is reused."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        client._get_client()
        client._get_client()

        # Should only create once
        assert mock_client_class.call_count == 1


class TestSonarrClientGetStatus:
    """Tests for get_status method."""

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_get_status_success(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test successful status retrieval."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"appName": "Sonarr", "version": "3.0.0"}
        mock_http_client.get.return_value = mock_response

        result = client.get_status()

        assert result == {"appName": "Sonarr", "version": "3.0.0"}
        mock_http_client.get.assert_called_once_with("/api/v3/system/status")

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_get_status_auth_error(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test 401 response raises SonarrAuthError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_http_client.get.return_value = mock_response

        with pytest.raises(SonarrAuthError, match="Invalid API key"):
            client.get_status()

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_get_status_connect_error(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test connection error raises SonarrConnectionError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(SonarrConnectionError, match="Cannot connect to Sonarr"):
            client.get_status()

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_get_status_timeout_error(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test timeout raises SonarrConnectionError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(SonarrConnectionError, match="Connection timeout"):
            client.get_status()

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_get_status_http_error(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test HTTP error raises SonarrConnectionError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_http_client.get.return_value = mock_response

        with pytest.raises(SonarrConnectionError, match="HTTP error"):
            client.get_status()


class TestSonarrClientValidateConnection:
    """Tests for validate_connection method."""

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_validate_connection_success(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test successful connection validation."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"appName": "Sonarr", "version": "3.0.0"}
        mock_http_client.get.return_value = mock_response

        result = client.validate_connection()

        assert result is True

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_validate_connection_wrong_app(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test wrong app name raises error."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"appName": "Radarr", "version": "4.0.0"}
        mock_http_client.get.return_value = mock_response

        with pytest.raises(SonarrConnectionError, match="Expected Sonarr, got Radarr"):
            client.validate_connection()


class TestSonarrClientParse:
    """Tests for parse method."""

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_success_with_match(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test successful parse with series match."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "series": {
                "id": 123,
                "title": "Test Series",
                "year": 2020,
                "path": "/tv/Test Series",
                "originalLanguage": {"id": 1, "name": "English"},
                "imdbId": "tt7654321",
                "tvdbId": 987654,
            },
            "episodes": [
                {
                    "id": 456,
                    "seriesId": 123,
                    "seasonNumber": 1,
                    "episodeNumber": 5,
                    "title": "Test Episode",
                    "hasFile": True,
                }
            ],
        }
        mock_http_client.get.return_value = mock_response

        result = client.parse("/tv/Test Series/Season 1/S01E05.mkv")

        assert result.series is not None
        assert result.series.id == 123
        assert result.series.title == "Test Series"
        assert result.series.original_language == SonarrLanguage(id=1, name="English")
        assert len(result.episodes) == 1
        assert result.episodes[0].season_number == 1
        assert result.episodes[0].episode_number == 5

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_success_no_match(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test parse with no series match."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "series": None,
            "episodes": [],
        }
        mock_http_client.get.return_value = mock_response

        result = client.parse("/some/unknown/file.mkv")

        assert result.series is None
        assert result.episodes == ()

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_url_encodes_path(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test that file path is URL-encoded."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"series": None, "episodes": []}
        mock_http_client.get.return_value = mock_response

        client.parse("/tv/Test Show/Season 1/Test Show S01E01.mkv")

        # Check the URL was encoded
        call_args = mock_http_client.get.call_args[0][0]
        assert "path=" in call_args
        # Spaces should be encoded as %20
        assert "%20" in call_args or "+" in call_args

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_http_error(self, mock_client_class: MagicMock, client: SonarrClient):
        """Test HTTP error during parse."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.HTTPError("Request failed")

        with pytest.raises(SonarrConnectionError, match="Failed to parse path"):
            client.parse("/some/file.mkv")


class TestSonarrClientParseResponses:
    """Tests for response parsing methods."""

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_series_response_full(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test parsing a complete series response."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "series": {
                "id": 123,
                "title": "Test Series",
                "year": 2020,
                "path": "/tv/Test",
                "originalLanguage": {"id": 2, "name": "Japanese"},
                "imdbId": "tt1111111",
                "tvdbId": 222222,
            },
            "episodes": [],
        }
        mock_http_client.get.return_value = mock_response

        result = client.parse("/tv/Test/test.mkv")

        assert result.series is not None
        assert result.series.imdb_id == "tt1111111"
        assert result.series.tvdb_id == 222222
        assert result.series.original_language is not None
        assert result.series.original_language.name == "Japanese"

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_series_response_minimal(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test parsing a series response with minimal fields."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "series": {
                "id": 123,
                # Missing optional fields
            },
            "episodes": [],
        }
        mock_http_client.get.return_value = mock_response

        result = client.parse("/tv/Test/test.mkv")

        assert result.series is not None
        assert result.series.id == 123
        assert result.series.title == ""
        assert result.series.year == 0
        assert result.series.original_language is None

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_series_missing_id_raises(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test that missing series ID raises error."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "series": {
                "title": "No ID",
                # Missing 'id' field
            },
            "episodes": [],
        }
        mock_http_client.get.return_value = mock_response

        with pytest.raises(SonarrConnectionError, match="missing required 'id' field"):
            client.parse("/tv/Test/test.mkv")

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_episode_response(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test parsing episode responses."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "series": {"id": 123, "title": "Test"},
            "episodes": [
                {
                    "id": 456,
                    "seriesId": 123,
                    "seasonNumber": 2,
                    "episodeNumber": 10,
                    "title": "Episode Title",
                    "hasFile": True,
                }
            ],
        }
        mock_http_client.get.return_value = mock_response

        result = client.parse("/tv/Test/test.mkv")

        assert len(result.episodes) == 1
        ep = result.episodes[0]
        assert ep.id == 456
        assert ep.series_id == 123
        assert ep.season_number == 2
        assert ep.episode_number == 10
        assert ep.title == "Episode Title"
        assert ep.has_file is True

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_parse_multi_episode_response(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test parsing multi-episode file response."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "series": {"id": 123, "title": "Test"},
            "episodes": [
                {
                    "id": 456,
                    "seriesId": 123,
                    "seasonNumber": 1,
                    "episodeNumber": 1,
                    "title": "Episode 1",
                    "hasFile": True,
                },
                {
                    "id": 457,
                    "seriesId": 123,
                    "seasonNumber": 1,
                    "episodeNumber": 2,
                    "title": "Episode 2",
                    "hasFile": True,
                },
            ],
        }
        mock_http_client.get.return_value = mock_response

        result = client.parse("/tv/Test/test.mkv")

        assert len(result.episodes) == 2
        assert result.episodes[0].episode_number == 1
        assert result.episodes[1].episode_number == 2


class TestSonarrClientClose:
    """Tests for close method."""

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_close_with_client(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test closing an active client."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Create the client
        client._get_client()

        # Close it
        client.close()

        mock_http_client.close.assert_called_once()
        assert client._client is None

    def test_close_without_client(self, client: SonarrClient):
        """Test closing when no client was created."""
        # Should not raise
        client.close()
        assert client._client is None

    @patch("vpo.plugins.sonarr_metadata.client.httpx.Client")
    def test_close_allows_new_client(
        self, mock_client_class: MagicMock, client: SonarrClient
    ):
        """Test that closing allows creating a new client."""
        mock_http_client1 = MagicMock()
        mock_http_client2 = MagicMock()
        mock_client_class.side_effect = [mock_http_client1, mock_http_client2]

        client._get_client()
        client.close()
        client._get_client()

        assert mock_client_class.call_count == 2
