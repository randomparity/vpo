"""Unit tests for policy evaluation logic."""

from datetime import datetime
from pathlib import Path

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.evaluator import (
    NoTracksError,
    classify_track,
    compute_default_flags,
    compute_desired_order,
    evaluate_policy,
)
from video_policy_orchestrator.policy.matchers import CommentaryMatcher
from video_policy_orchestrator.policy.models import (
    ActionType,
    DefaultFlagsConfig,
    PolicySchema,
    TrackType,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def default_policy() -> PolicySchema:
    """Create a default policy for testing."""
    return PolicySchema(
        schema_version=1,
        track_order=(
            TrackType.VIDEO,
            TrackType.AUDIO_MAIN,
            TrackType.AUDIO_ALTERNATE,
            TrackType.SUBTITLE_MAIN,
            TrackType.SUBTITLE_FORCED,
            TrackType.AUDIO_COMMENTARY,
            TrackType.SUBTITLE_COMMENTARY,
            TrackType.ATTACHMENT,
        ),
        audio_language_preference=("eng", "und"),
        subtitle_language_preference=("eng", "und"),
        commentary_patterns=("commentary", "director"),
        default_flags=DefaultFlagsConfig(
            set_first_video_default=True,
            set_preferred_audio_default=True,
            set_preferred_subtitle_default=False,
            clear_other_defaults=True,
        ),
    )


@pytest.fixture
def japanese_policy() -> PolicySchema:
    """Create a Japanese-preferred policy for testing."""
    return PolicySchema(
        schema_version=1,
        audio_language_preference=("jpn", "eng", "und"),
        subtitle_language_preference=("eng", "und"),
        commentary_patterns=("commentary", "director"),
        default_flags=DefaultFlagsConfig(
            set_first_video_default=True,
            set_preferred_audio_default=True,
            set_preferred_subtitle_default=True,
            clear_other_defaults=True,
        ),
    )


@pytest.fixture
def matcher() -> CommentaryMatcher:
    """Create a commentary matcher for testing."""
    return CommentaryMatcher(("commentary", "director"))


# =============================================================================
# Track Classification Tests
# =============================================================================


class TestClassifyTrack:
    """Tests for track classification logic."""

    def test_video_track(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Video tracks should be classified as VIDEO."""
        track = TrackInfo(index=0, track_type="video", codec="hevc")
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.VIDEO

    def test_audio_main_preferred_language(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Audio with preferred language should be AUDIO_MAIN."""
        track = TrackInfo(index=1, track_type="audio", codec="aac", language="eng")
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.AUDIO_MAIN

    def test_audio_main_und_language(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Audio with 'und' language should be AUDIO_MAIN if in preference."""
        track = TrackInfo(index=1, track_type="audio", codec="aac", language="und")
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.AUDIO_MAIN

    def test_audio_alternate_non_preferred_language(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Audio with non-preferred language should be AUDIO_ALTERNATE."""
        track = TrackInfo(index=1, track_type="audio", codec="aac", language="fra")
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.AUDIO_ALTERNATE

    def test_audio_commentary_by_title(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Audio with commentary in title should be AUDIO_COMMENTARY."""
        track = TrackInfo(
            index=1,
            track_type="audio",
            codec="aac",
            language="eng",
            title="Director Commentary",
        )
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.AUDIO_COMMENTARY

    def test_subtitle_main(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Standard subtitle should be SUBTITLE_MAIN."""
        track = TrackInfo(
            index=2, track_type="subtitle", codec="subrip", language="eng"
        )
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.SUBTITLE_MAIN

    def test_subtitle_forced(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Forced subtitle should be SUBTITLE_FORCED."""
        track = TrackInfo(
            index=2,
            track_type="subtitle",
            codec="subrip",
            language="eng",
            is_forced=True,
        )
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.SUBTITLE_FORCED

    def test_subtitle_commentary(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Subtitle with commentary title should be SUBTITLE_COMMENTARY."""
        track = TrackInfo(
            index=2, track_type="subtitle", codec="subrip", title="Commentary Subtitles"
        )
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.SUBTITLE_COMMENTARY

    def test_attachment_track(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Attachment tracks should be classified as ATTACHMENT."""
        track = TrackInfo(index=3, track_type="attachment", codec="font/otf")
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.ATTACHMENT

    def test_unknown_track_type(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Unknown track types should default to ATTACHMENT."""
        track = TrackInfo(index=3, track_type="unknown", codec="data")
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.ATTACHMENT

    def test_audio_missing_language_treated_as_und(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Audio with missing language should be treated as 'und'."""
        track = TrackInfo(index=1, track_type="audio", codec="aac", language=None)
        result = classify_track(track, default_policy, matcher)
        assert result == TrackType.AUDIO_MAIN  # 'und' is in preference list


# =============================================================================
# Track Ordering Tests
# =============================================================================


class TestComputeDesiredOrder:
    """Tests for track ordering computation."""

    def test_empty_tracks(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Empty track list should return empty order."""
        result = compute_desired_order([], default_policy, matcher)
        assert result == []

    def test_single_video_track(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Single video track should remain at index 0."""
        tracks = [TrackInfo(index=0, track_type="video", codec="hevc")]
        result = compute_desired_order(tracks, default_policy, matcher)
        assert result == [0]

    def test_video_audio_subtitle_order(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Tracks should be ordered: video, audio, subtitle."""
        tracks = [
            TrackInfo(index=0, track_type="subtitle", codec="subrip", language="eng"),
            TrackInfo(index=1, track_type="video", codec="hevc"),
            TrackInfo(index=2, track_type="audio", codec="aac", language="eng"),
        ]
        result = compute_desired_order(tracks, default_policy, matcher)
        # Expected: video (1), audio_main (2), subtitle_main (0)
        assert result == [1, 2, 0]

    def test_commentary_at_end(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Commentary tracks should come after main tracks."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                title="Commentary",
            ),
            TrackInfo(index=2, track_type="audio", codec="aac", language="eng"),
        ]
        result = compute_desired_order(tracks, default_policy, matcher)
        # Expected: video (0), audio_main (2), audio_commentary (1)
        assert result == [0, 2, 1]

    def test_language_preference_ordering(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Audio tracks should be sorted by language preference."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="und"),
            TrackInfo(index=2, track_type="audio", codec="aac", language="eng"),
        ]
        result = compute_desired_order(tracks, default_policy, matcher)
        # Expected: video (0), eng audio (2), und audio (1)
        assert result == [0, 2, 1]

    def test_forced_subtitles_before_commentary(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Forced subtitles should come before commentary subtitles."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(
                index=1, track_type="subtitle", codec="subrip", title="Commentary Subs"
            ),
            TrackInfo(
                index=2,
                track_type="subtitle",
                codec="subrip",
                language="eng",
                is_forced=True,
            ),
            TrackInfo(index=3, track_type="subtitle", codec="subrip", language="eng"),
        ]
        result = compute_desired_order(tracks, default_policy, matcher)
        # Order: video (0), sub_main (3), sub_forced (2), sub_commentary (1)
        assert result == [0, 3, 2, 1]

    def test_attachments_at_end(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Attachment tracks should always come last."""
        tracks = [
            TrackInfo(index=0, track_type="attachment", codec="font/otf"),
            TrackInfo(index=1, track_type="video", codec="hevc"),
            TrackInfo(index=2, track_type="audio", codec="aac", language="eng"),
        ]
        result = compute_desired_order(tracks, default_policy, matcher)
        # Expected: video (1), audio_main (2), attachment (0)
        assert result == [1, 2, 0]


# =============================================================================
# Default Flag Tests
# =============================================================================


class TestComputeDefaultFlags:
    """Tests for default flag computation."""

    def test_first_video_gets_default(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """First video track should get default flag."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="video", codec="hevc"),
        ]
        result = compute_default_flags(tracks, default_policy, matcher)
        assert result[0] is True
        assert result[1] is False

    def test_preferred_audio_gets_default(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Preferred language audio should get default flag."""
        tracks = [
            TrackInfo(index=0, track_type="audio", codec="aac", language="fra"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="eng"),
        ]
        result = compute_default_flags(tracks, default_policy, matcher)
        assert result[0] is False
        assert result[1] is True

    def test_commentary_not_default(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Commentary tracks should not get default flag."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="audio",
                codec="aac",
                language="eng",
                title="Commentary",
            ),
            TrackInfo(index=1, track_type="audio", codec="aac", language="fra"),
        ]
        result = compute_default_flags(tracks, default_policy, matcher)
        # Commentary skipped, French audio is next best
        assert result[0] is False
        assert result[1] is True

    def test_all_commentary_falls_back_to_first(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """If all audio is commentary, fall back to first track."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="audio",
                codec="aac",
                language="eng",
                title="Commentary 1",
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                title="Director Commentary",
            ),
        ]
        result = compute_default_flags(tracks, default_policy, matcher)
        assert result[0] is True
        assert result[1] is False

    def test_subtitle_default_not_set_by_default_policy(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Subtitles should not get default flag with default policy."""
        tracks = [
            TrackInfo(index=0, track_type="subtitle", codec="subrip", language="eng"),
        ]
        result = compute_default_flags(tracks, default_policy, matcher)
        # set_preferred_subtitle_default is False in default policy
        assert result[0] is False

    def test_subtitle_default_set_when_enabled(
        self, japanese_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """Subtitles should get default flag when enabled in policy."""
        tracks = [
            TrackInfo(index=0, track_type="subtitle", codec="subrip", language="eng"),
            TrackInfo(index=1, track_type="subtitle", codec="subrip", language="fra"),
        ]
        result = compute_default_flags(tracks, japanese_policy, matcher)
        assert result[0] is True
        assert result[1] is False

    def test_no_audio_tracks_skips_audio_defaults(
        self, default_policy: PolicySchema, matcher: CommentaryMatcher
    ):
        """No audio tracks should not cause errors."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="subtitle", codec="subrip", language="eng"),
        ]
        result = compute_default_flags(tracks, default_policy, matcher)
        assert result[0] is True  # Video gets default
        assert result[1] is False  # Subtitle cleared

    def test_subtitle_default_when_audio_language_differs(
        self, matcher: CommentaryMatcher
    ):
        """English subtitle gets default when audio is German and English preferred."""
        policy = PolicySchema(
            schema_version=1,
            audio_language_preference=("eng", "und"),
            subtitle_language_preference=("eng", "und"),
            commentary_patterns=("commentary", "director"),
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                set_preferred_subtitle_default=False,
                clear_other_defaults=True,
                set_subtitle_default_when_audio_differs=True,
            ),
        )
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="deu"),
            TrackInfo(index=2, track_type="subtitle", codec="subrip", language="eng"),
            TrackInfo(index=3, track_type="subtitle", codec="subrip", language="deu"),
        ]
        result = compute_default_flags(tracks, policy, matcher)
        assert result[0] is True  # Video gets default
        assert result[1] is True  # Audio gets default (only audio)
        assert result[2] is True  # English subtitle gets default
        assert result[3] is False  # German subtitle cleared

    def test_subtitle_default_when_audio_matches(self, matcher: CommentaryMatcher):
        """No subtitle default when audio matches preferred language."""
        policy = PolicySchema(
            schema_version=1,
            audio_language_preference=("eng", "und"),
            subtitle_language_preference=("eng", "und"),
            commentary_patterns=("commentary", "director"),
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                set_preferred_subtitle_default=False,
                clear_other_defaults=True,
                set_subtitle_default_when_audio_differs=True,
            ),
        )
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="eng"),
            TrackInfo(index=2, track_type="subtitle", codec="subrip", language="eng"),
        ]
        result = compute_default_flags(tracks, policy, matcher)
        assert result[0] is True  # Video gets default
        assert result[1] is True  # Audio gets default
        assert result[2] is False  # Subtitle does NOT get default

    def test_subtitle_default_when_audio_undefined(self, matcher: CommentaryMatcher):
        """Subtitle gets default when audio language is undefined."""
        policy = PolicySchema(
            schema_version=1,
            audio_language_preference=("eng",),  # Note: 'und' NOT in preference
            subtitle_language_preference=("eng", "und"),
            commentary_patterns=("commentary", "director"),
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                set_preferred_subtitle_default=False,
                clear_other_defaults=True,
                set_subtitle_default_when_audio_differs=True,
            ),
        )
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="und"),
            TrackInfo(index=2, track_type="subtitle", codec="subrip", language="eng"),
        ]
        result = compute_default_flags(tracks, policy, matcher)
        assert result[0] is True  # Video gets default
        assert result[1] is True  # Audio gets default (only audio)
        assert result[2] is True  # Subtitle gets default (audio lang doesn't match)

    def test_subtitle_default_when_only_commentary_audio(
        self, matcher: CommentaryMatcher
    ):
        """Subtitle gets default when only commentary audio exists."""
        policy = PolicySchema(
            schema_version=1,
            audio_language_preference=("eng", "und"),
            subtitle_language_preference=("eng", "und"),
            commentary_patterns=("commentary", "director"),
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                set_preferred_subtitle_default=False,
                clear_other_defaults=True,
                set_subtitle_default_when_audio_differs=True,
            ),
        )
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                title="Director Commentary",
            ),
            TrackInfo(index=2, track_type="subtitle", codec="subrip", language="eng"),
        ]
        result = compute_default_flags(tracks, policy, matcher)
        assert result[0] is True  # Video gets default
        assert result[1] is True  # Commentary audio gets default (only audio)
        assert result[2] is True  # Subtitle gets default (no main audio)

    def test_subtitle_default_when_no_audio(self, matcher: CommentaryMatcher):
        """Subtitle gets default when no audio tracks exist."""
        policy = PolicySchema(
            schema_version=1,
            audio_language_preference=("eng", "und"),
            subtitle_language_preference=("eng", "und"),
            commentary_patterns=("commentary", "director"),
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                set_preferred_subtitle_default=False,
                clear_other_defaults=True,
                set_subtitle_default_when_audio_differs=True,
            ),
        )
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="subtitle", codec="subrip", language="eng"),
        ]
        result = compute_default_flags(tracks, policy, matcher)
        assert result[0] is True  # Video gets default
        assert result[1] is True  # Subtitle gets default (no audio)

    def test_subtitle_default_disabled_by_config(self, matcher: CommentaryMatcher):
        """No subtitle default when feature is disabled, regardless of audio."""
        policy = PolicySchema(
            schema_version=1,
            audio_language_preference=("eng", "und"),
            subtitle_language_preference=("eng", "und"),
            commentary_patterns=("commentary", "director"),
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                set_preferred_subtitle_default=False,
                clear_other_defaults=True,
                set_subtitle_default_when_audio_differs=False,  # Feature disabled
            ),
        )
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="deu"),
            TrackInfo(index=2, track_type="subtitle", codec="subrip", language="eng"),
        ]
        result = compute_default_flags(tracks, policy, matcher)
        assert result[0] is True  # Video gets default
        assert result[1] is True  # Audio gets default (only audio)
        assert result[2] is False  # Subtitle does NOT get default (feature disabled)


# =============================================================================
# Full Evaluation Tests
# =============================================================================


class TestEvaluatePolicy:
    """Tests for full policy evaluation."""

    def test_no_tracks_raises_error(self, default_policy: PolicySchema):
        """Evaluating with no tracks should raise NoTracksError."""
        with pytest.raises(NoTracksError):
            evaluate_policy(
                file_id="test-id",
                file_path=Path("/test/file.mkv"),
                container="mkv",
                tracks=[],
                policy=default_policy,
            )

    def test_already_compliant_returns_empty_plan(self, default_policy: PolicySchema):
        """File already matching policy should return empty plan."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc", is_default=True),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=True,
            ),
            TrackInfo(
                index=2,
                track_type="subtitle",
                codec="subrip",
                language="eng",
                is_default=False,
            ),
        ]
        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=tracks,
            policy=default_policy,
        )
        assert plan.is_empty
        assert plan.summary == "No changes required"

    def test_reorder_action_generated(self, default_policy: PolicySchema):
        """Reorder action should be generated when tracks are out of order."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="subtitle",
                codec="subrip",
                language="eng",
                is_default=False,
            ),
            TrackInfo(index=1, track_type="video", codec="hevc", is_default=True),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=True,
            ),
        ]
        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=tracks,
            policy=default_policy,
        )
        assert plan.requires_remux
        reorder_actions = [
            a for a in plan.actions if a.action_type == ActionType.REORDER
        ]
        assert len(reorder_actions) == 1
        assert reorder_actions[0].desired_value == [1, 2, 0]

    def test_reorder_not_generated_for_non_mkv(self, default_policy: PolicySchema):
        """Reorder action should NOT be generated for non-MKV containers."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="subtitle",
                codec="subrip",
                language="eng",
                is_default=False,
            ),
            TrackInfo(index=1, track_type="video", codec="hevc", is_default=True),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=True,
            ),
        ]
        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/file.mp4"),
            container="mp4",
            tracks=tracks,
            policy=default_policy,
        )
        # MP4 doesn't support reordering, so no REORDER action
        assert not plan.requires_remux
        reorder_actions = [
            a for a in plan.actions if a.action_type == ActionType.REORDER
        ]
        assert len(reorder_actions) == 0

    def test_set_default_action_generated(self, default_policy: PolicySchema):
        """SET_DEFAULT action should be generated when default flag needs changing."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc", is_default=False),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=False,
            ),
        ]
        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=tracks,
            policy=default_policy,
        )
        set_default_actions = [
            a for a in plan.actions if a.action_type == ActionType.SET_DEFAULT
        ]
        assert len(set_default_actions) == 2  # Video and audio

    def test_clear_default_action_generated(self, default_policy: PolicySchema):
        """CLEAR_DEFAULT action should be generated for non-preferred tracks."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="hevc", is_default=True),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=True,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="fra",
                is_default=True,
            ),
        ]
        plan = evaluate_policy(
            file_id="test-id",
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=tracks,
            policy=default_policy,
        )
        clear_default_actions = [
            a for a in plan.actions if a.action_type == ActionType.CLEAR_DEFAULT
        ]
        assert len(clear_default_actions) == 1  # French audio should be cleared

    def test_plan_metadata(self, default_policy: PolicySchema):
        """Plan should contain correct metadata."""
        tracks = [TrackInfo(index=0, track_type="video", codec="hevc", is_default=True)]
        plan = evaluate_policy(
            file_id="test-file-id",
            file_path=Path("/test/file.mkv"),
            container="mkv",
            tracks=tracks,
            policy=default_policy,
        )
        assert plan.file_id == "test-file-id"
        assert plan.file_path == Path("/test/file.mkv")
        assert plan.policy_version == 1
        assert isinstance(plan.created_at, datetime)
