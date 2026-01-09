"""Integration tests for track reordering using real video files.

These tests verify that mkvmerge track reordering operations work correctly
on actual video files.

Tier 2: Track operations that require remuxing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vpo.executor.mkvmerge import MkvmergeExecutor
from vpo.policy.types import (
    ActionType,
    Plan,
    PlannedAction,
)

if TYPE_CHECKING:
    from vpo.introspector.ffprobe import FFprobeIntrospector

from .conftest import get_audio_tracks, get_video_tracks

pytestmark = [
    pytest.mark.integration,
]


class TestTrackReordering:
    """Test track reordering operations using mkvmerge."""

    def test_reorder_audio_tracks_by_language(
        self,
        generated_multi_audio: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Audio tracks should be reordered according to language preference."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_audio, "reordered.mkv")

        # Introspect original
        original = introspector.get_file_info(working_copy)
        original_audio = get_audio_tracks(original)
        video_tracks = get_video_tracks(original)

        assert len(original_audio) >= 3, "Expected at least 3 audio tracks"
        assert len(video_tracks) >= 1, "Expected at least 1 video track"

        # Find tracks by language
        eng_track = next((t for t in original_audio if t.language == "eng"), None)
        jpn_track = next((t for t in original_audio if t.language == "jpn"), None)
        fra_track = next((t for t in original_audio if t.language == "fra"), None)

        if eng_track is None or jpn_track is None:
            pytest.skip("Missing required language tracks (eng, jpn)")

        # Create new order: video first, then audio tracks in specified order
        # Build based on what tracks we actually have
        audio_new_order = [jpn_track.index, eng_track.index]
        if fra_track is not None:
            audio_new_order.append(fra_track.index)

        new_order = [video_tracks[0].index] + audio_new_order

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=2,
            requires_remux=True,
            actions=(
                PlannedAction(
                    action_type=ActionType.REORDER,
                    track_index=None,  # File-level action
                    current_value=[t.index for t in original.tracks],
                    desired_value=new_order,
                ),
            ),
        )

        executor = MkvmergeExecutor()
        assert executor.can_handle(plan)

        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success, f"Execution failed: {result.error}"

        # Verify new order
        modified = introspector.get_file_info(working_copy)
        modified_audio = get_audio_tracks(modified)

        # First audio should now be Japanese
        assert modified_audio[0].language == "jpn", (
            f"Expected Japanese first, got {modified_audio[0].language}"
        )
        # Second audio should be English
        assert modified_audio[1].language == "eng", (
            f"Expected English second, got {modified_audio[1].language}"
        )
        # If we had French, verify it's third
        if fra_track is not None and len(modified_audio) >= 3:
            assert modified_audio[2].language == "fra", (
                f"Expected French third, got {modified_audio[2].language}"
            )

    def test_commentary_track_moved_to_end(
        self,
        generated_commentary: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Commentary track should be moved after main audio."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_commentary is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_commentary, "commentary_last.mkv")

        original = introspector.get_file_info(working_copy)
        original_audio = get_audio_tracks(original)
        video_tracks = get_video_tracks(original)

        assert len(original_audio) >= 2, "Expected at least 2 audio tracks"

        # Find commentary track (by title pattern)
        commentary_track = next(
            (t for t in original_audio if t.title and "commentary" in t.title.lower()),
            None,
        )
        main_track = next(
            (
                t
                for t in original_audio
                if not (t.title and "commentary" in t.title.lower())
            ),
            None,
        )

        assert commentary_track is not None, "Expected commentary track"
        assert main_track is not None, "Expected main audio track"

        # Order: video, main audio, commentary (commentary last)
        new_order = [video_tracks[0].index, main_track.index, commentary_track.index]

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=2,
            requires_remux=True,
            actions=(
                PlannedAction(
                    action_type=ActionType.REORDER,
                    track_index=None,
                    current_value=[t.index for t in original.tracks],
                    desired_value=new_order,
                ),
            ),
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success

        # Verify
        modified = introspector.get_file_info(working_copy)
        modified_audio = get_audio_tracks(modified)

        # Last audio track should be commentary
        last_audio = modified_audio[-1]
        assert last_audio.title is not None and "commentary" in last_audio.title.lower()


class TestReorderingWithMetadata:
    """Test that metadata is preserved during reordering."""

    def test_language_tags_preserved_after_reorder(
        self,
        generated_multi_audio: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Language tags should be preserved after reordering."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_audio, "reversed.mkv")

        original = introspector.get_file_info(working_copy)
        original_audio = get_audio_tracks(original)
        video_tracks = get_video_tracks(original)

        # Reverse audio order
        reversed_audio = list(reversed([t.index for t in original_audio]))
        new_order = [video_tracks[0].index] + reversed_audio

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=2,
            requires_remux=True,
            actions=(
                PlannedAction(
                    action_type=ActionType.REORDER,
                    track_index=None,
                    current_value=[t.index for t in original.tracks],
                    desired_value=new_order,
                ),
            ),
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success

        # Verify languages preserved
        modified = introspector.get_file_info(working_copy)
        modified_audio = get_audio_tracks(modified)

        # The languages should be the same set (order will be reversed)
        modified_languages = {t.language for t in modified_audio}
        original_language_set = {t.language for t in original_audio}
        assert modified_languages == original_language_set

    def test_track_titles_preserved_after_reorder(
        self,
        generated_multi_audio: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Track titles should be preserved after reordering."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_audio, "titles_test.mkv")

        original = introspector.get_file_info(working_copy)
        original_audio = get_audio_tracks(original)
        video_tracks = get_video_tracks(original)

        # Record original titles
        original_titles = {t.language: t.title for t in original_audio if t.title}

        # Reorder
        eng = next((t for t in original_audio if t.language == "eng"), None)
        jpn = next((t for t in original_audio if t.language == "jpn"), None)
        fra = next((t for t in original_audio if t.language == "fra"), None)

        if not all([eng, jpn, fra]):
            pytest.skip("Missing expected language tracks")

        new_order = [video_tracks[0].index, fra.index, jpn.index, eng.index]

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=2,
            requires_remux=True,
            actions=(
                PlannedAction(
                    action_type=ActionType.REORDER,
                    track_index=None,
                    current_value=[t.index for t in original.tracks],
                    desired_value=new_order,
                ),
            ),
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success

        modified = introspector.get_file_info(working_copy)
        modified_audio = get_audio_tracks(modified)

        # Check titles by language
        for track in modified_audio:
            if track.language in original_titles:
                expected_title = original_titles[track.language]
                assert track.title == expected_title, (
                    f"Title mismatch for {track.language}: "
                    f"expected '{expected_title}', got '{track.title}'"
                )
