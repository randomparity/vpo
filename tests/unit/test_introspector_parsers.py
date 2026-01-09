"""Unit tests for introspector parsing functions."""

from pathlib import Path

from vpo.introspector.parsers import (
    parse_duration,
    parse_ffprobe_output,
    parse_stream,
    parse_streams,
    sanitize_string,
)


class TestSanitizeString:
    """Tests for sanitize_string function."""

    def test_none_returns_none(self):
        """Test that None input returns None."""
        assert sanitize_string(None) is None

    def test_normal_string_unchanged(self):
        """Test that normal strings are unchanged."""
        assert sanitize_string("hello") == "hello"

    def test_string_with_spaces(self):
        """Test that strings with spaces are preserved."""
        assert sanitize_string("hello world") == "hello world"

    def test_empty_string(self):
        """Test that empty string is preserved."""
        assert sanitize_string("") == ""

    def test_unicode_preserved(self):
        """Test that valid unicode is preserved."""
        assert sanitize_string("日本語") == "日本語"


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_none_returns_none(self):
        """Test that None input returns None."""
        assert parse_duration(None) is None

    def test_valid_float_string(self):
        """Test parsing valid float strings."""
        assert parse_duration("3600.500") == 3600.5

    def test_valid_integer_string(self):
        """Test parsing integer strings."""
        assert parse_duration("120") == 120.0

    def test_zero_duration(self):
        """Test parsing zero duration."""
        assert parse_duration("0") == 0.0

    def test_invalid_string_returns_none(self):
        """Test that invalid strings return None."""
        assert parse_duration("not a number") is None
        assert parse_duration("") is None

    def test_negative_duration(self):
        """Test parsing negative duration (unlikely but valid)."""
        assert parse_duration("-10.5") == -10.5


class TestParseStream:
    """Tests for parse_stream function."""

    def test_minimal_video_stream(self):
        """Test parsing minimal video stream."""
        stream = {"index": 0, "codec_type": "video", "codec_name": "h264"}
        track = parse_stream(stream)

        assert track.index == 0
        assert track.track_type == "video"
        assert track.codec == "h264"
        assert track.language == "und"
        assert track.is_default is False
        assert track.is_forced is False

    def test_audio_stream_with_channels(self):
        """Test parsing audio stream with channel information."""
        stream = {
            "index": 1,
            "codec_type": "audio",
            "codec_name": "aac",
            "channels": 6,
        }
        track = parse_stream(stream)

        assert track.track_type == "audio"
        assert track.channels == 6
        assert track.channel_layout == "5.1"

    def test_video_stream_with_dimensions(self):
        """Test parsing video stream with width/height."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "hevc",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "24000/1001",
        }
        track = parse_stream(stream)

        assert track.width == 1920
        assert track.height == 1080
        assert track.frame_rate == "24000/1001"

    def test_stream_with_language(self):
        """Test parsing stream with language tag."""
        stream = {
            "index": 0,
            "codec_type": "audio",
            "codec_name": "aac",
            "tags": {"language": "eng"},
        }
        track = parse_stream(stream)

        assert track.language == "eng"

    def test_stream_with_disposition(self):
        """Test parsing stream with disposition flags."""
        stream = {
            "index": 0,
            "codec_type": "audio",
            "codec_name": "aac",
            "disposition": {"default": 1, "forced": 0},
        }
        track = parse_stream(stream)

        assert track.is_default is True
        assert track.is_forced is False

    def test_stream_with_title(self):
        """Test parsing stream with title tag."""
        stream = {
            "index": 0,
            "codec_type": "subtitle",
            "codec_name": "subrip",
            "tags": {"title": "English Subtitles"},
        }
        track = parse_stream(stream)

        assert track.title == "English Subtitles"

    def test_stream_with_container_duration_fallback(self):
        """Test duration fallback to container duration."""
        stream = {"index": 0, "codec_type": "video", "codec_name": "h264"}
        track = parse_stream(stream, container_duration=7200.0)

        assert track.duration_seconds == 7200.0

    def test_stream_duration_overrides_container(self):
        """Test that stream duration takes priority over container."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "duration": "3600.0",
        }
        track = parse_stream(stream, container_duration=7200.0)

        assert track.duration_seconds == 3600.0

    def test_video_with_hdr_metadata(self):
        """Test parsing video stream with HDR color metadata."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "hevc",
            "width": 3840,
            "height": 2160,
            "color_transfer": "smpte2084",
            "color_primaries": "bt2020",
            "color_space": "bt2020nc",
            "color_range": "tv",
        }
        track = parse_stream(stream)

        assert track.color_transfer == "smpte2084"
        assert track.color_primaries == "bt2020"
        assert track.color_space == "bt2020nc"
        assert track.color_range == "tv"


class TestParseStreams:
    """Tests for parse_streams function using fixtures."""

    def test_simple_single_track(self, simple_single_track_fixture: dict):
        """Test parsing a simple file with 1 video + 1 audio track."""
        streams = simple_single_track_fixture["streams"]
        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 2
        assert len(warnings) == 0

        # Check video track
        video = tracks[0]
        assert video.track_type == "video"
        assert video.codec == "h264"
        assert video.width == 1920
        assert video.height == 1080

        # Check audio track
        audio = tracks[1]
        assert audio.track_type == "audio"
        assert audio.codec == "aac"
        assert audio.channels == 2

    def test_multi_audio(self, multi_audio_fixture: dict):
        """Test parsing a file with multiple audio tracks."""
        streams = multi_audio_fixture["streams"]
        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 4
        assert len(warnings) == 0

        # Check we have the expected track types
        audio_tracks = [t for t in tracks if t.track_type == "audio"]
        assert len(audio_tracks) == 3

    def test_subtitle_heavy(self, subtitle_heavy_fixture: dict):
        """Test parsing a file with many subtitle tracks."""
        streams = subtitle_heavy_fixture["streams"]
        tracks, warnings = parse_streams(streams)

        subtitle_tracks = [t for t in tracks if t.track_type == "subtitle"]
        assert len(subtitle_tracks) == 5

    def test_duplicate_index_warning(self):
        """Test that duplicate stream indices generate warnings."""
        streams = [
            {"index": 0, "codec_type": "video", "codec_name": "h264"},
            {"index": 0, "codec_type": "audio", "codec_name": "aac"},
            {"index": 1, "codec_type": "audio", "codec_name": "opus"},
        ]

        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 2  # Duplicate skipped
        assert len(warnings) == 1
        assert "Duplicate stream index 0" in warnings[0]

    def test_empty_streams(self):
        """Test parsing empty streams list."""
        tracks, warnings = parse_streams([])

        assert len(tracks) == 0
        assert len(warnings) == 0


class TestParseFfprobeOutput:
    """Tests for parse_ffprobe_output function."""

    def test_with_simple_fixture(self, simple_single_track_fixture: dict):
        """Test parsing complete ffprobe output."""
        result = parse_ffprobe_output(
            Path("/fake/video.mkv"),
            simple_single_track_fixture,
        )

        assert result.success
        assert result.file_path == Path("/fake/video.mkv")
        assert len(result.tracks) == 2
        assert result.container_format is not None

    def test_empty_streams_adds_warning(self):
        """Test that empty streams list adds warning."""
        data = {"format": {"format_name": "matroska"}, "streams": []}

        result = parse_ffprobe_output(Path("/fake/video.mkv"), data)

        assert "No streams found in file" in result.warnings

    def test_container_format_extracted(self):
        """Test that container format is extracted from format info."""
        data = {
            "format": {"format_name": "matroska,webm"},
            "streams": [{"index": 0, "codec_type": "video", "codec_name": "vp9"}],
        }

        result = parse_ffprobe_output(Path("/fake/video.webm"), data)

        assert result.container_format == "matroska,webm"

    def test_container_duration_used_as_fallback(self):
        """Test container duration is passed to stream parsing."""
        data = {
            "format": {"format_name": "mp4", "duration": "7200.0"},
            "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264"}],
        }

        result = parse_ffprobe_output(Path("/fake/video.mp4"), data)

        # Stream should inherit container duration
        assert result.tracks[0].duration_seconds == 7200.0
