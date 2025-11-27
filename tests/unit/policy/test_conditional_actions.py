"""Tests for conditional action execution.

Tests for User Story 6: Skip Processing Actions (Priority: P3)
Skip video/audio transcoding based on conditions.

Tests for User Story 7: Warnings and Errors (Priority: P3)
Generate warnings or halt processing based on conditions.

Tests for User Story 3 (035): Set Forced/Default Actions
Manipulate track flags based on multi-language conditions.
"""

from pathlib import Path

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.actions import (
    ActionContext,
    execute_actions,
    execute_set_default_action,
    execute_set_forced_action,
    execute_skip_action,
    execute_warn_action,
)
from video_policy_orchestrator.policy.exceptions import ConditionalFailError
from video_policy_orchestrator.policy.models import (
    FailAction,
    SetDefaultAction,
    SetForcedAction,
    SkipAction,
    SkipFlags,
    SkipType,
    WarnAction,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def action_context() -> ActionContext:
    """A basic action context."""
    return ActionContext(
        file_path=Path("/videos/test_movie.mkv"),
        rule_name="Test Rule",
    )


# =============================================================================
# T075: Test file for conditional actions (verified by presence)
# T076: Test skip_video_transcode action
# =============================================================================


class TestSkipVideoTranscodeAction:
    """Test skip_video_transcode action behavior."""

    def test_skip_video_transcode_sets_flag(
        self, action_context: ActionContext
    ) -> None:
        """Skip video transcode action sets the correct flag."""
        action = SkipAction(skip_type=SkipType.VIDEO_TRANSCODE)

        result = execute_skip_action(action, action_context)

        assert result.skip_flags.skip_video_transcode is True
        assert result.skip_flags.skip_audio_transcode is False
        assert result.skip_flags.skip_track_filter is False

    def test_skip_video_transcode_via_execute_actions(
        self, action_context: ActionContext
    ) -> None:
        """Skip video transcode works through execute_actions."""
        actions = (SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),)

        result = execute_actions(actions, action_context)

        assert result.skip_flags.skip_video_transcode is True


# =============================================================================
# T077: Test skip_audio_transcode action
# =============================================================================


class TestSkipAudioTranscodeAction:
    """Test skip_audio_transcode action behavior."""

    def test_skip_audio_transcode_sets_flag(
        self, action_context: ActionContext
    ) -> None:
        """Skip audio transcode action sets the correct flag."""
        action = SkipAction(skip_type=SkipType.AUDIO_TRANSCODE)

        result = execute_skip_action(action, action_context)

        assert result.skip_flags.skip_video_transcode is False
        assert result.skip_flags.skip_audio_transcode is True
        assert result.skip_flags.skip_track_filter is False


# =============================================================================
# T078: Test skip_track_filter action
# =============================================================================


class TestSkipTrackFilterAction:
    """Test skip_track_filter action behavior."""

    def test_skip_track_filter_sets_flag(self, action_context: ActionContext) -> None:
        """Skip track filter action sets the correct flag."""
        action = SkipAction(skip_type=SkipType.TRACK_FILTER)

        result = execute_skip_action(action, action_context)

        assert result.skip_flags.skip_video_transcode is False
        assert result.skip_flags.skip_audio_transcode is False
        assert result.skip_flags.skip_track_filter is True


# =============================================================================
# T079: Test skip flags accumulation
# =============================================================================


class TestSkipFlagsAccumulation:
    """Test that multiple skip actions accumulate flags."""

    def test_multiple_skip_actions_accumulate(
        self, action_context: ActionContext
    ) -> None:
        """Multiple skip actions combine their flags."""
        actions = (
            SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),
            SkipAction(skip_type=SkipType.AUDIO_TRANSCODE),
        )

        result = execute_actions(actions, action_context)

        assert result.skip_flags.skip_video_transcode is True
        assert result.skip_flags.skip_audio_transcode is True
        assert result.skip_flags.skip_track_filter is False

    def test_all_skip_flags_can_be_set(self, action_context: ActionContext) -> None:
        """All three skip flags can be set together."""
        actions = (
            SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),
            SkipAction(skip_type=SkipType.AUDIO_TRANSCODE),
            SkipAction(skip_type=SkipType.TRACK_FILTER),
        )

        result = execute_actions(actions, action_context)

        assert result.skip_flags.skip_video_transcode is True
        assert result.skip_flags.skip_audio_transcode is True
        assert result.skip_flags.skip_track_filter is True


# =============================================================================
# T086: Test warn action
# =============================================================================


class TestWarnAction:
    """Test warn action behavior."""

    def test_warn_action_records_message(self, action_context: ActionContext) -> None:
        """Warn action records the warning message."""
        action = WarnAction(message="This is a warning")

        result = execute_warn_action(action, action_context)

        assert len(result.warnings) == 1
        assert "This is a warning" in result.warnings[0]

    def test_warn_action_via_execute_actions(
        self, action_context: ActionContext
    ) -> None:
        """Warn action works through execute_actions."""
        actions = (WarnAction(message="Test warning"),)

        result = execute_actions(actions, action_context)

        assert len(result.warnings) == 1
        assert "Test warning" in result.warnings[0]


# =============================================================================
# T087: Test fail action
# =============================================================================


class TestFailAction:
    """Test fail action behavior."""

    def test_fail_action_raises_error(self, action_context: ActionContext) -> None:
        """Fail action raises ConditionalFailError."""
        actions = (FailAction(message="Processing failed"),)

        with pytest.raises(ConditionalFailError) as exc_info:
            execute_actions(actions, action_context)

        assert exc_info.value.rule_name == "Test Rule"
        assert "Processing failed" in exc_info.value.message

    def test_fail_action_includes_file_path(
        self, action_context: ActionContext
    ) -> None:
        """Fail action includes file path in error."""
        actions = (FailAction(message="Error occurred"),)

        with pytest.raises(ConditionalFailError) as exc_info:
            execute_actions(actions, action_context)

        assert exc_info.value.file_path == str(action_context.file_path)


# =============================================================================
# T088: Test placeholder substitution
# =============================================================================


class TestPlaceholderSubstitution:
    """Test placeholder substitution in messages."""

    def test_filename_placeholder(self, action_context: ActionContext) -> None:
        """Filename placeholder is substituted."""
        action = WarnAction(message="File: {filename}")

        result = execute_warn_action(action, action_context)

        assert "test_movie.mkv" in result.warnings[0]

    def test_path_placeholder(self, action_context: ActionContext) -> None:
        """Path placeholder is substituted."""
        action = WarnAction(message="Path: {path}")

        result = execute_warn_action(action, action_context)

        assert "/videos/test_movie.mkv" in result.warnings[0]

    def test_rule_name_placeholder(self, action_context: ActionContext) -> None:
        """Rule name placeholder is substituted."""
        action = WarnAction(message="Rule: {rule_name}")

        result = execute_warn_action(action, action_context)

        assert "Test Rule" in result.warnings[0]

    def test_multiple_placeholders(self, action_context: ActionContext) -> None:
        """Multiple placeholders can be used together."""
        action = WarnAction(message="{rule_name}: {filename} at {path}")

        result = execute_warn_action(action, action_context)

        warning = result.warnings[0]
        assert "Test Rule" in warning
        assert "test_movie.mkv" in warning
        assert "/videos/test_movie.mkv" in warning

    def test_placeholder_in_fail_action(self, action_context: ActionContext) -> None:
        """Placeholders work in fail action messages."""
        actions = (FailAction(message="Failed processing {filename}"),)

        with pytest.raises(ConditionalFailError) as exc_info:
            execute_actions(actions, action_context)

        assert "test_movie.mkv" in exc_info.value.message


# =============================================================================
# T089: Test multiple warnings accumulation
# =============================================================================


class TestMultipleWarningsAccumulation:
    """Test that multiple warn actions accumulate."""

    def test_multiple_warnings_accumulate(self, action_context: ActionContext) -> None:
        """Multiple warn actions add to warnings list."""
        actions = (
            WarnAction(message="Warning 1"),
            WarnAction(message="Warning 2"),
            WarnAction(message="Warning 3"),
        )

        result = execute_actions(actions, action_context)

        assert len(result.warnings) == 3
        assert "Warning 1" in result.warnings[0]
        assert "Warning 2" in result.warnings[1]
        assert "Warning 3" in result.warnings[2]

    def test_skip_and_warn_together(self, action_context: ActionContext) -> None:
        """Skip and warn actions can be combined."""
        actions = (
            SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),
            WarnAction(message="Video transcode skipped"),
        )

        result = execute_actions(actions, action_context)

        assert result.skip_flags.skip_video_transcode is True
        assert len(result.warnings) == 1
        assert "transcode skipped" in result.warnings[0]


# =============================================================================
# Additional edge case tests
# =============================================================================


class TestActionEdgeCases:
    """Test edge cases in action execution."""

    def test_empty_actions_list(self, action_context: ActionContext) -> None:
        """Empty actions list returns unchanged context."""
        result = execute_actions((), action_context)

        assert result.skip_flags == SkipFlags()
        assert result.warnings == []

    def test_fail_action_stops_execution(self, action_context: ActionContext) -> None:
        """Fail action stops execution before subsequent actions."""
        actions = (
            WarnAction(message="Before fail"),
            FailAction(message="Stop here"),
            WarnAction(message="After fail"),  # Should not execute
        )

        with pytest.raises(ConditionalFailError):
            execute_actions(actions, action_context)

        # Can't check warnings since exception was raised

    def test_action_context_filename_property(self) -> None:
        """ActionContext filename property extracts basename."""
        context = ActionContext(
            file_path=Path("/deep/nested/path/to/video.mkv"),
            rule_name="Test",
        )

        assert context.filename == "video.mkv"

    def test_skip_flags_immutable_default(self) -> None:
        """SkipFlags default is a new instance each time."""
        flags1 = SkipFlags()
        flags2 = SkipFlags()

        assert flags1 == flags2
        assert flags1 is not flags2  # Different instances


# =============================================================================
# T072: Test execute_set_forced_action()
# =============================================================================


class TestSetForcedAction:
    """Test set_forced action behavior."""

    @pytest.fixture
    def tracks_with_subtitles(self) -> list[TrackInfo]:
        """Create a list of tracks including subtitles."""
        return [
            TrackInfo(index=0, track_type="video", codec="h264"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="eng"),
            TrackInfo(index=2, track_type="subtitle", codec="srt", language="eng"),
            TrackInfo(index=3, track_type="subtitle", codec="srt", language="spa"),
        ]

    @pytest.fixture
    def context_with_tracks(
        self, tracks_with_subtitles: list[TrackInfo]
    ) -> ActionContext:
        """ActionContext with tracks populated."""
        return ActionContext(
            file_path=Path("/videos/test_movie.mkv"),
            rule_name="Test Rule",
            tracks=tracks_with_subtitles,
        )

    def test_set_forced_creates_flag_change(
        self, context_with_tracks: ActionContext
    ) -> None:
        """Set forced action creates flag changes for matching tracks."""
        action = SetForcedAction(track_type="subtitle")

        result = execute_set_forced_action(action, context_with_tracks)

        assert len(result.track_flag_changes) == 2  # Both subtitle tracks
        assert result.track_flag_changes[0].flag_type == "forced"
        assert result.track_flag_changes[0].value is True

    def test_set_forced_filters_by_language(
        self, context_with_tracks: ActionContext
    ) -> None:
        """Set forced action filters tracks by language."""
        action = SetForcedAction(track_type="subtitle", language="eng")

        result = execute_set_forced_action(action, context_with_tracks)

        assert len(result.track_flag_changes) == 1
        assert result.track_flag_changes[0].track_index == 2  # English subtitle

    def test_set_forced_with_value_false(
        self, context_with_tracks: ActionContext
    ) -> None:
        """Set forced action can clear the forced flag."""
        action = SetForcedAction(track_type="subtitle", value=False)

        result = execute_set_forced_action(action, context_with_tracks)

        for change in result.track_flag_changes:
            assert change.value is False

    def test_set_forced_no_matching_tracks(
        self, context_with_tracks: ActionContext
    ) -> None:
        """Set forced action with no matching tracks records nothing."""
        action = SetForcedAction(track_type="subtitle", language="jpn")

        result = execute_set_forced_action(action, context_with_tracks)

        assert len(result.track_flag_changes) == 0

    def test_set_forced_no_tracks_in_context(self) -> None:
        """Set forced action with no tracks in context logs warning."""
        context = ActionContext(
            file_path=Path("/videos/test.mkv"),
            rule_name="Test",
            tracks=[],
        )
        action = SetForcedAction()

        result = execute_set_forced_action(action, context)

        assert len(result.track_flag_changes) == 0

    def test_set_forced_via_execute_actions(
        self, context_with_tracks: ActionContext
    ) -> None:
        """Set forced action works through execute_actions."""
        actions = (SetForcedAction(track_type="subtitle", language="spa"),)

        result = execute_actions(actions, context_with_tracks)

        assert len(result.track_flag_changes) == 1
        assert result.track_flag_changes[0].track_index == 3


# =============================================================================
# T073: Test execute_set_default_action()
# =============================================================================


class TestSetDefaultAction:
    """Test set_default action behavior."""

    @pytest.fixture
    def tracks_with_audio(self) -> list[TrackInfo]:
        """Create a list of tracks with multiple audio options."""
        return [
            TrackInfo(index=0, track_type="video", codec="h264"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="eng"),
            TrackInfo(index=2, track_type="audio", codec="dts", language="jpn"),
            TrackInfo(index=3, track_type="subtitle", codec="srt", language="eng"),
        ]

    @pytest.fixture
    def context_with_audio_tracks(
        self, tracks_with_audio: list[TrackInfo]
    ) -> ActionContext:
        """ActionContext with audio tracks."""
        return ActionContext(
            file_path=Path("/videos/test_movie.mkv"),
            rule_name="Test Rule",
            tracks=tracks_with_audio,
        )

    def test_set_default_creates_flag_change(
        self, context_with_audio_tracks: ActionContext
    ) -> None:
        """Set default action creates flag change for first matching track."""
        action = SetDefaultAction(track_type="audio")

        result = execute_set_default_action(action, context_with_audio_tracks)

        # Should only set default on FIRST matching track
        assert len(result.track_flag_changes) == 1
        assert result.track_flag_changes[0].flag_type == "default"
        assert result.track_flag_changes[0].track_index == 1

    def test_set_default_filters_by_language(
        self, context_with_audio_tracks: ActionContext
    ) -> None:
        """Set default action filters tracks by language."""
        action = SetDefaultAction(track_type="audio", language="jpn")

        result = execute_set_default_action(action, context_with_audio_tracks)

        assert len(result.track_flag_changes) == 1
        assert result.track_flag_changes[0].track_index == 2  # Japanese audio

    def test_set_default_with_value_false(
        self, context_with_audio_tracks: ActionContext
    ) -> None:
        """Set default action can clear the default flag."""
        action = SetDefaultAction(track_type="audio", value=False)

        result = execute_set_default_action(action, context_with_audio_tracks)

        assert result.track_flag_changes[0].value is False

    def test_set_default_no_matching_tracks(
        self, context_with_audio_tracks: ActionContext
    ) -> None:
        """Set default action with no matching tracks records nothing."""
        action = SetDefaultAction(track_type="audio", language="fre")

        result = execute_set_default_action(action, context_with_audio_tracks)

        assert len(result.track_flag_changes) == 0

    def test_set_default_subtitle_track(
        self, context_with_audio_tracks: ActionContext
    ) -> None:
        """Set default action works for subtitle tracks."""
        action = SetDefaultAction(track_type="subtitle", language="eng")

        result = execute_set_default_action(action, context_with_audio_tracks)

        assert len(result.track_flag_changes) == 1
        assert result.track_flag_changes[0].track_index == 3

    def test_set_default_via_execute_actions(
        self, context_with_audio_tracks: ActionContext
    ) -> None:
        """Set default action works through execute_actions."""
        actions = (SetDefaultAction(track_type="subtitle"),)

        result = execute_actions(actions, context_with_audio_tracks)

        assert len(result.track_flag_changes) == 1


# =============================================================================
# T074: Test missing track warning
# =============================================================================


class TestTrackFlagActionWarnings:
    """Test warning behavior for set_forced/set_default actions."""

    def test_set_forced_warns_on_no_match(self, caplog) -> None:
        """Set forced logs warning when no tracks match."""
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="Test",
            tracks=[TrackInfo(index=0, track_type="audio", codec="aac")],
        )
        action = SetForcedAction(track_type="subtitle")

        execute_set_forced_action(action, context)

        assert "no matching subtitle tracks" in caplog.text.lower()

    def test_set_default_warns_on_no_match(self, caplog) -> None:
        """Set default logs warning when no tracks match."""
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="Test",
            tracks=[TrackInfo(index=0, track_type="video", codec="h264")],
        )
        action = SetDefaultAction(track_type="audio")

        execute_set_default_action(action, context)

        assert "no matching audio tracks" in caplog.text.lower()


# =============================================================================
# Combined action tests
# =============================================================================


class TestCombinedActions:
    """Test combinations of actions including set_forced/set_default."""

    @pytest.fixture
    def context_with_all_tracks(self) -> ActionContext:
        """Context with video, audio, and subtitle tracks."""
        return ActionContext(
            file_path=Path("/videos/movie.mkv"),
            rule_name="Multi-language Handler",
            tracks=[
                TrackInfo(index=0, track_type="video", codec="h264"),
                TrackInfo(index=1, track_type="audio", codec="aac", language="eng"),
                TrackInfo(index=2, track_type="subtitle", codec="srt", language="eng"),
            ],
        )

    def test_skip_and_set_forced_together(
        self, context_with_all_tracks: ActionContext
    ) -> None:
        """Skip and set_forced actions can be combined."""
        actions = (
            SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),
            SetForcedAction(track_type="subtitle", language="eng"),
        )

        result = execute_actions(actions, context_with_all_tracks)

        assert result.skip_flags.skip_video_transcode is True
        assert len(result.track_flag_changes) == 1
        assert result.track_flag_changes[0].flag_type == "forced"

    def test_warn_and_set_default_together(
        self, context_with_all_tracks: ActionContext
    ) -> None:
        """Warn and set_default actions can be combined."""
        actions = (
            WarnAction(message="Setting default audio for {filename}"),
            SetDefaultAction(track_type="audio", language="eng"),
        )

        result = execute_actions(actions, context_with_all_tracks)

        assert len(result.warnings) == 1
        assert "movie.mkv" in result.warnings[0]
        assert len(result.track_flag_changes) == 1
        assert result.track_flag_changes[0].flag_type == "default"

    def test_multiple_track_flag_actions(
        self, context_with_all_tracks: ActionContext
    ) -> None:
        """Multiple set_forced and set_default actions accumulate."""
        actions = (
            SetForcedAction(track_type="subtitle"),
            SetDefaultAction(track_type="subtitle"),
            SetDefaultAction(track_type="audio"),
        )

        result = execute_actions(actions, context_with_all_tracks)

        assert len(result.track_flag_changes) == 3
        forced_changes = [
            c for c in result.track_flag_changes if c.flag_type == "forced"
        ]
        default_changes = [
            c for c in result.track_flag_changes if c.flag_type == "default"
        ]
        assert len(forced_changes) == 1
        assert len(default_changes) == 2
