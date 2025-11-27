"""Integration tests for transcode executor with V6 schema features.

Tests the end-to-end flow of:
- Skip conditions (codec matching, resolution, bitrate)
- CRF quality settings and audio preservation
- Scaling with hardware acceleration detection
- Edge case handling (VFR, missing bitrate, multiple video streams)
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.executor.transcode import (
    TranscodeExecutor,
    TranscodePlan,
    build_ffmpeg_command,
)
from video_policy_orchestrator.policy.models import (
    AudioTranscodeConfig,
    QualityMode,
    QualitySettings,
    SkipCondition,
    TranscodePolicyConfig,
)
from video_policy_orchestrator.policy.video_analysis import (
    detect_hdr_content,
    detect_missing_bitrate,
    detect_vfr_content,
    select_primary_video_stream,
)
from video_policy_orchestrator.tools.encoders import select_encoder_with_fallback

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_ffmpeg():
    """Mock require_tool to return a fake ffmpeg path."""
    with patch(
        "video_policy_orchestrator.executor.transcode.require_tool"
    ) as mock_require:
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        yield mock_require


@pytest.fixture
def hevc_policy() -> TranscodePolicyConfig:
    """Basic HEVC transcoding policy."""
    return TranscodePolicyConfig(
        target_video_codec="hevc",
        target_crf=20,
        max_resolution="1080p",
    )


@pytest.fixture
def skip_condition_hevc_1080p() -> SkipCondition:
    """Skip condition for HEVC files at 1080p or lower."""
    return SkipCondition(
        codec_matches=("hevc", "h265"),
        resolution_within="1080p",
        bitrate_under="15M",
    )


@pytest.fixture
def quality_crf_20() -> QualitySettings:
    """CRF 20 quality settings."""
    return QualitySettings(
        mode=QualityMode.CRF,
        crf=20,
        preset="medium",
        tune="film",
    )


@pytest.fixture
def audio_config_preserve_lossless() -> AudioTranscodeConfig:
    """Audio config that preserves lossless codecs."""
    return AudioTranscodeConfig(
        preserve_codecs=("truehd", "dts-hd", "flac"),
        transcode_to="aac",
        transcode_bitrate="192k",
    )


@pytest.fixture
def video_track_hevc_1080p() -> TrackInfo:
    """HEVC video track at 1080p."""
    return TrackInfo(
        index=0,
        track_type="video",
        codec="hevc",
        width=1920,
        height=1080,
        frame_rate="24000/1001",
    )


@pytest.fixture
def video_track_h264_4k() -> TrackInfo:
    """H.264 video track at 4K."""
    return TrackInfo(
        index=0,
        track_type="video",
        codec="h264",
        width=3840,
        height=2160,
        frame_rate="24000/1001",
    )


@pytest.fixture
def audio_track_truehd_51() -> TrackInfo:
    """TrueHD 5.1 audio track (lossless)."""
    return TrackInfo(
        index=1,
        track_type="audio",
        codec="truehd",
        language="eng",
        channels=6,
        channel_layout="5.1",
    )


@pytest.fixture
def audio_track_ac3_stereo() -> TrackInfo:
    """AC3 stereo audio track (lossy)."""
    return TrackInfo(
        index=2,
        track_type="audio",
        codec="ac3",
        language="eng",
        channels=2,
        channel_layout="stereo",
    )


# =============================================================================
# T091: Integration test - Skip + CRF + audio preservation
# =============================================================================


class TestSkipConditionWithCRFAndAudioPreservation:
    """Test skip conditions work correctly with CRF quality and audio preservation."""

    def test_hevc_1080p_file_is_skipped(
        self,
        hevc_policy: TranscodePolicyConfig,
        skip_condition_hevc_1080p: SkipCondition,
        audio_config_preserve_lossless: AudioTranscodeConfig,
        video_track_hevc_1080p: TrackInfo,
        audio_track_truehd_51: TrackInfo,
    ) -> None:
        """HEVC 1080p file matching skip conditions should be skipped."""
        executor = TranscodeExecutor(
            policy=hevc_policy,
            skip_if=skip_condition_hevc_1080p,
            audio_config=audio_config_preserve_lossless,
        )

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=8_000_000,  # 8 Mbps (under 15M threshold)
            duration_seconds=7200,
            audio_tracks=[audio_track_truehd_51],
        )

        assert plan.should_skip is True
        assert plan.needs_any_transcode is False
        assert "Already compliant" in (plan.skip_reason or "")

    def test_h264_file_not_skipped(
        self,
        hevc_policy: TranscodePolicyConfig,
        skip_condition_hevc_1080p: SkipCondition,
        audio_config_preserve_lossless: AudioTranscodeConfig,
        audio_track_truehd_51: TrackInfo,
    ) -> None:
        """H.264 file should not be skipped (codec doesn't match)."""
        executor = TranscodeExecutor(
            policy=hevc_policy,
            skip_if=skip_condition_hevc_1080p,
            audio_config=audio_config_preserve_lossless,
        )

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="h264",  # Not HEVC
            video_width=1920,
            video_height=1080,
            video_bitrate=8_000_000,
            duration_seconds=7200,
            audio_tracks=[audio_track_truehd_51],
        )

        assert plan.should_skip is False
        assert plan.needs_video_transcode is True

    def test_high_bitrate_not_skipped(
        self,
        hevc_policy: TranscodePolicyConfig,
        skip_condition_hevc_1080p: SkipCondition,
        audio_config_preserve_lossless: AudioTranscodeConfig,
        audio_track_truehd_51: TrackInfo,
    ) -> None:
        """HEVC file with high bitrate should not be skipped."""
        executor = TranscodeExecutor(
            policy=hevc_policy,
            skip_if=skip_condition_hevc_1080p,
            audio_config=audio_config_preserve_lossless,
        )

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=20_000_000,  # 20 Mbps (over 15M threshold)
            duration_seconds=7200,
            audio_tracks=[audio_track_truehd_51],
        )

        assert plan.should_skip is False
        assert "exceeds" in (plan.skip_result.reason or "").lower()

    def test_4k_resolution_not_skipped(
        self,
        hevc_policy: TranscodePolicyConfig,
        skip_condition_hevc_1080p: SkipCondition,
        audio_config_preserve_lossless: AudioTranscodeConfig,
        audio_track_truehd_51: TrackInfo,
    ) -> None:
        """4K HEVC file should not be skipped (resolution exceeds threshold)."""
        executor = TranscodeExecutor(
            policy=hevc_policy,
            skip_if=skip_condition_hevc_1080p,
            audio_config=audio_config_preserve_lossless,
        )

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="hevc",
            video_width=3840,
            video_height=2160,  # 4K exceeds 1080p threshold
            video_bitrate=8_000_000,
            duration_seconds=7200,
            audio_tracks=[audio_track_truehd_51],
        )

        assert plan.should_skip is False
        assert "resolution" in (plan.skip_result.reason or "").lower()

    def test_lossless_audio_preserved_in_plan(
        self,
        hevc_policy: TranscodePolicyConfig,
        audio_config_preserve_lossless: AudioTranscodeConfig,
        audio_track_truehd_51: TrackInfo,
        audio_track_ac3_stereo: TrackInfo,
    ) -> None:
        """Lossless audio should be preserved, lossy should be transcoded."""
        executor = TranscodeExecutor(
            policy=hevc_policy,
            audio_config=audio_config_preserve_lossless,
        )

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="h264",  # Needs transcode
            video_width=1920,
            video_height=1080,
            duration_seconds=7200,
            audio_tracks=[audio_track_truehd_51, audio_track_ac3_stereo],
        )

        assert plan.audio_plan is not None
        assert len(plan.audio_plan.tracks) == 2

        # TrueHD should be copied
        truehd_track = plan.audio_plan.tracks[0]
        assert truehd_track.action.value == "copy"

        # AC3 should be transcoded
        ac3_track = plan.audio_plan.tracks[1]
        assert ac3_track.action.value == "transcode"
        assert ac3_track.target_codec == "aac"


class TestCRFQualitySettingsInFFmpegCommand:
    """Test that CRF quality settings are correctly applied to FFmpeg commands."""

    def test_crf_mode_generates_correct_args(
        self,
        mock_ffmpeg,
        hevc_policy: TranscodePolicyConfig,
        quality_crf_20: QualitySettings,
    ) -> None:
        """CRF mode should generate -crf flag in FFmpeg command."""
        plan = TranscodePlan(
            input_path=Path("/test/input.mkv"),
            output_path=Path("/test/output.mkv"),
            policy=hevc_policy,
            needs_video_transcode=True,
        )

        cmd = build_ffmpeg_command(plan, quality=quality_crf_20)

        assert "-crf" in cmd
        crf_idx = cmd.index("-crf")
        assert cmd[crf_idx + 1] == "20"

        # Should include preset for x265
        assert "-preset" in cmd
        preset_idx = cmd.index("-preset")
        assert cmd[preset_idx + 1] == "medium"

        # Should include tune
        assert "-tune" in cmd
        tune_idx = cmd.index("-tune")
        assert cmd[tune_idx + 1] == "film"


# =============================================================================
# T092: Integration test - Scaling + hardware acceleration
# =============================================================================


class TestScalingWithHardwareAcceleration:
    """Test scaling operations with hardware acceleration detection."""

    def test_4k_to_1080p_scaling_plan(
        self,
        hevc_policy: TranscodePolicyConfig,
        video_track_h264_4k: TrackInfo,
    ) -> None:
        """4K input should be scaled to 1080p with max_resolution policy."""
        executor = TranscodeExecutor(policy=hevc_policy)

        plan = executor.create_plan(
            input_path=Path("/test/4k-movie.mkv"),
            output_path=Path("/test/output/4k-movie.mkv"),
            video_codec="h264",
            video_width=3840,
            video_height=2160,
            duration_seconds=7200,
        )

        assert plan.needs_video_scale is True
        assert plan.needs_video_transcode is True
        assert plan.target_width is not None
        assert plan.target_height is not None
        assert plan.target_width <= 1920
        assert plan.target_height <= 1080

    def test_scaling_command_includes_filter(
        self,
        mock_ffmpeg,
        hevc_policy: TranscodePolicyConfig,
    ) -> None:
        """Scaling plan should generate -vf scale filter in command."""
        plan = TranscodePlan(
            input_path=Path("/test/input.mkv"),
            output_path=Path("/test/output.mkv"),
            policy=hevc_policy,
            needs_video_transcode=True,
            needs_video_scale=True,
            target_width=1920,
            target_height=1080,
        )

        cmd = build_ffmpeg_command(plan)

        assert "-vf" in cmd
        vf_idx = cmd.index("-vf")
        assert "scale=1920:1080" in cmd[vf_idx + 1]

    def test_hw_encoder_selection_with_fallback(self) -> None:
        """Hardware encoder selection should fall back to software."""
        # Mock check_encoder_available to return False
        with patch(
            "video_policy_orchestrator.tools.encoders.check_encoder_available"
        ) as mock_check:
            mock_check.return_value = False

            encoder, encoder_type = select_encoder_with_fallback(
                codec="hevc",
                hw_mode="auto",
                fallback_to_cpu=True,
            )

            assert encoder_type == "software"
            assert encoder == "libx265"

    def test_hw_encoder_selection_nvenc_available(self) -> None:
        """Should select NVENC when available in auto mode."""
        with patch(
            "video_policy_orchestrator.tools.encoders.check_encoder_available"
        ) as mock_check:
            # Only NVENC is available
            mock_check.side_effect = lambda enc: enc == "hevc_nvenc"

            encoder, encoder_type = select_encoder_with_fallback(
                codec="hevc",
                hw_mode="auto",
                fallback_to_cpu=True,
            )

            assert encoder_type == "hardware"
            assert encoder == "hevc_nvenc"

    def test_hw_encoder_selection_explicit_mode(self) -> None:
        """Explicit hardware mode should select that encoder."""
        with patch(
            "video_policy_orchestrator.tools.encoders.check_encoder_available"
        ) as mock_check:
            mock_check.return_value = True

            encoder, encoder_type = select_encoder_with_fallback(
                codec="hevc",
                hw_mode="qsv",
                fallback_to_cpu=True,
            )

            assert encoder_type == "hardware"
            assert encoder == "hevc_qsv"

    def test_hw_encoder_selection_none_mode(self) -> None:
        """Mode 'none' should force software encoding."""
        encoder, encoder_type = select_encoder_with_fallback(
            codec="hevc",
            hw_mode="none",
            fallback_to_cpu=True,
        )

        assert encoder_type == "software"
        assert encoder == "libx265"


# =============================================================================
# Edge Case Detection Tests
# =============================================================================


class TestEdgeCaseDetection:
    """Test edge case detection utilities."""

    def test_vfr_detection_with_difference(self) -> None:
        """VFR should be detected when frame rates differ significantly."""
        is_vfr, warning = detect_vfr_content(
            r_frame_rate="30/1",
            avg_frame_rate="24000/1001",  # ~23.976
        )

        assert is_vfr is True
        assert warning is not None
        assert "Variable frame rate" in warning

    def test_vfr_not_detected_for_cfr(self) -> None:
        """VFR should not be detected for constant frame rate content."""
        is_vfr, warning = detect_vfr_content(
            r_frame_rate="24000/1001",
            avg_frame_rate="24000/1001",
        )

        assert is_vfr is False
        assert warning is None

    def test_missing_bitrate_estimation(self) -> None:
        """Missing bitrate should be estimated from file size and duration."""
        was_estimated, estimated, warning = detect_missing_bitrate(
            bitrate=None,
            file_size_bytes=1_000_000_000,  # 1 GB
            duration_seconds=3600,  # 1 hour
        )

        assert was_estimated is True
        assert estimated is not None
        assert estimated > 0
        assert warning is not None
        assert "estimated" in warning.lower()

    def test_bitrate_not_estimated_when_present(self) -> None:
        """Bitrate should not be estimated when already present."""
        was_estimated, actual, warning = detect_missing_bitrate(
            bitrate=8_000_000,  # 8 Mbps
            file_size_bytes=1_000_000_000,
            duration_seconds=3600,
        )

        assert was_estimated is False
        assert actual == 8_000_000
        assert warning is None

    def test_multiple_video_streams_primary_selection(self) -> None:
        """Primary video stream should be selected from multiple streams."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc", is_default=False),
            TrackInfo(index=1, track_type="video", codec="h264", is_default=True),
            TrackInfo(index=2, track_type="audio", codec="aac"),
        ]

        primary, warnings = select_primary_video_stream(tracks)

        assert primary is not None
        assert primary.index == 1  # Default should be selected
        assert len(warnings) == 1
        assert "Multiple video streams" in warnings[0]

    def test_single_video_stream_no_warning(self) -> None:
        """Single video stream should not generate warnings."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="audio", codec="aac"),
        ]

        primary, warnings = select_primary_video_stream(tracks)

        assert primary is not None
        assert primary.index == 0
        assert len(warnings) == 0

    def test_hdr_detection_by_title(self) -> None:
        """HDR should be detected from track title."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                title="4K HDR Video",
            ),
        ]

        is_hdr, hdr_type = detect_hdr_content(tracks)

        assert is_hdr is True
        assert hdr_type is not None
        assert "hdr" in hdr_type.lower()

    def test_no_hdr_detection_for_sdr(self) -> None:
        """SDR content should not be detected as HDR."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                title="Regular Video",
            ),
        ]

        is_hdr, hdr_type = detect_hdr_content(tracks)

        assert is_hdr is False
        assert hdr_type is None


class TestTranscodePlanWithEdgeCases:
    """Test TranscodePlan includes edge case information."""

    def test_plan_includes_vfr_warning(
        self,
        hevc_policy: TranscodePolicyConfig,
    ) -> None:
        """Plan should include VFR warning when detected."""
        executor = TranscodeExecutor(policy=hevc_policy)

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="h264",
            video_width=1920,
            video_height=1080,
            duration_seconds=7200,
            r_frame_rate="30/1",
            avg_frame_rate="24000/1001",  # Different = VFR
        )

        assert plan.is_vfr is True
        assert plan.warnings is not None
        assert any("Variable frame rate" in w for w in plan.warnings)

    def test_plan_includes_bitrate_estimation(
        self,
        hevc_policy: TranscodePolicyConfig,
    ) -> None:
        """Plan should estimate bitrate when metadata is missing."""
        executor = TranscodeExecutor(policy=hevc_policy)

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="h264",
            video_width=1920,
            video_height=1080,
            video_bitrate=None,  # Missing
            duration_seconds=7200,
            file_size_bytes=2_000_000_000,  # 2 GB
        )

        assert plan.bitrate_estimated is True
        # video_bitrate should now have estimated value
        assert plan.video_bitrate is not None
        assert plan.video_bitrate > 0

    def test_plan_includes_multiple_video_warning(
        self,
        hevc_policy: TranscodePolicyConfig,
    ) -> None:
        """Plan should warn about multiple video streams."""
        all_tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="video", codec="h264"),
            TrackInfo(index=2, track_type="audio", codec="aac"),
        ]

        executor = TranscodeExecutor(policy=hevc_policy)

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            duration_seconds=7200,
            all_tracks=all_tracks,
        )

        assert plan.primary_video_index is not None
        assert plan.warnings is not None
        assert any("Multiple video streams" in w for w in plan.warnings)

    def test_plan_includes_hdr_warning_when_scaling(
        self,
        hevc_policy: TranscodePolicyConfig,
    ) -> None:
        """Plan should warn about HDR when scaling."""
        all_tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                title="4K HDR",
                width=3840,
                height=2160,
            ),
        ]

        executor = TranscodeExecutor(policy=hevc_policy)

        plan = executor.create_plan(
            input_path=Path("/test/movie.mkv"),
            output_path=Path("/test/output/movie.mkv"),
            video_codec="hevc",
            video_width=3840,
            video_height=2160,
            duration_seconds=7200,
            all_tracks=all_tracks,
        )

        assert plan.is_hdr is True
        assert plan.needs_video_scale is True
        assert plan.warnings is not None
        assert any("HDR" in w for w in plan.warnings)
