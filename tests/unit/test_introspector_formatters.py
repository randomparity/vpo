"""Tests for introspector formatters module."""

import json
from pathlib import Path

from vpo.db.types import IntrospectionResult, TrackInfo
from vpo.introspector.formatters import (
    format_human,
    format_json,
    format_track_line,
    frame_rate_to_fps,
    track_to_dict,
)


class TestFrameRateToFps:
    """Tests for frame_rate_to_fps conversion."""

    def test_fraction_24fps(self):
        """24/1 -> 24."""
        assert frame_rate_to_fps("24/1") == "24"

    def test_fraction_30fps(self):
        """30/1 -> 30."""
        assert frame_rate_to_fps("30/1") == "30"

    def test_fraction_ntsc(self):
        """30000/1001 -> 29.97."""
        result = frame_rate_to_fps("30000/1001")
        assert result == "29.97"

    def test_fraction_film_ntsc(self):
        """24000/1001 -> 23.976."""
        result = frame_rate_to_fps("24000/1001")
        assert result == "23.976"

    def test_decimal_string(self):
        """Decimal string passthrough."""
        assert frame_rate_to_fps("29.97") == "29.97"

    def test_integer_string(self):
        """Integer string."""
        assert frame_rate_to_fps("24") == "24"

    def test_zero_denominator(self):
        """Division by zero returns None."""
        assert frame_rate_to_fps("0/0") is None

    def test_empty_string(self):
        """Empty string returns None."""
        assert frame_rate_to_fps("") is None

    def test_invalid_string(self):
        """Invalid string returns None."""
        assert frame_rate_to_fps("invalid") is None


class TestFormatTrackLine:
    """Tests for format_track_line function."""

    def test_video_track_basic(self):
        """Video track with codec and resolution."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            width=1920,
            height=1080,
            is_default=True,
            is_forced=False,
        )
        result = format_track_line(track)
        assert "#0" in result
        assert "[video]" in result
        assert "hevc" in result
        assert "1920x1080" in result
        assert "(default)" in result

    def test_video_track_with_frame_rate(self):
        """Video track with frame rate."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="h264",
            width=1920,
            height=1080,
            frame_rate="24/1",
            is_default=True,
            is_forced=False,
        )
        result = format_track_line(track)
        assert "@ 24fps" in result

    def test_video_track_hdr_pq(self):
        """Video track with HDR PQ shows [HDR] indicator."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            width=3840,
            height=2160,
            color_transfer="smpte2084",
            is_default=True,
            is_forced=False,
        )
        result = format_track_line(track)
        assert "[HDR]" in result

    def test_video_track_hdr_hlg(self):
        """Video track with HDR HLG shows [HDR] indicator."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            width=3840,
            height=2160,
            color_transfer="arib-std-b67",
            is_default=True,
            is_forced=False,
        )
        result = format_track_line(track)
        assert "[HDR]" in result

    def test_video_track_sdr_no_hdr_indicator(self):
        """SDR video track does not show [HDR] indicator."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="h264",
            width=1920,
            height=1080,
            color_transfer="bt709",
            is_default=True,
            is_forced=False,
        )
        result = format_track_line(track)
        assert "[HDR]" not in result

    def test_audio_track_with_layout(self):
        """Audio track with channel layout."""
        track = TrackInfo(
            index=1,
            track_type="audio",
            codec="aac",
            language="eng",
            channel_layout="stereo",
            is_default=True,
            is_forced=False,
        )
        result = format_track_line(track)
        assert "#1" in result
        assert "[audio]" in result
        assert "aac" in result
        assert "stereo" in result
        assert "eng" in result

    def test_subtitle_track(self):
        """Subtitle track with language."""
        track = TrackInfo(
            index=2,
            track_type="subtitle",
            codec="subrip",
            language="spa",
            is_default=False,
            is_forced=True,
        )
        result = format_track_line(track)
        assert "#2" in result
        assert "[subtitle]" in result
        assert "spa" in result
        assert "(forced)" in result

    def test_track_with_title(self):
        """Track with title shows quoted title."""
        track = TrackInfo(
            index=1,
            track_type="audio",
            codec="ac3",
            language="eng",
            title="Director's Commentary",
            is_default=False,
            is_forced=False,
        )
        result = format_track_line(track)
        assert '"Director\'s Commentary"' in result

    def test_track_und_language_hidden(self):
        """Undefined language is not shown."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="h264",
            language="und",
            is_default=True,
            is_forced=False,
        )
        result = format_track_line(track)
        assert "und" not in result


class TestTrackToDict:
    """Tests for track_to_dict function."""

    def test_basic_fields(self):
        """Basic fields are always present."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            language="eng",
            title="Main Video",
            is_default=True,
            is_forced=False,
        )
        d = track_to_dict(track)
        assert d["index"] == 0
        assert d["type"] == "video"
        assert d["codec"] == "hevc"
        assert d["language"] == "eng"
        assert d["title"] == "Main Video"
        assert d["is_default"] is True
        assert d["is_forced"] is False

    def test_video_fields(self):
        """Video-specific fields included when present."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            width=1920,
            height=1080,
            frame_rate="24/1",
            is_default=True,
            is_forced=False,
        )
        d = track_to_dict(track)
        assert d["width"] == 1920
        assert d["height"] == 1080
        assert d["frame_rate"] == "24/1"

    def test_hdr_color_metadata(self):
        """HDR color metadata fields included when present."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            color_transfer="smpte2084",
            color_primaries="bt2020",
            color_space="bt2020nc",
            color_range="tv",
            is_default=True,
            is_forced=False,
        )
        d = track_to_dict(track)
        assert d["color_transfer"] == "smpte2084"
        assert d["color_primaries"] == "bt2020"
        assert d["color_space"] == "bt2020nc"
        assert d["color_range"] == "tv"

    def test_audio_fields(self):
        """Audio-specific fields included when present."""
        track = TrackInfo(
            index=1,
            track_type="audio",
            codec="aac",
            channels=6,
            channel_layout="5.1",
            is_default=True,
            is_forced=False,
        )
        d = track_to_dict(track)
        assert d["channels"] == 6
        assert d["channel_layout"] == "5.1"

    def test_duration_seconds(self):
        """Duration included when present."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            duration_seconds=3600.5,
            is_default=True,
            is_forced=False,
        )
        d = track_to_dict(track)
        assert d["duration_seconds"] == 3600.5

    def test_none_fields_excluded(self):
        """Fields with None values are not included."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            is_default=True,
            is_forced=False,
        )
        d = track_to_dict(track)
        assert "width" not in d
        assert "height" not in d
        assert "frame_rate" not in d
        assert "color_transfer" not in d
        assert "channels" not in d
        assert "duration_seconds" not in d


class TestFormatJson:
    """Tests for format_json function."""

    def test_basic_structure(self):
        """JSON output has correct structure."""
        result = IntrospectionResult(
            file_path=Path("/test/video.mkv"),
            container_format="matroska",
            tracks=[
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="hevc",
                    width=1920,
                    height=1080,
                    duration_seconds=3600.0,
                    is_default=True,
                    is_forced=False,
                ),
            ],
            warnings=[],
        )
        json_str = format_json(result)
        data = json.loads(json_str)

        assert data["file"] == "/test/video.mkv"
        assert data["container"] == "matroska"
        assert data["duration_seconds"] == 3600.0
        assert len(data["tracks"]) == 1
        assert data["warnings"] == []

    def test_includes_duration_seconds(self):
        """Container duration is included."""
        result = IntrospectionResult(
            file_path=Path("/test/video.mkv"),
            container_format="matroska",
            tracks=[
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="hevc",
                    duration_seconds=7200.0,
                    is_default=True,
                    is_forced=False,
                ),
            ],
            warnings=[],
        )
        json_str = format_json(result)
        data = json.loads(json_str)
        assert data["duration_seconds"] == 7200.0

    def test_hdr_metadata_in_tracks(self):
        """HDR metadata is included in track data."""
        result = IntrospectionResult(
            file_path=Path("/test/hdr.mkv"),
            container_format="matroska",
            tracks=[
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="hevc",
                    width=3840,
                    height=2160,
                    color_transfer="smpte2084",
                    color_primaries="bt2020",
                    is_default=True,
                    is_forced=False,
                ),
            ],
            warnings=[],
        )
        json_str = format_json(result)
        data = json.loads(json_str)
        track = data["tracks"][0]
        assert track["color_transfer"] == "smpte2084"
        assert track["color_primaries"] == "bt2020"

    def test_warnings_included(self):
        """Warnings are included in output."""
        result = IntrospectionResult(
            file_path=Path("/test/video.mkv"),
            container_format="matroska",
            tracks=[],
            warnings=["No tracks found"],
        )
        json_str = format_json(result)
        data = json.loads(json_str)
        assert data["warnings"] == ["No tracks found"]


class TestFormatHuman:
    """Tests for format_human function."""

    def test_basic_output(self):
        """Basic human-readable output."""
        result = IntrospectionResult(
            file_path=Path("/test/movie.mkv"),
            container_format="matroska",
            tracks=[
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="hevc",
                    width=1920,
                    height=1080,
                    is_default=True,
                    is_forced=False,
                ),
                TrackInfo(
                    index=1,
                    track_type="audio",
                    codec="aac",
                    language="eng",
                    channel_layout="stereo",
                    is_default=True,
                    is_forced=False,
                ),
            ],
            warnings=[],
        )
        output = format_human(result)
        assert "File: /test/movie.mkv" in output
        assert "Container: Matroska" in output
        assert "Video:" in output
        assert "Audio:" in output
        assert "hevc" in output
        assert "aac" in output

    def test_grouped_by_type(self):
        """Tracks are grouped by type."""
        result = IntrospectionResult(
            file_path=Path("/test/movie.mkv"),
            container_format="matroska",
            tracks=[
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="hevc",
                    is_default=True,
                    is_forced=False,
                ),
                TrackInfo(
                    index=1,
                    track_type="audio",
                    codec="aac",
                    is_default=True,
                    is_forced=False,
                ),
                TrackInfo(
                    index=2,
                    track_type="subtitle",
                    codec="subrip",
                    is_default=False,
                    is_forced=False,
                ),
            ],
            warnings=[],
        )
        output = format_human(result)
        assert "Video:" in output
        assert "Audio:" in output
        assert "Subtitles:" in output

    def test_warnings_displayed(self):
        """Warnings are displayed."""
        result = IntrospectionResult(
            file_path=Path("/test/movie.mkv"),
            container_format="matroska",
            tracks=[],
            warnings=["File may be corrupted", "Missing audio track"],
        )
        output = format_human(result)
        assert "Warnings:" in output
        assert "File may be corrupted" in output
        assert "Missing audio track" in output

    def test_no_tracks_message(self):
        """Shows message when no tracks found."""
        result = IntrospectionResult(
            file_path=Path("/test/empty.mkv"),
            container_format="matroska",
            tracks=[],
            warnings=[],
        )
        output = format_human(result)
        assert "(no tracks found)" in output
