"""Tests for hardware encoder fallback in TranscodeExecutor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.executor.transcode import TranscodeExecutor
from vpo.executor.transcode.executor import detect_encoder_type
from vpo.executor.transcode.types import TranscodePlan
from vpo.policy.types import (
    HardwareAccelConfig,
    HardwareAccelMode,
    TranscodePolicyConfig,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def basic_policy() -> TranscodePolicyConfig:
    """Basic transcode policy for testing."""
    return TranscodePolicyConfig(target_video_codec="hevc")


@pytest.fixture
def hw_accel_config_with_fallback() -> HardwareAccelConfig:
    """Hardware acceleration config with fallback enabled."""
    return HardwareAccelConfig(
        enabled=HardwareAccelMode.NVENC,
        fallback_to_cpu=True,
    )


@pytest.fixture
def hw_accel_config_without_fallback() -> HardwareAccelConfig:
    """Hardware acceleration config with fallback disabled."""
    return HardwareAccelConfig(
        enabled=HardwareAccelMode.NVENC,
        fallback_to_cpu=False,
    )


@pytest.fixture
def executor_with_hw_fallback(
    basic_policy: TranscodePolicyConfig,
    hw_accel_config_with_fallback: HardwareAccelConfig,
) -> TranscodeExecutor:
    """Executor with hardware fallback enabled."""
    return TranscodeExecutor(
        policy=basic_policy,
        hardware_acceleration=hw_accel_config_with_fallback,
    )


@pytest.fixture
def executor_without_hw_fallback(
    basic_policy: TranscodePolicyConfig,
    hw_accel_config_without_fallback: HardwareAccelConfig,
) -> TranscodeExecutor:
    """Executor with hardware fallback disabled."""
    return TranscodeExecutor(
        policy=basic_policy,
        hardware_acceleration=hw_accel_config_without_fallback,
    )


@pytest.fixture
def executor_software_only(basic_policy: TranscodePolicyConfig) -> TranscodeExecutor:
    """Executor with software encoding only."""
    return TranscodeExecutor(
        policy=basic_policy,
        hardware_acceleration=HardwareAccelConfig(
            enabled=HardwareAccelMode.NONE,
            fallback_to_cpu=True,
        ),
    )


@pytest.fixture
def make_plan(tmp_path: Path, basic_policy: TranscodePolicyConfig):
    """Factory for creating TranscodePlan objects."""

    def _make(needs_video_transcode: bool = True) -> TranscodePlan:
        input_path = tmp_path / "input.mkv"
        if not input_path.exists():
            input_path.write_bytes(b"x" * 10000)
        return TranscodePlan(
            input_path=input_path,
            output_path=tmp_path / "output.mkv",
            policy=basic_policy,
            video_codec="h264",
            video_width=1920,
            video_height=1080,
            video_bitrate=10_000_000,
            needs_video_transcode=needs_video_transcode,
            needs_video_scale=False,
        )

    return _make


# =============================================================================
# Tests for _should_retry_with_software
# =============================================================================


class TestShouldRetryWithSoftware:
    """Tests for the _should_retry_with_software helper method."""

    def test_returns_false_when_no_hw_config(self, basic_policy: TranscodePolicyConfig):
        """Returns False when no hardware acceleration configured."""
        executor = TranscodeExecutor(
            policy=basic_policy,
            hardware_acceleration=None,
        )
        cmd = ["ffmpeg", "-c:v", "hevc_nvenc", "-i", "input.mkv", "output.mkv"]
        stderr = ["nvenc initialization failed"]

        result = executor._should_retry_with_software(cmd, stderr)

        assert result is False

    def test_returns_false_when_fallback_disabled(
        self, executor_without_hw_fallback: TranscodeExecutor
    ):
        """Returns False when fallback_to_cpu is disabled."""
        cmd = ["ffmpeg", "-c:v", "hevc_nvenc", "-i", "input.mkv", "output.mkv"]
        stderr = ["nvenc initialization failed"]

        result = executor_without_hw_fallback._should_retry_with_software(cmd, stderr)

        assert result is False

    def test_returns_false_when_software_encoder_used(
        self, executor_with_hw_fallback: TranscodeExecutor
    ):
        """Returns False when a software encoder was used."""
        cmd = ["ffmpeg", "-c:v", "libx265", "-i", "input.mkv", "output.mkv"]
        stderr = ["some error"]

        result = executor_with_hw_fallback._should_retry_with_software(cmd, stderr)

        assert result is False

    def test_returns_false_when_hw_mode_none(
        self, executor_software_only: TranscodeExecutor
    ):
        """Returns False when hardware mode is NONE."""
        cmd = ["ffmpeg", "-c:v", "hevc_nvenc", "-i", "input.mkv", "output.mkv"]
        stderr = ["nvenc initialization failed"]

        result = executor_software_only._should_retry_with_software(cmd, stderr)

        assert result is False

    def test_returns_false_when_no_hw_error_in_stderr(
        self, executor_with_hw_fallback: TranscodeExecutor
    ):
        """Returns False when stderr doesn't contain HW error patterns."""
        cmd = ["ffmpeg", "-c:v", "hevc_nvenc", "-i", "input.mkv", "output.mkv"]
        stderr = ["encoding complete", "success"]

        result = executor_with_hw_fallback._should_retry_with_software(cmd, stderr)

        assert result is False

    def test_returns_true_on_nvenc_failure(
        self, executor_with_hw_fallback: TranscodeExecutor
    ):
        """Returns True when NVENC initialization fails."""
        cmd = ["ffmpeg", "-c:v", "hevc_nvenc", "-i", "input.mkv", "output.mkv"]
        stderr = ["Cannot load nvenc library"]

        result = executor_with_hw_fallback._should_retry_with_software(cmd, stderr)

        assert result is True

    def test_returns_true_on_vaapi_failure(self, basic_policy: TranscodePolicyConfig):
        """Returns True when VAAPI initialization fails."""
        executor = TranscodeExecutor(
            policy=basic_policy,
            hardware_acceleration=HardwareAccelConfig(
                enabled=HardwareAccelMode.VAAPI,
                fallback_to_cpu=True,
            ),
        )
        cmd = ["ffmpeg", "-c:v", "hevc_vaapi", "-i", "input.mkv", "output.mkv"]
        # Use a pattern that matches HW_ENCODER_ERROR_PATTERNS in encoders.py
        stderr = ["VAAPI device not found or not supported"]

        result = executor._should_retry_with_software(cmd, stderr)

        assert result is True

    def test_returns_true_on_device_not_found(
        self, executor_with_hw_fallback: TranscodeExecutor
    ):
        """Returns True when device is not found."""
        cmd = ["ffmpeg", "-c:v", "hevc_nvenc", "-i", "input.mkv", "output.mkv"]
        stderr = ["No device available for encoding"]

        result = executor_with_hw_fallback._should_retry_with_software(cmd, stderr)

        assert result is True


# =============================================================================
# Tests for detect_encoder_type helper
# =============================================================================


class TestDetectEncoderType:
    """Tests for the detect_encoder_type helper function."""

    def test_detects_nvenc(self):
        """Detects NVIDIA NVENC encoder."""
        cmd = ["ffmpeg", "-c:v", "hevc_nvenc", "-i", "input.mkv", "output.mkv"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_vaapi(self):
        """Detects VA-API encoder."""
        cmd = ["ffmpeg", "-c:v", "h264_vaapi", "-i", "input.mkv", "output.mkv"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_qsv(self):
        """Detects Intel Quick Sync encoder."""
        cmd = ["ffmpeg", "-c:v", "hevc_qsv", "-i", "input.mkv", "output.mkv"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_libx265(self):
        """Detects software libx265 encoder."""
        cmd = ["ffmpeg", "-c:v", "libx265", "-i", "input.mkv", "output.mkv"]
        assert detect_encoder_type(cmd) == "software"

    def test_detects_libx264(self):
        """Detects software libx264 encoder."""
        cmd = ["ffmpeg", "-c:v", "libx264", "-i", "input.mkv", "output.mkv"]
        assert detect_encoder_type(cmd) == "software"

    def test_detects_copy_as_unknown(self):
        """Stream copy returns unknown."""
        cmd = ["ffmpeg", "-c:v", "copy", "-i", "input.mkv", "output.mkv"]
        assert detect_encoder_type(cmd) == "unknown"

    def test_no_video_codec_returns_unknown(self):
        """Missing video codec returns unknown."""
        cmd = ["ffmpeg", "-i", "input.mkv", "output.mkv"]
        assert detect_encoder_type(cmd) == "unknown"


# =============================================================================
# Tests for execute with hardware fallback
# =============================================================================


class TestExecuteHardwareFallback:
    """Tests for hardware fallback during execute()."""

    @patch("vpo.executor.transcode.command.require_tool")
    @patch("vpo.executor.transcode.executor.TranscodeExecutor._run_ffmpeg_with_timeout")
    def test_retries_with_software_on_hw_failure(
        self,
        mock_run_ffmpeg: MagicMock,
        mock_require_tool: MagicMock,
        executor_with_hw_fallback: TranscodeExecutor,
        make_plan,
        tmp_path: Path,
    ):
        """Retries with software encoder when hardware fails."""
        mock_require_tool.return_value = Path("/usr/bin/ffmpeg")

        plan = make_plan(needs_video_transcode=True)
        plan.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp output file to simulate ffmpeg success
        temp_output = plan.output_path.with_name(f".vpo_temp_{plan.output_path.name}")

        def create_temp_on_success(*args, **kwargs):
            """Side effect that creates temp file on SW success."""
            # First call fails (HW), second call succeeds (SW)
            if mock_run_ffmpeg.call_count == 1:
                return (False, 1, ["Cannot load nvenc"], None)
            else:
                # Create temp file to simulate ffmpeg output
                temp_output.write_bytes(b"fake video data")
                return (
                    True,
                    0,
                    [],
                    MagicMock(
                        avg_fps=30,
                        avg_bitrate_kbps=5000,
                        total_frames=1000,
                        sample_count=10,
                    ),
                )

        mock_run_ffmpeg.side_effect = create_temp_on_success

        result = executor_with_hw_fallback.execute(plan)

        # Should have called ffmpeg twice (once with HW, once with SW)
        assert mock_run_ffmpeg.call_count == 2
        # Result should be success from the SW retry
        assert result.success is True

    @patch("vpo.executor.transcode.command.require_tool")
    @patch("vpo.executor.transcode.executor.TranscodeExecutor._run_ffmpeg_with_timeout")
    def test_no_retry_when_fallback_disabled(
        self,
        mock_run_ffmpeg: MagicMock,
        mock_require_tool: MagicMock,
        executor_without_hw_fallback: TranscodeExecutor,
        make_plan,
    ):
        """Does not retry when fallback_to_cpu is disabled."""
        mock_require_tool.return_value = Path("/usr/bin/ffmpeg")

        # HW fails with NVENC error
        mock_run_ffmpeg.return_value = (
            False,
            1,
            ["Cannot load nvenc"],
            None,
        )

        plan = make_plan(needs_video_transcode=True)
        result = executor_without_hw_fallback.execute(plan)

        # Should have called ffmpeg only once
        assert mock_run_ffmpeg.call_count == 1
        assert result.success is False

    @patch("vpo.executor.transcode.command.require_tool")
    @patch("vpo.executor.transcode.executor.TranscodeExecutor._run_ffmpeg_with_timeout")
    def test_no_retry_on_non_hw_error(
        self,
        mock_run_ffmpeg: MagicMock,
        mock_require_tool: MagicMock,
        executor_with_hw_fallback: TranscodeExecutor,
        make_plan,
    ):
        """Does not retry on non-hardware errors."""
        mock_require_tool.return_value = Path("/usr/bin/ffmpeg")

        # Failure without HW error patterns
        mock_run_ffmpeg.return_value = (
            False,
            1,
            ["Conversion failed", "Invalid data found"],
            None,
        )

        plan = make_plan(needs_video_transcode=True)
        result = executor_with_hw_fallback.execute(plan)

        # Should have called ffmpeg only once (no retry for non-HW error)
        assert mock_run_ffmpeg.call_count == 1
        assert result.success is False


# =============================================================================
# Tests for HardwareAccelConfig validation
# =============================================================================


class TestHardwareAccelConfigValidation:
    """Tests for HardwareAccelConfig __post_init__ validation."""

    def test_valid_enum_value(self):
        """Valid enum values are accepted."""
        config = HardwareAccelConfig(
            enabled=HardwareAccelMode.NVENC,
            fallback_to_cpu=True,
        )
        assert config.enabled == HardwareAccelMode.NVENC

    def test_all_valid_modes(self):
        """All HardwareAccelMode values are accepted."""
        for mode in HardwareAccelMode:
            config = HardwareAccelConfig(enabled=mode, fallback_to_cpu=True)
            assert config.enabled == mode

    def test_invalid_enabled_value_rejected(self):
        """Non-enum value for enabled raises ValueError."""
        with pytest.raises(ValueError, match="must be a HardwareAccelMode"):
            # Use object.__new__ to bypass normal initialization
            config = object.__new__(HardwareAccelConfig)
            object.__setattr__(config, "enabled", "invalid_string")
            object.__setattr__(config, "fallback_to_cpu", True)
            config.__post_init__()
