"""Tests for core formatting utilities."""

from vpo.core.formatting import (
    format_audio_languages,
    format_file_size,
    get_resolution_label,
    truncate_filename,
)


class TestGetResolutionLabel:
    """Tests for get_resolution_label function."""

    def test_4k_resolution(self):
        """get_resolution_label returns '4K' for 2160p and above."""
        assert get_resolution_label(3840, 2160) == "4K"
        assert get_resolution_label(4096, 2160) == "4K"
        assert get_resolution_label(3840, 2400) == "4K"

    def test_1440p_resolution(self):
        """get_resolution_label returns '1440p' for 1440p content."""
        assert get_resolution_label(2560, 1440) == "1440p"
        assert get_resolution_label(2560, 1500) == "1440p"

    def test_1080p_resolution(self):
        """get_resolution_label returns '1080p' for 1080p content."""
        assert get_resolution_label(1920, 1080) == "1080p"
        assert get_resolution_label(1920, 1200) == "1080p"

    def test_720p_resolution(self):
        """get_resolution_label returns '720p' for 720p content."""
        assert get_resolution_label(1280, 720) == "720p"
        assert get_resolution_label(1280, 800) == "720p"

    def test_480p_resolution(self):
        """get_resolution_label returns '480p' for 480p content."""
        assert get_resolution_label(720, 480) == "480p"
        assert get_resolution_label(854, 480) == "480p"
        assert get_resolution_label(640, 500) == "480p"

    def test_below_480p(self):
        """get_resolution_label returns height with 'p' for below 480p."""
        assert get_resolution_label(320, 240) == "240p"
        assert get_resolution_label(640, 360) == "360p"
        assert get_resolution_label(480, 320) == "320p"

    def test_width_none_returns_em_dash(self):
        """get_resolution_label returns em-dash when width is None."""
        assert get_resolution_label(None, 1080) == "\u2014"

    def test_height_none_returns_em_dash(self):
        """get_resolution_label returns em-dash when height is None."""
        assert get_resolution_label(1920, None) == "\u2014"

    def test_both_none_returns_em_dash(self):
        """get_resolution_label returns em-dash when both are None."""
        assert get_resolution_label(None, None) == "\u2014"

    def test_height_zero_returns_em_dash(self):
        """get_resolution_label returns em-dash when height is 0."""
        assert get_resolution_label(1920, 0) == "\u2014"

    def test_boundary_between_1080p_and_1440p(self):
        """get_resolution_label handles boundary between 1080p and 1440p."""
        # 1079 is below the 1080 threshold, so it's "720p"
        assert get_resolution_label(2560, 1079) == "720p"
        # 1080 is the threshold for "1080p"
        assert get_resolution_label(2560, 1080) == "1080p"
        # 1439 is below 1440 threshold, still "1080p"
        assert get_resolution_label(2560, 1439) == "1080p"
        # 1440 is the threshold for "1440p"
        assert get_resolution_label(2560, 1440) == "1440p"

    def test_boundary_between_720p_and_1080p(self):
        """get_resolution_label handles boundary between 720p and 1080p."""
        # 719 is below 720 threshold, so it's "480p"
        assert get_resolution_label(1920, 719) == "480p"
        # 720 is the threshold for "720p"
        assert get_resolution_label(1920, 720) == "720p"
        # 1079 is below 1080 threshold, still "720p"
        assert get_resolution_label(1920, 1079) == "720p"


class TestFormatAudioLanguages:
    """Tests for format_audio_languages function."""

    def test_none_returns_em_dash(self):
        """format_audio_languages returns em-dash for None input."""
        assert format_audio_languages(None) == "\u2014"

    def test_empty_string_returns_em_dash(self):
        """format_audio_languages returns em-dash for empty string."""
        assert format_audio_languages("") == "\u2014"

    def test_single_language(self):
        """format_audio_languages formats single language."""
        assert format_audio_languages("eng") == "eng"

    def test_two_languages(self):
        """format_audio_languages formats two languages."""
        assert format_audio_languages("eng,jpn") == "eng, jpn"

    def test_three_languages(self):
        """format_audio_languages formats three languages."""
        assert format_audio_languages("eng,jpn,fra") == "eng, jpn, fra"

    def test_four_languages_truncates(self):
        """format_audio_languages truncates when more than 3 languages."""
        result = format_audio_languages("eng,jpn,fra,deu")
        assert result == "eng, jpn, fra +1 more"

    def test_five_languages_truncates(self):
        """format_audio_languages shows +N more for 5+ languages."""
        result = format_audio_languages("eng,jpn,fra,deu,spa")
        assert result == "eng, jpn, fra +2 more"

    def test_strips_whitespace_from_languages(self):
        """format_audio_languages strips whitespace from each language."""
        result = format_audio_languages(" eng , jpn ")
        assert result == "eng, jpn"

    def test_filters_empty_entries(self):
        """format_audio_languages filters out empty entries."""
        result = format_audio_languages("eng,,jpn,")
        assert result == "eng, jpn"

    def test_only_whitespace_entries(self):
        """format_audio_languages returns em-dash for whitespace-only entries."""
        result = format_audio_languages(" , , ")
        assert result == "\u2014"

    def test_mixed_whitespace_and_valid(self):
        """format_audio_languages handles mixed whitespace and valid entries."""
        result = format_audio_languages("eng, , jpn, ")
        assert result == "eng, jpn"


class TestFormatFileSize:
    """Tests for format_file_size function."""

    def test_bytes_range(self):
        """format_file_size formats bytes correctly."""
        assert format_file_size(0) == "0 B"
        assert format_file_size(1) == "1 B"
        assert format_file_size(512) == "512 B"
        assert format_file_size(1023) == "1023 B"

    def test_kilobytes_range(self):
        """format_file_size formats kilobytes correctly."""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(2048) == "2.0 KB"
        assert format_file_size(1024 * 1000) == "1000.0 KB"

    def test_megabytes_range(self):
        """format_file_size formats megabytes correctly."""
        assert format_file_size(1024**2) == "1.0 MB"
        assert format_file_size(int(1.5 * 1024**2)) == "1.5 MB"
        assert format_file_size(128 * 1024**2) == "128.0 MB"

    def test_gigabytes_range(self):
        """format_file_size formats gigabytes correctly."""
        assert format_file_size(1024**3) == "1.0 GB"
        assert format_file_size(int(4.2 * 1024**3)) == "4.2 GB"
        assert format_file_size(10 * 1024**3) == "10.0 GB"

    def test_large_gigabytes(self):
        """format_file_size handles large gigabyte values."""
        assert format_file_size(100 * 1024**3) == "100.0 GB"
        assert format_file_size(1024 * 1024**3) == "1024.0 GB"

    def test_boundary_kb_to_mb(self):
        """format_file_size handles boundary between KB and MB."""
        # Just under 1MB
        assert format_file_size(1024**2 - 1).endswith("KB")
        # Exactly 1MB
        assert format_file_size(1024**2) == "1.0 MB"

    def test_boundary_mb_to_gb(self):
        """format_file_size handles boundary between MB and GB."""
        # Just under 1GB
        assert format_file_size(1024**3 - 1).endswith("MB")
        # Exactly 1GB
        assert format_file_size(1024**3) == "1.0 GB"

    def test_one_decimal_precision(self):
        """format_file_size uses one decimal place precision."""
        # 1.23 GB should be formatted as 1.2 GB
        size = int(1.23 * 1024**3)
        result = format_file_size(size)
        assert result == "1.2 GB"


class TestTruncateFilename:
    """Tests for truncate_filename function."""

    def test_short_filename_unchanged(self):
        """truncate_filename returns short filenames unchanged."""
        assert truncate_filename("short.mp4", 40) == "short.mp4"
        assert truncate_filename("movie.mkv", 40) == "movie.mkv"

    def test_exact_length_unchanged(self):
        """truncate_filename returns filename at exact max length unchanged."""
        filename = "a" * 36 + ".mkv"  # 40 chars total
        assert truncate_filename(filename, 40) == filename

    def test_truncation_preserves_extension(self):
        """truncate_filename preserves the file extension."""
        result = truncate_filename("some-very-long-movie-name.mkv", 20)
        assert result.endswith(".mkv")
        assert "…" in result

    def test_truncation_shows_beginning(self):
        """truncate_filename shows the beginning of the filename."""
        result = truncate_filename("abcdefghij-long-name.mkv", 15)
        assert result.startswith("a")
        assert result.endswith(".mkv")
        assert "…" in result

    def test_uses_single_ellipsis_character(self):
        """truncate_filename uses U+2026 ellipsis character."""
        result = truncate_filename("very-long-filename.mkv", 15)
        assert "…" in result
        assert "..." not in result

    def test_no_extension(self):
        """truncate_filename handles files without extension."""
        result = truncate_filename("somefile", 5)
        assert result == "some…"
        assert len(result) == 5

    def test_empty_filename_returns_empty(self):
        """truncate_filename returns empty string for empty input."""
        assert truncate_filename("", 40) == ""

    def test_none_returns_none(self):
        """truncate_filename returns None for None input."""
        assert truncate_filename(None, 40) is None

    def test_very_long_extension_falls_back(self):
        """truncate_filename falls back to simple truncation for long extensions."""
        # Extension is longer than max_length - 1
        result = truncate_filename("file.verylongextension", 10)
        assert len(result) == 10
        assert result.endswith("…")

    def test_exact_truncation_length(self):
        """truncate_filename produces result of correct length."""
        result = truncate_filename("some-very-long-movie-name.mkv", 20)
        assert len(result) == 20

    def test_default_max_length(self):
        """truncate_filename uses default max_length of 40."""
        # A filename longer than 40 chars should be truncated
        long_name = "a" * 50 + ".mkv"
        result = truncate_filename(long_name)
        assert len(result) == 40

    def test_dot_at_beginning_not_extension(self):
        """truncate_filename does not treat leading dot as extension separator."""
        # .hidden should have the dot as part of the base, no extension
        result = truncate_filename(".hiddenfilename", 10)
        assert result == ".hiddenfi…"

    def test_multiple_dots_uses_last(self):
        """truncate_filename uses last dot for extension."""
        result = truncate_filename("file.name.with.dots.mkv", 20)
        assert result.endswith(".mkv")

    def test_extension_with_numbers(self):
        """truncate_filename handles extensions with numbers."""
        result = truncate_filename("movie-name.mp4", 12)
        assert result.endswith(".mp4")

    def test_boundary_available_for_base_is_one(self):
        """truncate_filename handles case where base gets exactly 1 char."""
        # Extension is 4 chars (.mkv), ellipsis is 1 char
        # So max_length 6 gives 1 char for base
        result = truncate_filename("abcdef.mkv", 6)
        assert result == "a….mkv"
        assert len(result) == 6

    def test_boundary_available_for_base_is_zero(self):
        """truncate_filename handles case where no room for base."""
        # Extension is 4 chars (.mkv), ellipsis is 1 char
        # max_length 5 gives 0 chars for base, should fall back
        result = truncate_filename("abcdef.mkv", 5)
        assert result == "abcd…"
        assert len(result) == 5

    def test_unicode_accented_characters(self):
        """truncate_filename handles accented characters correctly."""
        # French movie title with accents
        result = truncate_filename("Amélie-du-café.mkv", 15)
        assert result.endswith(".mkv")
        assert "…" in result
        assert len(result) == 15

    def test_unicode_cjk_characters(self):
        """truncate_filename handles CJK characters correctly."""
        # Japanese movie title (longer than max_length)
        result = truncate_filename("千と千尋の神隠し.mkv", 10)
        assert result.endswith(".mkv")
        assert "…" in result
        assert len(result) == 10

    def test_unicode_emoji_in_filename(self):
        """truncate_filename handles emoji in filenames correctly."""
        # Filename with emoji
        result = truncate_filename("movie🎬title🎥.mp4", 12)
        assert result.endswith(".mp4")
        assert "…" in result
        assert len(result) == 12

    def test_unicode_mixed_characters(self):
        """truncate_filename handles mixed Unicode characters correctly."""
        # Mix of Latin, CJK, and accents
        result = truncate_filename("Movie_映画_Película.mkv", 18)
        assert result.endswith(".mkv")
        assert "…" in result
        assert len(result) == 18

    def test_unicode_short_filename_unchanged(self):
        """truncate_filename returns short Unicode filenames unchanged."""
        # Japanese filename within limit
        assert truncate_filename("映画.mkv", 40) == "映画.mkv"
        # French filename within limit
        assert truncate_filename("café.mp4", 40) == "café.mp4"

    def test_unicode_preserves_extension_with_cjk(self):
        """truncate_filename preserves extension even with CJK base."""
        result = truncate_filename("日本語の長いファイル名.mkv", 15)
        assert result.endswith(".mkv")
        assert result.startswith("日")

    def test_unicode_korean_filename(self):
        """truncate_filename handles Korean characters correctly."""
        result = truncate_filename("한국영화제목입니다.mkv", 12)
        assert result.endswith(".mkv")
        assert "…" in result
        assert len(result) == 12

    def test_unicode_arabic_filename(self):
        """truncate_filename handles Arabic characters correctly."""
        # Arabic movie title
        result = truncate_filename("فيلم-عربي-طويل.mkv", 12)
        assert result.endswith(".mkv")
        assert "…" in result
        assert len(result) == 12

    def test_unicode_combining_characters(self):
        """truncate_filename handles combining characters correctly."""
        # e followed by combining acute accent (é decomposed)
        decomposed = "cafe\u0301.mp4"  # café with decomposed é
        result = truncate_filename(decomposed, 40)
        # Should return unchanged when under limit
        assert result == decomposed
