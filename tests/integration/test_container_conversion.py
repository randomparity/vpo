"""Integration tests for container conversion functionality.

Tests the end-to-end flow of container conversion (AVI to MKV, MKV to MP4)
through the evaluator and executor.
"""

from pathlib import Path

import pytest

from vpo.db import TrackInfo
from vpo.policy.evaluator import evaluate_policy
from vpo.policy.exceptions import IncompatibleCodecError
from vpo.policy.types import (
    AudioFilterConfig,
    ContainerConfig,
    EvaluationPolicy,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def v3_mkv_target_policy(temp_dir: Path) -> Path:
    """Create a policy file with MKV container target."""
    policy_path = temp_dir / "mkv-target-policy.yaml"
    policy_path.write_text("""
schema_version: 12
config:
  audio_language_preference:
    - eng
  subtitle_language_preference:
    - eng
phases:
  - name: apply
    track_order:
      - video
      - audio_main
      - subtitle_main
    container:
      target: mkv
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
""")
    return policy_path


@pytest.fixture
def v3_mp4_target_policy(temp_dir: Path) -> Path:
    """Create a policy file with MP4 container target."""
    policy_path = temp_dir / "mp4-target-policy.yaml"
    policy_path.write_text("""
schema_version: 12
config:
  audio_language_preference:
    - eng
  subtitle_language_preference:
    - eng
phases:
  - name: apply
    track_order:
      - video
      - audio_main
    container:
      target: mp4
      on_incompatible_codec: error
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
""")
    return policy_path


@pytest.fixture
def v3_mp4_skip_policy(temp_dir: Path) -> Path:
    """Create a policy file with MP4 target and skip mode."""
    policy_path = temp_dir / "mp4-skip-policy.yaml"
    policy_path.write_text("""
schema_version: 12
config:
  audio_language_preference:
    - eng
  subtitle_language_preference:
    - eng
phases:
  - name: apply
    track_order:
      - video
      - audio_main
    container:
      target: mp4
      on_incompatible_codec: skip
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
""")
    return policy_path


@pytest.fixture
def avi_compatible_tracks() -> list[TrackInfo]:
    """Create test tracks for an AVI file with MKV-compatible codecs."""
    return [
        TrackInfo(
            index=0,
            track_type="video",
            codec="mpeg4",
            width=1920,
            height=1080,
        ),
        TrackInfo(
            index=1,
            track_type="audio",
            codec="mp3",
            language="eng",
            channels=2,
        ),
    ]


@pytest.fixture
def mkv_mp4_compatible_tracks() -> list[TrackInfo]:
    """Create test tracks for an MKV file with MP4-compatible codecs."""
    return [
        TrackInfo(
            index=0,
            track_type="video",
            codec="h264",
            width=1920,
            height=1080,
        ),
        TrackInfo(
            index=1,
            track_type="audio",
            codec="aac",
            language="eng",
            channels=6,
        ),
    ]


@pytest.fixture
def mkv_mp4_incompatible_tracks() -> list[TrackInfo]:
    """Create test tracks for an MKV file with MP4-incompatible codecs."""
    return [
        TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            width=3840,
            height=2160,
        ),
        TrackInfo(
            index=1,
            track_type="audio",
            codec="truehd",  # Incompatible with MP4
            language="eng",
            channels=8,
        ),
        TrackInfo(
            index=2,
            track_type="subtitle",
            codec="hdmv_pgs_subtitle",  # Incompatible with MP4
            language="eng",
        ),
    ]


# =============================================================================
# Tests for AVI to MKV Conversion (T040)
# =============================================================================


class TestAviToMkvConversion:
    """Integration tests for AVI to MKV container conversion."""

    def test_avi_to_mkv_plan_created(
        self,
        avi_compatible_tracks: list[TrackInfo],
    ) -> None:
        """AVI to MKV conversion should create a plan with container_change."""
        policy = EvaluationPolicy(
            container=ContainerConfig(target="mkv"),
        )

        plan = evaluate_policy(
            file_id="test-avi-id",
            file_path=Path("/test/video.avi"),
            container="avi",
            tracks=avi_compatible_tracks,
            policy=policy,
        )

        assert plan.container_change is not None
        assert plan.container_change.source_format == "avi"
        assert plan.container_change.target_format == "mkv"
        assert plan.requires_remux is True
        assert len(plan.container_change.incompatible_tracks) == 0

    def test_mov_to_mkv_plan_created(
        self,
        avi_compatible_tracks: list[TrackInfo],
    ) -> None:
        """MOV to MKV conversion should create a plan with container_change."""
        policy = EvaluationPolicy(
            container=ContainerConfig(target="mkv"),
        )

        plan = evaluate_policy(
            file_id="test-mov-id",
            file_path=Path("/test/video.mov"),
            container="mov",
            tracks=avi_compatible_tracks,
            policy=policy,
        )

        assert plan.container_change is not None
        assert plan.container_change.source_format == "mov"
        assert plan.container_change.target_format == "mkv"

    def test_mkv_to_mkv_no_change(
        self,
        mkv_mp4_compatible_tracks: list[TrackInfo],
    ) -> None:
        """MKV to MKV should not require remux."""
        policy = EvaluationPolicy(
            container=ContainerConfig(target="mkv"),
        )

        plan = evaluate_policy(
            file_id="test-mkv-id",
            file_path=Path("/test/video.mkv"),
            container="mkv",
            tracks=mkv_mp4_compatible_tracks,
            policy=policy,
        )

        # ContainerChange is created for logging, but no remux is needed
        assert plan.container_change is not None
        assert plan.container_change.source_format == "mkv"
        assert plan.container_change.target_format == "mkv"
        assert plan.requires_remux is False

    def test_matroska_format_normalized(
        self,
        mkv_mp4_compatible_tracks: list[TrackInfo],
    ) -> None:
        """'matroska' container format should be normalized to 'mkv'."""
        policy = EvaluationPolicy(
            container=ContainerConfig(target="mkv"),
        )

        plan = evaluate_policy(
            file_id="test-matroska-id",
            file_path=Path("/test/video.mkv"),
            container="matroska",  # ffprobe format name
            tracks=mkv_mp4_compatible_tracks,
            policy=policy,
        )

        # Should recognize that matroska == mkv, no remux needed
        assert plan.container_change is not None
        assert plan.container_change.source_format == "mkv"  # normalized
        assert plan.container_change.target_format == "mkv"
        assert plan.requires_remux is False


# =============================================================================
# Tests for MKV to MP4 Conversion (T052)
# =============================================================================


class TestMkvToMp4Conversion:
    """Integration tests for MKV to MP4 container conversion."""

    def test_mkv_to_mp4_compatible_plan_created(
        self,
        mkv_mp4_compatible_tracks: list[TrackInfo],
    ) -> None:
        """MKV to MP4 with compatible codecs should create a valid plan."""
        policy = EvaluationPolicy(
            container=ContainerConfig(target="mp4", on_incompatible_codec="error"),
        )

        plan = evaluate_policy(
            file_id="test-mkv-id",
            file_path=Path("/test/video.mkv"),
            container="mkv",
            tracks=mkv_mp4_compatible_tracks,
            policy=policy,
        )

        assert plan.container_change is not None
        assert plan.container_change.source_format == "mkv"
        assert plan.container_change.target_format == "mp4"
        assert plan.requires_remux is True
        assert len(plan.container_change.incompatible_tracks) == 0

    def test_mkv_to_mp4_incompatible_error_mode(
        self,
        mkv_mp4_incompatible_tracks: list[TrackInfo],
    ) -> None:
        """MKV to MP4 with incompatible codecs should raise error in error mode."""
        policy = EvaluationPolicy(
            container=ContainerConfig(target="mp4", on_incompatible_codec="error"),
        )

        with pytest.raises(IncompatibleCodecError) as exc_info:
            evaluate_policy(
                file_id="test-mkv-id",
                file_path=Path("/test/video.mkv"),
                container="mkv",
                tracks=mkv_mp4_incompatible_tracks,
                policy=policy,
            )

        error = exc_info.value
        assert error.target_container == "mp4"
        # Should list truehd and pgs as incompatible
        track_indices = [t[0] for t in error.incompatible_tracks]
        assert 1 in track_indices  # truehd audio
        assert 2 in track_indices  # pgs subtitle

    def test_mkv_to_mp4_incompatible_skip_mode(
        self,
        mkv_mp4_incompatible_tracks: list[TrackInfo],
    ) -> None:
        """MKV to MP4 with incompatible codecs should skip conversion in skip mode."""
        policy = EvaluationPolicy(
            container=ContainerConfig(target="mp4", on_incompatible_codec="skip"),
        )

        plan = evaluate_policy(
            file_id="test-mkv-id",
            file_path=Path("/test/video.mkv"),
            container="mkv",
            tracks=mkv_mp4_incompatible_tracks,
            policy=policy,
        )

        # Conversion should be skipped (container_change is None)
        assert plan.container_change is None

    def test_mp4_to_mp4_no_change(
        self,
        mkv_mp4_compatible_tracks: list[TrackInfo],
    ) -> None:
        """MP4 to MP4 should not require remux."""
        policy = EvaluationPolicy(
            container=ContainerConfig(target="mp4"),
        )

        plan = evaluate_policy(
            file_id="test-mp4-id",
            file_path=Path("/test/video.mp4"),
            container="mp4",
            tracks=mkv_mp4_compatible_tracks,
            policy=policy,
        )

        # ContainerChange is created for logging, but no remux is needed
        assert plan.container_change is not None
        assert plan.container_change.source_format == "mp4"
        assert plan.container_change.target_format == "mp4"
        assert plan.requires_remux is False


# =============================================================================
# Tests for Combined Track Filtering and Container Conversion
# =============================================================================


class TestCombinedFilteringAndConversion:
    """Integration tests for combining track filtering with container conversion."""

    def test_audio_filter_with_mkv_conversion(self) -> None:
        """Audio filtering should work together with MKV conversion."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="mpeg4",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="mp3",
                language="eng",
                channels=2,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="mp3",
                language="fra",
                channels=2,
            ),
        ]

        policy = EvaluationPolicy(
            audio_filter=AudioFilterConfig(languages=("eng",)),
            container=ContainerConfig(target="mkv"),
        )

        plan = evaluate_policy(
            file_id="test-avi-id",
            file_path=Path("/test/video.avi"),
            container="avi",
            tracks=tracks,
            policy=policy,
        )

        # Should have both container change and track filtering
        assert plan.container_change is not None
        assert plan.container_change.target_format == "mkv"
        assert plan.tracks_removed == 1  # French audio removed
        assert plan.tracks_kept == 2  # Video + English audio

        # Check track dispositions
        fra_track = next(d for d in plan.track_dispositions if d.language == "fra")
        assert fra_track.action == "REMOVE"
        assert "not in keep list" in fra_track.reason
