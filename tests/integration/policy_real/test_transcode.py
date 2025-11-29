"""Integration tests for transcode operations using real video files.

These tests verify that ffmpeg transcode operations work correctly
on actual video files.

Tier 3: Transcode operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from video_policy_orchestrator.executor.transcode import (
    TranscodeExecutor,
    build_ffmpeg_command,
)
from video_policy_orchestrator.policy.models import (
    TranscodePolicyConfig,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector

from .conftest import get_video_tracks

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,  # Mark as slow since transcoding takes time
]


class TestTranscodePlanCreation:
    """Test transcode plan creation with real files."""

    def test_plan_creation_for_h264_to_hevc(
        self,
        generated_h264_1080p: Path | None,
        tmp_path: Path,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """Plan should indicate H.264 to HEVC transcode is needed."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_h264_1080p is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_h264_1080p)
        video_track = get_video_tracks(result)[0]

        # Verify file is H.264
        assert video_track.codec in ("h264", "avc"), (
            f"Expected H.264, got {video_track.codec}"
        )

        policy = TranscodePolicyConfig(
            target_video_codec="hevc",
            target_crf=28,
        )

        executor = TranscodeExecutor(policy=policy)

        plan = executor.create_plan(
            input_path=generated_h264_1080p,
            output_path=tmp_path / "output.mkv",
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            duration_seconds=2.0,
        )

        # Plan should require transcode
        assert plan.needs_video_transcode is True
        assert plan.should_skip is False

    def test_plan_creation_hevc_no_transcode_needed(
        self,
        generated_basic_hevc: Path | None,
        tmp_path: Path,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """Plan should not require transcode when codec already matches."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_basic_hevc is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_basic_hevc)
        video_track = get_video_tracks(result)[0]

        # Verify file is HEVC
        assert video_track.codec in ("hevc", "h265"), (
            f"Expected HEVC, got {video_track.codec}"
        )

        policy = TranscodePolicyConfig(
            target_video_codec="hevc",
            target_crf=28,
        )

        executor = TranscodeExecutor(policy=policy)

        plan = executor.create_plan(
            input_path=generated_basic_hevc,
            output_path=tmp_path / "output.mkv",
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            duration_seconds=2.0,
        )

        # Plan should NOT require transcode (codec already matches)
        assert plan.needs_video_transcode is False


class TestTranscodeCommandGeneration:
    """Test FFmpeg command generation for real files."""

    def test_command_includes_codec_settings(
        self,
        generated_h264_1080p: Path | None,
        tmp_path: Path,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """Generated command should include correct codec and quality settings."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_h264_1080p is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_h264_1080p)
        video_track = get_video_tracks(result)[0]

        policy = TranscodePolicyConfig(
            target_video_codec="hevc",
            target_crf=28,
        )

        executor = TranscodeExecutor(policy=policy)

        plan = executor.create_plan(
            input_path=generated_h264_1080p,
            output_path=tmp_path / "output.mkv",
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            duration_seconds=2.0,
        )

        # Build command
        cmd = build_ffmpeg_command(plan)

        # Command should be a list of strings
        assert isinstance(cmd, list)

        # Command should include essential elements
        cmd_str = " ".join(cmd)
        assert "-i" in cmd_str  # Input file
        assert "libx265" in cmd_str or "hevc" in cmd_str  # HEVC encoder


class TestScalingPlan:
    """Test scaling detection in transcode plans."""

    def test_4k_needs_scaling_to_1080p(
        self,
        generated_hevc_4k: Path | None,
        tmp_path: Path,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """4K file should be scaled to 1080p when max_resolution set."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_hevc_4k is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_hevc_4k)
        video_track = get_video_tracks(result)[0]

        # Verify file is 4K
        assert video_track.width is not None and video_track.width >= 3840

        policy = TranscodePolicyConfig(
            target_video_codec="hevc",
            target_crf=28,
            max_resolution="1080p",  # Scale down from 4K
        )

        executor = TranscodeExecutor(policy=policy)

        plan = executor.create_plan(
            input_path=generated_hevc_4k,
            output_path=tmp_path / "output.mkv",
            video_codec=video_track.codec,
            video_width=video_track.width,
            video_height=video_track.height or 2160,
            duration_seconds=2.0,
        )

        # Plan should indicate scaling is needed
        assert plan.needs_video_scale is True
        assert plan.target_height is not None
        assert plan.target_height <= 1080

    def test_1080p_no_scaling_needed(
        self,
        generated_h264_1080p: Path | None,
        tmp_path: Path,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """1080p file should not need scaling when max is 1080p."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_h264_1080p is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_h264_1080p)
        video_track = get_video_tracks(result)[0]

        policy = TranscodePolicyConfig(
            target_video_codec="hevc",
            target_crf=28,
            max_resolution="1080p",
        )

        executor = TranscodeExecutor(policy=policy)

        plan = executor.create_plan(
            input_path=generated_h264_1080p,
            output_path=tmp_path / "output.mkv",
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            duration_seconds=2.0,
        )

        # 1080p should not need scaling
        assert plan.needs_video_scale is False
