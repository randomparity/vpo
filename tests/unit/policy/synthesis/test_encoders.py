"""Unit tests for FFmpeg encoder detection and configuration."""

from unittest.mock import MagicMock, patch

import pytest

from vpo.policy.synthesis.encoders import (
    CODEC_TO_ENCODER,
    CODEC_TO_FORMAT,
    check_all_encoders,
    get_available_encoders,
    get_bitrate,
    get_encoder_for_codec,
    get_format_for_codec,
    is_encoder_available,
    parse_bitrate,
    require_encoder,
)
from vpo.policy.synthesis.exceptions import (
    EncoderUnavailableError,
)
from vpo.policy.synthesis.models import AudioCodec


class TestGetAvailableEncoders:
    """Tests for get_available_encoders function."""

    def test_parses_ffmpeg_output(self):
        """Test that FFmpeg encoder output is parsed correctly."""
        mock_output = """\
Encoders:
 V..... = Video
 A..... = Audio
 S..... = Subtitle
 .F.... = Frame-level multithreading
 ..S... = Slice-level multithreading
 ...X.. = Codec is experimental
 ....B. = Supports draw_horiz_band
 .....D = Supports direct rendering method 1
 ------
 A..... aac                  AAC (Advanced Audio Coding)
 A..... ac3                  ATSC A/52A (AC-3)
 A..... eac3                 ATSC A/52B (Enhanced AC-3)
 A..... flac                 FLAC (Free Lossless Audio Codec)
 A..... libopus              libopus Opus
 V..... libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10
"""
        with patch("vpo.policy.synthesis.encoders.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=mock_output, stderr=""
            )
            # Clear cache to force re-evaluation
            get_available_encoders.cache_clear()

            encoders = get_available_encoders()

            assert "aac" in encoders
            assert "ac3" in encoders
            assert "eac3" in encoders
            assert "flac" in encoders
            assert "libopus" in encoders
            # Video encoders should not be included
            assert "libx264" not in encoders

    def test_returns_empty_on_failure(self):
        """Test that empty set is returned when FFmpeg fails."""
        with patch("vpo.policy.synthesis.encoders.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            get_available_encoders.cache_clear()

            encoders = get_available_encoders()

            assert encoders == frozenset()

    def test_returns_empty_on_timeout(self):
        """Test that empty set is returned on timeout."""
        import subprocess

        with patch("vpo.policy.synthesis.encoders.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 10)
            get_available_encoders.cache_clear()

            encoders = get_available_encoders()

            assert encoders == frozenset()


class TestIsEncoderAvailable:
    """Tests for is_encoder_available function."""

    def test_eac3_available(self):
        """Test EAC3 encoder availability check."""
        with patch(
            "vpo.policy.synthesis.encoders.get_available_encoders"
        ) as mock_encoders:
            mock_encoders.return_value = frozenset(["eac3", "aac", "ac3"])

            assert is_encoder_available(AudioCodec.EAC3) is True

    def test_eac3_unavailable(self):
        """Test EAC3 encoder unavailability check."""
        with patch(
            "vpo.policy.synthesis.encoders.get_available_encoders"
        ) as mock_encoders:
            mock_encoders.return_value = frozenset(["aac", "ac3"])

            assert is_encoder_available(AudioCodec.EAC3) is False

    def test_libopus_mapped_correctly(self):
        """Test that OPUS codec maps to libopus encoder."""
        with patch(
            "vpo.policy.synthesis.encoders.get_available_encoders"
        ) as mock_encoders:
            mock_encoders.return_value = frozenset(["libopus"])

            assert is_encoder_available(AudioCodec.OPUS) is True


class TestRequireEncoder:
    """Tests for require_encoder function."""

    def test_returns_encoder_name_when_available(self):
        """Test that encoder name is returned when available."""
        with patch(
            "vpo.policy.synthesis.encoders.is_encoder_available"
        ) as mock_available:
            mock_available.return_value = True

            encoder = require_encoder(AudioCodec.EAC3)

            assert encoder == "eac3"

    def test_raises_when_unavailable(self):
        """Test that EncoderUnavailableError is raised when encoder missing."""
        with patch(
            "vpo.policy.synthesis.encoders.is_encoder_available"
        ) as mock_available:
            mock_available.return_value = False

            with pytest.raises(EncoderUnavailableError) as exc_info:
                require_encoder(AudioCodec.EAC3)

            assert exc_info.value.encoder == "eac3"
            assert exc_info.value.codec == "eac3"


class TestGetEncoderForCodec:
    """Tests for get_encoder_for_codec function."""

    def test_eac3_mapping(self):
        """Test EAC3 codec to encoder mapping."""
        assert get_encoder_for_codec(AudioCodec.EAC3) == "eac3"

    def test_aac_mapping(self):
        """Test AAC codec to encoder mapping."""
        assert get_encoder_for_codec(AudioCodec.AAC) == "aac"

    def test_opus_mapping(self):
        """Test OPUS codec to libopus encoder mapping."""
        assert get_encoder_for_codec(AudioCodec.OPUS) == "libopus"


class TestGetFormatForCodec:
    """Tests for get_format_for_codec function."""

    def test_eac3_format(self):
        """Test EAC3 format mapping."""
        assert get_format_for_codec(AudioCodec.EAC3) == "eac3"

    def test_aac_format(self):
        """Test AAC uses ADTS format."""
        assert get_format_for_codec(AudioCodec.AAC) == "adts"


class TestParseBitrate:
    """Tests for parse_bitrate function."""

    def test_parse_k_suffix(self):
        """Test parsing bitrate with k suffix."""
        assert parse_bitrate("640k") == 640_000
        assert parse_bitrate("192k") == 192_000

    def test_parse_m_suffix(self):
        """Test parsing bitrate with M suffix."""
        assert parse_bitrate("1.5m") == 1_500_000

    def test_parse_raw_number(self):
        """Test parsing raw bitrate number."""
        assert parse_bitrate("192000") == 192_000

    def test_invalid_format_raises(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_bitrate("invalid")


class TestGetBitrate:
    """Tests for get_bitrate function."""

    def test_uses_specified_bitrate(self):
        """Test that specified bitrate is used when provided."""
        result = get_bitrate(AudioCodec.EAC3, 6, "768k")
        assert result == 768_000

    def test_uses_default_for_51(self):
        """Test default bitrate for 5.1 EAC3."""
        result = get_bitrate(AudioCodec.EAC3, 6, None)
        assert result == 640_000

    def test_uses_default_for_stereo(self):
        """Test default bitrate for stereo AAC."""
        result = get_bitrate(AudioCodec.AAC, 2, None)
        assert result == 192_000

    def test_flac_returns_none(self):
        """Test that FLAC (lossless) returns None for bitrate."""
        result = get_bitrate(AudioCodec.FLAC, 6, None)
        assert result is None


class TestCheckAllEncoders:
    """Tests for check_all_encoders function."""

    def test_returns_dict_for_all_codecs(self):
        """Test that all codec availability is checked."""
        with patch(
            "vpo.policy.synthesis.encoders.is_encoder_available"
        ) as mock_available:
            mock_available.return_value = True

            result = check_all_encoders()

            assert len(result) == len(AudioCodec)
            for codec in AudioCodec:
                assert codec in result


class TestCodecMappings:
    """Tests for codec mapping constants."""

    def test_all_codecs_have_encoder(self):
        """Test that all AudioCodec values have an encoder mapping."""
        for codec in AudioCodec:
            assert codec in CODEC_TO_ENCODER

    def test_all_codecs_have_format(self):
        """Test that all AudioCodec values have a format mapping."""
        for codec in AudioCodec:
            assert codec in CODEC_TO_FORMAT
