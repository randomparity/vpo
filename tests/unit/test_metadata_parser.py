"""Unit tests for metadata filename parser."""

from pathlib import Path

from video_policy_orchestrator.metadata.parser import (
    ParsedMetadata,
    _clean_title,
    parse_filename,
    parse_movie_filename,
    parse_tv_filename,
)


class TestCleanTitle:
    """Tests for _clean_title helper function."""

    def test_dots_to_spaces(self):
        """Dots are converted to spaces."""
        assert _clean_title("Movie.Name.Here") == "Movie Name Here"

    def test_underscores_to_spaces(self):
        """Underscores are converted to spaces."""
        assert _clean_title("Movie_Name_Here") == "Movie Name Here"

    def test_mixed_separators(self):
        """Mixed dots and underscores are handled."""
        assert _clean_title("Movie.Name_Here") == "Movie Name Here"

    def test_multiple_dots_collapsed(self):
        """Multiple dots become single space."""
        assert _clean_title("Movie...Name") == "Movie Name"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is removed."""
        assert _clean_title("  Movie Name  ") == "Movie Name"

    def test_collapses_multiple_spaces(self):
        """Multiple spaces are collapsed to one."""
        assert _clean_title("Movie   Name") == "Movie Name"


class TestParsedMetadata:
    """Tests for ParsedMetadata dataclass."""

    def test_is_tv_show_with_season(self):
        """TV show detection with season number."""
        meta = ParsedMetadata(original_filename="test", season=1)
        assert meta.is_tv_show is True
        assert meta.is_movie is False

    def test_is_tv_show_with_episode(self):
        """TV show detection with episode number."""
        meta = ParsedMetadata(original_filename="test", episode=5)
        assert meta.is_tv_show is True
        assert meta.is_movie is False

    def test_is_movie_with_year(self):
        """Movie detection with year."""
        meta = ParsedMetadata(original_filename="test", year=2023)
        assert meta.is_movie is True
        assert meta.is_tv_show is False

    def test_tv_show_with_year_is_not_movie(self):
        """TV show with year is still a TV show, not a movie."""
        meta = ParsedMetadata(original_filename="test", year=2023, season=1)
        assert meta.is_tv_show is True
        assert meta.is_movie is False

    def test_as_dict_basic(self):
        """as_dict returns correct fields."""
        meta = ParsedMetadata(
            original_filename="test",
            title="Movie Name",
            year=2023,
        )
        d = meta.as_dict()
        assert d["title"] == "Movie Name"
        assert d["year"] == "2023"

    def test_as_dict_season_episode_formatting(self):
        """Season and episode are zero-padded."""
        meta = ParsedMetadata(original_filename="test", season=1, episode=5)
        d = meta.as_dict()
        assert d["season"] == "01"
        assert d["episode"] == "05"

    def test_as_dict_excludes_none_values(self):
        """None values are excluded from dict."""
        meta = ParsedMetadata(original_filename="test", title="Test")
        d = meta.as_dict()
        assert "year" not in d
        assert "season" not in d


class TestParseMovieFilename:
    """Tests for movie filename parsing."""

    def test_scene_naming_full(self):
        """Standard scene naming with all fields."""
        result = parse_movie_filename("Movie.Name.2023.1080p.BluRay.x264-GROUP")
        assert result is not None
        assert result.title == "Movie Name"
        assert result.year == 2023
        assert result.resolution == "1080p"
        assert result.source == "BluRay"
        assert result.codec == "x264"
        assert result.pattern_matched == "scene_movie"

    def test_scene_naming_minimal(self):
        """Scene naming with just title and year."""
        result = parse_movie_filename("Movie.Name.2023")
        assert result is not None
        assert result.title == "Movie Name"
        assert result.year == 2023
        assert result.pattern_matched == "scene_movie"

    def test_scene_naming_no_codec(self):
        """Scene naming without codec."""
        result = parse_movie_filename("Movie.Name.2023.1080p.BluRay")
        assert result is not None
        assert result.title == "Movie Name"
        assert result.year == 2023
        assert result.resolution == "1080p"
        assert result.source == "BluRay"

    def test_scene_naming_hevc(self):
        """Scene naming with HEVC codec."""
        result = parse_movie_filename("Movie.Name.2023.1080p.WEB-DL.HEVC")
        assert result is not None
        assert result.codec == "HEVC"

    def test_paren_format(self):
        """Movie Name (2023) format."""
        result = parse_movie_filename("Movie Name (2023)")
        assert result is not None
        assert result.title == "Movie Name"
        assert result.year == 2023
        assert result.pattern_matched == "paren_movie"

    def test_paren_format_with_resolution(self):
        """Movie Name (2023) [1080p] format."""
        result = parse_movie_filename("Movie Name (2023) [1080p]")
        assert result is not None
        assert result.title == "Movie Name"
        assert result.year == 2023
        assert result.resolution == "1080p"

    def test_simple_movie_format(self):
        """Simple Movie.Name.2023 format."""
        result = parse_movie_filename("Simple.Movie.2023")
        assert result is not None
        assert result.title == "Simple Movie"
        assert result.year == 2023

    def test_no_match_returns_none(self):
        """Non-matching filename returns None."""
        result = parse_movie_filename("random_file_name")
        assert result is None

    def test_confidence_with_year(self):
        """Confidence is higher when year is present."""
        result = parse_movie_filename("Movie.Name.2023")
        assert result is not None
        assert result.confidence == 0.8


class TestParseTVFilename:
    """Tests for TV show filename parsing."""

    def test_sxxexx_format(self):
        """Standard S01E02 format."""
        result = parse_tv_filename("Series.Name.S01E02.Episode.Title.720p.WEB-DL")
        assert result is not None
        assert result.series == "Series Name"
        assert result.season == 1
        assert result.episode == 2
        assert result.resolution == "720p"
        assert result.source == "WEB-DL"
        assert result.pattern_matched == "sxxexx"

    def test_sxxexx_minimal(self):
        """S01E02 format with minimal info."""
        result = parse_tv_filename("Series.Name.S01E02")
        assert result is not None
        assert result.series == "Series Name"
        assert result.season == 1
        assert result.episode == 2

    def test_dash_format(self):
        """Series Name - S01E02 - Episode Title format."""
        result = parse_tv_filename("Series Name - S01E02 - Episode Title")
        assert result is not None
        assert result.series == "Series Name"
        assert result.season == 1
        assert result.episode == 2
        assert result.title == "Episode Title"
        assert result.pattern_matched == "dash_sxxexx"

    def test_nxnn_format(self):
        """1x02 format."""
        result = parse_tv_filename("Series Name 1x02")
        assert result is not None
        assert result.series == "Series Name"
        assert result.season == 1
        assert result.episode == 2
        assert result.pattern_matched == "nxnn"

    def test_combined_format(self):
        """Combined 102 format (season 1, episode 02)."""
        result = parse_tv_filename("Series.Name.102")
        assert result is not None
        assert result.series == "Series Name"
        assert result.season == 1
        assert result.episode == 2
        assert result.pattern_matched == "combined"

    def test_double_digit_season_episode(self):
        """Double digit season and episode."""
        result = parse_tv_filename("Series.Name.S12E15.Episode.Title")
        assert result is not None
        assert result.season == 12
        assert result.episode == 15

    def test_three_digit_episode(self):
        """Three digit episode number."""
        result = parse_tv_filename("Series.Name.S01E100")
        assert result is not None
        assert result.episode == 100

    def test_no_match_returns_none(self):
        """Non-matching filename returns None."""
        result = parse_tv_filename("random_file_name")
        assert result is None

    def test_confidence_with_season_and_episode(self):
        """Confidence is high when both season and episode present."""
        result = parse_tv_filename("Series.Name.S01E02")
        assert result is not None
        assert result.confidence == 0.9


class TestParseFilename:
    """Tests for the main parse_filename function."""

    def test_path_object(self):
        """Accepts Path objects."""
        result = parse_filename(Path("/videos/Movie.Name.2023.mkv"))
        assert result.title == "Movie Name"
        assert result.year == 2023

    def test_string_path(self):
        """Accepts string paths."""
        result = parse_filename("/videos/Movie.Name.2023.mkv")
        assert result.title == "Movie Name"
        assert result.year == 2023

    def test_tv_show_priority(self):
        """TV show patterns are tried before movie patterns."""
        # This could match either, but TV pattern takes priority
        result = parse_filename("Show.2023.S01E01.mkv")
        assert result.is_tv_show is True

    def test_fallback_for_no_match(self):
        """Returns basic metadata when no pattern matches."""
        result = parse_filename("random_file.mkv")
        assert result.original_filename == "random_file"
        assert result.title == "random file"
        assert result.confidence == 0.0

    def test_extension_stripped(self):
        """File extension is stripped before parsing."""
        result = parse_filename("Movie.Name.2023.1080p.BluRay.x264.mkv")
        assert result.title == "Movie Name"
        assert result.year == 2023
        # The .mkv should not appear in any parsed field

    def test_additional_metadata_extraction(self):
        """Additional metadata is extracted from filename."""
        # Resolution not captured by pattern but found by secondary search
        result = parse_filename("Movie (2023) 1080p BluRay HEVC.mkv")
        assert result.year == 2023
        assert result.resolution == "1080p"
        assert result.source == "BluRay"
        assert result.codec == "hevc"

    def test_4k_resolution(self):
        """4K resolution is detected."""
        result = parse_filename("Movie (2023) 4K HDR.mkv")
        assert result.resolution == "4K"

    def test_codec_normalization_h264(self):
        """h.264 is normalized to h264."""
        result = parse_filename("Movie (2023) h.264.mkv")
        assert result.codec == "h264"

    def test_codec_normalization_h265(self):
        """h.265 and HEVC are normalized to hevc."""
        result = parse_filename("Movie (2023) h.265.mkv")
        assert result.codec == "hevc"


class TestEdgeCases:
    """Tests for edge cases and unusual filenames."""

    def test_year_in_title(self):
        """Movie with year-like number in title."""
        result = parse_filename("2001.A.Space.Odyssey.1968.1080p.mkv")
        assert result is not None
        # Should get the actual release year, not 2001
        assert result.year == 1968

    def test_special_characters_in_title(self):
        """Title with special characters."""
        result = parse_filename("The.Matrix.Reloaded.2003.mkv")
        assert result.title == "The Matrix Reloaded"

    def test_lowercase_extension(self):
        """Lowercase extension."""
        result = parse_filename("Movie.Name.2023.mkv")
        assert result.year == 2023

    def test_uppercase_extension(self):
        """Uppercase extension."""
        result = parse_filename("Movie.Name.2023.MKV")
        assert result.year == 2023

    def test_tv_show_with_year_in_series_name(self):
        """TV show with year in the series name."""
        result = parse_filename("The.2000s.S01E01.Episode.Title.mkv")
        assert result.is_tv_show is True
        assert result.series == "The 2000s"
        assert result.season == 1
        assert result.episode == 1
