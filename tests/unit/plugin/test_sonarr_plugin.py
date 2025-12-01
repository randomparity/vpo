"""Unit tests for Sonarr metadata plugin."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.config.models import PluginConnectionConfig
from video_policy_orchestrator.plugin.events import FileScannedEvent
from video_policy_orchestrator.plugin.interfaces import AnalyzerPlugin
from video_policy_orchestrator.plugins.sonarr_metadata.client import (
    SonarrAuthError,
    SonarrConnectionError,
)
from video_policy_orchestrator.plugins.sonarr_metadata.models import (
    SonarrEpisode,
    SonarrLanguage,
    SonarrParseResult,
    SonarrSeries,
)
from video_policy_orchestrator.plugins.sonarr_metadata.plugin import (
    SonarrMetadataPlugin,
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
def mock_client():
    """Create a mock SonarrClient."""
    with patch(
        "video_policy_orchestrator.plugins.sonarr_metadata.plugin.SonarrClient"
    ) as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def plugin(config: PluginConnectionConfig, mock_client: MagicMock):
    """Create a SonarrMetadataPlugin with mocked client."""
    return SonarrMetadataPlugin(config)


@pytest.fixture
def sample_series() -> SonarrSeries:
    """Create a sample series for testing."""
    return SonarrSeries(
        id=123,
        title="Test Series",
        year=2020,
        path="/tv/Test Series",
        original_language=SonarrLanguage(id=1, name="English"),
        imdb_id="tt7654321",
        tvdb_id=987654,
    )


@pytest.fixture
def sample_episode() -> SonarrEpisode:
    """Create a sample episode for testing."""
    return SonarrEpisode(
        id=456,
        series_id=123,
        season_number=1,
        episode_number=5,
        title="Test Episode",
        has_file=True,
    )


@pytest.fixture
def sample_parse_result(
    sample_series: SonarrSeries,
    sample_episode: SonarrEpisode,
) -> SonarrParseResult:
    """Create a sample parse result."""
    return SonarrParseResult(
        series=sample_series,
        episodes=(sample_episode,),
    )


class TestSonarrMetadataPluginMetadata:
    """Tests for plugin metadata and attributes."""

    def test_plugin_name(self, plugin: SonarrMetadataPlugin):
        """Plugin has correct name."""
        assert plugin.name == "sonarr-metadata"

    def test_plugin_version(self, plugin: SonarrMetadataPlugin):
        """Plugin has correct version."""
        assert plugin.version == "1.0.0"

    def test_plugin_events(self, plugin: SonarrMetadataPlugin):
        """Plugin subscribes to file.scanned event."""
        assert "file.scanned" in plugin.events


class TestSonarrMetadataPluginProtocols:
    """Tests for protocol compliance."""

    def test_implements_analyzer_protocol(self, plugin: SonarrMetadataPlugin):
        """Plugin implements AnalyzerPlugin protocol."""
        assert isinstance(plugin, AnalyzerPlugin)

    def test_has_required_analyzer_methods(self, plugin: SonarrMetadataPlugin):
        """Plugin has all required AnalyzerPlugin methods."""
        assert hasattr(plugin, "on_file_scanned")
        assert hasattr(plugin, "on_policy_evaluate")
        assert hasattr(plugin, "on_plan_complete")
        assert callable(plugin.on_file_scanned)
        assert callable(plugin.on_policy_evaluate)
        assert callable(plugin.on_plan_complete)


class TestSonarrMetadataPluginInit:
    """Tests for plugin initialization."""

    def test_init_validates_connection(self, config: PluginConnectionConfig):
        """Test that init validates connection."""
        with patch(
            "video_policy_orchestrator.plugins.sonarr_metadata.plugin.SonarrClient"
        ) as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client

            SonarrMetadataPlugin(config)

            mock_client.validate_connection.assert_called_once()

    def test_init_auth_error_disables_plugin(self, config: PluginConnectionConfig):
        """Test that auth error disables plugin and re-raises."""
        with patch(
            "video_policy_orchestrator.plugins.sonarr_metadata.plugin.SonarrClient"
        ) as mock_class:
            mock_client = MagicMock()
            mock_client.validate_connection.side_effect = SonarrAuthError("Invalid key")
            mock_class.return_value = mock_client

            with pytest.raises(SonarrAuthError):
                SonarrMetadataPlugin(config)

    def test_init_connection_error_raises(self, config: PluginConnectionConfig):
        """Test that connection error is re-raised."""
        with patch(
            "video_policy_orchestrator.plugins.sonarr_metadata.plugin.SonarrClient"
        ) as mock_class:
            mock_client = MagicMock()
            mock_client.validate_connection.side_effect = SonarrConnectionError(
                "Connection refused"
            )
            mock_class.return_value = mock_client

            with pytest.raises(SonarrConnectionError):
                SonarrMetadataPlugin(config)


class TestSonarrMetadataPluginOnFileScanned:
    """Tests for on_file_scanned method."""

    def test_returns_none_when_disabled(
        self,
        config: PluginConnectionConfig,
        tmp_path: Path,
    ):
        """Test that disabled plugin returns None."""
        with patch(
            "video_policy_orchestrator.plugins.sonarr_metadata.plugin.SonarrClient"
        ) as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client

            plugin = SonarrMetadataPlugin(config)
            plugin._disabled = True

            event = FileScannedEvent(
                file_path=tmp_path / "test.mkv",
                file_info=MagicMock(),
                tracks=[],
            )
            result = plugin.on_file_scanned(event)

            assert result is None

    def test_checks_cache_first(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        sample_parse_result: SonarrParseResult,
        tmp_path: Path,
    ):
        """Test that cache is checked before calling parse."""
        file_path = tmp_path / "test.mkv"
        normalized_path = str(file_path.resolve())

        # Pre-populate cache
        plugin._cache.parse_results[normalized_path] = sample_parse_result
        plugin._cache.series[123] = sample_parse_result.series

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        # Should not call parse since result was cached
        mock_client.parse.assert_not_called()
        assert result is not None

    def test_calls_parse_when_not_cached(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        sample_parse_result: SonarrParseResult,
        tmp_path: Path,
    ):
        """Test that parse is called when path is not cached."""
        mock_client.parse.return_value = sample_parse_result

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        plugin.on_file_scanned(event)

        mock_client.parse.assert_called_once()

    def test_caches_parse_result(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        sample_parse_result: SonarrParseResult,
        tmp_path: Path,
    ):
        """Test that parse results are cached."""
        mock_client.parse.return_value = sample_parse_result
        file_path = tmp_path / "test.mkv"
        normalized_path = str(file_path.resolve())

        event = FileScannedEvent(
            file_path=file_path,
            file_info=MagicMock(),
            tracks=[],
        )
        plugin.on_file_scanned(event)

        assert normalized_path in plugin._cache.parse_results
        assert 123 in plugin._cache.series

    def test_returns_enrichment_when_series_found(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        sample_parse_result: SonarrParseResult,
        tmp_path: Path,
    ):
        """Test successful enrichment when series is found."""
        mock_client.parse.return_value = sample_parse_result

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        assert result["external_source"] == "sonarr"
        assert result["external_id"] == 123
        assert result["external_title"] == "Test Series"
        assert result["external_year"] == 2020
        assert result["imdb_id"] == "tt7654321"
        assert result["tvdb_id"] == 987654
        # TV-specific fields
        assert result["series_title"] == "Test Series"
        assert result["season_number"] == 1
        assert result["episode_number"] == 5
        assert result["episode_title"] == "Test Episode"

    def test_returns_none_when_series_not_found(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that None is returned when series is not found."""
        mock_client.parse.return_value = SonarrParseResult(series=None, episodes=())

        event = FileScannedEvent(
            file_path=tmp_path / "unknown.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is None

    def test_auth_error_disables_plugin(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that auth error during scan disables plugin."""
        mock_client.parse.side_effect = SonarrAuthError("Token expired")

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
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that connection error returns None but doesn't disable."""
        mock_client.parse.side_effect = SonarrConnectionError("Timeout")

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
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that unexpected errors are caught and return None."""
        mock_client.parse.side_effect = RuntimeError("Unexpected")

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is None


class TestSonarrMetadataPluginEnrichment:
    """Tests for enrichment data creation."""

    def test_enrichment_normalizes_language(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test that language names are normalized to ISO codes."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test",
            original_language=SonarrLanguage(id=2, name="Japanese"),
        )
        episode = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=1,
            episode_number=1,
            title="Test",
        )
        mock_client.parse.return_value = SonarrParseResult(
            series=series,
            episodes=(episode,),
        )

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        # Japanese should be normalized to ISO code
        assert result["original_language"] == "jpn"

    def test_enrichment_handles_no_language(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test enrichment when series has no original language."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test",
            original_language=None,
        )
        episode = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=1,
            episode_number=1,
            title="Test",
        )
        mock_client.parse.return_value = SonarrParseResult(
            series=series,
            episodes=(episode,),
        )

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        assert result["original_language"] is None

    def test_enrichment_handles_zero_year(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test enrichment when series has year = 0."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=0,
            path="/tv/Test",
        )
        episode = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=1,
            episode_number=1,
            title="Test",
        )
        mock_client.parse.return_value = SonarrParseResult(
            series=series,
            episodes=(episode,),
        )

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        # external_year is omitted when None (not included in dict)
        assert "external_year" not in result

    def test_enrichment_handles_no_episodes(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
        tmp_path: Path,
    ):
        """Test enrichment when series is found but no episodes."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test",
        )
        mock_client.parse.return_value = SonarrParseResult(
            series=series,
            episodes=(),  # No episodes
        )

        event = FileScannedEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            tracks=[],
        )
        result = plugin.on_file_scanned(event)

        assert result is not None
        assert result["series_title"] == "Test Series"
        # TV-specific fields are omitted when None (not included in dict)
        assert "season_number" not in result
        assert "episode_number" not in result
        assert "episode_title" not in result


class TestSonarrMetadataPluginOtherMethods:
    """Tests for other AnalyzerPlugin methods."""

    def test_on_policy_evaluate_does_nothing(self, plugin: SonarrMetadataPlugin):
        """Test that on_policy_evaluate is a no-op."""
        mock_event = MagicMock()
        # Should not raise
        plugin.on_policy_evaluate(mock_event)

    def test_on_plan_complete_does_nothing(self, plugin: SonarrMetadataPlugin):
        """Test that on_plan_complete is a no-op."""
        mock_event = MagicMock()
        # Should not raise
        plugin.on_plan_complete(mock_event)


class TestSonarrMetadataPluginClose:
    """Tests for plugin close method."""

    def test_close_closes_client(
        self,
        plugin: SonarrMetadataPlugin,
        mock_client: MagicMock,
    ):
        """Test that close() closes the HTTP client."""
        plugin.close()

        mock_client.close.assert_called_once()
