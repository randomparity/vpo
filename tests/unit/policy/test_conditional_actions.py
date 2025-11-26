"""Tests for conditional action execution.

Tests for User Story 6: Skip Processing Actions (Priority: P3)
Skip video/audio transcoding based on conditions.

Tests for User Story 7: Warnings and Errors (Priority: P3)
Generate warnings or halt processing based on conditions.
"""

from pathlib import Path

import pytest

from video_policy_orchestrator.policy.actions import (
    ActionContext,
    execute_actions,
    execute_skip_action,
    execute_warn_action,
)
from video_policy_orchestrator.policy.exceptions import ConditionalFailError
from video_policy_orchestrator.policy.models import (
    FailAction,
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
