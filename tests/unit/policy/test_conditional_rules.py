"""Tests for conditional rule evaluation.

Tests for User Story 1: Basic Conditional Rules (Priority: P1) MVP
Enable if/then/else rules in policies with first-match-wins semantics.
"""

from pathlib import Path

import pytest

from vpo.db import TrackInfo
from vpo.policy.evaluator import (
    evaluate_conditional_rules,
)
from vpo.policy.types import (
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
        skip_flags = result.skip_flags
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
        skip_flags = result.skip_flags
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
        skip_flags = result.skip_flags
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
        skip_flags = result.skip_flags
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
        skip_flags = result.skip_flags
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
        skip_flags = result.skip_flags
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
        skip_flags = result.skip_flags
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


# =============================================================================
# Tests for track_flag_changes propagation (set_forced/set_default)
# =============================================================================


@pytest.fixture
def audio_track_ger() -> TrackInfo:
    """A German audio track (non-English)."""
    return TrackInfo(
        index=1,
        track_type="audio",
        codec="eac3",
        language="ger",
        title="German Audio",
        is_default=True,
        is_forced=False,
        channels=6,
        channel_layout="5.1(side)",
        width=None,
        height=None,
        frame_rate=None,
    )


@pytest.fixture
def subtitle_track_eng_not_forced() -> TrackInfo:
    """An English subtitle track that is not forced."""
    return TrackInfo(
        index=2,
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
def foreign_audio_tracks(
    video_track_1080p: TrackInfo,
    audio_track_ger: TrackInfo,
    subtitle_track_eng_not_forced: TrackInfo,
) -> list[TrackInfo]:
    """Track set with German audio and English subtitle (not forced)."""
    return [video_track_1080p, audio_track_ger, subtitle_track_eng_not_forced]


class TestSetForcedActionPropagation:
    """Test that set_forced actions create track_flag_changes in ConditionalResult."""

    def test_set_forced_creates_track_flag_change_in_result(
        self, foreign_audio_tracks: list[TrackInfo]
    ) -> None:
        """When set_forced action executes, track_flag_changes should be populated."""
        from vpo.policy.types import (
            NotCondition,
            SetForcedAction,
        )

        # Rule: if no English audio exists, set forced on English subtitles
        rule = ConditionalRule(
            name="force_subs_for_foreign_audio",
            when=NotCondition(inner=make_exists_condition("audio", language="eng")),
            then_actions=(
                SetForcedAction(track_type="subtitle", language="eng", value=True),
            ),
            else_actions=None,
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=foreign_audio_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule == "force_subs_for_foreign_audio"
        assert result.matched_branch == "then"
        assert len(result.track_flag_changes) == 1

        change = result.track_flag_changes[0]
        assert change.track_index == 2  # English subtitle track
        assert change.flag_type == "forced"
        assert change.value is True

    def test_set_forced_from_else_branch(self, basic_tracks: list[TrackInfo]) -> None:
        """set_forced in else branch should also populate track_flag_changes."""
        from vpo.policy.types import SetForcedAction

        # Rule: if attachment exists (false), else set forced on subtitles
        rule = ConditionalRule(
            name="fallback_set_forced",
            when=make_exists_condition("attachment"),  # Will fail
            then_actions=(),
            else_actions=(
                SetForcedAction(track_type="subtitle", language="eng", value=True),
            ),
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule == "fallback_set_forced"
        assert result.matched_branch == "else"
        assert len(result.track_flag_changes) == 1

        change = result.track_flag_changes[0]
        assert change.track_index == 3  # English subtitle track in basic_tracks
        assert change.flag_type == "forced"
        assert change.value is True

    def test_set_forced_clear_forced(
        self, subtitle_track_eng: TrackInfo, video_track_1080p: TrackInfo
    ) -> None:
        """set_forced with value=False should create CLEAR_FORCED change."""
        from vpo.policy.types import SetForcedAction

        # Create a subtitle track that is already forced
        forced_subtitle = TrackInfo(
            index=1,
            track_type="subtitle",
            codec="subrip",
            language="eng",
            title="English Subtitles",
            is_default=False,
            is_forced=True,  # Already forced
            channels=None,
            channel_layout=None,
            width=None,
            height=None,
            frame_rate=None,
        )
        tracks = [video_track_1080p, forced_subtitle]

        rule = ConditionalRule(
            name="clear_forced",
            when=make_exists_condition("video"),
            then_actions=(
                SetForcedAction(track_type="subtitle", language="eng", value=False),
            ),
            else_actions=None,
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert len(result.track_flag_changes) == 1
        change = result.track_flag_changes[0]
        assert change.flag_type == "forced"
        assert change.value is False

    def test_no_matching_tracks_no_flag_changes(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """No matching tracks means track_flag_changes should be empty."""
        from vpo.policy.types import SetForcedAction

        # Try to set forced on Japanese subtitles (none exist)
        rule = ConditionalRule(
            name="set_forced_jpn",
            when=make_exists_condition("video"),
            then_actions=(
                SetForcedAction(track_type="subtitle", language="jpn", value=True),
            ),
            else_actions=None,
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert result.matched_rule == "set_forced_jpn"
        assert len(result.track_flag_changes) == 0


class TestSetDefaultActionPropagation:
    """Test that set_default actions create track_flag_changes in ConditionalResult."""

    def test_set_default_creates_track_flag_change(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """When set_default action executes, track_flag_changes should be populated."""
        from vpo.policy.types import SetDefaultAction

        rule = ConditionalRule(
            name="set_subtitle_default",
            when=make_exists_condition("video"),
            then_actions=(
                SetDefaultAction(track_type="subtitle", language="eng", value=True),
            ),
            else_actions=None,
        )

        result = evaluate_conditional_rules(
            rules=(rule,),
            tracks=basic_tracks,
            file_path=Path("/test/file.mkv"),
        )

        assert len(result.track_flag_changes) == 1
        change = result.track_flag_changes[0]
        assert change.track_index == 3  # English subtitle
        assert change.flag_type == "default"
        assert change.value is True


# =============================================================================
# Tests for track_flag_changes conversion to PlannedAction in evaluate_plan()
# =============================================================================


class TestTrackFlagChangesToPlannedAction:
    """Test that track_flag_changes become PlannedAction in evaluate_plan()."""

    def test_set_forced_becomes_planned_action(
        self, foreign_audio_tracks: list[TrackInfo], tmp_path: Path
    ) -> None:
        """set_forced action should create SET_FORCED PlannedAction in plan."""
        from vpo.policy.evaluator import evaluate_policy
        from vpo.policy.loader import load_policy
        from vpo.policy.types import ActionType

        # Create a policy with conditional set_forced
        policy_path = tmp_path / "policy.yaml"
        policy_path.write_text("""
schema_version: 12

conditional:
  - name: force_english_subs_for_foreign_audio
    when:
      not:
        exists:
          track_type: audio
          language: eng
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          value: true
""")
        policy = load_policy(policy_path)

        plan = evaluate_policy(
            file_id=None,
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=foreign_audio_tracks,
            policy=policy,
        )

        # Find SET_FORCED action
        forced_actions = [
            a for a in plan.actions if a.action_type == ActionType.SET_FORCED
        ]
        assert len(forced_actions) == 1

        action = forced_actions[0]
        assert action.track_index == 2  # English subtitle
        assert action.current_value is False
        assert action.desired_value is True

    def test_clear_forced_becomes_planned_action(
        self, video_track_1080p: TrackInfo, tmp_path: Path
    ) -> None:
        """set_forced(value=False) should create CLEAR_FORCED PlannedAction."""
        from vpo.policy.evaluator import evaluate_policy
        from vpo.policy.loader import load_policy
        from vpo.policy.types import ActionType

        # Create a subtitle track that is already forced
        forced_subtitle = TrackInfo(
            index=1,
            track_type="subtitle",
            codec="subrip",
            language="eng",
            title="English Subtitles",
            is_default=False,
            is_forced=True,
            channels=None,
            channel_layout=None,
            width=None,
            height=None,
            frame_rate=None,
        )
        tracks = [video_track_1080p, forced_subtitle]

        policy_path = tmp_path / "policy.yaml"
        policy_path.write_text("""
schema_version: 12

conditional:
  - name: clear_forced_subs
    when:
      exists:
        track_type: video
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          value: false
""")
        policy = load_policy(policy_path)

        plan = evaluate_policy(
            file_id=None,
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=tracks,
            policy=policy,
        )

        # Find CLEAR_FORCED action
        clear_actions = [
            a for a in plan.actions if a.action_type == ActionType.CLEAR_FORCED
        ]
        assert len(clear_actions) == 1

        action = clear_actions[0]
        assert action.track_index == 1
        assert action.current_value is True
        assert action.desired_value is False

    def test_no_action_when_flag_already_matches(
        self, video_track_1080p: TrackInfo, tmp_path: Path
    ) -> None:
        """No PlannedAction when track already has the requested flag value."""
        from vpo.policy.evaluator import evaluate_policy
        from vpo.policy.loader import load_policy
        from vpo.policy.types import ActionType

        # Create a subtitle that is already forced
        already_forced = TrackInfo(
            index=1,
            track_type="subtitle",
            codec="subrip",
            language="eng",
            title="English Subtitles",
            is_default=False,
            is_forced=True,  # Already forced
            channels=None,
            channel_layout=None,
            width=None,
            height=None,
            frame_rate=None,
        )
        tracks = [video_track_1080p, already_forced]

        policy_path = tmp_path / "policy.yaml"
        policy_path.write_text("""
schema_version: 12

conditional:
  - name: set_forced_subs
    when:
      exists:
        track_type: video
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          value: true
""")
        policy = load_policy(policy_path)

        plan = evaluate_policy(
            file_id=None,
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=tracks,
            policy=policy,
        )

        # Should NOT have SET_FORCED action (already forced)
        forced_actions = [
            a for a in plan.actions if a.action_type == ActionType.SET_FORCED
        ]
        assert len(forced_actions) == 0
