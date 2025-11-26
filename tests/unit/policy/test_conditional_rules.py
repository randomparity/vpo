"""Tests for conditional rule evaluation.

Tests for User Story 1: Basic Conditional Rules (Priority: P1) MVP
Enable if/then/else rules in policies with first-match-wins semantics.
"""

from pathlib import Path

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.evaluator import (
    _extract_skip_flags_from_result,
    evaluate_conditional_rules,
)
from video_policy_orchestrator.policy.models import (
    ConditionalRule,
    ExistsCondition,
    SkipAction,
    SkipFlags,
    SkipType,
    TrackFilters,
    WarnAction,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def video_track_1080p() -> TrackInfo:
    """A 1080p video track."""
    return TrackInfo(
        index=0,
        track_type="video",
        codec="hevc",
        language=None,
        title="Main Video",
        is_default=True,
        is_forced=False,
        channels=None,
        channel_layout=None,
        width=1920,
        height=1080,
        frame_rate="24000/1001",
    )


@pytest.fixture
def video_track_4k() -> TrackInfo:
    """A 4K video track."""
    return TrackInfo(
        index=0,
        track_type="video",
        codec="hevc",
        language=None,
        title="Main Video",
        is_default=True,
        is_forced=False,
        channels=None,
        channel_layout=None,
        width=3840,
        height=2160,
        frame_rate="24000/1001",
    )


@pytest.fixture
def audio_track_eng() -> TrackInfo:
    """An English audio track."""
    return TrackInfo(
        index=1,
        track_type="audio",
        codec="aac",
        language="eng",
        title="English Audio",
        is_default=True,
        is_forced=False,
        channels=2,
        channel_layout="stereo",
        width=None,
        height=None,
        frame_rate=None,
    )


@pytest.fixture
def audio_track_jpn() -> TrackInfo:
    """A Japanese audio track."""
    return TrackInfo(
        index=2,
        track_type="audio",
        codec="aac",
        language="jpn",
        title="Japanese Audio",
        is_default=False,
        is_forced=False,
        channels=2,
        channel_layout="stereo",
        width=None,
        height=None,
        frame_rate=None,
    )


@pytest.fixture
def subtitle_track_eng() -> TrackInfo:
    """An English subtitle track."""
    return TrackInfo(
        index=3,
        track_type="subtitle",
        codec="subrip",
        language="eng",
        title="English Subtitles",
        is_default=False,
        is_forced=False,
        channels=None,
        channel_layout=None,
        width=None,
        height=None,
        frame_rate=None,
    )


@pytest.fixture
def basic_tracks(
    video_track_1080p: TrackInfo,
    audio_track_eng: TrackInfo,
    subtitle_track_eng: TrackInfo,
) -> list[TrackInfo]:
    """Basic set of tracks: 1080p video, English audio, English subtitles."""
    return [video_track_1080p, audio_track_eng, subtitle_track_eng]


@pytest.fixture
def tracks_4k(
    video_track_4k: TrackInfo,
    audio_track_eng: TrackInfo,
    subtitle_track_eng: TrackInfo,
) -> list[TrackInfo]:
    """Track set with 4K video."""
    return [video_track_4k, audio_track_eng, subtitle_track_eng]


# =============================================================================
# Test Helpers
# =============================================================================


def make_exists_condition(track_type: str, **filters) -> ExistsCondition:
    """Helper to create an ExistsCondition with filters."""
    return ExistsCondition(track_type=track_type, filters=TrackFilters(**filters))


def make_rule(
    name: str,
    condition: ExistsCondition,
    then_actions: tuple = (),
    else_actions: tuple | None = None,
) -> ConditionalRule:
    """Helper to create a ConditionalRule."""
    return ConditionalRule(
        name=name,
        when=condition,
        then_actions=then_actions,
        else_actions=else_actions,
    )


# =============================================================================
# T026: Test single rule matching then branch
# =============================================================================


class TestSingleRuleThenBranch:
    """Test that a single rule executes then_actions when condition matches."""

    def test_rule_matches_executes_then_actions(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """When condition matches, then_actions should execute."""
        # Rule: if video exists, skip video transcode
        rule = make_rule(
            name="Skip video transcode",
            condition=make_exists_condition("video"),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule == "Skip video transcode"
        assert result.matched_branch == "then"
        skip_flags = _extract_skip_flags_from_result(result)
        assert skip_flags.skip_video_transcode is True

    def test_rule_matches_with_warn_action(self, basic_tracks: list[TrackInfo]) -> None:
        """When condition matches and action is warn, warning is recorded."""
        rule = make_rule(
            name="Warn about video",
            condition=make_exists_condition("video"),
            then_actions=(WarnAction(message="Video exists in {filename}"),),
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule == "Warn about video"
        assert result.matched_branch == "then"
        assert len(result.warnings) == 1
        assert "Video exists in file.mkv" in result.warnings[0]


# =============================================================================
# T027: Test single rule matching else branch
# =============================================================================


class TestSingleRuleElseBranch:
    """Test that a single rule executes else_actions when condition fails."""

    def test_rule_not_matches_executes_else_actions(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """When condition fails and else_actions exist, they should execute."""
        # Rule: if attachment exists (it doesn't), else skip track filter
        rule = make_rule(
            name="Check attachments",
            condition=make_exists_condition("attachment"),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
            else_actions=(SkipAction(skip_type=SkipType.TRACK_FILTER),),
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule == "Check attachments"
        assert result.matched_branch == "else"
        skip_flags = _extract_skip_flags_from_result(result)
        assert skip_flags.skip_video_transcode is False
        assert skip_flags.skip_track_filter is True

    def test_rule_not_matches_no_else_actions(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """When condition fails and no else_actions, result shows no match."""
        # Rule: if attachment exists (it doesn't), no else clause
        rule = make_rule(
            name="Check attachments",
            condition=make_exists_condition("attachment"),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
            else_actions=None,
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule is None
        assert result.matched_branch is None
        skip_flags = _extract_skip_flags_from_result(result)
        assert skip_flags.skip_video_transcode is False


# =============================================================================
# T028: Test multiple rules first-match-wins
# =============================================================================


class TestMultipleRulesFirstMatchWins:
    """Test first-match-wins semantics with multiple rules."""

    def test_first_matching_rule_wins(self, basic_tracks: list[TrackInfo]) -> None:
        """First matching rule should execute, subsequent rules ignored."""
        rules = (
            make_rule(
                name="Rule 1 - Video exists",
                condition=make_exists_condition("video"),
                then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
            ),
            make_rule(
                name="Rule 2 - Audio exists",
                condition=make_exists_condition("audio"),
                then_actions=(SkipAction(skip_type=SkipType.AUDIO_TRANSCODE),),
            ),
        )

        result = evaluate_conditional_rules(
            rules=rules,
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        # Rule 1 matches first, Rule 2 should not execute
        assert result.matched_rule == "Rule 1 - Video exists"
        skip_flags = _extract_skip_flags_from_result(result)
        assert skip_flags.skip_video_transcode is True
        assert skip_flags.skip_audio_transcode is False  # Rule 2 not executed

    def test_second_rule_matches_when_first_fails(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """When first rule fails, second rule should be evaluated."""
        rules = (
            make_rule(
                name="Rule 1 - Attachment exists",
                condition=make_exists_condition("attachment"),  # Will fail
                then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
            ),
            make_rule(
                name="Rule 2 - Audio exists",
                condition=make_exists_condition("audio"),  # Will match
                then_actions=(SkipAction(skip_type=SkipType.AUDIO_TRANSCODE),),
            ),
        )

        result = evaluate_conditional_rules(
            rules=rules,
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        # Rule 1 fails, Rule 2 matches
        assert result.matched_rule == "Rule 2 - Audio exists"
        skip_flags = _extract_skip_flags_from_result(result)
        assert skip_flags.skip_video_transcode is False
        assert skip_flags.skip_audio_transcode is True

    def test_evaluation_trace_includes_all_rules(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """Evaluation trace should include all evaluated rules."""
        rules = (
            make_rule(
                name="Rule 1 - Attachment exists",
                condition=make_exists_condition("attachment"),  # Will fail
                then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
            ),
            make_rule(
                name="Rule 2 - Audio exists",
                condition=make_exists_condition("audio"),  # Will match
                then_actions=(SkipAction(skip_type=SkipType.AUDIO_TRANSCODE),),
            ),
        )

        result = evaluate_conditional_rules(
            rules=rules,
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        # Both rules should be in the trace
        assert len(result.evaluation_trace) == 2
        assert result.evaluation_trace[0].rule_name == "Rule 1 - Attachment exists"
        assert result.evaluation_trace[0].matched is False
        assert result.evaluation_trace[1].rule_name == "Rule 2 - Audio exists"
        assert result.evaluation_trace[1].matched is True


# =============================================================================
# T029: Test no rules matching
# =============================================================================


class TestNoRulesMatching:
    """Test behavior when no rules match."""

    def test_no_rules_match_returns_empty_result(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """When no rules match, result should indicate no match."""
        rules = (
            make_rule(
                name="Rule 1 - Attachment exists",
                condition=make_exists_condition("attachment"),  # Will fail
                then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
            ),
        )

        result = evaluate_conditional_rules(
            rules=rules,
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule is None
        assert result.matched_branch is None
        skip_flags = _extract_skip_flags_from_result(result)
        assert skip_flags == SkipFlags()

    def test_empty_rules_returns_empty_result(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """When no rules are defined, result should be empty."""
        result = evaluate_conditional_rules(
            rules=(),
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule is None
        assert result.matched_branch is None
        skip_flags = _extract_skip_flags_from_result(result)
        assert skip_flags == SkipFlags()
        assert len(result.evaluation_trace) == 0

    def test_last_rule_else_executes_when_no_match(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """When no rules match, last rule's else_actions should execute."""
        rules = (
            make_rule(
                name="Rule with else",
                condition=make_exists_condition("attachment"),  # Will fail
                then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
                else_actions=(WarnAction(message="No attachment found"),),
            ),
        )

        result = evaluate_conditional_rules(
            rules=rules,
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule == "Rule with else"
        assert result.matched_branch == "else"
        assert len(result.warnings) == 1
        assert "No attachment found" in result.warnings[0]
