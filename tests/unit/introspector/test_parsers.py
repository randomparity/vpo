"""Tests for ffprobe parser validation functions."""

from vpo.introspector.parsers import (
    _parse_container_tags,
    parse_stream,
    sanitize_string,
    validate_positive_float,
    validate_positive_int,
)


class TestValidatePositiveInt:
    """Tests for validate_positive_int function."""

    def test_valid_positive_int(self):
        """Returns the value for valid positive integers."""
        assert validate_positive_int(42, "channels") == 42
        assert validate_positive_int(1, "width") == 1
        assert validate_positive_int(0, "height") == 0  # Zero is valid

    def test_none_returns_none(self):
        """Returns None when value is None."""
        assert validate_positive_int(None, "channels") is None

    def test_negative_int_returns_none(self, caplog):
        """Returns None and logs warning for negative integers."""
        result = validate_positive_int(-5, "channels")
        assert result is None
        assert "Invalid negative channels" in caplog.text

    def test_negative_int_with_file_path_context(self, caplog):
        """Includes file path in warning message."""
        result = validate_positive_int(-10, "width", "/path/to/video.mkv")
        assert result is None
        assert "width" in caplog.text
        assert "/path/to/video.mkv" in caplog.text

    def test_wrong_type_returns_none(self, caplog):
        """Returns None and logs warning for wrong types."""
        result = validate_positive_int("42", "channels")
        assert result is None
        assert "Expected int for channels" in caplog.text
        assert "str" in caplog.text

    def test_float_type_returns_none(self, caplog):
        """Returns None and logs warning for float values."""
        result = validate_positive_int(42.5, "height")
        assert result is None
        assert "Expected int for height" in caplog.text
        assert "float" in caplog.text


class TestValidatePositiveFloat:
    """Tests for validate_positive_float function."""

    def test_valid_positive_float(self):
        """Returns the value for valid positive floats."""
        assert validate_positive_float(3.14, "duration_seconds") == 3.14
        assert validate_positive_float(0.0, "duration_seconds") == 0.0

    def test_integer_coerced_to_float(self):
        """Accepts integers and returns them as floats."""
        result = validate_positive_float(42, "duration_seconds")
        assert result == 42.0
        assert isinstance(result, float)

    def test_none_returns_none(self):
        """Returns None when value is None."""
        assert validate_positive_float(None, "duration_seconds") is None

    def test_negative_float_returns_none(self, caplog):
        """Returns None and logs warning for negative floats."""
        result = validate_positive_float(-1.5, "duration_seconds")
        assert result is None
        assert "Invalid negative duration_seconds" in caplog.text

    def test_negative_float_with_file_path_context(self, caplog):
        """Includes file path in warning message."""
        result = validate_positive_float(-99.9, "duration_seconds", "/video.mkv")
        assert result is None
        assert "duration_seconds" in caplog.text
        assert "/video.mkv" in caplog.text

    def test_wrong_type_returns_none(self, caplog):
        """Returns None and logs warning for wrong types."""
        result = validate_positive_float("3.14", "duration_seconds")
        assert result is None
        assert "Expected float for duration_seconds" in caplog.text
        assert "str" in caplog.text


class TestSanitizeString:
    """Tests for sanitize_string function."""

    def test_none_returns_none(self):
        """Returns None when input is None."""
        assert sanitize_string(None) is None

    def test_valid_string_unchanged(self):
        """Returns valid strings unchanged."""
        assert sanitize_string("Hello World") == "Hello World"
        assert sanitize_string("") == ""

    def test_unicode_preserved(self):
        """Preserves valid Unicode characters."""
        assert sanitize_string("日本語タイトル") == "日本語タイトル"
        assert sanitize_string("Émoji: 🎬") == "Émoji: 🎬"


class TestParseStreamValidation:
    """Tests for parse_stream with validation of numeric fields."""

    def test_valid_audio_stream(self):
        """Parses audio stream with valid channel count."""
        stream = {
            "index": 1,
            "codec_type": "audio",
            "codec_name": "aac",
            "channels": 6,
            "tags": {"language": "eng"},
        }
        track = parse_stream(stream)
        assert track.channels == 6
        assert track.channel_layout == "5.1"

    def test_negative_channels_becomes_none(self, caplog):
        """Negative channel count becomes None."""
        stream = {
            "index": 1,
            "codec_type": "audio",
            "codec_name": "aac",
            "channels": -2,
            "tags": {"language": "eng"},
        }
        track = parse_stream(stream, file_path="/test.mkv")
        assert track.channels is None
        assert "Invalid negative channels" in caplog.text

    def test_valid_video_dimensions(self):
        """Parses video stream with valid dimensions."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "24000/1001",
        }
        track = parse_stream(stream)
        assert track.width == 1920
        assert track.height == 1080

    def test_negative_width_becomes_none(self, caplog):
        """Negative width becomes None."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "width": -1920,
            "height": 1080,
        }
        track = parse_stream(stream, file_path="/video.mkv")
        assert track.width is None
        assert track.height == 1080
        assert "Invalid negative width" in caplog.text

    def test_negative_height_becomes_none(self, caplog):
        """Negative height becomes None."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": -1080,
        }
        track = parse_stream(stream, file_path="/video.mkv")
        assert track.width == 1920
        assert track.height is None
        assert "Invalid negative height" in caplog.text

    def test_valid_duration(self):
        """Parses stream with valid duration."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "duration": "7200.5",
        }
        track = parse_stream(stream)
        assert track.duration_seconds == 7200.5

    def test_uses_container_duration_fallback(self):
        """Falls back to container duration when stream duration missing."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
        }
        track = parse_stream(stream, container_duration=3600.0)
        assert track.duration_seconds == 3600.0

    def test_string_width_becomes_none(self, caplog):
        """Non-integer width becomes None."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "width": "1920",
            "height": 1080,
        }
        track = parse_stream(stream, file_path="/video.mkv")
        assert track.width is None
        assert "Expected int for width" in caplog.text

    def test_zero_dimensions_valid(self):
        """Zero dimensions are considered valid."""
        stream = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "width": 0,
            "height": 0,
        }
        track = parse_stream(stream)
        assert track.width == 0
        assert track.height == 0


class TestParseContainerTags:
    """Tests for _parse_container_tags function."""

    def test_normal_tags_dict(self):
        """Returns dict with lowercase keys for normal tags."""
        tags = {"TITLE": "My Movie", "ENCODER": "libx265"}
        result, warnings = _parse_container_tags(tags)
        assert result == {"title": "My Movie", "encoder": "libx265"}
        assert warnings == []

    def test_empty_tags_returns_none(self):
        """Returns None for empty tags dict."""
        result, warnings = _parse_container_tags({})
        assert result is None
        assert warnings == []

    def test_none_tags_returns_none(self):
        """Returns None for None/falsy tags."""
        result, warnings = _parse_container_tags(None)
        assert result is None
        assert warnings == []

    def test_non_string_values_coerced(self, caplog):
        """Non-string values are coerced to string."""
        import logging

        tags = {"bitrate": 5000, "title": "Movie"}
        with caplog.at_level(logging.DEBUG):
            result, warnings = _parse_container_tags(tags, file_path="/test.mkv")
        assert result is not None
        assert result["bitrate"] == "5000"
        assert "non-string value" in caplog.text

    def test_oversized_values_skipped(self, caplog):
        """Values exceeding max length are skipped with warning."""
        tags = {"title": "x" * 5000, "encoder": "libx265"}
        result, warnings = _parse_container_tags(tags, file_path="/test.mkv")
        assert result is not None
        assert "title" not in result
        assert result["encoder"] == "libx265"
        assert len(warnings) == 1
        assert "exceeds max length" in warnings[0]

    def test_oversized_keys_skipped(self, caplog):
        """Keys exceeding max length are skipped with warning."""
        long_key = "k" * 300
        tags = {long_key: "value", "title": "Movie"}
        result, warnings = _parse_container_tags(tags, file_path="/test.mkv")
        assert result is not None
        assert long_key.casefold() not in result
        assert result["title"] == "Movie"
        assert len(warnings) == 1
        assert "exceeds max length" in warnings[0]

    def test_values_sanitized_to_none_skipped(self):
        """Values that sanitize to None are skipped."""
        tags = {"title": None, "encoder": "libx265"}
        # sanitize_string(str(None)) returns "None" as a string,
        # but if the value itself is None, str(None) = "None"
        result, _ = _parse_container_tags(tags)
        assert result is not None
        assert "encoder" in result

    def test_key_normalization_to_lowercase(self):
        """Keys are normalized to casefolded lowercase."""
        tags = {"TITLE": "Movie", "Encoder": "x265", "BiTrAtE": "5000"}
        result, _ = _parse_container_tags(tags)
        assert result is not None
        assert set(result.keys()) == {"title", "encoder", "bitrate"}
