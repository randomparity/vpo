"""Unit tests for TranscodeExecutor execute flow.

Tests the full execute() method including:
- Success path execution
- Skip condition handling
- Disk space checking
- Backup creation
- Cleanup on failure
- Output verification
- Timeout handling
- Hardware encoder detection
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.types import TrackInfo
from vpo.executor.transcode import TranscodeExecutor
from vpo.executor.transcode.executor import (
    check_hardware_fallback,
    detect_encoder_type,
)
from vpo.executor.transcode.types import TranscodePlan
from vpo.policy.transcode import SkipEvaluationResult
from vpo.policy.types import (
    QualityMode,
    QualitySettings,
    TranscodePolicyConfig,
)
from vpo.policy.video_analysis import HDRType

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_require_tool():
    """Mock require_tool to return a fake ffmpeg path for CI environments."""
    with patch(
        "vpo.executor.transcode.command.require_tool",
        return_value=Path("/usr/bin/ffmpeg"),
    ):
        yield


@pytest.fixture
def basic_policy() -> TranscodePolicyConfig:
    """Basic transcode policy for testing."""
    return TranscodePolicyConfig(target_video_codec="hevc")


@pytest.fixture
def basic_executor(basic_policy: TranscodePolicyConfig) -> TranscodeExecutor:
    """Basic executor instance for testing."""
    return TranscodeExecutor(policy=basic_policy)


@pytest.fixture
def make_plan_for_executor(tmp_path, basic_policy):
    """Factory for creating TranscodePlan objects for executor tests."""

    def _make(
        needs_video_transcode: bool = True,
        needs_video_scale: bool = False,
        should_skip: bool = False,
        skip_reason: str | None = None,
        audio_tracks: list[TrackInfo] | None = None,
        is_hdr: bool = False,
        hdr_type: HDRType = HDRType.NONE,
        video_width: int | None = 1920,
        video_height: int | None = 1080,
        video_codec: str | None = "h264",
        video_bitrate: int | None = 10_000_000,
    ) -> TranscodePlan:
        skip_result = None
        if should_skip:
            skip_result = SkipEvaluationResult(skip=True, reason=skip_reason or "test")
        # Create input file for tests that need it
        input_path = tmp_path / "input.mkv"
        if not input_path.exists():
            input_path.write_bytes(b"x" * 10000)
        return TranscodePlan(
            input_path=input_path,
            output_path=tmp_path / "output.mkv",
            policy=basic_policy,
            video_codec=video_codec,
            video_width=video_width,
            video_height=video_height,
            video_bitrate=video_bitrate,
            needs_video_transcode=needs_video_transcode,
            needs_video_scale=needs_video_scale,
            skip_result=skip_result,
            audio_tracks=audio_tracks,
            is_hdr=is_hdr,
            hdr_type=hdr_type,
        )

    return _make


# =============================================================================
# Tests for detect_encoder_type
# =============================================================================


class TestDetectEncoderType:
    """Tests for detect_encoder_type function."""

    def test_detects_nvenc_hardware(self):
        """Detects NVIDIA NVENC as hardware encoder."""
        cmd = ["-c:v", "hevc_nvenc", "-preset", "fast"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_vaapi_hardware(self):
        """Detects VA-API as hardware encoder."""
        cmd = ["-c:v", "hevc_vaapi", "-qp", "22"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_qsv_hardware(self):
        """Detects Intel Quick Sync as hardware encoder."""
        cmd = ["-c:v", "h264_qsv", "-preset", "medium"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_amf_hardware(self):
        """Detects AMD AMF as hardware encoder."""
        cmd = ["-c:v", "h264_amf", "-quality", "balanced"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_videotoolbox_hardware(self):
        """Detects Apple VideoToolbox as hardware encoder."""
        cmd = ["-c:v", "hevc_videotoolbox", "-allow_sw", "0"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_libx264_software(self):
        """Detects libx264 as software encoder."""
        cmd = ["-c:v", "libx264", "-crf", "20"]
        assert detect_encoder_type(cmd) == "software"

    def test_detects_libx265_software(self):
        """Detects libx265 as software encoder."""
        cmd = ["-c:v", "libx265", "-preset", "medium"]
        assert detect_encoder_type(cmd) == "software"

    def test_detects_libvpx_software(self):
        """Detects libvpx as software encoder."""
        cmd = ["-c:v", "libvpx-vp9", "-crf", "30"]
        assert detect_encoder_type(cmd) == "software"

    def test_detects_generic_codec_names(self):
        """Detects generic codec names as software."""
        for codec in ["h264", "hevc", "h265", "vp8", "vp9", "av1"]:
            cmd = ["-c:v", codec]
            assert detect_encoder_type(cmd) == "software"

    def test_copy_returns_unknown(self):
        """Stream copy returns unknown encoder type."""
        cmd = ["-c:v", "copy"]
        assert detect_encoder_type(cmd) == "unknown"

    def test_no_codec_returns_unknown(self):
        """Missing codec argument returns unknown."""
        cmd = ["-i", "input.mkv", "-an", "output.mkv"]
        assert detect_encoder_type(cmd) == "unknown"

    def test_handles_codec_v_alias(self):
        """Handles -codec:v as alias for -c:v."""
        cmd = ["-codec:v", "libx265", "-crf", "20"]
        assert detect_encoder_type(cmd) == "software"

    def test_handles_vcodec_alias(self):
        """Handles -vcodec as alias for -c:v."""
        cmd = ["-vcodec", "hevc_nvenc", "-preset", "fast"]
        assert detect_encoder_type(cmd) == "hardware"


# =============================================================================
# Tests for check_hardware_fallback
# =============================================================================


class TestCheckHardwareFallback:
    """Tests for check_hardware_fallback function."""

    def test_detects_vaapi_fallback(self):
        """Detects VAAPI initialization failure."""
        cmd = ["-c:v", "hevc_vaapi"]
        stderr = ["Failed to initialise VAAPI connection: -1"]

        encoder_type, was_fallback = check_hardware_fallback(cmd, stderr)

        assert encoder_type == "software"
        assert was_fallback is True

    def test_detects_nvenc_fallback(self):
        """Detects NVENC unavailability."""
        cmd = ["-c:v", "h264_nvenc"]
        stderr = ["NVENC not available on this system"]

        encoder_type, was_fallback = check_hardware_fallback(cmd, stderr)

        assert encoder_type == "software"
        assert was_fallback is True

    def test_no_fallback_for_software_encoder(self):
        """No fallback detection for software encoder."""
        cmd = ["-c:v", "libx265"]
        stderr = ["Some warning message"]

        encoder_type, was_fallback = check_hardware_fallback(cmd, stderr)

        assert encoder_type == "software"
        assert was_fallback is False

    def test_no_fallback_when_hardware_succeeds(self):
        """No fallback when hardware encoding succeeds."""
        cmd = ["-c:v", "hevc_nvenc"]
        stderr = ["Encoding started successfully"]

        encoder_type, was_fallback = check_hardware_fallback(cmd, stderr)

        assert encoder_type == "hardware"
        assert was_fallback is False

    def test_case_insensitive_pattern_matching(self):
        """Pattern matching is case-insensitive."""
        cmd = ["-c:v", "hevc_vaapi"]
        stderr = ["FAILED TO INITIALISE VAAPI"]

        encoder_type, was_fallback = check_hardware_fallback(cmd, stderr)

        assert was_fallback is True


# =============================================================================
# Tests for TranscodeExecutor.execute
# =============================================================================


class TestTranscodeExecutorExecute:
    """Tests for TranscodeExecutor.execute method."""

    def test_execute_success_path(
        self, basic_executor, make_plan_for_executor, tmp_path, mock_require_tool
    ):
        """Successful execution returns success result with output path."""
        plan = make_plan_for_executor(needs_video_transcode=True)

        # Create temp output path so the exists check passes
        temp_output = tmp_path / ".vpo_temp_output.mkv"
        temp_output.write_bytes(b"transcoded content")

        # Mock FFmpeg to succeed
        with patch.object(basic_executor, "_run_ffmpeg_with_timeout") as mock_ffmpeg:
            mock_ffmpeg.return_value = (
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

            result = basic_executor.execute(plan)

        assert result.success is True

    def test_skips_when_v6_skip_condition_met(
        self, basic_executor, make_plan_for_executor
    ):
        """Skips transcode when skip_result indicates should_skip."""
        plan = make_plan_for_executor(
            should_skip=True,
            skip_reason="codec_matches: hevc",
            needs_video_transcode=False,
        )

        result = basic_executor.execute(plan)

        assert result.success is True
        # No transcode was performed

    def test_skips_when_file_already_compliant(
        self, basic_executor, make_plan_for_executor
    ):
        """Skips transcode when file already meets policy requirements."""
        plan = make_plan_for_executor(needs_video_transcode=False)

        result = basic_executor.execute(plan)

        assert result.success is True

    def test_checks_disk_space_before_transcode(
        self, basic_executor, make_plan_for_executor, tmp_path
    ):
        """Fails early when disk space is insufficient."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = make_plan_for_executor(needs_video_transcode=True)

        with patch.object(basic_executor, "_check_disk_space_for_plan") as mock_check:
            mock_check.return_value = "Insufficient disk space: 0.1GB free, need ~1.0GB"

            result = basic_executor.execute(plan)

        assert result.success is False
        assert "Insufficient disk space" in result.error_message

    def test_cleans_up_partial_on_failure(
        self, basic_executor, make_plan_for_executor, tmp_path, mock_require_tool
    ):
        """Cleans up partial output file when FFmpeg fails."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = make_plan_for_executor(needs_video_transcode=True)

        cleanup_called = {"called": False}

        def mock_cleanup(path):
            cleanup_called["called"] = True

        with patch.object(basic_executor, "_run_ffmpeg_with_timeout") as mock_ffmpeg:
            mock_ffmpeg.return_value = (False, 1, ["Error: encoding failed"], None)

            with patch.object(
                basic_executor, "_cleanup_partial", side_effect=mock_cleanup
            ):
                result = basic_executor.execute(plan)

        assert result.success is False
        assert cleanup_called["called"] is True

    def test_handles_timeout_error(
        self, basic_executor, make_plan_for_executor, tmp_path, mock_require_tool
    ):
        """Returns error result when transcode times out."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = make_plan_for_executor(needs_video_transcode=True)

        with patch.object(basic_executor, "_run_ffmpeg_with_timeout") as mock_ffmpeg:
            mock_ffmpeg.return_value = (False, -1, [], None)  # -1 = timeout

            with patch.object(basic_executor, "_cleanup_partial"):
                result = basic_executor.execute(plan)

        assert result.success is False
        assert "timed out" in result.error_message.lower()


# =============================================================================
# Tests for two-pass encoding
# =============================================================================


class TestTwoPassEncoding:
    """Tests for two-pass encoding in TranscodeExecutor."""

    def test_two_pass_creates_passlog(
        self, basic_executor, make_plan_for_executor, tmp_path, mock_require_tool
    ):
        """Two-pass encoding creates pass log file for second pass."""
        plan = make_plan_for_executor(needs_video_transcode=True)
        quality = QualitySettings(
            mode=QualityMode.BITRATE,
            bitrate="5M",
            two_pass=True,
        )

        # Create temp output file
        temp_output = tmp_path / ".vpo_temp_output.mkv"
        temp_output.write_bytes(b"transcoded content")

        # Mock both passes succeeding
        with patch.object(basic_executor, "_run_ffmpeg_with_timeout") as mock_ffmpeg:
            mock_ffmpeg.return_value = (
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

            with patch.object(
                basic_executor, "_verify_output_integrity", return_value=True
            ):
                basic_executor.execute(plan, quality=quality)

        # Should have called FFmpeg twice (pass 1 and pass 2)
        assert mock_ffmpeg.call_count == 2

    def test_pass1_failure_returns_early(
        self, basic_executor, make_plan_for_executor, tmp_path, mock_require_tool
    ):
        """Two-pass encoding returns early when pass 1 fails."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = make_plan_for_executor(needs_video_transcode=True)
        quality = QualitySettings(
            mode=QualityMode.BITRATE,
            bitrate="5M",
            two_pass=True,
        )

        with patch.object(basic_executor, "_run_ffmpeg_with_timeout") as mock_ffmpeg:
            mock_ffmpeg.return_value = (False, 1, ["Pass 1 error"], None)

            result = basic_executor.execute(plan, quality=quality)

        assert result.success is False
        assert "pass 1" in result.error_message.lower()
        # Only called once (pass 1 failed)
        assert mock_ffmpeg.call_count == 1

    def test_pass2_failure_cleans_up_output(
        self, basic_executor, make_plan_for_executor, tmp_path, mock_require_tool
    ):
        """Two-pass encoding cleans up when pass 2 fails."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = make_plan_for_executor(needs_video_transcode=True)
        quality = QualitySettings(
            mode=QualityMode.BITRATE,
            bitrate="5M",
            two_pass=True,
        )

        cleanup_called = {"called": False}

        def mock_cleanup(path):
            cleanup_called["called"] = True

        with patch.object(basic_executor, "_run_ffmpeg_with_timeout") as mock_ffmpeg:
            # Pass 1 succeeds, Pass 2 fails
            mock_ffmpeg.side_effect = [
                (True, 0, [], None),  # Pass 1
                (False, 1, ["Pass 2 error"], None),  # Pass 2
            ]

            with patch.object(
                basic_executor, "_cleanup_partial", side_effect=mock_cleanup
            ):
                result = basic_executor.execute(plan, quality=quality)

        assert result.success is False
        assert "pass 2" in result.error_message.lower()
        assert cleanup_called["called"] is True


# =============================================================================
# Tests for edge case detection
# =============================================================================


class TestEdgeCaseDetection:
    """Tests for edge case detection in create_plan."""

    def test_detects_vfr_content(self, basic_executor, tmp_path):
        """VFR content is detected and warning added."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = basic_executor.create_plan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            video_codec="h264",
            video_width=1920,
            video_height=1080,
            r_frame_rate="24000/1001",  # 23.976 fps
            avg_frame_rate="30/1",  # 30 fps (very different)
        )

        assert plan.is_vfr is True
        assert plan.warnings is not None
        assert any("VFR" in w or "variable" in w.lower() for w in plan.warnings)

    def test_estimates_bitrate_from_file_size(self, basic_executor, tmp_path):
        """Bitrate is estimated when metadata missing."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = basic_executor.create_plan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            video_codec="h264",
            video_width=1920,
            video_height=1080,
            video_bitrate=None,  # Missing bitrate
            file_size_bytes=1_000_000_000,  # 1GB
            duration_seconds=3600,  # 1 hour
        )

        assert plan.bitrate_estimated is True
        # Estimated bitrate should be calculated
        assert plan.video_bitrate is not None

    def test_selects_primary_video_stream(self, basic_executor, tmp_path):
        """Primary video stream is selected from multiple."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        all_tracks = [
            TrackInfo(
                index=0, track_type="video", codec="h264", width=1920, height=1080
            ),
            TrackInfo(
                index=1, track_type="video", codec="mjpeg", width=640, height=480
            ),  # Thumbnail
            TrackInfo(index=2, track_type="audio", codec="aac"),
        ]

        plan = basic_executor.create_plan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            video_codec="h264",
            video_width=1920,
            video_height=1080,
            all_tracks=all_tracks,
        )

        # Primary video index should be set
        assert plan.primary_video_index == 0

    def test_detects_hdr_content(self, basic_executor, tmp_path):
        """HDR content is detected from color metadata."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        all_tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=3840,
                height=2160,
                color_transfer="smpte2084",  # HDR10
                color_primaries="bt2020",
            ),
        ]

        plan = basic_executor.create_plan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            video_codec="hevc",
            video_width=3840,
            video_height=2160,
            all_tracks=all_tracks,
        )

        assert plan.is_hdr is True
        assert plan.hdr_type == HDRType.HDR10


# =============================================================================
# Tests for is_compliant
# =============================================================================


class TestIsCompliant:
    """Tests for TranscodeExecutor.is_compliant method."""

    def test_compliant_when_codec_matches(self, basic_executor):
        """File is compliant when codec matches target."""
        result = basic_executor.is_compliant(
            video_codec="hevc",  # Matches policy target
            video_width=1920,
            video_height=1080,
        )

        assert result is True

    def test_not_compliant_when_codec_differs(self, basic_executor):
        """File is not compliant when codec differs from target."""
        result = basic_executor.is_compliant(
            video_codec="h264",  # Different from hevc target
            video_width=1920,
            video_height=1080,
        )

        assert result is False


# =============================================================================
# Tests for dry_run
# =============================================================================


class TestDryRun:
    """Tests for TranscodeExecutor.dry_run method."""

    def test_dry_run_shows_operations(
        self, basic_executor, make_plan_for_executor, mock_require_tool
    ):
        """Dry run returns planned operations."""
        plan = make_plan_for_executor(
            needs_video_transcode=True,
            video_codec="h264",
        )

        result = basic_executor.dry_run(plan)

        assert result["needs_transcode"] is True
        assert len(result["video_operations"]) > 0
        assert result["video_operations"][0]["type"] == "video_transcode"
        assert result["video_operations"][0]["from_codec"] == "h264"
        assert result["video_operations"][0]["to_codec"] == "hevc"

    def test_dry_run_skipped_returns_skip_reason(
        self, basic_executor, make_plan_for_executor
    ):
        """Dry run returns skip reason when file is compliant."""
        plan = make_plan_for_executor(
            should_skip=True,
            skip_reason="codec_matches: hevc",
            needs_video_transcode=False,
        )

        result = basic_executor.dry_run(plan)

        assert result["skipped"] is True
        assert "skip_reason" in result
        assert "hevc" in result["skip_reason"]
