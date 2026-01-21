"""Integration tests for conditional policy functionality.

Tests the end-to-end flow of conditional rule evaluation including
policy loading, condition evaluation, action execution, and plan generation.
"""

from pathlib import Path

import pytest

from vpo.db import TrackInfo
from vpo.policy.evaluator import (
    evaluate_conditional_rules,
    evaluate_policy,
)
from vpo.policy.exceptions import ConditionalFailError
from vpo.policy.loader import load_policy
from vpo.policy.types import (
    EvaluationPolicy,
    SkipFlags,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def v4_conditional_policy(temp_dir: Path) -> Path:
    """Create a V4 policy file with conditional rules."""
    policy_path = temp_dir / "conditional-policy.yaml"
    policy_path.write_text("""
schema_version: 12

config:
  audio_language_preference:
    - eng
    - und
  subtitle_language_preference:
    - eng
    - und

phases:
  - name: apply
    conditional:
      - name: "4K HEVC passthrough"
        when:
          and:
            - exists:
                track_type: video
                height: { gte: 2160 }
            - exists:
                track_type: video
                codec: hevc
        then:
          - skip_video_transcode: true
          - warn: "4K HEVC detected - skipping video transcode"

      - name: "Single audio track"
        when:
          count:
            track_type: audio
            eq: 1
        then:
          - skip_track_filter: true

      - name: "Default processing"
        when:
          exists:
            track_type: video
        then:
          - warn: "Standard processing"

    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
""")
    return policy_path


@pytest.fixture
def v4_fail_policy(temp_dir: Path) -> Path:
    """Create a V4 policy file with fail action."""
    policy_path = temp_dir / "fail-policy.yaml"
    policy_path.write_text("""
schema_version: 12

config:
  audio_language_preference:
    - eng

phases:
  - name: apply
    conditional:
      - name: "Missing English audio"
        when:
          not:
            exists:
              track_type: audio
              language: eng
        then:
          - fail: "{filename} has no English audio track"
""")
    return policy_path


@pytest.fixture
def v4_track_filter_policy(temp_dir: Path) -> Path:
    """Create a V4 policy with conditional skip_track_filter."""
    policy_path = temp_dir / "track-filter-policy.yaml"
    policy_path.write_text("""
schema_version: 12

config:
  audio_language_preference:
    - eng

phases:
  - name: apply
    conditional:
      - name: "Skip filtering for single audio"
        when:
          count:
            track_type: audio
            eq: 1
        then:
          - skip_track_filter: true
          - warn: "Single audio - skipping filter"

    audio_filter:
      languages:
        - eng
      minimum: 1
""")
    return policy_path


@pytest.fixture
def video_track_4k_hevc() -> TrackInfo:
    """A 4K HEVC video track."""
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
def video_track_1080p_h264() -> TrackInfo:
    """A 1080p H.264 video track."""
    return TrackInfo(
        index=0,
        track_type="video",
        codec="h264",
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


# =============================================================================
# T097: Integration test for complete conditional policy flow
# =============================================================================


class TestConditionalPolicyLoading:
    """Test V4 policy loading with conditional rules."""

    def test_load_v4_policy_with_conditional_rules(
        self, v4_conditional_policy: Path
    ) -> None:
        """V4 policy with conditional section should load correctly."""
        policy = load_policy(v4_conditional_policy)

        assert policy.schema_version == 12
        # Conditional rules are now in phases
        assert policy.phases[0].conditional is not None
        assert len(policy.phases[0].conditional) == 3

        # Check first rule
        rule1 = policy.phases[0].conditional[0]
        assert rule1.name == "4K HEVC passthrough"
        assert len(rule1.then_actions) == 2


class TestConditionalRuleEvaluation:
    """Test conditional rule evaluation end-to-end."""

    def test_4k_hevc_matches_first_rule(
        self,
        v4_conditional_policy: Path,
        video_track_4k_hevc: TrackInfo,
        audio_track_eng: TrackInfo,
        subtitle_track_eng: TrackInfo,
    ) -> None:
        """4K HEVC file should match the 4K HEVC passthrough rule."""
        policy = load_policy(v4_conditional_policy)
        tracks = [video_track_4k_hevc, audio_track_eng, subtitle_track_eng]

        result = evaluate_conditional_rules(
            rules=policy.phases[0].conditional,
            tracks=tracks,
            file_path=Path("/test/movie.mkv"),
        )

        assert result.matched_rule == "4K HEVC passthrough"
        assert result.matched_branch == "then"
        skip_flags = result.skip_flags
        assert skip_flags.skip_video_transcode is True
        assert len(result.warnings) == 1
        assert "4K HEVC" in result.warnings[0]

    def test_1080p_h264_matches_default_rule(
        self,
        v4_conditional_policy: Path,
        video_track_1080p_h264: TrackInfo,
        audio_track_eng: TrackInfo,
        audio_track_jpn: TrackInfo,
        subtitle_track_eng: TrackInfo,
    ) -> None:
        """1080p H.264 file with multiple audio should match default rule."""
        policy = load_policy(v4_conditional_policy)
        tracks = [
            video_track_1080p_h264,
            audio_track_eng,
            audio_track_jpn,
            subtitle_track_eng,
        ]

        result = evaluate_conditional_rules(
            rules=policy.phases[0].conditional,
            tracks=tracks,
            file_path=Path("/test/movie.mkv"),
        )

        # Should skip 4K rule, skip single-audio rule, match default
        assert result.matched_rule == "Default processing"
        assert result.matched_branch == "then"
        skip_flags = result.skip_flags
        assert skip_flags.skip_video_transcode is False
        assert skip_flags.skip_track_filter is False

    def test_single_audio_matches_second_rule(
        self,
        v4_conditional_policy: Path,
        video_track_1080p_h264: TrackInfo,
        audio_track_eng: TrackInfo,
        subtitle_track_eng: TrackInfo,
    ) -> None:
        """File with single audio track should match single audio rule."""
        policy = load_policy(v4_conditional_policy)
        tracks = [video_track_1080p_h264, audio_track_eng, subtitle_track_eng]

        result = evaluate_conditional_rules(
            rules=policy.phases[0].conditional,
            tracks=tracks,
            file_path=Path("/test/movie.mkv"),
        )

        # Should skip 4K rule, match single-audio rule
        assert result.matched_rule == "Single audio track"
        assert result.matched_branch == "then"
        skip_flags = result.skip_flags
        assert skip_flags.skip_track_filter is True

    def test_evaluation_trace_records_all_rules(
        self,
        v4_conditional_policy: Path,
        video_track_1080p_h264: TrackInfo,
        audio_track_eng: TrackInfo,
        subtitle_track_eng: TrackInfo,
    ) -> None:
        """Evaluation trace should record all evaluated rules."""
        policy = load_policy(v4_conditional_policy)
        tracks = [video_track_1080p_h264, audio_track_eng, subtitle_track_eng]

        result = evaluate_conditional_rules(
            rules=policy.phases[0].conditional,
            tracks=tracks,
            file_path=Path("/test/movie.mkv"),
        )

        # Should have trace entries for rules evaluated before match
        assert len(result.evaluation_trace) == 2
        assert result.evaluation_trace[0].rule_name == "4K HEVC passthrough"
        assert result.evaluation_trace[0].matched is False
        assert result.evaluation_trace[1].rule_name == "Single audio track"
        assert result.evaluation_trace[1].matched is True


class TestConditionalFailAction:
    """Test fail action halts processing."""

    def test_fail_action_raises_error(
        self,
        v4_fail_policy: Path,
        video_track_1080p_h264: TrackInfo,
        audio_track_jpn: TrackInfo,  # No English audio
    ) -> None:
        """Fail action should raise ConditionalFailError."""
        policy = load_policy(v4_fail_policy)
        tracks = [video_track_1080p_h264, audio_track_jpn]

        with pytest.raises(ConditionalFailError) as exc_info:
            evaluate_conditional_rules(
                rules=policy.phases[0].conditional,
                tracks=tracks,
                file_path=Path("/test/anime.mkv"),
            )

        assert exc_info.value.rule_name == "Missing English audio"
        assert "anime.mkv" in exc_info.value.message
        assert exc_info.value.file_path == "/test/anime.mkv"

    def test_fail_action_not_triggered_when_english_exists(
        self,
        v4_fail_policy: Path,
        video_track_1080p_h264: TrackInfo,
        audio_track_eng: TrackInfo,
    ) -> None:
        """Fail action should not trigger when condition doesn't match."""
        policy = load_policy(v4_fail_policy)
        tracks = [video_track_1080p_h264, audio_track_eng]

        result = evaluate_conditional_rules(
            rules=policy.phases[0].conditional,
            tracks=tracks,
            file_path=Path("/test/movie.mkv"),
        )

        # No match since English audio exists (NOT condition fails)
        assert result.matched_rule is None


# =============================================================================
# T098: Integration test for conditional with track filtering
# =============================================================================


class TestConditionalWithTrackFiltering:
    """Test conditional skip_track_filter interacts with track filtering."""

    def test_skip_track_filter_bypasses_audio_filter(
        self, v4_track_filter_policy: Path
    ) -> None:
        """skip_track_filter should bypass audio filtering."""
        policy = load_policy(v4_track_filter_policy)
        # Convert to EvaluationPolicy for evaluate_policy
        eval_policy = EvaluationPolicy.from_phase(policy.phases[0], policy.config)

        # Single Japanese audio track (no English)
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="jpn",
                channels=2,
            ),
        ]

        # Evaluate with policy that has audio_filter requiring eng
        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/anime.mkv"),
            container="matroska",
            tracks=tracks,
            policy=eval_policy,
        )

        # skip_track_filter should be set
        assert plan.skip_flags.skip_track_filter is True

        # All tracks should be kept (filter bypassed - no dispositions generated)
        # When skip_track_filter is set, track_dispositions should be empty
        assert len(plan.track_dispositions) == 0

        # Warning should be present (on conditional_result)
        assert plan.conditional_result is not None
        assert len(plan.conditional_result.warnings) >= 1
        assert any("Single audio" in w for w in plan.conditional_result.warnings)

    def test_track_filter_applies_when_not_skipped(
        self, v4_track_filter_policy: Path
    ) -> None:
        """Track filtering should apply when skip_track_filter is not set."""
        policy = load_policy(v4_track_filter_policy)
        # Convert to EvaluationPolicy for evaluate_policy
        eval_policy = EvaluationPolicy.from_phase(policy.phases[0], policy.config)

        # Multiple audio tracks (skip condition won't match)
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                channels=2,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="jpn",
                channels=2,
            ),
        ]

        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/movie.mkv"),
            container="matroska",
            tracks=tracks,
            policy=eval_policy,
        )

        # skip_track_filter should NOT be set (multiple audio)
        assert plan.skip_flags.skip_track_filter is False

        # Japanese audio should be filtered out
        removed = [d for d in plan.track_dispositions if d.action == "REMOVE"]
        assert len(removed) == 1
        assert removed[0].language == "jpn"


class TestEvaluatePolicyWithConditionals:
    """Test evaluate_policy integrates conditional rules correctly."""

    def test_evaluate_policy_returns_conditional_result(
        self, v4_conditional_policy: Path
    ) -> None:
        """evaluate_policy should include conditional result in plan."""
        policy = load_policy(v4_conditional_policy)
        # Convert to EvaluationPolicy for evaluate_policy
        eval_policy = EvaluationPolicy.from_phase(policy.phases[0], policy.config)

        tracks = [
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
                codec="aac",
                language="eng",
                channels=2,
            ),
        ]

        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/4k-movie.mkv"),
            container="matroska",
            tracks=tracks,
            policy=eval_policy,
        )

        # Plan should have conditional result
        assert plan.conditional_result is not None
        assert plan.conditional_result.matched_rule == "4K HEVC passthrough"

        # Skip flags should be propagated
        assert plan.skip_flags.skip_video_transcode is True

        # Warnings from conditional should be on conditional_result
        assert plan.conditional_result is not None
        assert len(plan.conditional_result.warnings) >= 1
        assert any("4K HEVC" in w for w in plan.conditional_result.warnings)

    def test_evaluate_policy_with_no_conditional_rules(self, temp_dir: Path) -> None:
        """evaluate_policy should work with policy (no conditionals)."""
        policy_path = temp_dir / "no-conditionals-policy.yaml"
        policy_path.write_text("""
schema_version: 12
config:
  audio_language_preference:
    - eng
  subtitle_language_preference:
    - eng
phases:
  - name: apply
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
""")
        policy = load_policy(policy_path)
        # Convert to EvaluationPolicy for evaluate_policy
        eval_policy = EvaluationPolicy.from_phase(policy.phases[0], policy.config)

        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                channels=2,
            ),
        ]

        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/movie.mkv"),
            container="matroska",
            tracks=tracks,
            policy=eval_policy,
        )

        # No conditional result
        assert plan.conditional_result is None
        # Default skip flags
        assert plan.skip_flags == SkipFlags()


class TestConditionalPolicyFixtureLoading:
    """Test loading the conditional-test.yaml fixture."""

    def test_load_conditional_test_fixture(self) -> None:
        """Test that conditional-test.yaml fixture loads correctly."""
        fixture_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "policies"
            / "conditional-test.yaml"
        )
        if not fixture_path.exists():
            pytest.skip("conditional-test.yaml fixture not found")

        policy = load_policy(fixture_path)

        assert policy.schema_version == 12
        # Conditional rules are in the first phase
        assert policy.phases[0].conditional is not None
        assert len(policy.phases[0].conditional) == 4

        # Verify rule names
        rule_names = [r.name for r in policy.phases[0].conditional]
        assert "4K HEVC passthrough" in rule_names
        assert "Single audio track" in rule_names
        assert "Missing English audio" in rule_names
        assert "Default processing" in rule_names
