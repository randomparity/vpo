"""Unit tests for container configuration and conversion logic.

Tests for container conversion validation, compatibility checking,
and container change evaluation.
"""

import pytest

from vpo.db import TrackInfo
from vpo.policy.exceptions import IncompatibleCodecError
from vpo.policy.types import (
    CodecTranscodeMapping,
    ContainerConfig,
    EvaluationPolicy,
)

# =============================================================================
# Helper functions for creating test data
# =============================================================================


def make_video_track(
    index: int = 0,
    codec: str = "hevc",
    width: int = 1920,
    height: int = 1080,
) -> TrackInfo:
    """Create a test video track."""
    return TrackInfo(
        index=index,
        track_type="video",
        codec=codec,
        width=width,
        height=height,
    )


def make_audio_track(
    index: int,
    codec: str = "aac",
    language: str | None = "eng",
    channels: int = 2,
) -> TrackInfo:
    """Create a test audio track."""
    return TrackInfo(
        index=index,
        track_type="audio",
        codec=codec,
        language=language,
        channels=channels,
    )


def make_subtitle_track(
    index: int,
    codec: str = "subrip",
    language: str | None = "eng",
) -> TrackInfo:
    """Create a test subtitle track."""
    return TrackInfo(
        index=index,
        track_type="subtitle",
        codec=codec,
        language=language,
    )


def make_policy_with_container(
    target: str,
    on_incompatible_codec: str = "error",
    codec_mappings: dict[str, CodecTranscodeMapping] | None = None,
) -> EvaluationPolicy:
    """Create a test policy with container configuration."""
    return EvaluationPolicy(
        schema_version=12,
        container=ContainerConfig(
            target=target,
            on_incompatible_codec=on_incompatible_codec,
            codec_mappings=codec_mappings,
        ),
    )


# =============================================================================
# Tests for ContainerConfig validation (T034)
# =============================================================================


class TestContainerConfigValidation:
    """Tests for ContainerConfig validation."""

    def test_valid_mkv_target(self) -> None:
        """MKV target should be valid."""
        config = ContainerConfig(target="mkv")
        assert config.target == "mkv"

    def test_valid_mp4_target(self) -> None:
        """MP4 target should be valid."""
        config = ContainerConfig(target="mp4")
        assert config.target == "mp4"

    def test_default_on_incompatible_codec(self) -> None:
        """Default on_incompatible_codec should be 'error'."""
        config = ContainerConfig(target="mp4")
        assert config.on_incompatible_codec == "error"

    def test_skip_on_incompatible_codec(self) -> None:
        """Skip mode should be valid."""
        config = ContainerConfig(target="mp4", on_incompatible_codec="skip")
        assert config.on_incompatible_codec == "skip"

    def test_policy_loading_with_container(self) -> None:
        """Policy with container config should load correctly."""
        from vpo.policy.loader import load_policy_from_dict

        data = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "apply",
                    "track_order": ["video", "audio_main"],
                    "container": {"target": "mkv"},
                }
            ],
        }

        policy = load_policy_from_dict(data)
        assert policy.phases[0].container is not None
        assert policy.phases[0].container.target == "mkv"


# =============================================================================
# Tests for MKV container compatibility (T035)
# =============================================================================


class TestMkvContainerCompatibility:
    """Tests for MKV container compatibility - all codecs supported."""

    def test_mkv_supports_all_video_codecs(self) -> None:
        """MKV should support all common video codecs."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        video_codecs = ["h264", "hevc", "av1", "vp9", "mpeg2video", "mpeg4"]

        for codec in video_codecs:
            tracks = [
                make_video_track(index=0, codec=codec),
                make_audio_track(index=1),
            ]
            policy = make_policy_with_container(target="mkv")

            change = _evaluate_container_change(tracks, "avi", policy)

            # MKV should accept all codecs
            assert change is not None
            assert len(change.incompatible_tracks) == 0, (
                f"Codec {codec} should be compatible with MKV"
            )

    def test_mkv_supports_all_audio_codecs(self) -> None:
        """MKV should support all common audio codecs."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        audio_codecs = ["aac", "ac3", "eac3", "dts", "truehd", "flac", "opus", "mp3"]

        for codec in audio_codecs:
            tracks = [
                make_video_track(index=0),
                make_audio_track(index=1, codec=codec),
            ]
            policy = make_policy_with_container(target="mkv")

            change = _evaluate_container_change(tracks, "avi", policy)

            assert change is not None
            assert len(change.incompatible_tracks) == 0, (
                f"Codec {codec} should be compatible with MKV"
            )

    def test_mkv_supports_all_subtitle_codecs(self) -> None:
        """MKV should support all common subtitle codecs."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        subtitle_codecs = ["subrip", "ass", "hdmv_pgs_subtitle", "dvd_subtitle"]

        for codec in subtitle_codecs:
            tracks = [
                make_video_track(index=0),
                make_audio_track(index=1),
                make_subtitle_track(index=2, codec=codec),
            ]
            policy = make_policy_with_container(target="mkv")

            change = _evaluate_container_change(tracks, "mp4", policy)

            assert change is not None
            assert len(change.incompatible_tracks) == 0, (
                f"Codec {codec} should be compatible with MKV"
            )


# =============================================================================
# Tests for container change evaluation (T036-T038)
# =============================================================================


class TestEvaluateContainerChange:
    """Tests for _evaluate_container_change function."""

    def test_no_change_when_already_mkv(self) -> None:
        """Should return None when file is already MKV and target is MKV."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1),
        ]
        policy = make_policy_with_container(target="mkv")

        # Source is already MKV
        change = _evaluate_container_change(tracks, "mkv", policy)

        assert change is None

    def test_no_change_when_already_matroska(self) -> None:
        """Should return None when container_format is 'matroska'."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1),
        ]
        policy = make_policy_with_container(target="mkv")

        # Source is matroska (ffprobe format name)
        change = _evaluate_container_change(tracks, "matroska", policy)

        assert change is None

    def test_avi_to_mkv_conversion(self) -> None:
        """Should create change for AVI to MKV conversion."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0, codec="mpeg4"),
            make_audio_track(index=1, codec="mp3"),
        ]
        policy = make_policy_with_container(target="mkv")

        change = _evaluate_container_change(tracks, "avi", policy)

        assert change is not None
        assert change.source_format == "avi"
        assert change.target_format == "mkv"
        assert len(change.incompatible_tracks) == 0

    def test_mov_to_mkv_conversion(self) -> None:
        """Should create change for MOV to MKV conversion."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = make_policy_with_container(target="mkv")

        change = _evaluate_container_change(tracks, "mov", policy)

        assert change is not None
        assert change.source_format == "mov"
        assert change.target_format == "mkv"

    def test_no_change_when_no_container_config(self) -> None:
        """Should return None when policy has no container config."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1),
        ]
        policy = EvaluationPolicy()  # No container config

        change = _evaluate_container_change(tracks, "avi", policy)

        assert change is None


# =============================================================================
# Tests for MP4 codec compatibility (T041-T043)
# =============================================================================


class TestMp4CodecCompatibility:
    """Tests for MP4 container codec compatibility checking."""

    def test_mp4_supports_h264_aac(self) -> None:
        """MP4 should support H.264 video and AAC audio."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = make_policy_with_container(target="mp4")

        change = _evaluate_container_change(tracks, "mkv", policy)

        assert change is not None
        assert len(change.incompatible_tracks) == 0

    def test_mp4_supports_hevc(self) -> None:
        """MP4 should support HEVC (H.265) video."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = make_policy_with_container(target="mp4")

        change = _evaluate_container_change(tracks, "mkv", policy)

        assert change is not None
        assert len(change.incompatible_tracks) == 0

    def test_mp4_rejects_truehd(self) -> None:
        """MP4 should reject TrueHD audio codec."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="truehd"),
        ]
        policy = make_policy_with_container(target="mp4")

        change = _evaluate_container_change(tracks, "mkv", policy)

        assert change is not None
        assert 1 in change.incompatible_tracks
        assert len(change.warnings) > 0

    def test_mp4_rejects_dts(self) -> None:
        """MP4 should reject DTS audio codec."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="dts"),
        ]
        policy = make_policy_with_container(target="mp4")

        change = _evaluate_container_change(tracks, "mkv", policy)

        assert change is not None
        assert 1 in change.incompatible_tracks

    def test_mp4_rejects_pgs_subtitles(self) -> None:
        """MP4 should reject PGS subtitle codec."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
            make_subtitle_track(index=2, codec="hdmv_pgs_subtitle"),
        ]
        policy = make_policy_with_container(target="mp4")

        change = _evaluate_container_change(tracks, "mkv", policy)

        assert change is not None
        assert 2 in change.incompatible_tracks

    def test_mp4_accepts_mov_text_subtitles(self) -> None:
        """MP4 should accept mov_text subtitles."""
        from vpo.policy.evaluator.container import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
            make_subtitle_track(index=2, codec="mov_text"),
        ]
        policy = make_policy_with_container(target="mp4")

        change = _evaluate_container_change(tracks, "mkv", policy)

        assert change is not None
        assert 2 not in change.incompatible_tracks


# =============================================================================
# Tests for IncompatibleCodecError scenarios (T042)
# =============================================================================


class TestIncompatibleCodecError:
    """Tests for IncompatibleCodecError handling."""

    def test_error_raised_with_error_mode(self) -> None:
        """Should raise IncompatibleCodecError when mode is 'error'."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="truehd"),  # Incompatible with MP4
        ]
        policy = make_policy_with_container(target="mp4", on_incompatible_codec="error")

        with pytest.raises(IncompatibleCodecError) as exc_info:
            evaluate_container_change_with_policy(tracks, "mkv", policy)

        err = exc_info.value
        assert "mp4" in err.target_container.lower()
        # Check that incompatible tracks are recorded
        assert len(err.incompatible_tracks) > 0
        track_indices = [t[0] for t in err.incompatible_tracks]
        assert 1 in track_indices

    def test_no_error_with_skip_mode(self) -> None:
        """Should not raise error when mode is 'skip'."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="truehd"),
        ]
        policy = make_policy_with_container(target="mp4", on_incompatible_codec="skip")

        # Should return None (skip conversion), not raise error
        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is None

    def test_error_includes_helpful_context(self) -> None:
        """Error message should include helpful context."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="dts"),
        ]
        policy = make_policy_with_container(target="mp4")

        with pytest.raises(IncompatibleCodecError) as exc_info:
            evaluate_container_change_with_policy(tracks, "mkv", policy)

        error_message = str(exc_info.value)
        assert "dts" in error_message.lower()
        assert "mp4" in error_message.lower()


# =============================================================================
# Tests for on_incompatible_codec modes (T043)
# =============================================================================


class TestEvaluatePolicyContainerIntegration:
    """Tests for evaluate_policy() container change integration (T037)."""

    def test_evaluate_policy_includes_container_change(self) -> None:
        """evaluate_policy() should include container_change in Plan."""
        from pathlib import Path

        from vpo.policy.evaluator import evaluate_policy

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = make_policy_with_container(target="mkv")

        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/file.avi"),
            container="avi",
            tracks=tracks,
            policy=policy,
        )

        assert plan.container_change is not None
        assert plan.container_change.source_format == "avi"
        assert plan.container_change.target_format == "mkv"
        assert plan.requires_remux is True

    def test_evaluate_policy_no_container_change_when_same_format(self) -> None:
        """evaluate_policy() should not include container_change when same format."""
        from pathlib import Path

        from vpo.policy.evaluator import evaluate_policy

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = make_policy_with_container(target="mkv")

        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=tracks,
            policy=policy,
        )

        assert plan.container_change is None

    def test_evaluate_policy_no_container_change_without_config(self) -> None:
        """evaluate_policy() should not include container_change without config."""
        from pathlib import Path

        from vpo.policy.evaluator import evaluate_policy

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = EvaluationPolicy()  # No container config

        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/file.avi"),
            container="avi",
            tracks=tracks,
            policy=policy,
        )

        assert plan.container_change is None

    def test_evaluate_policy_raises_on_incompatible_codec(self) -> None:
        """evaluate_policy() should raise IncompatibleCodecError with error mode."""
        from pathlib import Path

        from vpo.policy.evaluator import evaluate_policy

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="truehd"),  # Incompatible with MP4
        ]
        policy = make_policy_with_container(target="mp4", on_incompatible_codec="error")

        with pytest.raises(IncompatibleCodecError):
            evaluate_policy(
                file_id="test-id",
                file_path=Path("/test/file.mkv"),
                container="mkv",
                tracks=tracks,
                policy=policy,
            )


class TestOnIncompatibleCodecModes:
    """Tests for on_incompatible_codec behavior."""

    def test_error_mode_raises_on_incompatible(self) -> None:
        """Error mode should raise exception for incompatible codecs."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="truehd"),
        ]
        policy = make_policy_with_container(target="mp4", on_incompatible_codec="error")

        with pytest.raises(IncompatibleCodecError):
            evaluate_container_change_with_policy(tracks, "mkv", policy)

    def test_skip_mode_returns_none(self) -> None:
        """Skip mode should return None to skip conversion entirely."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="truehd"),
        ]
        policy = make_policy_with_container(target="mp4", on_incompatible_codec="skip")

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is None

    def test_compatible_codecs_proceed_in_error_mode(self) -> None:
        """Error mode should allow conversion when codecs are compatible."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = make_policy_with_container(target="mp4", on_incompatible_codec="error")

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.target_format == "mp4"

    def test_compatible_codecs_proceed_in_skip_mode(self) -> None:
        """Skip mode should allow conversion when codecs are compatible."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = make_policy_with_container(target="mp4", on_incompatible_codec="skip")

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.target_format == "mp4"


# =============================================================================
# Tests for on_incompatible_codec: transcode mode (Issue #258)
# =============================================================================


class TestTranscodeMode:
    """Tests for on_incompatible_codec='transcode' behavior."""

    def test_transcode_mode_creates_plan_for_truehd(self) -> None:
        """Transcode mode should create a plan to convert TrueHD to AAC."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="truehd"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.target_format == "mp4"
        assert result.transcode_plan is not None
        assert len(result.transcode_plan.track_plans) == 1

        plan = result.transcode_plan.track_plans[0]
        assert plan.track_index == 1
        assert plan.track_type == "audio"
        assert plan.source_codec == "truehd"
        assert plan.action == "transcode"
        assert plan.target_codec == "aac"
        assert plan.target_bitrate == "256k"

    def test_transcode_mode_creates_plan_for_dts(self) -> None:
        """Transcode mode should create a plan to convert DTS to AAC."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="dts"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        assert len(result.transcode_plan.track_plans) == 1

        plan = result.transcode_plan.track_plans[0]
        assert plan.action == "transcode"
        assert plan.target_codec == "aac"
        assert plan.target_bitrate == "256k"

    def test_transcode_mode_creates_plan_for_dts_hd(self) -> None:
        """Transcode mode should use higher bitrate for DTS-HD."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="dts-hd ma"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]
        assert plan.target_bitrate == "320k"  # Higher bitrate for HD

    def test_transcode_mode_removes_bitmap_subtitles(self) -> None:
        """Transcode mode should remove PGS bitmap subtitles with warning."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
            make_subtitle_track(index=2, codec="hdmv_pgs_subtitle"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        assert len(result.transcode_plan.track_plans) == 1

        plan = result.transcode_plan.track_plans[0]
        assert plan.track_index == 2
        assert plan.track_type == "subtitle"
        assert plan.source_codec == "hdmv_pgs_subtitle"
        assert plan.action == "remove"
        assert plan.target_codec is None

        # Check for warning about removal
        assert any("removed" in w.lower() for w in result.warnings)

    def test_transcode_mode_converts_text_subtitles(self) -> None:
        """Transcode mode should convert SRT to mov_text."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
            make_subtitle_track(index=2, codec="subrip"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        assert len(result.transcode_plan.track_plans) == 1

        plan = result.transcode_plan.track_plans[0]
        assert plan.track_index == 2
        assert plan.action == "convert"
        assert plan.target_codec == "mov_text"

    def test_transcode_mode_warns_about_ass_styling_loss(self) -> None:
        """Transcode mode should warn about ASS styling loss."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
            make_subtitle_track(index=2, codec="ass"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None

        # Check for warning about styling loss
        assert any("styling" in w.lower() for w in result.warnings)

    def test_transcode_mode_mixed_tracks(self) -> None:
        """Transcode mode should handle multiple incompatible tracks."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="truehd"),  # transcode
            make_audio_track(index=2, codec="aac"),  # compatible
            make_subtitle_track(index=3, codec="hdmv_pgs_subtitle"),  # remove
            make_subtitle_track(index=4, codec="subrip"),  # convert
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        assert len(result.transcode_plan.track_plans) == 3

        # Verify each track plan
        plans_by_index = {p.track_index: p for p in result.transcode_plan.track_plans}

        assert plans_by_index[1].action == "transcode"
        assert plans_by_index[1].target_codec == "aac"

        assert plans_by_index[3].action == "remove"

        assert plans_by_index[4].action == "convert"
        assert plans_by_index[4].target_codec == "mov_text"

    def test_transcode_mode_preserves_compatible(self) -> None:
        """Transcode mode should not create plans for compatible tracks."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),  # compatible
            make_audio_track(index=2, codec="ac3"),  # compatible
            make_subtitle_track(index=3, codec="mov_text"),  # compatible
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        # No transcode plan needed when all are compatible
        assert result.transcode_plan is None
        assert len(result.incompatible_tracks) == 0

    def test_compatible_codecs_no_transcode_plan(self) -> None:
        """No transcode plan should be created when all codecs are compatible."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="hevc"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.target_format == "mp4"
        assert result.transcode_plan is None

    def test_transcode_mode_unknown_audio_codec_uses_generic_defaults(self) -> None:
        """Unknown audio codecs should use generic AAC transcode."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="unknown_audio_codec"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]
        assert plan.action == "transcode"
        assert plan.target_codec == "aac"
        assert plan.target_bitrate == "192k"  # Generic default

    def test_transcode_mode_dvd_subtitle_removed(self) -> None:
        """DVD subtitles should be removed like PGS."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
            make_subtitle_track(index=2, codec="dvd_subtitle"),
        ]
        policy = make_policy_with_container(
            target="mp4", on_incompatible_codec="transcode"
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]
        assert plan.action == "remove"


# =============================================================================
# Tests for per-codec overrides in transcode mode (Issue #258)
# =============================================================================


class TestCodecMappingOverrides:
    """Tests for codec_mappings configuration in transcode mode."""

    def test_custom_audio_codec_override(self) -> None:
        """Custom codec mapping should override default AAC target."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="truehd"),
        ]
        policy = make_policy_with_container(
            target="mp4",
            on_incompatible_codec="transcode",
            codec_mappings={
                "truehd": CodecTranscodeMapping(codec="ac3", bitrate="448k"),
            },
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]
        assert plan.action == "transcode"
        assert plan.target_codec == "ac3"
        assert plan.target_bitrate == "448k"

    def test_custom_bitrate_override(self) -> None:
        """Custom bitrate should override default for known codecs."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="dts"),
        ]
        policy = make_policy_with_container(
            target="mp4",
            on_incompatible_codec="transcode",
            codec_mappings={
                "dts": CodecTranscodeMapping(codec="aac", bitrate="320k"),
            },
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]
        assert plan.target_codec == "aac"
        assert plan.target_bitrate == "320k"  # Custom, not default 256k

    def test_explicit_remove_action(self) -> None:
        """Explicit remove action should remove track even if convertible."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
            make_subtitle_track(index=2, codec="subrip"),  # Normally converts
        ]
        policy = make_policy_with_container(
            target="mp4",
            on_incompatible_codec="transcode",
            codec_mappings={
                "subrip": CodecTranscodeMapping(codec="mov_text", action="remove"),
            },
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]
        assert plan.action == "remove"
        assert plan.target_codec is None

    def test_unmapped_codecs_use_defaults(self) -> None:
        """Codecs not in mapping should still use default behavior."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="truehd"),  # Mapped
            make_audio_track(index=2, codec="dts"),  # Not mapped
        ]
        policy = make_policy_with_container(
            target="mp4",
            on_incompatible_codec="transcode",
            codec_mappings={
                "truehd": CodecTranscodeMapping(codec="ac3", bitrate="640k"),
            },
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        assert len(result.transcode_plan.track_plans) == 2

        plans_by_index = {p.track_index: p for p in result.transcode_plan.track_plans}

        # Mapped codec uses custom settings
        assert plans_by_index[1].target_codec == "ac3"
        assert plans_by_index[1].target_bitrate == "640k"

        # Unmapped codec uses defaults
        assert plans_by_index[2].target_codec == "aac"
        assert plans_by_index[2].target_bitrate == "256k"

    def test_case_insensitive_codec_matching(self) -> None:
        """Codec mapping keys should be case-insensitive."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="TrueHD"),  # Mixed case
        ]
        policy = make_policy_with_container(
            target="mp4",
            on_incompatible_codec="transcode",
            codec_mappings={
                "truehd": CodecTranscodeMapping(codec="eac3", bitrate="384k"),
            },
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]
        assert plan.target_codec == "eac3"

    def test_policy_yaml_parsing_with_codec_mappings(self) -> None:
        """Policy YAML with codec_mappings should parse correctly."""
        from vpo.policy.loader import load_policy_from_dict

        data = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "convert",
                    "container": {
                        "target": "mp4",
                        "on_incompatible_codec": "transcode",
                        "codec_mappings": {
                            "truehd": {"codec": "ac3", "bitrate": "640k"},
                            "dts": {"codec": "aac", "bitrate": "256k"},
                            "hdmv_pgs_subtitle": {
                                "codec": "mov_text",
                                "action": "remove",
                            },
                        },
                    },
                }
            ],
        }

        policy = load_policy_from_dict(data)

        assert policy.phases[0].container is not None
        assert policy.phases[0].container.codec_mappings is not None
        mappings = policy.phases[0].container.codec_mappings

        assert "truehd" in mappings
        assert mappings["truehd"].codec == "ac3"
        assert mappings["truehd"].bitrate == "640k"

        assert "dts" in mappings
        assert mappings["dts"].codec == "aac"

        assert "hdmv_pgs_subtitle" in mappings
        assert mappings["hdmv_pgs_subtitle"].action == "remove"

    def test_empty_codec_mappings_uses_defaults(self) -> None:
        """Empty codec_mappings should behave like no mappings."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="truehd"),
        ]
        policy = make_policy_with_container(
            target="mp4",
            on_incompatible_codec="transcode",
            codec_mappings={},  # Empty dict
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]
        # Should use default truehd -> aac mapping
        assert plan.target_codec == "aac"
        assert plan.target_bitrate == "256k"


# =============================================================================
# Tests for bitrate validation (Issue #258 review)
# =============================================================================


class TestBitrateValidation:
    """Tests for bitrate format validation in codec_mappings."""

    def test_valid_bitrate_with_k_suffix(self) -> None:
        """Bitrate with 'k' suffix should be accepted."""
        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        mapping = CodecTranscodeMappingModel(codec="aac", bitrate="256k")
        assert mapping.bitrate == "256k"

    def test_valid_bitrate_with_m_suffix(self) -> None:
        """Bitrate with 'm' suffix should be accepted."""
        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        mapping = CodecTranscodeMappingModel(codec="aac", bitrate="1m")
        assert mapping.bitrate == "1m"

    def test_valid_bitrate_decimal_mbps(self) -> None:
        """Decimal mbps bitrate should be accepted."""
        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        mapping = CodecTranscodeMappingModel(codec="aac", bitrate="1.5m")
        assert mapping.bitrate == "1.5m"

    def test_rejects_bare_numeric_bitrate(self) -> None:
        """Bare numeric bitrate without unit should be rejected."""
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        with pytest.raises(ValidationError) as exc_info:
            CodecTranscodeMappingModel(codec="aac", bitrate="256")

        # Should mention unit suffix requirement
        error_str = str(exc_info.value).lower()
        assert "unit" in error_str or "suffix" in error_str

    def test_rejects_zero_bitrate(self) -> None:
        """Zero bitrate should be rejected (below minimum)."""
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        with pytest.raises(ValidationError) as exc_info:
            CodecTranscodeMappingModel(codec="aac", bitrate="0k")

        error_str = str(exc_info.value).lower()
        assert "low" in error_str or "minimum" in error_str

    def test_rejects_bitrate_below_minimum(self) -> None:
        """Bitrate below 32k should be rejected."""
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        with pytest.raises(ValidationError) as exc_info:
            CodecTranscodeMappingModel(codec="aac", bitrate="16k")

        error_str = str(exc_info.value).lower()
        assert "low" in error_str or "minimum" in error_str

    def test_rejects_bitrate_above_maximum(self) -> None:
        """Bitrate above 1536k should be rejected."""
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        with pytest.raises(ValidationError) as exc_info:
            CodecTranscodeMappingModel(codec="aac", bitrate="2000k")

        error_str = str(exc_info.value).lower()
        assert "high" in error_str or "maximum" in error_str

    def test_accepts_boundary_minimum_bitrate(self) -> None:
        """Exactly 32k bitrate should be accepted."""
        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        mapping = CodecTranscodeMappingModel(codec="aac", bitrate="32k")
        assert mapping.bitrate == "32k"

    def test_accepts_boundary_maximum_bitrate(self) -> None:
        """Exactly 1536k (1.5m) bitrate should be accepted."""
        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        mapping = CodecTranscodeMappingModel(codec="aac", bitrate="1536k")
        assert mapping.bitrate == "1536k"

    def test_none_bitrate_allowed(self) -> None:
        """None bitrate should be allowed (optional field)."""
        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        mapping = CodecTranscodeMappingModel(codec="aac", bitrate=None)
        assert mapping.bitrate is None


# =============================================================================
# Tests for codec validation warnings (Issue #258 review)
# =============================================================================


class TestCodecValidationWarnings:
    """Tests for codec validation warnings in codec_mappings."""

    def test_known_codec_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Known MP4-compatible codec should not generate warning."""
        import logging

        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        with caplog.at_level(logging.WARNING):
            CodecTranscodeMappingModel(codec="aac", bitrate="256k")

        assert "not a recognized" not in caplog.text

    def test_unknown_codec_generates_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unknown codec should generate a warning."""
        import logging

        from vpo.policy.pydantic_models import CodecTranscodeMappingModel

        with caplog.at_level(logging.WARNING):
            CodecTranscodeMappingModel(codec="unknowncodec", bitrate="256k")

        assert "not a recognized" in caplog.text.lower()

    def test_codec_mappings_warns_when_not_transcode_mode(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """codec_mappings should warn when on_incompatible_codec is not 'transcode'."""
        import logging

        from vpo.policy.pydantic_models import (
            CodecTranscodeMappingModel,
            ContainerModel,
        )

        with caplog.at_level(logging.WARNING):
            ContainerModel(
                target="mp4",
                on_incompatible_codec="error",
                codec_mappings={
                    "truehd": CodecTranscodeMappingModel(codec="aac", bitrate="256k"),
                },
            )

        assert "ignored" in caplog.text.lower() or "transcode" in caplog.text.lower()

    def test_codec_mappings_no_warn_when_transcode_mode(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """codec_mappings should not warn when on_incompatible_codec is 'transcode'."""
        import logging

        from vpo.policy.pydantic_models import (
            CodecTranscodeMappingModel,
            ContainerModel,
        )

        with caplog.at_level(logging.WARNING):
            ContainerModel(
                target="mp4",
                on_incompatible_codec="transcode",
                codec_mappings={
                    "truehd": CodecTranscodeMappingModel(codec="aac", bitrate="256k"),
                },
            )

        # Should not warn about codec_mappings being ignored
        assert "ignored" not in caplog.text.lower()


# =============================================================================
# Tests for IncompatibleTrackPlan invariants (Issue #258 review)
# =============================================================================


class TestIncompatibleTrackPlanInvariants:
    """Tests for IncompatibleTrackPlan dataclass invariants."""

    def test_transcode_action_requires_target_codec(self) -> None:
        """Transcode action should require target_codec to be set."""
        from vpo.policy.types import IncompatibleTrackPlan

        with pytest.raises(ValueError) as exc_info:
            IncompatibleTrackPlan(
                track_index=1,
                track_type="audio",
                source_codec="truehd",
                action="transcode",
                target_codec=None,  # Missing!
                reason="test",
            )

        assert "target_codec" in str(exc_info.value)

    def test_convert_action_requires_target_codec(self) -> None:
        """Convert action should require target_codec to be set."""
        from vpo.policy.types import IncompatibleTrackPlan

        with pytest.raises(ValueError) as exc_info:
            IncompatibleTrackPlan(
                track_index=2,
                track_type="subtitle",
                source_codec="subrip",
                action="convert",
                target_codec=None,  # Missing!
                reason="test",
            )

        assert "target_codec" in str(exc_info.value)

    def test_remove_action_requires_no_target_codec(self) -> None:
        """Remove action should require target_codec to be None."""
        from vpo.policy.types import IncompatibleTrackPlan

        with pytest.raises(ValueError) as exc_info:
            IncompatibleTrackPlan(
                track_index=2,
                track_type="subtitle",
                source_codec="hdmv_pgs_subtitle",
                action="remove",
                target_codec="mov_text",  # Should be None!
                reason="test",
            )

        assert "target_codec" in str(exc_info.value)

    def test_remove_action_with_none_target_codec_valid(self) -> None:
        """Remove action with None target_codec should be valid."""
        from vpo.policy.types import IncompatibleTrackPlan

        plan = IncompatibleTrackPlan(
            track_index=2,
            track_type="subtitle",
            source_codec="hdmv_pgs_subtitle",
            action="remove",
            target_codec=None,
            reason="bitmap subtitles removed",
        )
        assert plan.action == "remove"
        assert plan.target_codec is None

    def test_bitrate_only_valid_for_transcode_action(self) -> None:
        """target_bitrate should only be valid for transcode action."""
        from vpo.policy.types import IncompatibleTrackPlan

        with pytest.raises(ValueError) as exc_info:
            IncompatibleTrackPlan(
                track_index=2,
                track_type="subtitle",
                source_codec="subrip",
                action="convert",
                target_codec="mov_text",
                target_bitrate="256k",  # Invalid for convert!
                reason="test",
            )

        assert "target_bitrate" in str(exc_info.value)

    def test_transcode_with_bitrate_valid(self) -> None:
        """Transcode action with bitrate should be valid."""
        from vpo.policy.types import IncompatibleTrackPlan

        plan = IncompatibleTrackPlan(
            track_index=1,
            track_type="audio",
            source_codec="truehd",
            action="transcode",
            target_codec="aac",
            target_bitrate="256k",
            reason="truehd is not MP4-compatible",
        )
        assert plan.action == "transcode"
        assert plan.target_bitrate == "256k"


# =============================================================================
# Tests for reason string formatting (Issue #258 review)
# =============================================================================


class TestReasonStringFormatting:
    """Tests for proper reason string formatting in track plans."""

    def test_remove_action_reason_does_not_show_none(self) -> None:
        """Remove action reason should not show 'None' for target codec."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
            make_subtitle_track(index=2, codec="hdmv_pgs_subtitle"),
        ]
        policy = make_policy_with_container(
            target="mp4",
            on_incompatible_codec="transcode",
            codec_mappings={
                "hdmv_pgs_subtitle": CodecTranscodeMapping(
                    codec="mov_text", action="remove"
                ),
            },
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]

        # Reason should say "removed" not "-> None"
        assert plan.action == "remove"
        assert "removed" in plan.reason.lower()
        assert "none" not in plan.reason.lower()

    def test_transcode_action_shows_codec_mapping(self) -> None:
        """Transcode action reason should show source -> target mapping."""
        from vpo.policy.evaluator import (
            evaluate_container_change_with_policy,
        )

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="truehd"),
        ]
        policy = make_policy_with_container(
            target="mp4",
            on_incompatible_codec="transcode",
            codec_mappings={
                "truehd": CodecTranscodeMapping(codec="ac3", bitrate="640k"),
            },
        )

        result = evaluate_container_change_with_policy(tracks, "mkv", policy)

        assert result is not None
        assert result.transcode_plan is not None
        plan = result.transcode_plan.track_plans[0]

        # Reason should show the mapping
        assert "->" in plan.reason
        assert "ac3" in plan.reason.lower()
