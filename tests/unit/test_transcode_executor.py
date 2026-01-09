"""Unit tests for transcode executor."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vpo.executor.transcode import (
    TranscodePlan,
    build_ffmpeg_command,
    should_transcode_video,
)
from vpo.policy.models import TranscodePolicyConfig


@pytest.fixture
def mock_ffmpeg():
    """Mock require_tool to return a fake ffmpeg path."""
    with patch("vpo.executor.transcode.require_tool") as mock_require:
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        yield mock_require


class TestShouldTranscodeVideo:
    """Tests for should_transcode_video function."""

    def test_needs_transcode_for_different_codec(self):
        """Returns True when codec doesn't match target."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")

        needs, scale, w, h = should_transcode_video(policy, "h264", 1920, 1080)

        assert needs is True
        assert scale is False

    def test_no_transcode_for_same_codec(self):
        """Returns False when codec already matches target."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")

        needs, scale, w, h = should_transcode_video(policy, "hevc", 1920, 1080)

        assert needs is False

    def test_handles_codec_aliases(self):
        """Handles codec aliases (h265/hevc, h264/avc)."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")

        # h265 is alias for hevc
        needs, _, _, _ = should_transcode_video(policy, "h265", 1920, 1080)
        assert needs is False

        # x265 is also hevc family
        needs, _, _, _ = should_transcode_video(policy, "x265", 1920, 1080)
        assert needs is False

    def test_needs_scale_for_oversized(self):
        """Returns True for scale when resolution exceeds max."""
        policy = TranscodePolicyConfig(max_resolution="1080p")

        needs, scale, w, h = should_transcode_video(policy, "hevc", 3840, 2160)

        assert needs is True  # Scale triggers transcode
        assert scale is True
        assert w <= 1920
        assert h <= 1080

    def test_no_scale_for_undersized(self):
        """No scale needed when resolution is within limits."""
        policy = TranscodePolicyConfig(max_resolution="1080p")

        needs, scale, w, h = should_transcode_video(policy, "hevc", 1280, 720)

        assert scale is False
        assert w is None
        assert h is None

    def test_maintains_aspect_ratio(self):
        """Scaling maintains aspect ratio."""
        policy = TranscodePolicyConfig(max_resolution="1080p")

        # 21:9 ultrawide
        _, _, w, h = should_transcode_video(policy, "h264", 3440, 1440)

        # Should scale down but maintain aspect ratio
        if w and h:
            original_ratio = 3440 / 1440
            new_ratio = w / h
            assert abs(original_ratio - new_ratio) < 0.1

    def test_ensures_even_dimensions(self):
        """Scaled dimensions are even (required by most codecs)."""
        policy = TranscodePolicyConfig(max_resolution="720p")

        _, _, w, h = should_transcode_video(policy, "h264", 1920, 1080)

        if w and h:
            assert w % 2 == 0
            assert h % 2 == 0

    def test_no_policy_settings_no_transcode(self):
        """No transcode needed when no policy settings specified."""
        policy = TranscodePolicyConfig()

        needs, scale, w, h = should_transcode_video(policy, "h264", 1920, 1080)

        assert needs is False
        assert scale is False

    def test_max_width_height_override(self):
        """max_width/max_height override max_resolution."""
        policy = TranscodePolicyConfig(max_width=1280, max_height=720)

        needs, scale, w, h = should_transcode_video(policy, "hevc", 1920, 1080)

        assert scale is True
        assert w <= 1280
        assert h <= 720


class TestBuildFFmpegCommand:
    """Tests for build_ffmpeg_command function."""

    def test_basic_command_structure(self, mock_ffmpeg):
        """Command has correct basic structure."""
        policy = TranscodePolicyConfig(target_video_codec="hevc", target_crf=23)
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )

        cmd = build_ffmpeg_command(plan)

        assert cmd[0].endswith("ffmpeg")
        assert "-i" in cmd
        assert "/input.mkv" in cmd
        assert "/output.mkv" in cmd

    def test_includes_hevc_encoder(self, mock_ffmpeg):
        """Uses libx265 for HEVC."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )

        cmd = build_ffmpeg_command(plan)

        assert "-c:v" in cmd
        idx = cmd.index("-c:v")
        assert cmd[idx + 1] == "libx265"

    def test_includes_h264_encoder(self, mock_ffmpeg):
        """Uses libx264 for H264."""
        policy = TranscodePolicyConfig(target_video_codec="h264")
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )

        cmd = build_ffmpeg_command(plan)

        idx = cmd.index("-c:v")
        assert cmd[idx + 1] == "libx264"

    def test_includes_crf(self, mock_ffmpeg):
        """Includes CRF setting."""
        policy = TranscodePolicyConfig(target_video_codec="hevc", target_crf=18)
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )

        cmd = build_ffmpeg_command(plan)

        assert "-crf" in cmd
        idx = cmd.index("-crf")
        assert cmd[idx + 1] == "18"

    def test_includes_bitrate(self, mock_ffmpeg):
        """Includes bitrate setting."""
        policy = TranscodePolicyConfig(target_video_codec="hevc", target_bitrate="5M")
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )

        cmd = build_ffmpeg_command(plan)

        assert "-b:v" in cmd
        idx = cmd.index("-b:v")
        assert cmd[idx + 1] == "5M"

    def test_includes_scale_filter(self, mock_ffmpeg):
        """Includes scale filter when needed."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=True,
            needs_video_scale=True,
            target_width=1920,
            target_height=1080,
        )

        cmd = build_ffmpeg_command(plan)

        assert "-vf" in cmd
        idx = cmd.index("-vf")
        assert "scale=" in cmd[idx + 1]

    def test_copies_video_when_no_transcode(self, mock_ffmpeg):
        """Uses copy for video when no transcode needed."""
        policy = TranscodePolicyConfig()
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=False,
        )

        cmd = build_ffmpeg_command(plan)

        assert "-c:v" in cmd
        idx = cmd.index("-c:v")
        assert cmd[idx + 1] == "copy"

    def test_includes_cpu_threads(self, mock_ffmpeg):
        """Includes thread count when specified."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )

        cmd = build_ffmpeg_command(plan, cpu_cores=4)

        assert "-threads" in cmd
        idx = cmd.index("-threads")
        assert cmd[idx + 1] == "4"

    def test_copies_subtitles(self, mock_ffmpeg):
        """Copies subtitle streams."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )

        cmd = build_ffmpeg_command(plan)

        assert "-c:s" in cmd
        idx = cmd.index("-c:s")
        assert cmd[idx + 1] == "copy"


class TestTranscodePlan:
    """Tests for TranscodePlan dataclass."""

    def test_needs_any_transcode_video(self):
        """needs_any_transcode is True for video transcode."""
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=TranscodePolicyConfig(),
            needs_video_transcode=True,
        )
        assert plan.needs_any_transcode is True

    def test_needs_any_transcode_false(self):
        """needs_any_transcode is False when nothing to do."""
        plan = TranscodePlan(
            input_path="/input.mkv",
            output_path="/output.mkv",
            policy=TranscodePolicyConfig(),
            needs_video_transcode=False,
        )
        assert plan.needs_any_transcode is False


class TestTranscodePolicyConfigValidation:
    """Tests for TranscodePolicyConfig validation."""

    def test_valid_codec_accepted(self):
        """Valid codecs are accepted."""
        for codec in ["hevc", "h264", "vp9", "av1"]:
            policy = TranscodePolicyConfig(target_video_codec=codec)
            assert policy.target_video_codec == codec

    def test_invalid_codec_raises(self):
        """Invalid codec raises ValueError."""
        with pytest.raises(ValueError) as exc:
            TranscodePolicyConfig(target_video_codec="invalid")
        assert "Invalid target_video_codec" in str(exc.value)

    def test_crf_range_validation(self):
        """CRF must be 0-51."""
        # Valid
        TranscodePolicyConfig(target_crf=0)
        TranscodePolicyConfig(target_crf=51)

        # Invalid
        with pytest.raises(ValueError):
            TranscodePolicyConfig(target_crf=-1)
        with pytest.raises(ValueError):
            TranscodePolicyConfig(target_crf=52)

    def test_valid_resolution_accepted(self):
        """Valid resolutions are accepted."""
        for res in ["480p", "720p", "1080p", "1440p", "4k", "8k"]:
            policy = TranscodePolicyConfig(max_resolution=res)
            assert policy.max_resolution == res

    def test_invalid_resolution_raises(self):
        """Invalid resolution raises ValueError."""
        with pytest.raises(ValueError):
            TranscodePolicyConfig(max_resolution="invalid")

    def test_has_video_settings_property(self):
        """has_video_settings property works."""
        # No settings
        policy = TranscodePolicyConfig()
        assert policy.has_video_settings is False

        # With codec
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        assert policy.has_video_settings is True

        # With resolution
        policy = TranscodePolicyConfig(max_resolution="1080p")
        assert policy.has_video_settings is True
