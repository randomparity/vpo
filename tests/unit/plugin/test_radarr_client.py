"""Unit tests for Radarr API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from vpo.config.models import PluginConnectionConfig
from vpo.plugins.radarr_metadata.client import (
    RadarrAuthError,
    RadarrClient,
    RadarrConnectionError,
)
from vpo.plugins.radarr_metadata.models import (
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_get_status_connect_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test connection error raises RadarrConnectionError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(RadarrConnectionError, match="Cannot connect to Radarr"):
            client.get_status()

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_get_status_timeout_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test timeout raises RadarrConnectionError."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(RadarrConnectionError, match="Connection timeout"):
            client.get_status()

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_build_cache_success(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test successful cache building."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Tag response
        tag_response = MagicMock()
        tag_response.json.return_value = [
            {"id": 1, "label": "4k"},
            {"id": 2, "label": "hdr"},
        ]

        # Movie response
        movie_response = MagicMock()
        movie_response.json.return_value = [
            {
                "id": 123,
                "title": "Test Movie",
                "year": 2023,
                "path": "/movies/Test Movie (2023)",
                "hasFile": True,
                "tags": [1],
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

        mock_http_client.get.side_effect = [tag_response, movie_response, file_response]

        cache = client.build_cache()

        assert 123 in cache.movies
        assert cache.movies[123].title == "Test Movie"
        assert cache.movies[123].tags == "4k"
        assert cache.tags == {1: "4k", 2: "hdr"}
        # Path is normalized, so check the movie_id mapping exists
        assert len(cache.path_to_movie) == 1
        assert len(cache.files) == 1

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_build_cache_empty(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test building cache with no movies."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        tag_response = MagicMock()
        tag_response.json.return_value = []

        movie_response = MagicMock()
        movie_response.json.return_value = []

        file_response = MagicMock()
        file_response.json.return_value = []

        mock_http_client.get.side_effect = [tag_response, movie_response, file_response]

        cache = client.build_cache()

        assert cache.movies == {}
        assert cache.files == {}
        assert cache.path_to_movie == {}
        assert cache.tags == {}

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_build_cache_tag_failure_continues(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test that tag fetch failure doesn't prevent cache building."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Tag call fails, movie and file calls succeed
        tag_response = MagicMock()
        tag_response.raise_for_status.side_effect = httpx.HTTPError("Tag fetch failed")

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

        file_response = MagicMock()
        file_response.json.return_value = []

        mock_http_client.get.side_effect = [tag_response, movie_response, file_response]

        cache = client.build_cache()

        assert 123 in cache.movies
        assert cache.tags == {}


class TestRadarrClientGetTags:
    """Tests for get_tags method."""

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_get_tags_success(self, mock_client_class: MagicMock, client: RadarrClient):
        """Test successful tag retrieval."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": 1, "label": "4k"},
            {"id": 2, "label": "hdr"},
            {"id": 3, "label": "anime"},
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_tags()

        assert result == {1: "4k", 2: "hdr", 3: "anime"}
        mock_http_client.get.assert_called_once_with("/api/v3/tag")

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_get_tags_empty(self, mock_client_class: MagicMock, client: RadarrClient):
        """Test empty tag list."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_http_client.get.return_value = mock_response

        result = client.get_tags()

        assert result == {}

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_get_tags_http_error(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test HTTP error during tag retrieval."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = httpx.HTTPError("Request failed")

        with pytest.raises(RadarrConnectionError, match="Failed to get tags"):
            client.get_tags()

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_get_tags_skips_malformed_entries(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test that entries without id or label are skipped."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": 1, "label": "good"},
            {"id": 2},  # Missing label
            {"label": "orphan"},  # Missing id
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_tags()

        assert result == {1: "good"}


class TestRadarrClientExpandedParsing:
    """Tests for expanded movie and movie file parsing."""

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_genres_flattened(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test genre array is flattened to comma-separated string."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "title": "Test",
                "year": 2023,
                "path": "/movies/Test",
                "hasFile": True,
                "genres": ["Action", "Sci-Fi", "Thriller"],
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert result[0].genres == "Action, Sci-Fi, Thriller"

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_collection_name(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test collection name extracted from nested object."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "title": "Test",
                "year": 2023,
                "path": "/movies/Test",
                "hasFile": True,
                "collection": {"name": "Marvel Cinematic Universe", "tmdbId": 529892},
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert result[0].collection_name == "Marvel Cinematic Universe"

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_ratings_flattened(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test ratings flattened from nested objects."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "title": "Test",
                "year": 2023,
                "path": "/movies/Test",
                "hasFile": True,
                "ratings": {
                    "tmdb": {"value": 8.2, "votes": 10000},
                    "imdb": {"value": 7.9, "votes": 50000},
                },
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert result[0].rating_tmdb == 8.2
        assert result[0].rating_imdb == 7.9

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_tags_resolved(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test tag IDs resolved to names via tag map."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "title": "Test",
                "year": 2023,
                "path": "/movies/Test",
                "hasFile": True,
                "tags": [1, 3],
            }
        ]
        mock_http_client.get.return_value = mock_response

        tag_map = {1: "4k", 2: "hdr", 3: "anime"}
        result = client.get_movies(tag_map=tag_map)

        assert result[0].tags == "4k, anime"

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_all_new_fields(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test all new movie fields are parsed."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "title": "Test Movie",
                "year": 2023,
                "path": "/movies/Test",
                "hasFile": True,
                "certification": "PG-13",
                "genres": ["Action"],
                "runtime": 148,
                "status": "released",
                "studio": "Warner Bros.",
                "popularity": 42.5,
                "monitored": True,
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert result[0].certification == "PG-13"
        assert result[0].genres == "Action"
        assert result[0].runtime == 148
        assert result[0].status == "released"
        assert result[0].studio == "Warner Bros."
        assert result[0].popularity == 42.5
        assert result[0].monitored is True

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_missing_new_fields_default_none(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test missing new fields default to None."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "title": "Minimal",
                "year": 2023,
                "path": "/movies/Minimal",
                "hasFile": False,
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert result[0].certification is None
        assert result[0].genres is None
        assert result[0].runtime is None
        assert result[0].collection_name is None
        assert result[0].studio is None
        assert result[0].rating_tmdb is None
        assert result[0].rating_imdb is None
        assert result[0].tags is None

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_empty_certification_becomes_none(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test that empty string certification becomes None."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "title": "Test",
                "year": 2023,
                "path": "/movies/Test",
                "hasFile": True,
                "certification": "",
                "studio": "",
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movies()

        assert result[0].certification is None
        assert result[0].studio is None

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_file_new_fields(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test new movie file fields are parsed."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 456,
                "movieId": 123,
                "path": "/movies/Test/Test.mkv",
                "relativePath": "Test.mkv",
                "size": 5000000000,
                "edition": "Director's Cut",
                "releaseGroup": "SPARKS",
                "sceneName": "Test.Movie.2023.Directors.Cut.1080p.BluRay",
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movie_files()

        assert result[0].edition == "Director's Cut"
        assert result[0].release_group == "SPARKS"
        assert result[0].scene_name == "Test.Movie.2023.Directors.Cut.1080p.BluRay"

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
    def test_parse_movie_file_empty_strings_become_none(
        self, mock_client_class: MagicMock, client: RadarrClient
    ):
        """Test that empty string file fields become None."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 456,
                "movieId": 123,
                "path": "/movies/Test/Test.mkv",
                "relativePath": "Test.mkv",
                "size": 1000,
                "edition": "",
                "releaseGroup": "",
                "sceneName": "",
            }
        ]
        mock_http_client.get.return_value = mock_response

        result = client.get_movie_files()

        assert result[0].edition is None
        assert result[0].release_group is None
        assert result[0].scene_name is None


class TestRadarrClientClose:
    """Tests for close method."""

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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

    @patch("vpo.plugins.radarr_metadata.client.httpx.Client")
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
