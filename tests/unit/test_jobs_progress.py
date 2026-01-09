"""Unit tests for FFmpeg progress parsing."""

from vpo.jobs.progress import (
    FFmpegProgress,
    parse_progress_block,
    parse_progress_line,
    parse_stderr_progress,
)


class TestFFmpegProgress:
    """Tests for FFmpegProgress dataclass."""

    def test_out_time_seconds_conversion(self):
        """Converts microseconds to seconds."""
        progress = FFmpegProgress(out_time_us=5_500_000)
        assert progress.out_time_seconds == 5.5

    def test_out_time_seconds_none(self):
        """Returns None when out_time_us is None."""
        progress = FFmpegProgress()
        assert progress.out_time_seconds is None

    def test_get_percent_basic(self):
        """Calculates percentage correctly."""
        progress = FFmpegProgress(out_time_us=30_000_000)  # 30 seconds
        assert progress.get_percent(60.0) == 50.0

    def test_get_percent_100(self):
        """Returns 100% when at or past duration."""
        progress = FFmpegProgress(out_time_us=60_000_000)  # 60 seconds
        assert progress.get_percent(60.0) == 100.0

    def test_get_percent_over_100_capped(self):
        """Caps percentage at 100%."""
        progress = FFmpegProgress(out_time_us=90_000_000)  # 90 seconds
        assert progress.get_percent(60.0) == 100.0

    def test_get_percent_zero_duration(self):
        """Returns 0% for zero duration."""
        progress = FFmpegProgress(out_time_us=30_000_000)
        assert progress.get_percent(0.0) == 0.0

    def test_get_percent_none_duration(self):
        """Returns 0% for None duration."""
        progress = FFmpegProgress(out_time_us=30_000_000)
        assert progress.get_percent(None) == 0.0

    def test_get_percent_no_out_time(self):
        """Returns 0% when out_time_us is None."""
        progress = FFmpegProgress()
        assert progress.get_percent(60.0) == 0.0


class TestParseProgressLine:
    """Tests for parse_progress_line function."""

    def test_parse_frame(self):
        """Parses frame count."""
        result = parse_progress_line("frame=1234")
        assert result == {"frame": 1234}

    def test_parse_fps(self):
        """Parses FPS as float."""
        result = parse_progress_line("fps=29.97")
        assert result == {"fps": 29.97}

    def test_parse_bitrate(self):
        """Parses bitrate as string."""
        result = parse_progress_line("bitrate=5000kbits/s")
        assert result == {"bitrate": "5000kbits/s"}

    def test_parse_total_size(self):
        """Parses total_size as int."""
        result = parse_progress_line("total_size=1234567")
        assert result == {"total_size": 1234567}

    def test_parse_out_time_us(self):
        """Parses out_time_us as int."""
        result = parse_progress_line("out_time_us=5500000")
        assert result == {"out_time_us": 5500000}

    def test_parse_speed(self):
        """Parses speed as string."""
        result = parse_progress_line("speed=2.5x")
        assert result == {"speed": "2.5x"}

    def test_bitrate_na(self):
        """Handles N/A bitrate."""
        result = parse_progress_line("bitrate=N/A")
        assert result == {"bitrate": None}

    def test_speed_na(self):
        """Handles N/A speed."""
        result = parse_progress_line("speed=N/A")
        assert result == {"speed": None}

    def test_empty_line(self):
        """Empty line returns empty dict."""
        result = parse_progress_line("")
        assert result == {}

    def test_no_equals(self):
        """Line without equals returns empty dict."""
        result = parse_progress_line("some random text")
        assert result == {}

    def test_whitespace_handling(self):
        """Handles whitespace around key/value."""
        result = parse_progress_line("  frame = 100  ")
        assert result == {"frame": 100}

    def test_invalid_int_returns_empty(self):
        """Invalid integer returns empty dict."""
        result = parse_progress_line("frame=notanumber")
        assert result == {}


class TestParseProgressBlock:
    """Tests for parse_progress_block function."""

    def test_parses_complete_block(self):
        """Parses a complete progress block."""
        block = """frame=1000
fps=30.0
bitrate=5000kbits/s
total_size=50000000
out_time_us=33000000
speed=2.0x"""

        result = parse_progress_block(block)

        assert result.frame == 1000
        assert result.fps == 30.0
        assert result.bitrate == "5000kbits/s"
        assert result.total_size == 50000000
        assert result.out_time_us == 33000000
        assert result.speed == "2.0x"

    def test_parses_partial_block(self):
        """Parses block with missing fields."""
        block = """frame=500
fps=25.0"""

        result = parse_progress_block(block)

        assert result.frame == 500
        assert result.fps == 25.0
        assert result.bitrate is None
        assert result.speed is None

    def test_empty_block(self):
        """Empty block returns default FFmpegProgress."""
        result = parse_progress_block("")
        assert result.frame is None
        assert result.fps is None


class TestParseStderrProgress:
    """Tests for parse_stderr_progress function."""

    def test_parses_typical_stderr_line(self):
        """Parses typical FFmpeg stderr progress line."""
        line = (
            "frame=  500 fps= 30 q=25.0 size=   10000kB "
            "time=00:00:16.67 bitrate=4914.3kbits/s speed=1.00x"
        )

        result = parse_stderr_progress(line)

        assert result is not None
        assert result.frame == 500
        assert result.fps == 30.0
        assert "4914" in result.bitrate
        assert result.speed == "1.00x"
        # Check time parsing: 16.67 seconds = 16670000 microseconds
        assert result.out_time_us == 16670000

    def test_returns_none_without_frame(self):
        """Returns None if line doesn't contain frame=."""
        result = parse_stderr_progress("Starting transcoding...")
        assert result is None

    def test_parses_time_format(self):
        """Parses time in HH:MM:SS.cc format."""
        line = "frame=1000 fps=25 time=01:23:45.67 bitrate=5000kbits/s speed=2x"

        result = parse_stderr_progress(line)

        assert result is not None
        # 1 hour + 23 minutes + 45 seconds + 0.67 seconds
        expected_seconds = 1 * 3600 + 23 * 60 + 45
        expected_us = expected_seconds * 1_000_000 + 67 * 10_000
        assert result.out_time_us == expected_us

    def test_parses_zero_time(self):
        """Parses zero time correctly."""
        line = "frame=0 fps=0 time=00:00:00.00 bitrate=N/A speed=N/A"

        result = parse_stderr_progress(line)

        assert result is not None
        assert result.out_time_us == 0
        assert result.bitrate is None
        assert result.speed is None

    def test_handles_large_values(self):
        """Handles large frame/time values."""
        line = "frame=999999 fps=60.0 time=10:30:00.00 bitrate=10000kbits/s speed=3.5x"

        result = parse_stderr_progress(line)

        assert result is not None
        assert result.frame == 999999
        assert result.fps == 60.0
        # 10 hours + 30 minutes
        expected_us = (10 * 3600 + 30 * 60) * 1_000_000
        assert result.out_time_us == expected_us


class TestIntegration:
    """Integration tests for progress parsing."""

    def test_progress_to_percent(self):
        """End-to-end progress to percentage calculation."""
        line = "frame=500 fps=30 time=00:00:30.00 bitrate=5000kbits/s speed=1x"
        duration = 60.0  # 1 minute video

        progress = parse_stderr_progress(line)
        assert progress is not None

        percent = progress.get_percent(duration)
        assert percent == 50.0
