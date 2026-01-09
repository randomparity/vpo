"""Unit tests for Radarr API models."""

import pytest

from vpo.plugins.radarr_metadata.models import (
    RadarrCache,
    RadarrLanguage,
    RadarrMovie,
    RadarrMovieFile,
)


class TestRadarrLanguage:
    """Tests for RadarrLanguage dataclass."""

    def test_create_language(self):
        """Test creating a language instance."""
        lang = RadarrLanguage(id=1, name="English")
        assert lang.id == 1
        assert lang.name == "English"

    def test_language_is_frozen(self):
        """Test that RadarrLanguage is immutable."""
        lang = RadarrLanguage(id=1, name="English")
        with pytest.raises(AttributeError):
            lang.name = "French"  # type: ignore[misc]

    def test_language_equality(self):
        """Test equality comparison."""
        lang1 = RadarrLanguage(id=1, name="English")
        lang2 = RadarrLanguage(id=1, name="English")
        assert lang1 == lang2

    def test_language_hash(self):
        """Test that frozen dataclass is hashable."""
        lang = RadarrLanguage(id=1, name="English")
        # Should not raise
        hash(lang)
        # Can be used in sets
        lang_set = {lang}
        assert lang in lang_set


class TestRadarrMovie:
    """Tests for RadarrMovie dataclass."""

    def test_create_movie_minimal(self):
        """Test creating a movie with required fields only."""
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title=None,
            original_language=None,
            year=2023,
            path="/movies/Test Movie (2023)",
            has_file=True,
        )
        assert movie.id == 123
        assert movie.title == "Test Movie"
        assert movie.original_title is None
        assert movie.original_language is None
        assert movie.year == 2023
        assert movie.path == "/movies/Test Movie (2023)"
        assert movie.has_file is True
        assert movie.imdb_id is None
        assert movie.tmdb_id is None

    def test_create_movie_full(self):
        """Test creating a movie with all fields."""
        lang = RadarrLanguage(id=1, name="English")
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title="Original Test Movie",
            original_language=lang,
            year=2023,
            path="/movies/Test Movie (2023)",
            has_file=True,
            imdb_id="tt1234567",
            tmdb_id=456789,
        )
        assert movie.original_title == "Original Test Movie"
        assert movie.original_language == lang
        assert movie.imdb_id == "tt1234567"
        assert movie.tmdb_id == 456789

    def test_movie_is_frozen(self):
        """Test that RadarrMovie is immutable."""
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title=None,
            original_language=None,
            year=2023,
            path="/movies/Test Movie (2023)",
            has_file=True,
        )
        with pytest.raises(AttributeError):
            movie.title = "Changed"  # type: ignore[misc]


class TestRadarrMovieFile:
    """Tests for RadarrMovieFile dataclass."""

    def test_create_movie_file(self):
        """Test creating a movie file instance."""
        movie_file = RadarrMovieFile(
            id=456,
            movie_id=123,
            path="/movies/Test Movie (2023)/Test.Movie.2023.mkv",
            relative_path="Test.Movie.2023.mkv",
            size=5_000_000_000,
        )
        assert movie_file.id == 456
        assert movie_file.movie_id == 123
        assert movie_file.path == "/movies/Test Movie (2023)/Test.Movie.2023.mkv"
        assert movie_file.relative_path == "Test.Movie.2023.mkv"
        assert movie_file.size == 5_000_000_000

    def test_movie_file_is_frozen(self):
        """Test that RadarrMovieFile is immutable."""
        movie_file = RadarrMovieFile(
            id=456,
            movie_id=123,
            path="/movies/Test.mkv",
            relative_path="Test.mkv",
            size=1000,
        )
        with pytest.raises(AttributeError):
            movie_file.size = 2000  # type: ignore[misc]


class TestRadarrCache:
    """Tests for RadarrCache dataclass."""

    def test_empty_cache(self):
        """Test creating an empty cache."""
        cache = RadarrCache.empty()
        assert cache.movies == {}
        assert cache.files == {}
        assert cache.path_to_movie == {}

    def test_lookup_by_path_found(self):
        """Test looking up a movie by file path."""
        movie = RadarrMovie(
            id=123,
            title="Test Movie",
            original_title=None,
            original_language=None,
            year=2023,
            path="/movies/Test Movie (2023)",
            has_file=True,
        )
        cache = RadarrCache(
            movies={123: movie},
            files={},
            path_to_movie={"/movies/Test.mkv": 123},
        )
        result = cache.lookup_by_path("/movies/Test.mkv")
        assert result == movie

    def test_lookup_by_path_not_found(self):
        """Test looking up a non-existent path."""
        cache = RadarrCache.empty()
        result = cache.lookup_by_path("/movies/nonexistent.mkv")
        assert result is None

    def test_lookup_by_path_orphaned_file(self):
        """Test looking up a file that references a non-existent movie."""
        cache = RadarrCache(
            movies={},  # No movies
            files={},
            path_to_movie={"/movies/Test.mkv": 999},  # References missing movie
        )
        result = cache.lookup_by_path("/movies/Test.mkv")
        assert result is None

    def test_cache_is_mutable(self):
        """Test that cache can be modified (not frozen)."""
        cache = RadarrCache.empty()
        movie = RadarrMovie(
            id=1,
            title="Test",
            original_title=None,
            original_language=None,
            year=2023,
            path="/test",
            has_file=True,
        )
        cache.movies[1] = movie
        assert cache.movies[1] == movie
