"""Integration tests for V6 skip conditions using real video files.

These tests verify that transcode skip conditions (codec matching, resolution,
bitrate thresholds) work correctly when evaluating real video files.

Tier 3: Advanced transcode features.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vpo.executor.transcode import (
    TranscodeExecutor,
)
from vpo.policy.transcode import evaluate_skip_condition
from vpo.policy.types import (
    SkipCondition,
    TranscodePolicyConfig,
)

if TYPE_CHECKING:
    from vpo.introspector.ffprobe import FFprobeIntrospector

from .conftest import get_video_tracks

pytestmark = [
    pytest.mark.integration,
]


class TestSkipConditionCodecMatching:
    """Test skip conditions based on codec matching."""

    def test_hevc_file_skipped_when_codec_matches(
        self,
        generated_hevc_low_bitrate: Path | None,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """HEVC file should be skipped when skip_if.codec_matches includes hevc."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_hevc_low_bitrate is None:
            pytest.skip("Test video not available")

        # Introspect the file
        result = introspector.get_file_info(generated_hevc_low_bitrate)
        video_track = get_video_tracks(result)[0]

        # Verify file is HEVC
        assert video_track.codec in ("hevc", "h265"), (
            f"Expected HEVC, got {video_track.codec}"
        )

        # Create skip condition
        skip_condition = SkipCondition(
            codec_matches=("hevc", "h265"),
            resolution_within="1080p",
            bitrate_under="15M",
        )

        # Evaluate skip condition directly
        skip_result = evaluate_skip_condition(
            skip_condition,
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            video_bitrate=8_000_000,  # Under 15M threshold
        )

        # Should be skipped
        assert skip_result.skip is True

    def test_h264_file_not_skipped_codec_mismatch(
        self,
        generated_h264_1080p: Path | None,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """H.264 file should NOT be skipped when codec doesn't match."""
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

        skip_condition = SkipCondition(
            codec_matches=("hevc", "h265"),  # H.264 won't match
            resolution_within="1080p",
            bitrate_under="15M",
        )

        skip_result = evaluate_skip_condition(
            skip_condition,
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            video_bitrate=8_000_000,
        )

        # Should NOT be skipped (codec doesn't match)
        assert skip_result.skip is False


class TestSkipConditionResolution:
    """Test skip conditions based on resolution thresholds."""

    def test_4k_not_skipped_resolution_exceeds(
        self,
        generated_hevc_4k: Path | None,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """4K file should NOT be skipped when resolution exceeds threshold."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_hevc_4k is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_hevc_4k)
        video_track = get_video_tracks(result)[0]

        # Verify file is 4K
        assert video_track.width is not None and video_track.width >= 3840

        skip_condition = SkipCondition(
            codec_matches=("hevc", "h265"),
            resolution_within="1080p",  # 4K exceeds this
            bitrate_under="15M",
        )

        skip_result = evaluate_skip_condition(
            skip_condition,
            video_codec=video_track.codec,
            video_width=video_track.width,
            video_height=video_track.height or 2160,
            video_bitrate=8_000_000,
        )

        # Should NOT be skipped (resolution exceeds threshold)
        assert skip_result.skip is False

    def test_1080p_skipped_resolution_within(
        self,
        generated_basic_hevc: Path | None,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """1080p file should be skipped when resolution is within threshold."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_basic_hevc is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_basic_hevc)
        video_track = get_video_tracks(result)[0]

        # Verify file is 1080p or less
        assert video_track.height is not None and video_track.height <= 1080

        skip_condition = SkipCondition(
            codec_matches=("hevc", "h265"),
            resolution_within="1080p",
            bitrate_under="15M",
        )

        skip_result = evaluate_skip_condition(
            skip_condition,
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height,
            video_bitrate=8_000_000,  # Under threshold
        )

        # Should be skipped (all conditions met)
        assert skip_result.skip is True


class TestSkipConditionBitrate:
    """Test skip conditions based on bitrate thresholds."""

    def test_high_bitrate_not_skipped(
        self,
        generated_hevc_high_bitrate: Path | None,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """High bitrate file should NOT be skipped."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_hevc_high_bitrate is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_hevc_high_bitrate)
        video_track = get_video_tracks(result)[0]

        skip_condition = SkipCondition(
            codec_matches=("hevc", "h265"),
            resolution_within="1080p",
            bitrate_under="15M",  # High bitrate file should exceed this
        )

        # Use the actual target bitrate from the spec (20M)
        skip_result = evaluate_skip_condition(
            skip_condition,
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            video_bitrate=20_000_000,  # 20M exceeds 15M threshold
        )

        # Should NOT be skipped (bitrate exceeds threshold)
        assert skip_result.skip is False

    def test_low_bitrate_skipped(
        self,
        generated_hevc_low_bitrate: Path | None,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """Low bitrate file should be skipped when under threshold."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_hevc_low_bitrate is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_hevc_low_bitrate)
        video_track = get_video_tracks(result)[0]

        skip_condition = SkipCondition(
            codec_matches=("hevc", "h265"),
            resolution_within="1080p",
            bitrate_under="15M",
        )

        skip_result = evaluate_skip_condition(
            skip_condition,
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            video_bitrate=8_000_000,  # 8M under 15M threshold
        )

        # Should be skipped (all conditions met)
        assert skip_result.skip is True


class TestTranscodePlanCreation:
    """Test creating transcode plans with real files."""

    def test_plan_creation_with_skip_condition(
        self,
        generated_basic_hevc: Path | None,
        tmp_path: Path,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """TranscodePlan should correctly indicate skip status."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_basic_hevc is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_basic_hevc)
        video_track = get_video_tracks(result)[0]

        policy = TranscodePolicyConfig(
            target_video_codec="hevc",
            target_crf=20,
        )
        skip_condition = SkipCondition(
            codec_matches=("hevc", "h265"),
            resolution_within="1080p",
            bitrate_under="15M",
        )

        executor = TranscodeExecutor(
            policy=policy,
            skip_if=skip_condition,
        )

        plan = executor.create_plan(
            input_path=generated_basic_hevc,
            output_path=tmp_path / "output.mkv",
            video_codec=video_track.codec,
            video_width=video_track.width or 1920,
            video_height=video_track.height or 1080,
            video_bitrate=8_000_000,
            duration_seconds=2.0,
        )

        # Verify plan has correct skip state
        assert plan.should_skip is True
        assert plan.skip_reason is not None

    def test_plan_creation_needs_transcode(
        self,
        generated_h264_1080p: Path | None,
        tmp_path: Path,
        introspector: FFprobeIntrospector,
        ffmpeg_available: bool,
    ) -> None:
        """Plan should indicate transcode needed when codec differs."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if generated_h264_1080p is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_h264_1080p)
        video_track = get_video_tracks(result)[0]

        policy = TranscodePolicyConfig(
            target_video_codec="hevc",  # Target is HEVC, but file is H.264
            target_crf=20,
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

        # Should NOT be skipped - needs transcode from H.264 to HEVC
        assert plan.should_skip is False
        assert plan.needs_video_transcode is True
