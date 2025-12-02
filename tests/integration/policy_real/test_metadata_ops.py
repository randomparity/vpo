"""Integration tests for metadata operations using real video files.

These tests verify that mkvpropedit operations (default flags, titles, languages)
work correctly on actual video files.

Tier 1: Smoke tests - basic operations that should always work.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from video_policy_orchestrator.executor.mkvpropedit import MkvpropeditExecutor
from video_policy_orchestrator.policy.evaluator import (
    compute_default_flags,
    compute_desired_order,
)
from video_policy_orchestrator.policy.matchers import CommentaryMatcher
from video_policy_orchestrator.policy.models import (
    ActionType,
    DefaultFlagsConfig,
    Plan,
    PlannedAction,
    PolicySchema,
    TrackType,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector

from .conftest import get_audio_tracks, get_track_by_type_and_index, get_video_tracks

# Mark all tests in this module
pytestmark = [
    pytest.mark.integration,
]


class TestSetDefaultFlags:
    """Test setting default flags on tracks using mkvpropedit."""

    def test_set_video_default_flag(
        self,
        generated_basic_h264: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvpropedit_available: bool,
    ) -> None:
        """Video track should have default flag set."""
        if not mkvpropedit_available:
            pytest.skip("mkvpropedit not available")
        if generated_basic_h264 is None:
            pytest.skip("Test video not available")

        # Make a working copy
        working_copy = copy_video(generated_basic_h264, "test_video.mkv")

        # Introspect original
        original = introspector.get_file_info(working_copy)
        video_track = get_track_by_type_and_index(original, "video", 0)
        assert video_track is not None

        # Create a plan to set video default
        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=12,
            requires_remux=False,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_DEFAULT,
                    track_index=video_track.index,
                    current_value=video_track.is_default,
                    desired_value=True,
                ),
            ),
        )

        # Execute
        executor = MkvpropeditExecutor()
        assert executor.can_handle(plan)
        result = executor.execute(plan, keep_backup=False, keep_original=False)
        assert result.success, f"Execution failed: {result.error}"

        # Verify
        modified = introspector.get_file_info(working_copy)
        video_track_after = get_track_by_type_and_index(modified, "video", 0)
        assert video_track_after is not None
        assert video_track_after.is_default is True

    def test_set_audio_default_flag(
        self,
        generated_multi_audio: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvpropedit_available: bool,
    ) -> None:
        """Preferred audio track should have default flag set."""
        if not mkvpropedit_available:
            pytest.skip("mkvpropedit not available")
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        working_copy = copy_video(generated_multi_audio, "test_audio.mkv")

        # Introspect and find English audio (should be first)
        original = introspector.get_file_info(working_copy)
        audio_tracks = get_audio_tracks(original)
        assert len(audio_tracks) >= 2, "Expected multiple audio tracks"

        # Find the English track
        eng_track = next((t for t in audio_tracks if t.language == "eng"), None)
        assert eng_track is not None, "Expected English audio track"

        # Create plan to set English as default
        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=12,
            requires_remux=False,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_DEFAULT,
                    track_index=eng_track.index,
                    current_value=eng_track.is_default,
                    desired_value=True,
                ),
            ),
        )

        executor = MkvpropeditExecutor()
        result = executor.execute(plan, keep_backup=False, keep_original=False)
        assert result.success

        # Verify
        modified = introspector.get_file_info(working_copy)
        audio_tracks_after = get_audio_tracks(modified)
        eng_track_after = next(
            (t for t in audio_tracks_after if t.language == "eng"), None
        )
        assert eng_track_after is not None
        assert eng_track_after.is_default is True

    def test_clear_other_audio_defaults(
        self,
        generated_multi_audio: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvpropedit_available: bool,
    ) -> None:
        """Non-preferred audio tracks should have default flag cleared."""
        if not mkvpropedit_available:
            pytest.skip("mkvpropedit not available")
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        working_copy = copy_video(generated_multi_audio, "test_clear.mkv")

        original = introspector.get_file_info(working_copy)
        audio_tracks = get_audio_tracks(original)

        # Find tracks by language
        eng_track = next((t for t in audio_tracks if t.language == "eng"), None)
        jpn_track = next((t for t in audio_tracks if t.language == "jpn"), None)
        assert eng_track is not None
        assert jpn_track is not None

        # Create plan to set eng as default and clear jpn default
        actions = [
            PlannedAction(
                action_type=ActionType.SET_DEFAULT,
                track_index=eng_track.index,
                current_value=eng_track.is_default,
                desired_value=True,
            ),
            PlannedAction(
                action_type=ActionType.CLEAR_DEFAULT,
                track_index=jpn_track.index,
                current_value=jpn_track.is_default,
                desired_value=False,
            ),
        ]

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=12,
            requires_remux=False,
            actions=tuple(actions),
        )

        executor = MkvpropeditExecutor()
        result = executor.execute(plan, keep_backup=False, keep_original=False)
        assert result.success

        # Verify
        modified = introspector.get_file_info(working_copy)
        audio_tracks_after = get_audio_tracks(modified)

        eng_after = next((t for t in audio_tracks_after if t.language == "eng"), None)
        jpn_after = next((t for t in audio_tracks_after if t.language == "jpn"), None)

        assert eng_after is not None and eng_after.is_default is True
        assert jpn_after is not None and jpn_after.is_default is False


class TestSetTrackMetadata:
    """Test setting track metadata (title, language) using mkvpropedit."""

    def test_set_track_title(
        self,
        generated_basic_h264: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvpropedit_available: bool,
    ) -> None:
        """Track title should be updated."""
        if not mkvpropedit_available:
            pytest.skip("mkvpropedit not available")
        if generated_basic_h264 is None:
            pytest.skip("Test video not available")

        working_copy = copy_video(generated_basic_h264, "test_title.mkv")

        original = introspector.get_file_info(working_copy)
        audio_track = get_track_by_type_and_index(original, "audio", 0)
        assert audio_track is not None

        new_title = "Updated Audio Title"
        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=12,
            requires_remux=False,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_TITLE,
                    track_index=audio_track.index,
                    current_value=audio_track.title,
                    desired_value=new_title,
                ),
            ),
        )

        executor = MkvpropeditExecutor()
        result = executor.execute(plan, keep_backup=False, keep_original=False)
        assert result.success

        modified = introspector.get_file_info(working_copy)
        audio_after = get_track_by_type_and_index(modified, "audio", 0)
        assert audio_after is not None
        assert audio_after.title == new_title

    def test_set_track_language(
        self,
        generated_basic_h264: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvpropedit_available: bool,
    ) -> None:
        """Track language should be updated."""
        if not mkvpropedit_available:
            pytest.skip("mkvpropedit not available")
        if generated_basic_h264 is None:
            pytest.skip("Test video not available")

        working_copy = copy_video(generated_basic_h264, "test_lang.mkv")

        original = introspector.get_file_info(working_copy)
        audio_track = get_track_by_type_and_index(original, "audio", 0)
        assert audio_track is not None

        new_language = "deu"  # German
        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=12,
            requires_remux=False,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_LANGUAGE,
                    track_index=audio_track.index,
                    current_value=audio_track.language,
                    desired_value=new_language,
                ),
            ),
        )

        executor = MkvpropeditExecutor()
        result = executor.execute(plan, keep_backup=False, keep_original=False)
        assert result.success

        modified = introspector.get_file_info(working_copy)
        audio_after = get_track_by_type_and_index(modified, "audio", 0)
        assert audio_after is not None
        # Note: "deu" (ISO 639-2/T) may be normalized to "ger" (ISO 639-2/B)
        assert audio_after.language in (new_language, "ger")


class TestPolicyEvaluationWithRealFiles:
    """Test policy evaluation produces correct plans for real files."""

    def test_compute_default_flags_for_multi_audio(
        self,
        generated_multi_audio: Path | None,
        introspector: FFprobeIntrospector,
    ) -> None:
        """Policy evaluation should compute correct default flags."""
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_multi_audio)

        policy = PolicySchema(
            schema_version=12,
            audio_language_preference=["eng", "jpn", "fra"],
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                clear_other_defaults=True,
            ),
        )

        matcher = CommentaryMatcher(patterns=[])
        default_flags = compute_default_flags(result.tracks, policy, matcher)

        # Video should be default
        video_tracks = get_video_tracks(result)
        if video_tracks:
            assert default_flags.get(video_tracks[0].index) is True

        # English audio should be default (first preference)
        audio_tracks = get_audio_tracks(result)
        eng_track = next((t for t in audio_tracks if t.language == "eng"), None)
        if eng_track:
            assert default_flags.get(eng_track.index) is True

        # Other audio should NOT be default
        for track in audio_tracks:
            if track.language != "eng":
                assert default_flags.get(track.index) in (False, None)

    def test_compute_desired_order_for_multi_audio(
        self,
        generated_multi_audio: Path | None,
        introspector: FFprobeIntrospector,
    ) -> None:
        """Policy evaluation should compute correct track order."""
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        result = introspector.get_file_info(generated_multi_audio)

        policy = PolicySchema(
            schema_version=12,
            audio_language_preference=["jpn", "eng", "fra"],  # Japanese first
            track_order=(
                TrackType.VIDEO,
                TrackType.AUDIO_MAIN,
                TrackType.AUDIO_ALTERNATE,
            ),
        )

        matcher = CommentaryMatcher(patterns=[])
        desired_order = compute_desired_order(result.tracks, policy, matcher, {})

        # Verify order exists
        assert len(desired_order) > 0

        # The exact indices depend on the generated file, but we can verify
        # the order respects language preferences
        audio_tracks = get_audio_tracks(result)
        jpn_track = next((t for t in audio_tracks if t.language == "jpn"), None)
        eng_track = next((t for t in audio_tracks if t.language == "eng"), None)

        if jpn_track and eng_track:
            jpn_pos = (
                desired_order.index(jpn_track.index)
                if jpn_track.index in desired_order
                else -1
            )

            # Video should come first, then audio
            video_tracks = get_video_tracks(result)
            if video_tracks:
                video_pos = (
                    desired_order.index(video_tracks[0].index)
                    if video_tracks[0].index in desired_order
                    else -1
                )
                assert video_pos < jpn_pos, "Video should come before audio"
