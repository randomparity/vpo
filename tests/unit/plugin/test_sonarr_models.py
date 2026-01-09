"""Unit tests for Sonarr API models."""

import pytest

from vpo.plugins.sonarr_metadata.models import (
    SonarrCache,
    SonarrEpisode,
    SonarrLanguage,
    SonarrParseResult,
    SonarrSeries,
)


class TestSonarrLanguage:
    """Tests for SonarrLanguage dataclass."""

    def test_create_language(self):
        """Test creating a language instance."""
        lang = SonarrLanguage(id=1, name="English")
        assert lang.id == 1
        assert lang.name == "English"

    def test_language_is_frozen(self):
        """Test that SonarrLanguage is immutable."""
        lang = SonarrLanguage(id=1, name="English")
        with pytest.raises(AttributeError):
            lang.name = "French"  # type: ignore[misc]

    def test_language_equality(self):
        """Test equality comparison."""
        lang1 = SonarrLanguage(id=1, name="English")
        lang2 = SonarrLanguage(id=1, name="English")
        assert lang1 == lang2

    def test_language_hash(self):
        """Test that frozen dataclass is hashable."""
        lang = SonarrLanguage(id=1, name="English")
        # Should not raise
        hash(lang)
        # Can be used in sets
        lang_set = {lang}
        assert lang in lang_set


class TestSonarrSeries:
    """Tests for SonarrSeries dataclass."""

    def test_create_series_minimal(self):
        """Test creating a series with required fields only."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test Series",
        )
        assert series.id == 123
        assert series.title == "Test Series"
        assert series.year == 2020
        assert series.path == "/tv/Test Series"
        assert series.original_language is None
        assert series.imdb_id is None
        assert series.tvdb_id is None

    def test_create_series_full(self):
        """Test creating a series with all fields."""
        lang = SonarrLanguage(id=1, name="Japanese")
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test Series",
            original_language=lang,
            imdb_id="tt7654321",
            tvdb_id=987654,
        )
        assert series.original_language == lang
        assert series.imdb_id == "tt7654321"
        assert series.tvdb_id == 987654

    def test_series_is_frozen(self):
        """Test that SonarrSeries is immutable."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test Series",
        )
        with pytest.raises(AttributeError):
            series.title = "Changed"  # type: ignore[misc]


class TestSonarrEpisode:
    """Tests for SonarrEpisode dataclass."""

    def test_create_episode_minimal(self):
        """Test creating an episode with required fields."""
        episode = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=1,
            episode_number=5,
            title="Test Episode",
        )
        assert episode.id == 456
        assert episode.series_id == 123
        assert episode.season_number == 1
        assert episode.episode_number == 5
        assert episode.title == "Test Episode"
        assert episode.has_file is False

    def test_create_episode_with_file(self):
        """Test creating an episode that has a file."""
        episode = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=2,
            episode_number=10,
            title="Test Episode",
            has_file=True,
        )
        assert episode.has_file is True

    def test_episode_is_frozen(self):
        """Test that SonarrEpisode is immutable."""
        episode = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=1,
            episode_number=5,
            title="Test Episode",
        )
        with pytest.raises(AttributeError):
            episode.title = "Changed"  # type: ignore[misc]


class TestSonarrParseResult:
    """Tests for SonarrParseResult dataclass."""

    def test_create_parse_result_no_match(self):
        """Test creating a parse result with no match."""
        result = SonarrParseResult(
            series=None,
            episodes=(),
        )
        assert result.series is None
        assert result.episodes == ()

    def test_create_parse_result_with_match(self):
        """Test creating a parse result with a match."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test Series",
        )
        episode = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=1,
            episode_number=5,
            title="Test Episode",
        )
        result = SonarrParseResult(
            series=series,
            episodes=(episode,),
        )
        assert result.series == series
        assert len(result.episodes) == 1
        assert result.episodes[0] == episode

    def test_create_parse_result_multiple_episodes(self):
        """Test creating a parse result with multiple episodes (multi-episode file)."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test Series",
        )
        ep1 = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=1,
            episode_number=5,
            title="Episode 5",
        )
        ep2 = SonarrEpisode(
            id=457,
            series_id=123,
            season_number=1,
            episode_number=6,
            title="Episode 6",
        )
        result = SonarrParseResult(
            series=series,
            episodes=(ep1, ep2),
        )
        assert len(result.episodes) == 2

    def test_parse_result_is_frozen(self):
        """Test that SonarrParseResult is immutable."""
        result = SonarrParseResult(series=None, episodes=())
        with pytest.raises(AttributeError):
            result.series = None  # type: ignore[misc]


class TestSonarrCache:
    """Tests for SonarrCache dataclass."""

    def test_empty_cache(self):
        """Test creating an empty cache."""
        cache = SonarrCache.empty()
        assert cache.series == {}
        assert cache.parse_results == {}

    def test_lookup_by_path_found(self):
        """Test looking up a cached parse result."""
        series = SonarrSeries(
            id=123,
            title="Test Series",
            year=2020,
            path="/tv/Test Series",
        )
        episode = SonarrEpisode(
            id=456,
            series_id=123,
            season_number=1,
            episode_number=5,
            title="Test Episode",
        )
        result = SonarrParseResult(series=series, episodes=(episode,))

        cache = SonarrCache(
            series={123: series},
            parse_results={"/tv/Test Series/S01E05.mkv": result},
        )
        lookup = cache.lookup_by_path("/tv/Test Series/S01E05.mkv")
        assert lookup == result

    def test_lookup_by_path_not_found(self):
        """Test looking up a non-existent path."""
        cache = SonarrCache.empty()
        result = cache.lookup_by_path("/tv/unknown.mkv")
        assert result is None

    def test_cache_is_mutable(self):
        """Test that cache can be modified (not frozen)."""
        cache = SonarrCache.empty()
        series = SonarrSeries(
            id=123,
            title="Test",
            year=2020,
            path="/tv/Test",
        )
        cache.series[123] = series
        assert cache.series[123] == series

    def test_cache_stores_parse_results(self):
        """Test that parse results can be stored."""
        cache = SonarrCache.empty()
        result = SonarrParseResult(series=None, episodes=())
        cache.parse_results["/path/to/file.mkv"] = result
        assert cache.parse_results["/path/to/file.mkv"] == result
