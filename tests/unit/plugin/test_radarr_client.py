"""Unit tests for Radarr API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from video_policy_orchestrator.config.models import PluginConnectionConfig
from video_policy_orchestrator.plugins.radarr_metadata.client import (
    RadarrAuthError,
    RadarrClient,
    RadarrConnectionError,
)
from video_policy_orchestrator.plugins.radarr_metadata.models import (
    RadarrLanguage,
    RadarrMovie,
    RadarrMovieFile,
)


@pytest.fixture
def config() -> PluginConnectionConfig:
    """Create a test connection config."""
    return PluginConnectionConfig(
        url="http://localhost:7878",
        api_key="test-api-key-12345",  # pragma: allowlist secret
        enabled=True,
        timeout_seconds=30,
    )


@pytest.fixture
def client(config: PluginConnectionConfig) -> RadarrClient:
    """Create a RadarrClient instance."""
    return RadarrClient(config)


class TestRadarrClientInit:
    """Tests for RadarrClient initialization."""

    def test_init_strips_trailing_slash(self, config: PluginConnectionConfig):
        """Test that trailing slashes are stripped from URL."""
        config_with_slash = PluginConnectionConfig(
            url="http://localhost:7878/",
            api_key="test-key",  # pragma: allowlist secret
            enabled=True,
            timeout_seconds=30,
        )
        client = RadarrClient(config_with_slash)
        assert client._base_url == "http://localhost:7878"

    def test_init_stores_config_values(self, config: PluginConnectionConfig):
        """Test that config values are stored correctly."""
        client = RadarrClient(config)
        assert client._base_url == "http://localhost:7878"
        assert client._api_key == "test-api-key-12345"  # pragma: allowlist secret
        assert client._timeout == 30

    def test_init_client_is_none(self, client: RadarrClient):
        """Test that HTTP client is not created until needed."""
        assert client._client is None


class TestRadarrClientHeaders:
    """Tests for API header generation."""

    def test_headers_include_api_key(self, client: RadarrClient):
        """Test that headers include X-Api-Key."""
        headers = client._headers()
        assert headers == {"X-Api-Key": "test-api-key-12345"}


class TestRadarrClientGetClient:
    """Tests for lazy HTTP client creation."""

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_creates_client_on_first_call(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test that HTTP client is created lazily."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        result = client._get_client()

        assert result == mock_http_client
        mock_client_class.assert_called_once_with(
            base_url="http://localhost:7878",
            timeout=30,
            headers={"X-Api-Key": "test-api-key-12345"},
        )

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_reuses_existing_client(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test that existing client is reused."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        client._get_client()
        client._get_client()

        # Should only create once
        assert mock_client_class.call_count == 1


class TestRadarrClientGetStatus:
    """Tests for get_status method."""

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_status_success(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test successful status retrieval."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"appName": "Radarr", "version": "4.0.0"}
        mock_http_client.get.return_value = mock_response

        result = client.get_status()

        assert result == {"appName": "Radarr", "version": "4.0.0"}
        mock_http_client.get.assert_called_once_with("/api/v3/system/status")

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_status_auth_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test 401 response raises RadarrAuthError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_http_client.get.return_value = mock_response

        with pytest.raises(RadarrAuthError, match="Invalid API key"):
            client.get_status()

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_status_connect_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test connection error raises RadarrConnectionError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(RadarrConnectionError, match="Cannot connect to Radarr"):
            client.get_status()

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_status_timeout_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test timeout raises RadarrConnectionError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(RadarrConnectionError, match="Connection timeout"):
            client.get_status()

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_status_http_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test HTTP error raises RadarrConnectionError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_http_client.get.return_value = mock_response

        with pytest.raises(RadarrConnectionError, match="HTTP error"):
            client.get_status()


class TestRadarrClientValidateConnection:
    """Tests for validate_connection method."""

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_validate_connection_success(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test successful connection validation."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"appName": "Radarr", "version": "4.0.0"}
        mock_http_client.get.return_value = mock_response

        result = client.validate_connection()

        assert result is True

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_validate_connection_wrong_app(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test wrong app name raises error."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"appName": "Sonarr", "version": "3.0.0"}
        mock_http_client.get.return_value = mock_response

        with pytest.raises(RadarrConnectionError, match="Expected Radarr, got Sonarr"):
            client.validate_connection()


class TestRadarrClientGetMovies:
    """Tests for get_movies method."""

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_movies_success(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test successful movie retrieval."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 123,
                "title": "Test Movie",
                "originalTitle": "Original Test",
                "originalLanguage": {"id": 1, "name": "English"},
                "year": 2023,
                "path": "/movies/Test Movie (2023)",
                "hasFile": True,
                "imdbId": "tt1234567",
                "tmdbId": 456789,
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert len(result) == 1
        assert isinstance(result[0], RadarrMovie)
        assert result[0].id == 123
        assert result[0].title == "Test Movie"
        assert result[0].original_title == "Original Test"
        assert result[0].original_language == RadarrLanguage(id=1, name="English")
        assert result[0].year == 2023
        assert result[0].imdb_id == "tt1234567"
        assert result[0].tmdb_id == 456789

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_movies_empty_list(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test empty movie list."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert result == []

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_movies_minimal_fields(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test movie with minimal fields."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 123,
                # Missing optional fields
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert len(result) == 1
        assert result[0].id == 123
        assert result[0].title == ""
        assert result[0].original_language is None

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_movies_http_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test HTTP error during movie retrieval."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.HTTPError("Request failed")

        with pytest.raises(RadarrConnectionError, match="Failed to get movies"):
            client.get_movies()


class TestRadarrClientGetMovieFiles:
    """Tests for get_movie_files method."""

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_movie_files_success(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test successful movie file retrieval."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 456,
                "movieId": 123,
                "path": "/movies/Test Movie (2023)/Test.Movie.2023.mkv",
                "relativePath": "Test.Movie.2023.mkv",
                "size": 5000000000,
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movie_files()

        assert len(result) == 1
        assert isinstance(result[0], RadarrMovieFile)
        assert result[0].id == 456
        assert result[0].movie_id == 123
        assert result[0].path == "/movies/Test Movie (2023)/Test.Movie.2023.mkv"
        assert result[0].relative_path == "Test.Movie.2023.mkv"
        assert result[0].size == 5000000000

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_get_movie_files_http_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test HTTP error during movie file retrieval."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.HTTPError("Request failed")

        with pytest.raises(RadarrConnectionError, match="Failed to get movie files"):
            client.get_movie_files()


class TestRadarrClientBuildCache:
    """Tests for build_cache method."""

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_build_cache_success(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test successful cache building."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Movie response
        movie_response = MagicMock()
        movie_response.json.return_value = [
            {
                "id": 123,
                "title": "Test Movie",
                "year": 2023,
                "path": "/movies/Test Movie (2023)",
                "hasFile": True,
            }
        ]

        # Movie file response
        file_response = MagicMock()
        file_response.json.return_value = [
            {
                "id": 456,
                "movieId": 123,
                "path": "/movies/Test Movie (2023)/Test.mkv",
                "relativePath": "Test.mkv",
                "size": 1000,
            }
        ]

        mock_http_client.get.side_effect = [movie_response, file_response]

        cache = client.build_cache()

        assert 123 in cache.movies
        assert cache.movies[123].title == "Test Movie"
        # Path is normalized, so check the movie_id mapping exists
        assert len(cache.path_to_movie) == 1
        assert len(cache.files) == 1

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_build_cache_empty(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test building cache with no movies."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        movie_response = MagicMock()
        movie_response.json.return_value = []

        file_response = MagicMock()
        file_response.json.return_value = []

        mock_http_client.get.side_effect = [movie_response, file_response]

        cache = client.build_cache()

        assert cache.movies == {}
        assert cache.files == {}
        assert cache.path_to_movie == {}


class TestRadarrClientClose:
    """Tests for close method."""

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_close_with_client(
        self, mock_client_class: MagicMock, client: RadarrClient
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

    def test_close_without_client(self, client: RadarrClient):
        """Test closing when no client was created."""
        # Should not raise
        client.close()
        assert client._client is None

    @patch("video_policy_orchestrator.plugins.radarr_metadata.client.httpx.Client")
    def test_close_allows_new_client(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test that closing allows creating a new client."""
        mock_http_client1 = MagicMock()
        mock_http_client2 = MagicMock()
        mock_client_class.side_effect = [mock_http_client1, mock_http_client2]

        client._get_client()
        client.close()
        client._get_client()

        assert mock_client_class.call_count == 2
