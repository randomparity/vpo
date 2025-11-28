"""Unit tests for FFprobeIntrospector.

Note: Stream parsing logic has been extracted to
video_policy_orchestrator.introspector.parsers and is tested in
test_introspector_parsers.py. This file tests FFprobeIntrospector-specific
functionality.
"""

from video_policy_orchestrator.introspector.mappings import (
    map_channel_layout,
    map_track_type,
)
from video_policy_orchestrator.introspector.parsers import (
    parse_streams,
    sanitize_string,
)


class TestParseStreams:
    """Tests for stream parsing via parse_streams function.

    These tests verify the parsing behavior using fixtures.
    The actual parsing logic is in the parsers module.
    """

    def test_parse_simple_single_track(self, simple_single_track_fixture: dict) -> None:
        """Test parsing a simple file with 1 video + 1 audio track."""
        streams = simple_single_track_fixture["streams"]
        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 2
        assert len(warnings) == 0

        # Check video track
        video = tracks[0]
        assert video.index == 0
        assert video.track_type == "video"
        assert video.codec == "h264"
        assert video.width == 1920
        assert video.height == 1080
        assert video.frame_rate == "24000/1001"
        assert video.is_default is True
        assert video.language == "eng"
        assert video.title == "Main Video"

        # Check audio track
        audio = tracks[1]
        assert audio.index == 1
        assert audio.track_type == "audio"
        assert audio.codec == "aac"
        assert audio.channels == 2
        assert audio.channel_layout == "stereo"
        assert audio.is_default is True
        assert audio.language == "eng"

    def test_parse_multi_audio(self, multi_audio_fixture: dict) -> None:
        """Test parsing a file with multiple audio tracks."""
        streams = multi_audio_fixture["streams"]
        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 4
        assert len(warnings) == 0

        # Check video track (4K HEVC)
        video = tracks[0]
        assert video.track_type == "video"
        assert video.codec == "hevc"
        assert video.width == 3840
        assert video.height == 2160

        # Check audio tracks have different languages
        # Note: "fra" in fixture is normalized to "fre" (ISO 639-2/B)
        languages = [t.language for t in tracks if t.track_type == "audio"]
        assert languages == ["eng", "jpn", "fre"]

        # Check channel layouts
        audio_tracks = [t for t in tracks if t.track_type == "audio"]
        assert audio_tracks[0].channels == 8
        assert audio_tracks[0].channel_layout == "7.1"
        assert audio_tracks[1].channels == 6
        assert audio_tracks[1].channel_layout == "5.1"
        assert audio_tracks[2].channels == 2
        assert audio_tracks[2].channel_layout == "stereo"

    def test_parse_subtitle_heavy(self, subtitle_heavy_fixture: dict) -> None:
        """Test parsing a file with many subtitle tracks."""
        streams = subtitle_heavy_fixture["streams"]
        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 7  # 1 video + 1 audio + 5 subtitles
        assert len(warnings) == 0

        subtitle_tracks = [t for t in tracks if t.track_type == "subtitle"]
        assert len(subtitle_tracks) == 5

        # Check subtitle languages
        sub_languages = [t.language for t in subtitle_tracks]
        assert sub_languages == ["eng", "jpn", "spa", "ger", "eng"]

        # Check forced subtitle
        forced_sub = [t for t in subtitle_tracks if t.is_forced]
        assert len(forced_sub) == 1
        assert forced_sub[0].title == "English (Signs/Songs)"

    def test_parse_edge_case_missing_metadata(
        self, edge_case_missing_metadata_fixture: dict
    ) -> None:
        """Test parsing a file with missing metadata fields."""
        streams = edge_case_missing_metadata_fixture["streams"]
        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 3
        assert len(warnings) == 0

        # Video track - missing disposition, tags
        video = tracks[0]
        assert video.track_type == "video"
        assert video.is_default is False  # Default when disposition missing
        assert video.language == "und"  # Default when language missing
        assert video.frame_rate is None  # No frame rate in fixture

        # Audio track - missing disposition, language, title
        audio = tracks[1]
        assert audio.track_type == "audio"
        assert audio.is_default is False
        assert audio.language == "und"
        assert audio.title is None
        assert audio.channels == 2

        # Subtitle track - missing disposition, language
        subtitle = tracks[2]
        assert subtitle.track_type == "subtitle"
        assert subtitle.language == "und"
        assert subtitle.title == "Subtitles"


class TestChannelLayoutMapping:
    """Tests for map_channel_layout function."""

    def test_mono(self) -> None:
        """Test mono (1 channel) mapping."""
        assert map_channel_layout(1) == "mono"

    def test_stereo(self) -> None:
        """Test stereo (2 channels) mapping."""
        assert map_channel_layout(2) == "stereo"

    def test_5_1(self) -> None:
        """Test 5.1 (6 channels) mapping."""
        assert map_channel_layout(6) == "5.1"

    def test_7_1(self) -> None:
        """Test 7.1 (8 channels) mapping."""
        assert map_channel_layout(8) == "7.1"

    def test_unknown_channels(self) -> None:
        """Test unknown channel counts use 'Nch' format."""
        assert map_channel_layout(3) == "3ch"
        assert map_channel_layout(4) == "4ch"
        assert map_channel_layout(10) == "10ch"


class TestTrackTypeMapping:
    """Tests for map_track_type function."""

    def test_video(self) -> None:
        """Test video codec_type mapping."""
        assert map_track_type("video") == "video"

    def test_audio(self) -> None:
        """Test audio codec_type mapping."""
        assert map_track_type("audio") == "audio"

    def test_subtitle(self) -> None:
        """Test subtitle codec_type mapping."""
        assert map_track_type("subtitle") == "subtitle"

    def test_attachment(self) -> None:
        """Test attachment codec_type mapping."""
        assert map_track_type("attachment") == "attachment"

    def test_unknown_type(self) -> None:
        """Test unknown codec_type maps to 'other'."""
        assert map_track_type("data") == "other"
        assert map_track_type("unknown") == "other"
        assert map_track_type("") == "other"


class TestEdgeCaseHandling:
    """Tests for edge case handling via parsers module."""

    def test_duplicate_stream_index(self) -> None:
        """Test that duplicate stream indices are skipped with warning."""
        streams = [
            {"index": 0, "codec_type": "video", "codec_name": "h264"},
            {"index": 0, "codec_type": "audio", "codec_name": "aac"},  # Duplicate!
            {"index": 1, "codec_type": "audio", "codec_name": "opus"},
        ]

        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 2  # Only 2 tracks, duplicate skipped
        assert len(warnings) == 1
        assert "Duplicate stream index 0" in warnings[0]

    def test_empty_streams(self) -> None:
        """Test parsing empty streams list."""
        tracks, warnings = parse_streams([])

        assert len(tracks) == 0
        assert len(warnings) == 0  # Warning added in parse_ffprobe_output, not here

    def test_missing_tags_entirely(self) -> None:
        """Test stream with no tags at all."""
        streams = [{"index": 0, "codec_type": "video", "codec_name": "h264"}]

        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 1
        assert tracks[0].language == "und"
        assert tracks[0].title is None

    def test_missing_disposition_entirely(self) -> None:
        """Test stream with no disposition at all."""
        streams = [{"index": 0, "codec_type": "audio", "codec_name": "aac"}]

        tracks, warnings = parse_streams(streams)

        assert len(tracks) == 1
        assert tracks[0].is_default is False
        assert tracks[0].is_forced is False

    def test_sanitize_string(self) -> None:
        """Test sanitize_string function."""
        assert sanitize_string(None) is None
        assert sanitize_string("normal") == "normal"
        assert sanitize_string("with spaces") == "with spaces"

    def test_uncommon_codec_preserved(self) -> None:
        """Test that uncommon codec names are preserved as-is."""
        streams = [
            {"index": 0, "codec_type": "video", "codec_name": "prores_ks"},
            {"index": 1, "codec_type": "audio", "codec_name": "pcm_s24le"},
        ]

        tracks, warnings = parse_streams(streams)

        assert tracks[0].codec == "prores_ks"
        assert tracks[1].codec == "pcm_s24le"


class TestFFprobeTimeout:
    """Tests for FFprobeIntrospector timeout handling."""

    def test_timeout_raises_introspection_error(self, monkeypatch, tmp_path) -> None:
        """Test that subprocess timeout is wrapped in MediaIntrospectionError."""
        import subprocess
        from unittest.mock import MagicMock

        from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector
        from video_policy_orchestrator.introspector.interface import (
            MediaIntrospectionError,
        )

        # Mock subprocess.run to raise TimeoutExpired
        mock_run = MagicMock(
            side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=60)
        )
        monkeypatch.setattr(
            "video_policy_orchestrator.introspector.ffprobe.subprocess.run",
            mock_run,
        )

        # Mock the tool path check to return a valid path
        monkeypatch.setattr(
            FFprobeIntrospector,
            "_get_configured_path",
            staticmethod(lambda: tmp_path / "ffprobe"),
        )

        introspector = FFprobeIntrospector()

        # Create a dummy file
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        import pytest

        with pytest.raises(MediaIntrospectionError, match="timed out.*after 60s"):
            introspector.get_file_info(test_file)
