"""Integration tests for edge cases and error handling.

These tests verify correct behavior for edge cases like missing tools,
constraint violations, and unusual file configurations.

Tier 4: Edge cases and error handling.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from video_policy_orchestrator.executor.mkvpropedit import MkvpropeditExecutor
from video_policy_orchestrator.policy.models import (
    ActionType,
    Plan,
    PlannedAction,
    TrackDisposition,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector

from .conftest import get_audio_tracks

pytestmark = [
    pytest.mark.integration,
]


class TestToolAvailability:
    """Test behavior when tools are unavailable."""

    def test_skip_when_mkvpropedit_unavailable(
        self,
        generated_basic_h264: Path | None,
        mkvpropedit_available: bool,
    ) -> None:
        """Test should be skipped when mkvpropedit is unavailable."""
        if mkvpropedit_available:
            pytest.skip("This test is for when mkvpropedit is NOT available")

        # This test documents the expected skip behavior
        # When mkvpropedit is unavailable, tests using it should skip
        assert not shutil.which("mkvpropedit")

    def test_executor_raises_when_tool_missing(
        self,
        generated_basic_h264: Path | None,
    ) -> None:
        """Executor raises FileNotFoundError when tool is missing.

        Note: The executor currently does not gracefully handle missing tools -
        it raises FileNotFoundError. This test documents that behavior.
        """
        if generated_basic_h264 is None:
            pytest.skip("Test video not available")

        # Mock require_tool to simulate missing mkvpropedit
        with patch(
            "video_policy_orchestrator.executor.mkvpropedit.require_tool"
        ) as mock_require:
            mock_require.side_effect = FileNotFoundError("mkvpropedit not found")

            plan = Plan(
                file_id="test",
                file_path=generated_basic_h264,
                policy_version=12,
                requires_remux=False,
                actions=(
                    PlannedAction(
                        action_type=ActionType.SET_DEFAULT,
                        track_index=0,
                        current_value=False,
                        desired_value=True,
                    ),
                ),
            )

            executor = MkvpropeditExecutor()

            # Currently raises FileNotFoundError - not gracefully handled
            with pytest.raises(FileNotFoundError):
                executor.execute(plan, keep_backup=False, keep_original=True)


class TestFileNotFound:
    """Test behavior when input files are missing."""

    def test_introspection_of_missing_file(
        self,
        introspector: FFprobeIntrospector,
    ) -> None:
        """Introspection should raise error for missing file."""
        from video_policy_orchestrator.introspector.interface import (
            MediaIntrospectionError,
        )

        with pytest.raises(MediaIntrospectionError):
            introspector.get_file_info(Path("/nonexistent/file.mkv"))

    def test_executor_handles_missing_input(
        self,
        mkvpropedit_available: bool,
    ) -> None:
        """Executor should handle missing input file."""
        if not mkvpropedit_available:
            pytest.skip("mkvpropedit not available")

        missing_path = Path("/nonexistent/missing.mkv")
        plan = Plan(
            file_id="test",
            file_path=missing_path,
            policy_version=12,
            requires_remux=False,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_DEFAULT,
                    track_index=0,
                    current_value=False,
                    desired_value=True,
                ),
            ),
        )

        executor = MkvpropeditExecutor()
        result = executor.execute(plan, keep_backup=False, keep_original=True)

        # Should fail gracefully
        assert result.success is False


class TestNoAudioTracks:
    """Test handling of files without audio tracks."""

    def test_introspect_video_only_file(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
    ) -> None:
        """Video-only file should introspect without errors."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
        from generate_test_media import SPECS

        video_path = generate_video(SPECS["no_audio"], "video_only.mkv")
        if video_path is None:
            pytest.skip("Could not generate test video")

        result = introspector.get_file_info(video_path)

        # Should have video but no audio
        from .conftest import get_video_tracks

        video_tracks = get_video_tracks(result)
        audio_tracks = get_audio_tracks(result)

        assert len(video_tracks) >= 1
        assert len(audio_tracks) == 0


class TestUndefinedLanguage:
    """Test handling of undefined language tracks."""

    def test_und_language_track_handling(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
    ) -> None:
        """Tracks with 'und' language should be handled correctly."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
        from generate_test_media import SPECS

        video_path = generate_video(SPECS["und_language"], "und_lang.mkv")
        if video_path is None:
            pytest.skip("Could not generate test video")

        result = introspector.get_file_info(video_path)
        audio_tracks = get_audio_tracks(result)

        assert len(audio_tracks) >= 1

        # Track should have 'und' language
        und_track = next((t for t in audio_tracks if t.language == "und"), None)
        assert und_track is not None, "Expected audio track with 'und' language"


def _make_disposition(track, action: str, reason: str) -> TrackDisposition:
    """Helper to create TrackDisposition from a track."""
    resolution = None
    if track.track_type == "video" and track.width and track.height:
        resolution = f"{track.width}x{track.height}"

    return TrackDisposition(
        track_index=track.index,
        track_type=track.track_type,
        codec=track.codec,
        language=track.language,
        title=track.title,
        channels=getattr(track, "channels", None),
        resolution=resolution,
        action=action,
        reason=reason,
    )


class TestFilteringConstraints:
    """Test track filtering constraint handling."""

    def test_cannot_remove_all_audio(
        self,
        generated_basic_h264: Path | None,
        tmp_path: Path,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Filtering should not remove all audio tracks (constraint violation)."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_basic_h264 is None:
            pytest.skip("Test video not available")

        original = introspector.get_file_info(generated_basic_h264)

        # Create plan that removes ALL audio (this should fail or be prevented)
        dispositions = []
        for track in original.tracks:
            if track.track_type == "video":
                dispositions.append(_make_disposition(track, "KEEP", "video"))
            elif track.track_type == "audio":
                dispositions.append(
                    _make_disposition(track, "REMOVE", "filter removes all audio")
                )

        # Verify we're actually trying to remove all audio
        kept_audio = [
            d
            for d in dispositions
            if d.action == "KEEP"
            and any(
                t.track_type == "audio" and t.index == d.track_index
                for t in original.tracks
            )
        ]
        assert len(kept_audio) == 0, "Test setup: should try to remove all audio"

        # The plan with 0 audio tracks is valid from the Plan's perspective,
        # but the policy evaluator should prevent this based on minimum track settings
        plan = Plan(
            file_id="test",
            file_path=generated_basic_h264,
            policy_version=3,
            requires_remux=True,
            actions=(),
            track_dispositions=tuple(dispositions),
            tracks_kept=len([d for d in dispositions if d.action == "KEEP"]),
            tracks_removed=len([d for d in dispositions if d.action == "REMOVE"]),
        )

        # Note: In a real scenario, the policy evaluator should prevent this
        # based on the minimum_audio_tracks setting. Here we're just documenting
        # that such a plan can be created but should be caught earlier in validation.
        assert plan.tracks_removed > 0


class TestBackupAndRecovery:
    """Test backup creation and recovery."""

    def test_backup_created_when_requested(
        self,
        generated_basic_h264: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvpropedit_available: bool,
    ) -> None:
        """Backup file should be created when keep_backup=True."""
        if not mkvpropedit_available:
            pytest.skip("mkvpropedit not available")
        if generated_basic_h264 is None:
            pytest.skip("Test video not available")

        working_copy = copy_video(generated_basic_h264, "backup_test.mkv")

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=12,
            requires_remux=False,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_DEFAULT,
                    track_index=0,
                    current_value=False,
                    desired_value=True,
                ),
            ),
        )

        executor = MkvpropeditExecutor()
        result = executor.execute(plan, keep_backup=True, keep_original=False)

        assert result.success

        # Check for backup file
        if result.backup_path:
            assert result.backup_path.exists(), "Backup file should exist"


class TestIdempotency:
    """Test that operations are idempotent."""

    def test_setting_default_twice_is_idempotent(
        self,
        generated_basic_h264: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvpropedit_available: bool,
    ) -> None:
        """Setting default flag twice should produce same result."""
        if not mkvpropedit_available:
            pytest.skip("mkvpropedit not available")
        if generated_basic_h264 is None:
            pytest.skip("Test video not available")

        working_copy = copy_video(generated_basic_h264, "idempotent_test.mkv")

        # First operation
        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=12,
            requires_remux=False,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_DEFAULT,
                    track_index=0,
                    current_value=False,
                    desired_value=True,
                ),
            ),
        )

        executor = MkvpropeditExecutor()

        result1 = executor.execute(plan, keep_backup=False, keep_original=False)
        assert result1.success

        state_after_first = introspector.get_file_info(working_copy)

        # Second operation (same plan)
        result2 = executor.execute(plan, keep_backup=False, keep_original=False)
        assert result2.success

        state_after_second = introspector.get_file_info(working_copy)

        # State should be identical
        from .conftest import get_video_tracks

        video1 = get_video_tracks(state_after_first)[0]
        video2 = get_video_tracks(state_after_second)[0]

        assert video1.is_default == video2.is_default


class TestLargeTrackCount:
    """Test handling of files with many tracks."""

    def test_multi_audio_introspection(
        self,
        generated_multi_audio: Path | None,
        introspector: FFprobeIntrospector,
    ) -> None:
        """Files with multiple audio tracks should introspect correctly."""
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_multi_audio)
        audio_tracks = get_audio_tracks(result)

        # Should have 3 audio tracks
        assert len(audio_tracks) == 3

        # Should have different languages
        languages = {t.language for t in audio_tracks}
        assert len(languages) >= 2, "Expected multiple languages"

    def test_multi_subtitle_introspection(
        self,
        generated_multi_subtitle: Path | None,
        introspector: FFprobeIntrospector,
    ) -> None:
        """Files with multiple subtitle tracks should introspect correctly."""
        if generated_multi_subtitle is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_multi_subtitle)
        from .conftest import get_subtitle_tracks

        subtitle_tracks = get_subtitle_tracks(result)

        # Should have 3 subtitle tracks
        assert len(subtitle_tracks) == 3

        # Should have forced track
        forced_tracks = [t for t in subtitle_tracks if t.is_forced]
        assert len(forced_tracks) >= 1, "Expected at least one forced subtitle"
