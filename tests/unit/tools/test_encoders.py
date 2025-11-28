"""Tests for tools/encoders.py - hardware encoder detection and selection."""

from unittest.mock import patch

import pytest

from video_policy_orchestrator.tools.encoders import (
    HARDWARE_ENCODERS,
    HW_ENCODER_ERROR_PATTERNS,
    SOFTWARE_ENCODERS,
    EncoderSelection,
    detect_hw_encoder_error,
    get_software_encoder,
    select_encoder,
    select_encoder_with_fallback,
)


class TestSoftwareEncoders:
    """Tests for SOFTWARE_ENCODERS constant."""

    def test_hevc_encoder(self) -> None:
        """HEVC uses libx265."""
        assert SOFTWARE_ENCODERS["hevc"] == "libx265"

    def test_h264_encoder(self) -> None:
        """H.264 uses libx264."""
        assert SOFTWARE_ENCODERS["h264"] == "libx264"

    def test_av1_encoder(self) -> None:
        """AV1 uses libaom-av1."""
        assert SOFTWARE_ENCODERS["av1"] == "libaom-av1"


class TestHardwareEncoders:
    """Tests for HARDWARE_ENCODERS constant."""

    def test_hevc_nvenc(self) -> None:
        """HEVC has NVENC encoder."""
        assert HARDWARE_ENCODERS["hevc"]["nvenc"] == "hevc_nvenc"

    def test_h264_qsv(self) -> None:
        """H.264 has Quick Sync encoder."""
        assert HARDWARE_ENCODERS["h264"]["qsv"] == "h264_qsv"

    def test_av1_nvenc(self) -> None:
        """AV1 has NVENC encoder (RTX 40+)."""
        assert HARDWARE_ENCODERS["av1"]["nvenc"] == "av1_nvenc"


class TestGetSoftwareEncoder:
    """Tests for get_software_encoder function."""

    def test_hevc(self) -> None:
        """Returns libx265 for hevc."""
        assert get_software_encoder("hevc") == "libx265"

    def test_h264(self) -> None:
        """Returns libx264 for h264."""
        assert get_software_encoder("h264") == "libx264"

    def test_case_insensitive(self) -> None:
        """Codec lookup is case-insensitive."""
        assert get_software_encoder("HEVC") == "libx265"
        assert get_software_encoder("H264") == "libx264"

    def test_unknown_codec_defaults_to_libx265(self) -> None:
        """Unknown codec defaults to libx265."""
        assert get_software_encoder("unknown") == "libx265"


class TestEncoderSelection:
    """Tests for EncoderSelection dataclass."""

    def test_software_selection(self) -> None:
        """Creates software encoder selection."""
        sel = EncoderSelection(
            encoder="libx265",
            encoder_type="software",
        )
        assert sel.encoder == "libx265"
        assert sel.encoder_type == "software"
        assert sel.hw_platform is None
        assert sel.fallback_occurred is False

    def test_hardware_selection(self) -> None:
        """Creates hardware encoder selection."""
        sel = EncoderSelection(
            encoder="hevc_nvenc",
            encoder_type="hardware",
            hw_platform="nvenc",
        )
        assert sel.encoder == "hevc_nvenc"
        assert sel.encoder_type == "hardware"
        assert sel.hw_platform == "nvenc"

    def test_fallback_selection(self) -> None:
        """Creates selection with fallback flag."""
        sel = EncoderSelection(
            encoder="libx265",
            encoder_type="software",
            fallback_occurred=True,
        )
        assert sel.fallback_occurred is True

    def test_frozen(self) -> None:
        """Selection is immutable."""
        sel = EncoderSelection(encoder="libx265", encoder_type="software")
        with pytest.raises(AttributeError):
            sel.encoder = "libx264"  # type: ignore[misc]


class TestSelectEncoder:
    """Tests for select_encoder function."""

    @patch("video_policy_orchestrator.tools.encoders.check_encoder_available")
    def test_none_mode_returns_software(self, mock_check: object) -> None:
        """hw_mode='none' returns software encoder without checking."""
        result = select_encoder("hevc", hw_mode="none")
        assert result.encoder == "libx265"
        assert result.encoder_type == "software"
        assert result.fallback_occurred is False

    @patch("video_policy_orchestrator.tools.encoders.check_encoder_available")
    def test_auto_mode_tries_nvenc_first(self, mock_check: object) -> None:
        """auto mode tries NVENC before QSV and VAAPI."""
        # Make NVENC available
        mock_check.return_value = True  # type: ignore[attr-defined]

        result = select_encoder("hevc", hw_mode="auto")
        assert result.encoder == "hevc_nvenc"
        assert result.encoder_type == "hardware"
        assert result.hw_platform == "nvenc"

    @patch("video_policy_orchestrator.tools.encoders.check_encoder_available")
    def test_auto_mode_falls_back_to_qsv(self, mock_check: object) -> None:
        """auto mode falls back to QSV if NVENC unavailable."""

        # NVENC unavailable, QSV available
        def side_effect(encoder: str) -> bool:
            return "qsv" in encoder

        mock_check.side_effect = side_effect  # type: ignore[attr-defined]

        result = select_encoder("hevc", hw_mode="auto")
        assert result.encoder == "hevc_qsv"
        assert result.hw_platform == "qsv"

    @patch("video_policy_orchestrator.tools.encoders.check_encoder_available")
    def test_auto_mode_falls_back_to_software(self, mock_check: object) -> None:
        """auto mode falls back to software if no HW available."""
        mock_check.return_value = False  # type: ignore[attr-defined]

        result = select_encoder("hevc", hw_mode="auto")
        assert result.encoder == "libx265"
        assert result.encoder_type == "software"
        assert result.fallback_occurred is True

    @patch("video_policy_orchestrator.tools.encoders.check_encoder_available")
    def test_explicit_hw_mode(self, mock_check: object) -> None:
        """Explicit hw_mode selects specific encoder."""
        mock_check.return_value = True  # type: ignore[attr-defined]

        result = select_encoder("hevc", hw_mode="qsv")
        assert result.encoder == "hevc_qsv"
        assert result.hw_platform == "qsv"

    @patch("video_policy_orchestrator.tools.encoders.check_encoder_available")
    def test_explicit_mode_fallback_disabled_raises(self, mock_check: object) -> None:
        """Raises error when HW unavailable and fallback disabled."""
        mock_check.return_value = False  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError) as exc_info:
            select_encoder("hevc", hw_mode="nvenc", fallback_to_cpu=False)

        assert "not available" in str(exc_info.value)

    @patch("video_policy_orchestrator.tools.encoders.check_encoder_available")
    def test_explicit_mode_fallback_enabled(self, mock_check: object) -> None:
        """Falls back to software when HW unavailable and fallback enabled."""
        mock_check.return_value = False  # type: ignore[attr-defined]

        result = select_encoder("hevc", hw_mode="nvenc", fallback_to_cpu=True)
        assert result.encoder == "libx265"
        assert result.encoder_type == "software"


class TestSelectEncoderWithFallback:
    """Tests for legacy select_encoder_with_fallback function."""

    @patch("video_policy_orchestrator.tools.encoders.check_encoder_available")
    def test_returns_tuple(self, mock_check: object) -> None:
        """Returns (encoder, encoder_type) tuple."""
        mock_check.return_value = False  # type: ignore[attr-defined]

        encoder, encoder_type = select_encoder_with_fallback("hevc")
        assert encoder == "libx265"
        assert encoder_type == "software"


class TestDetectHwEncoderError:
    """Tests for detect_hw_encoder_error function."""

    def test_detects_nvenc_error(self) -> None:
        """Detects NVENC-related error."""
        stderr = "Cannot load nvenc encoder"
        assert detect_hw_encoder_error(stderr) is True

    def test_detects_cuda_error(self) -> None:
        """Detects CUDA-related error."""
        stderr = "cuda error: device not found"
        assert detect_hw_encoder_error(stderr) is True

    def test_detects_memory_error(self) -> None:
        """Detects memory allocation error."""
        stderr = "Error: out of memory on device"
        assert detect_hw_encoder_error(stderr) is True

    def test_detects_initialization_failed(self) -> None:
        """Detects initialization failure."""
        stderr = "encoder initialization failed"
        assert detect_hw_encoder_error(stderr) is True

    def test_no_error_in_normal_output(self) -> None:
        """Returns False for normal output."""
        stderr = "frame=100 fps=25 size=1024kB time=00:00:04.00"
        assert detect_hw_encoder_error(stderr) is False

    def test_case_insensitive(self) -> None:
        """Detection is case-insensitive."""
        stderr = "NVENC ENCODER NOT FOUND"
        assert detect_hw_encoder_error(stderr) is True


class TestHwEncoderErrorPatterns:
    """Tests for HW_ENCODER_ERROR_PATTERNS constant."""

    def test_has_expected_patterns(self) -> None:
        """Contains expected error patterns."""
        assert "nvenc" in HW_ENCODER_ERROR_PATTERNS
        assert "cuda" in HW_ENCODER_ERROR_PATTERNS
        assert "memory" in HW_ENCODER_ERROR_PATTERNS
        assert "not found" in HW_ENCODER_ERROR_PATTERNS
