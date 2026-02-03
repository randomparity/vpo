"""Unit tests for Radarr metadata plugin."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.config.models import PluginConnectionConfig
from vpo.plugin.events import FileScannedEvent
from vpo.plugin.interfaces import AnalyzerPlugin
from vpo.plugins.radarr_metadata.client import (
    RadarrAuthError,
    RadarrConnectionError,
)
from vpo.plugins.radarr_metadata.models import (
    RadarrCache,
    RadarrLanguage,
    RadarrMovie,
    RadarrMovieFile,
)
from vpo.plugins.radarr_metadata.plugin import (
    RadarrMetadataPlugin,
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
def mock_client():
    """Create a mock RadarrClient."""
    with patch("vpo.plugins.radarr_metadata.plugin.RadarrClient") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def plugin(config: PluginConnectionConfig, mock_client: MagicMock):
    """Create a RadarrMetadataPlugin with mocked client."""
    return RadarrMetadataPlugin(config)


@pytest.fixture
def sample_movie() -> RadarrMovie:
    """Create a sample movie for testing."""
    return RadarrMovie(
        id=123,
        title="Test Movie",
        original_title="Original Test",
        original_language=RadarrLanguage(id=1, name="English"),
        year=2023,
        path="/movies/Test Movie (2023)",
        has_file=True,
        imdb_id="tt1234567",
        tmdb_id=456789,
    )


@pytest.fixture
def sample_cache(sample_movie: RadarrMovie) -> RadarrCache:
    """Create a sample cache with a movie."""
    return RadarrCache(
        movies={123: sample_movie},
        files={},
        path_to_movie={"/movies/Test Movie (2023)/Test.mkv": 123},
    )


class TestRadarrMetadataPluginMetadata:
    """Tests for plugin metadata and attributes."""

    def test_plugin_name(self, plugin: RadarrMetadataPlugin):
        """Plugin has correct name."""
        assert plugin.name == "radarr-metadata"

    def test_plugin_version(self, plugin: RadarrMetadataPlugin):
        """Plugin has correct version."""
        assert plugin.version == "1.1.0"

    def test_plugin_events(self, plugin: RadarrMetadataPlugin):
        """Plugin subscribes to file.scanned event."""
        assert "file.scanned" in plugin.events


class TestRadarrMetadataPluginProtocols:
    """Tests for protocol compliance."""

    def test_implements_analyzer_protocol(self, plugin: RadarrMetadataPlugin):
        """Plugin implements AnalyzerPlugin protocol."""
        assert isinstance(plugin, AnalyzerPlugin)

    def test_has_required_analyzer_methods(self, plugin: RadarrMetadataPlugin):
        """Plugin has all required AnalyzerPlugin methods."""
        assert hasattr(plugin, "on_file_scanned")
        assert hasattr(plugin, "on_policy_evaluate")
        assert hasattr(plugin, "on_plan_complete")
        assert callable(plugin.on_file_scanned)
        assert callable(plugin.on_policy_evaluate)
        assert callable(plugin.on_plan_complete)


class TestRadarrMetadataPluginInit:
    """Tests for plugin initialization."""

    def test_init_validates_connection(self, config: PluginConnectionConfig):
        """Test that init validates connection."""
        with patch("vpo.plugins.radarr_metadata.plugin.RadarrClient") as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client

            RadarrMetadataPlugin(config)

            mock_client.validate_connection.assert_called_once()

    def test_init_auth_error_disables_plugin(self, config: PluginConnectionConfig):
        """Test that auth error disables plugin and re-raises."""
        with patch("vpo.plugins.radarr_metadata.plugin.RadarrClient") as mock_class:
            mock_client = MagicMock()
            mock_client.validate_connection.side_effect = RadarrAuthError("Invalid key")
            mock_class.return_value = mock_client

            with pytest.raises(RadarrAuthError):
                RadarrMetadataPlugin(config)

    def test_init_connection_error_raises(self, config: PluginConnectionConfig):
        """Test that connection error is re-raised."""
        with patch("vpo.plugins.radarr_metadata.plugin.RadarrClient") as mock_class:
            mock_client = MagicMock()
            mock_client.validate_connection.side_effect = RadarrConnectionError(
                "Connection refused"
            )
            mock_class.return_value = mock_client

            with pytest.raises(RadarrConnectionError):
                RadarrMetadataPlugin(config)


class TestRadarrMetadataPluginOnFileScanned:
    """Tests for on_file_scanned method."""

    def test_returns_none_when_disabled(
        self,
        config: PluginConnectionConfig,
        tmp_path: Path,
    ):
        """Test that disabled plugin returns None."""
        with patch("vpo.plugins.radarr_metadata.plugin.RadarrClient") as mock_class:
            mock_client = MagicMock()
            mock_client.validate_connection.side_effect = RadarrAuthError("Invalid key")
            mock_class.return_value = mock_client

            # Plugin creation will fail, but we want to test the disabled state
            # So we'll create a working plugin and then disable it
            mock_client2 = MagicMock()
            mock_class.return_value = mock_client2

            plugin = RadarrMetadataPlugin(config)
            plugin._disabled = True

            event = FileScannedEvent(
                file_path=tmp_path / "test.mkv",
                file_info=MagicMock(),
                tracks=[],
            )
            result = plugin.on_file_scanned(event)

            assert result is None

    def test_builds_cache_on_first_call(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        sample_cache: RadarrCache,
        tmp_path: Path,
    ):
        """Test that cache is built on first call."""
        mock_client.build_cache.return_value = sample_cache

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        plugin.on_file_scanned(event)

        mock_client.build_cache.assert_called_once()

    def test_returns_enrichment_when_movie_found(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        sample_movie: RadarrMovie,
        tmp_path: Path,
    ):
        """Test successful enrichment when movie is found."""
        # Create cache that will match the file path
        file_path = tmp_path / "movies" / "Test Movie (2023)" / "Test.mkv"
        normalized_path = str(file_path.resolve())

        cache = RadarrCache(
            movies={123: sample_movie},
            files={},
            path_to_movie={normalized_path: 123},
        )
        mock_client.build_cache.return_value = cache

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        assert result["external_source"] == "radarr"
        assert result["external_id"] == 123
        assert result["external_title"] == "Test Movie"
        assert result["external_year"] == 2023
        assert result["imdb_id"] == "tt1234567"
        assert result["tmdb_id"] == 456789

    def test_returns_none_when_movie_not_found(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that None is returned when movie is not found."""
        mock_client.build_cache.return_value = RadarrCache.empty()

        event = FileScannedEvent(
            file_path=tmp_path / "unknown.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is None

    def test_auth_error_disables_plugin(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that auth error during scan disables plugin."""
        mock_client.build_cache.side_effect = RadarrAuthError("Token expired")

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is None
        assert plugin._disabled is True

    def test_connection_error_returns_none(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that connection error returns None but doesn't disable."""
        mock_client.build_cache.side_effect = RadarrConnectionError("Timeout")

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is None
        assert plugin._disabled is False

    def test_unexpected_error_returns_none(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that unexpected errors are caught and return None."""
        mock_client.build_cache.side_effect = RuntimeError("Unexpected")

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is None


class TestRadarrMetadataPluginEnrichment:
    """Tests for enrichment data creation."""

    def test_enrichment_normalizes_language(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that language names are normalized to ISO codes."""
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title=None,
            original_language=RadarrLanguage(id=1, name="Japanese"),
            year=2023,
            path="/movies/Test",
            has_file=True,
        )

        file_path = tmp_path / "test.mkv"
        normalized_path = str(file_path.resolve())

        cache = RadarrCache(
            movies={123: movie},
            files={},
            path_to_movie={normalized_path: 123},
        )
        mock_client.build_cache.return_value = cache

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        # Japanese should be normalized to ISO code
        assert result["original_language"] == "jpn"

    def test_enrichment_handles_no_language(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test enrichment when movie has no original language."""
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title=None,
            original_language=None,
            year=2023,
            path="/movies/Test",
            has_file=True,
        )

        file_path = tmp_path / "test.mkv"
        normalized_path = str(file_path.resolve())

        cache = RadarrCache(
            movies={123: movie},
            files={},
            path_to_movie={normalized_path: 123},
        )
        mock_client.build_cache.return_value = cache

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        assert result["original_language"] is None

    def test_enrichment_handles_zero_year(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test enrichment when movie has year = 0."""
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title=None,
            original_language=None,
            year=0,
            path="/movies/Test",
            has_file=True,
        )

        file_path = tmp_path / "test.mkv"
        normalized_path = str(file_path.resolve())

        cache = RadarrCache(
            movies={123: movie},
            files={},
            path_to_movie={normalized_path: 123},
        )
        mock_client.build_cache.return_value = cache

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        # external_year is omitted when None (not included in dict)
        assert "external_year" not in result


class TestRadarrMetadataPluginExpandedEnrichment:
    """Tests for v1.1.0 expanded enrichment fields."""

    def test_enrichment_includes_new_movie_fields(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that new v1.1.0 fields appear in enrichment dict."""
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title="Test Film Original",
            original_language=RadarrLanguage(id=1, name="English"),
            year=2023,
            path="/movies/Test",
            has_file=True,
            certification="R",
            genres="Action, Thriller",
            runtime=148,
            status="released",
            collection_name="Test Collection",
            studio="Test Studio",
            rating_tmdb=8.2,
            rating_imdb=7.9,
            popularity=42.5,
            monitored=True,
            tags="4k, hdr",
        )

        file_path = tmp_path / "test.mkv"
        normalized_path = str(file_path.resolve())

        cache = RadarrCache(
            movies={123: movie},
            files={},
            path_to_movie={normalized_path: 123},
        )
        mock_client.build_cache.return_value = cache

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        assert result["original_title"] == "Test Film Original"
        assert result["certification"] == "R"
        assert result["genres"] == "Action, Thriller"
        assert result["runtime"] == 148
        assert result["status"] == "released"
        assert result["collection_name"] == "Test Collection"
        assert result["studio"] == "Test Studio"
        assert result["rating_tmdb"] == 8.2
        assert result["rating_imdb"] == 7.9
        assert result["popularity"] == 42.5
        assert result["monitored"] is True
        assert result["tags"] == "4k, hdr"

    def test_enrichment_includes_movie_file_fields(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that movie file fields (edition, release_group, scene_name) appear."""
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title=None,
            original_language=None,
            year=2023,
            path="/movies/Test",
            has_file=True,
        )
        movie_file = RadarrMovieFile(
            id=456,
            movie_id=123,
            path="/movies/Test/Test.mkv",
            relative_path="Test.mkv",
            size=5000000000,
            edition="Director's Cut",
            release_group="SPARKS",
            scene_name="Test.Movie.2023.DC.1080p",
        )

        file_path = tmp_path / "test.mkv"
        normalized_path = str(file_path.resolve())

        cache = RadarrCache(
            movies={123: movie},
            files={normalized_path: movie_file},
            path_to_movie={normalized_path: 123},
        )
        mock_client.build_cache.return_value = cache

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        assert result["edition"] == "Director's Cut"
        assert result["release_group"] == "SPARKS"
        assert result["scene_name"] == "Test.Movie.2023.DC.1080p"

    def test_enrichment_omits_none_new_fields(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that None v1.1.0 fields are omitted from dict."""
        movie = RadarrMovie(
            id=123,
            title="Minimal Movie",
            original_title=None,
            original_language=None,
            year=2023,
            path="/movies/Test",
            has_file=True,
        )

        file_path = tmp_path / "test.mkv"
        normalized_path = str(file_path.resolve())

        cache = RadarrCache(
            movies={123: movie},
            files={},
            path_to_movie={normalized_path: 123},
        )
        mock_client.build_cache.return_value = cache

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        assert "certification" not in result
        assert "genres" not in result
        assert "runtime" not in result
        assert "collection_name" not in result
        assert "studio" not in result
        assert "rating_tmdb" not in result
        assert "rating_imdb" not in result
        assert "tags" not in result
        assert "edition" not in result
        assert "release_group" not in result
        assert "scene_name" not in result


class TestRadarrMetadataPluginOtherMethods:
    """Tests for other AnalyzerPlugin methods."""

    def test_on_policy_evaluate_does_nothing(self, plugin: RadarrMetadataPlugin):
        """Test that on_policy_evaluate is a no-op."""
        mock_event = MagicMock()
        # Should not raise
        plugin.on_policy_evaluate(mock_event)

    def test_on_plan_complete_does_nothing(self, plugin: RadarrMetadataPlugin):
        """Test that on_plan_complete is a no-op."""
        mock_event = MagicMock()
        # Should not raise
        plugin.on_plan_complete(mock_event)


class TestRadarrMetadataPluginClose:
    """Tests for plugin close method."""

    def test_close_closes_client(
        self,
        plugin: RadarrMetadataPlugin,
        mock_client: MagicMock,
    ):
        """Test that close() closes the HTTP client."""
        plugin.close()

        mock_client.close.assert_called_once()
