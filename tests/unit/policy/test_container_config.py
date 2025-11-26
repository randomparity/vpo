"""Unit tests for container configuration and conversion logic.

Tests for container conversion validation, compatibility checking,
and container change evaluation.
"""

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.exceptions import IncompatibleCodecError
from video_policy_orchestrator.policy.models import (
    ContainerConfig,
    PolicySchema,
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
) -> PolicySchema:
    """Create a test policy with container configuration."""
    return PolicySchema(
        schema_version=3,
        container=ContainerConfig(
            target=target,
            on_incompatible_codec=on_incompatible_codec,
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
        from video_policy_orchestrator.policy.loader import load_policy_from_dict

        data = {
            "schema_version": 3,
            "track_order": ["video", "audio_main"],
            "audio_language_preference": ["eng"],
            "subtitle_language_preference": ["eng"],
            "container": {
                "target": "mkv",
            },
        }

        policy = load_policy_from_dict(data)
        assert policy.container is not None
        assert policy.container.target == "mkv"


# =============================================================================
# Tests for MKV container compatibility (T035)
# =============================================================================


class TestMkvContainerCompatibility:
    """Tests for MKV container compatibility - all codecs supported."""

    def test_mkv_supports_all_video_codecs(self) -> None:
        """MKV should support all common video codecs."""
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
            _evaluate_container_change,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1),
        ]
        policy = PolicySchema(schema_version=3)  # No container config

        change = _evaluate_container_change(tracks, "avi", policy)

        assert change is None


# =============================================================================
# Tests for MP4 codec compatibility (T041-T043)
# =============================================================================


class TestMp4CodecCompatibility:
    """Tests for MP4 container codec compatibility checking."""

    def test_mp4_supports_h264_aac(self) -> None:
        """MP4 should support H.264 video and AAC audio."""
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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

        from video_policy_orchestrator.policy.evaluator import evaluate_policy

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

        from video_policy_orchestrator.policy.evaluator import evaluate_policy

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

        from video_policy_orchestrator.policy.evaluator import evaluate_policy

        tracks = [
            make_video_track(index=0, codec="h264"),
            make_audio_track(index=1, codec="aac"),
        ]
        policy = PolicySchema(schema_version=3)  # No container config

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

        from video_policy_orchestrator.policy.evaluator import evaluate_policy

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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
        from video_policy_orchestrator.policy.evaluator import (
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
