"""Unit tests for tool detection and version parsing."""

from pathlib import Path
from unittest.mock import patch

from video_policy_orchestrator.tools.detection import (
    _parse_codec_list,
    _parse_filter_list,
    _parse_format_list,
    detect_ffmpeg,
    detect_ffprobe,
    detect_mkvmerge,
    detect_mkvpropedit,
    parse_version_string,
)
from video_policy_orchestrator.tools.models import ToolStatus

# =============================================================================
# Version Parsing Tests
# =============================================================================


class TestParseVersionString:
    """Tests for version string parsing."""

    def test_standard_semver(self):
        """Standard semver should be parsed correctly."""
        assert parse_version_string("6.1.1") == (6, 1, 1)
        assert parse_version_string("1.2.3") == (1, 2, 3)

    def test_two_part_version(self):
        """Two-part versions should be parsed correctly."""
        assert parse_version_string("6.1") == (6, 1)
        assert parse_version_string("81.0") == (81, 0)

    def test_nightly_prefix(self):
        """FFmpeg nightly 'n' prefix should be stripped."""
        assert parse_version_string("n6.1.1") == (6, 1, 1)
        assert parse_version_string("n7.0") == (7, 0)

    def test_v_prefix(self):
        """Version 'v' prefix should be stripped."""
        assert parse_version_string("v81.0") == (81, 0)
        assert parse_version_string("v1.2.3") == (1, 2, 3)

    def test_version_with_suffix(self):
        """Version with suffix should extract numeric part."""
        assert parse_version_string("6.1.1-ubuntu") == (6, 1, 1)
        assert parse_version_string("81.0-alpha") == (81, 0)

    def test_version_with_build_metadata(self):
        """Version with build metadata should extract numeric part."""
        assert parse_version_string("6.1.1+build123") == (6, 1, 1)

    def test_empty_string(self):
        """Empty string should return None."""
        assert parse_version_string("") is None

    def test_non_version_string(self):
        """Non-version string should return None."""
        assert parse_version_string("not-a-version") is None
        assert parse_version_string("abc") is None

    def test_version_comparison(self):
        """Parsed versions should be comparable."""
        v1 = parse_version_string("6.0.0")
        v2 = parse_version_string("6.1.0")
        v3 = parse_version_string("7.0.0")

        assert v1 < v2 < v3
        assert v3 > v2 > v1

    def test_mkvtoolnix_version(self):
        """MKVToolNix versions should be parsed correctly."""
        # mkvmerge v81.0 ('A Tattered Line of String') 64-bit
        assert parse_version_string("81.0") == (81, 0)
        # Older version format
        assert parse_version_string("52.0.0") == (52, 0, 0)


# =============================================================================
# Codec/Format Parsing Tests
# =============================================================================


class TestCodecListParsing:
    """Tests for parsing ffmpeg codec lists."""

    def test_parse_encoder_list(self):
        """Encoder list should be parsed correctly."""
        output = """
Encoders:
 V..... libx264              H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 V..... libx265              H.265 / HEVC (codec hevc)
 A..... aac                  AAC (Advanced Audio Coding)
 A..... libopus              Opus (codec opus)
"""
        codecs = _parse_codec_list(output)
        assert "libx264" in codecs
        assert "libx265" in codecs
        assert "aac" in codecs
        assert "libopus" in codecs

    def test_parse_decoder_list(self):
        """Decoder list should be parsed correctly."""
        output = """
Decoders:
 V..... h264                 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10
 V..... hevc                 H.265 / HEVC
 A..... aac                  AAC (Advanced Audio Coding)
 S..... subrip               SubRip subtitle
"""
        codecs = _parse_codec_list(output)
        assert "h264" in codecs
        assert "hevc" in codecs
        assert "aac" in codecs
        assert "subrip" in codecs

    def test_empty_list(self):
        """Empty output should return empty set."""
        codecs = _parse_codec_list("")
        assert codecs == set()


class TestFormatListParsing:
    """Tests for parsing ffmpeg format lists."""

    def test_parse_muxer_list(self):
        """Muxer list should be parsed correctly."""
        output = """
Muxing formats:
 E  matroska             Matroska
 E  mp4                  MP4 (MPEG-4 Part 14)
 E  webm                 WebM
"""
        formats = _parse_format_list(output)
        assert "matroska" in formats
        assert "mp4" in formats
        assert "webm" in formats

    def test_parse_demuxer_list(self):
        """Demuxer list should be parsed correctly."""
        output = """
Demuxing formats:
 D  matroska,webm        Matroska / WebM
 D  mov,mp4,m4a,3gp,3g2,mj2 QuickTime / MOV
"""
        formats = _parse_format_list(output)
        assert "matroska,webm" in formats


class TestFilterListParsing:
    """Tests for parsing ffmpeg filter lists."""

    def test_parse_filter_list(self):
        """Filter list should be parsed correctly."""
        output = """
Filters:
 T.. scale            Scale the input video size and/or convert the image format.
 ... overlay          Overlay a video source on top of the input.
 TSC loudnorm         EBU R128 loudness normalization
"""
        filters = _parse_filter_list(output)
        assert "scale" in filters
        assert "overlay" in filters
        assert "loudnorm" in filters


# =============================================================================
# Tool Detection Tests
# =============================================================================


class TestDetectFFprobe:
    """Tests for ffprobe detection."""

    @patch("video_policy_orchestrator.tools.detection._find_tool")
    def test_missing_ffprobe(self, mock_find: patch):
        """Missing ffprobe should return MISSING status."""
        mock_find.return_value = None

        info = detect_ffprobe()

        assert info.status == ToolStatus.MISSING
        assert info.path is None
        assert "not found" in info.status_message.lower()

    @patch("video_policy_orchestrator.tools.detection._run_command")
    @patch("video_policy_orchestrator.tools.detection._find_tool")
    def test_detect_ffprobe_version(self, mock_find: patch, mock_run: patch):
        """FFprobe version should be detected correctly."""
        mock_find.return_value = Path("/usr/bin/ffprobe")
        mock_run.return_value = (
            "ffprobe version 6.1.1 Copyright (c) 2007-2023 the FFmpeg developers\n"
            "built with gcc 12 (Ubuntu 12.3.0-1ubuntu1~23.04)\n",
            "",
            0,
        )

        info = detect_ffprobe()

        assert info.status == ToolStatus.AVAILABLE
        assert info.version == "6.1.1"
        assert info.version_tuple == (6, 1, 1)
        assert info.path == Path("/usr/bin/ffprobe")


class TestDetectFFmpeg:
    """Tests for ffmpeg detection."""

    @patch("video_policy_orchestrator.tools.detection._find_tool")
    def test_missing_ffmpeg(self, mock_find: patch):
        """Missing ffmpeg should return MISSING status."""
        mock_find.return_value = None

        info = detect_ffmpeg()

        assert info.status == ToolStatus.MISSING

    @patch("video_policy_orchestrator.tools.detection._run_command")
    @patch("video_policy_orchestrator.tools.detection._find_tool")
    def test_detect_ffmpeg_version(self, mock_find: patch, mock_run: patch):
        """FFmpeg version should be detected correctly."""
        mock_find.return_value = Path("/usr/bin/ffmpeg")
        # Return version info, then empty responses for capability detection
        mock_run.side_effect = [
            (
                "ffmpeg version 6.1.1 Copyright (c) 2000-2023\n"
                "configuration: --enable-gpl --enable-libx264\n",
                "",
                0,
            ),
            ("", "", 0),  # encoders
            ("", "", 0),  # decoders
            ("", "", 0),  # muxers
            ("", "", 0),  # demuxers
            ("", "", 0),  # filters
        ]

        info = detect_ffmpeg()

        assert info.status == ToolStatus.AVAILABLE
        assert info.version == "6.1.1"
        assert info.version_tuple == (6, 1, 1)


class TestDetectMkvmerge:
    """Tests for mkvmerge detection."""

    @patch("video_policy_orchestrator.tools.detection._find_tool")
    def test_missing_mkvmerge(self, mock_find: patch):
        """Missing mkvmerge should return MISSING status."""
        mock_find.return_value = None

        info = detect_mkvmerge()

        assert info.status == ToolStatus.MISSING

    @patch("video_policy_orchestrator.tools.detection._run_command")
    @patch("video_policy_orchestrator.tools.detection._find_tool")
    def test_detect_mkvmerge_version(self, mock_find: patch, mock_run: patch):
        """MKVmerge version should be detected correctly."""
        mock_find.return_value = Path("/usr/bin/mkvmerge")
        mock_run.return_value = (
            "mkvmerge v81.0 ('A Tattered Line of String') 64-bit\n",
            "",
            0,
        )

        info = detect_mkvmerge()

        assert info.status == ToolStatus.AVAILABLE
        assert info.version == "81.0"
        assert info.version_tuple == (81, 0)
        assert info.supports_track_order is True
        assert info.supports_json_output is True  # Added in 9.0


class TestDetectMkvpropedit:
    """Tests for mkvpropedit detection."""

    @patch("video_policy_orchestrator.tools.detection._find_tool")
    def test_missing_mkvpropedit(self, mock_find: patch):
        """Missing mkvpropedit should return MISSING status."""
        mock_find.return_value = None

        info = detect_mkvpropedit()

        assert info.status == ToolStatus.MISSING

    @patch("video_policy_orchestrator.tools.detection._run_command")
    @patch("video_policy_orchestrator.tools.detection._find_tool")
    def test_detect_mkvpropedit_version(self, mock_find: patch, mock_run: patch):
        """MKVpropedit version should be detected correctly."""
        mock_find.return_value = Path("/usr/bin/mkvpropedit")
        mock_run.return_value = (
            "mkvpropedit v81.0 ('A Tattered Line of String') 64-bit\n",
            "",
            0,
        )

        info = detect_mkvpropedit()

        assert info.status == ToolStatus.AVAILABLE
        assert info.version == "81.0"
        assert info.version_tuple == (81, 0)
