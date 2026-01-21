"""Tests for core formatting utilities."""

from vpo.core.formatting import (
    format_audio_languages,
    format_file_size,
    get_resolution_label,
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
