"""Tests for condition evaluation.

Tests for User Story 2: Track Existence Conditions (Priority: P1)
Check whether specific tracks exist before taking action.

Tests for User Story 3: Boolean Operators (Priority: P2)
Combine conditions with AND/OR/NOT logic.

Tests for User Story 4: Comparison Operators (Priority: P2)
Compare numeric track properties with thresholds.

Tests for User Story 5: Track Count Conditions (Priority: P2)
Check count of matching tracks against thresholds.
"""

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.conditions import (
    evaluate_condition,
    evaluate_count,
    evaluate_exists,
    matches_track,
)
from video_policy_orchestrator.policy.models import (
    AndCondition,
    Comparison,
    ComparisonOperator,
    CountCondition,
    ExistsCondition,
    NotCondition,
    OrCondition,
    TitleMatch,
    TrackFilters,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def video_track_1080p() -> TrackInfo:
    """A 1080p HEVC video track."""
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
def audio_track_eng_stereo() -> TrackInfo:
    """An English stereo AAC audio track."""
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
def audio_track_eng_surround() -> TrackInfo:
    """An English 5.1 AC3 audio track."""
    return TrackInfo(
        index=2,
        track_type="audio",
        codec="ac3",
        language="eng",
        title="English 5.1",
        is_default=False,
        is_forced=False,
        channels=6,
        channel_layout="5.1(side)",
        width=None,
        height=None,
        frame_rate=None,
    )


@pytest.fixture
def audio_track_jpn() -> TrackInfo:
    """A Japanese stereo AAC audio track."""
    return TrackInfo(
        index=3,
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
def audio_track_commentary() -> TrackInfo:
    """A commentary audio track."""
    return TrackInfo(
        index=4,
        track_type="audio",
        codec="aac",
        language="eng",
        title="Director's Commentary",
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
    """An English SRT subtitle track."""
    return TrackInfo(
        index=5,
        track_type="subtitle",
        codec="subrip",
        language="eng",
        title="English",
        is_default=False,
        is_forced=False,
        channels=None,
        channel_layout=None,
        width=None,
        height=None,
        frame_rate=None,
    )


@pytest.fixture
def subtitle_track_eng_forced() -> TrackInfo:
    """An English forced subtitle track."""
    return TrackInfo(
        index=6,
        track_type="subtitle",
        codec="subrip",
        language="eng",
        title="English Forced",
        is_default=False,
        is_forced=True,
        channels=None,
        channel_layout=None,
        width=None,
        height=None,
        frame_rate=None,
    )


@pytest.fixture
def basic_tracks(
    video_track_1080p: TrackInfo,
    audio_track_eng_stereo: TrackInfo,
    subtitle_track_eng: TrackInfo,
) -> list[TrackInfo]:
    """Basic track set: 1080p video, English stereo audio, English subtitle."""
    return [video_track_1080p, audio_track_eng_stereo, subtitle_track_eng]


@pytest.fixture
def multi_audio_tracks(
    video_track_1080p: TrackInfo,
    audio_track_eng_stereo: TrackInfo,
    audio_track_eng_surround: TrackInfo,
    audio_track_jpn: TrackInfo,
    audio_track_commentary: TrackInfo,
    subtitle_track_eng: TrackInfo,
) -> list[TrackInfo]:
    """Track set with multiple audio tracks."""
    return [
        video_track_1080p,
        audio_track_eng_stereo,
        audio_track_eng_surround,
        audio_track_jpn,
        audio_track_commentary,
        subtitle_track_eng,
    ]


# =============================================================================
# T039: Test fixtures (verified by usage)
# T040: Test exists condition matching track
# =============================================================================


class TestExistsConditionMatching:
    """Test exists condition matching behavior."""

    def test_exists_matches_video_track(self, basic_tracks: list[TrackInfo]) -> None:
        """Exists condition returns True when track exists."""
        condition = ExistsCondition(
            track_type="video",
            filters=TrackFilters(),
        )

        result, reason = evaluate_exists(condition, basic_tracks)

        assert result is True
        assert "True" in reason
        assert "track[0]" in reason

    def test_exists_matches_audio_track_by_language(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """Exists condition matches audio track by language."""
        condition = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(language="eng"),
        )

        result, reason = evaluate_exists(condition, basic_tracks)

        assert result is True
        assert "eng" in reason

    def test_exists_matches_audio_with_multiple_languages(
        self, multi_audio_tracks: list[TrackInfo]
    ) -> None:
        """Exists condition matches when any language in list matches."""
        condition = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(language=("jpn", "kor")),
        )

        result, reason = evaluate_exists(condition, multi_audio_tracks)

        assert result is True


# =============================================================================
# T041: Test exists condition not matching
# =============================================================================


class TestExistsConditionNotMatching:
    """Test exists condition when nothing matches."""

    def test_exists_no_match_wrong_track_type(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """Exists returns False when track type doesn't exist."""
        condition = ExistsCondition(
            track_type="attachment",
            filters=TrackFilters(),
        )

        result, reason = evaluate_exists(condition, basic_tracks)

        assert result is False
        assert "False" in reason

    def test_exists_no_match_wrong_language(
        self, basic_tracks: list[TrackInfo]
    ) -> None:
        """Exists returns False when language doesn't match."""
        condition = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(language="fra"),
        )

        result, reason = evaluate_exists(condition, basic_tracks)

        assert result is False

    def test_exists_no_match_wrong_codec(self, basic_tracks: list[TrackInfo]) -> None:
        """Exists returns False when codec doesn't match."""
        condition = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(codec="truehd"),
        )

        result, reason = evaluate_exists(condition, basic_tracks)

        assert result is False


# =============================================================================
# T042: Test exists with multiple filter criteria
# =============================================================================


class TestExistsMultipleCriteria:
    """Test exists condition with multiple filter criteria."""

    def test_exists_multiple_criteria_all_match(
        self, multi_audio_tracks: list[TrackInfo]
    ) -> None:
        """Exists returns True when all criteria match."""
        condition = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(
                language="eng",
                codec="ac3",
                channels=6,
            ),
        )

        result, reason = evaluate_exists(condition, multi_audio_tracks)

        assert result is True

    def test_exists_multiple_criteria_partial_match_fails(
        self, multi_audio_tracks: list[TrackInfo]
    ) -> None:
        """Exists returns False when only some criteria match."""
        # Looking for English AAC with 6 channels - doesn't exist
        condition = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(
                language="eng",
                codec="aac",
                channels=6,
            ),
        )

        result, reason = evaluate_exists(condition, multi_audio_tracks)

        assert result is False

    def test_exists_is_default_filter(
        self, multi_audio_tracks: list[TrackInfo]
    ) -> None:
        """Exists can filter by is_default flag."""
        # Default audio track
        condition = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(is_default=True),
        )

        result, reason = evaluate_exists(condition, multi_audio_tracks)

        assert result is True

    def test_exists_is_forced_filter(
        self, subtitle_track_eng_forced: TrackInfo
    ) -> None:
        """Exists can filter by is_forced flag."""
        tracks = [subtitle_track_eng_forced]

        condition = ExistsCondition(
            track_type="subtitle",
            filters=TrackFilters(is_forced=True),
        )

        result, reason = evaluate_exists(condition, tracks)

        assert result is True

    def test_exists_is_forced_false_filter(self, subtitle_track_eng: TrackInfo) -> None:
        """Exists can filter for non-forced tracks."""
        tracks = [subtitle_track_eng]

        condition = ExistsCondition(
            track_type="subtitle",
            filters=TrackFilters(is_forced=False),
        )

        result, reason = evaluate_exists(condition, tracks)

        assert result is True


# =============================================================================
# T042a: Test title filter with contains matching
# =============================================================================


class TestTitleContainsMatching:
    """Test title matching with contains."""

    def test_title_contains_match(self, audio_track_commentary: TrackInfo) -> None:
        """Title contains filter matches substring."""
        filters = TrackFilters(title="Commentary")

        result = matches_track(audio_track_commentary, filters)

        assert result is True

    def test_title_contains_case_insensitive(
        self, audio_track_commentary: TrackInfo
    ) -> None:
        """Title contains match is case-insensitive."""
        filters = TrackFilters(title="commentary")

        result = matches_track(audio_track_commentary, filters)

        assert result is True

    def test_title_contains_no_match(self, audio_track_eng_stereo: TrackInfo) -> None:
        """Title contains filter doesn't match when substring not present."""
        filters = TrackFilters(title="Commentary")

        result = matches_track(audio_track_eng_stereo, filters)

        assert result is False

    def test_title_contains_with_title_match_object(
        self, audio_track_commentary: TrackInfo
    ) -> None:
        """Title filter works with TitleMatch object using contains."""
        filters = TrackFilters(title=TitleMatch(contains="Director"))

        result = matches_track(audio_track_commentary, filters)

        assert result is True


# =============================================================================
# T042b: Test title filter with regex matching
# =============================================================================


class TestTitleRegexMatching:
    """Test title matching with regex."""

    def test_title_regex_match(self, audio_track_commentary: TrackInfo) -> None:
        """Title regex filter matches pattern."""
        filters = TrackFilters(title=TitleMatch(regex=r"Director.*Commentary"))

        result = matches_track(audio_track_commentary, filters)

        assert result is True

    def test_title_regex_case_insensitive(
        self, audio_track_commentary: TrackInfo
    ) -> None:
        """Title regex match is case-insensitive."""
        filters = TrackFilters(title=TitleMatch(regex=r"director.*commentary"))

        result = matches_track(audio_track_commentary, filters)

        assert result is True

    def test_title_regex_no_match(self, audio_track_eng_stereo: TrackInfo) -> None:
        """Title regex filter doesn't match when pattern not found."""
        filters = TrackFilters(title=TitleMatch(regex=r"Commentary"))

        result = matches_track(audio_track_eng_stereo, filters)

        assert result is False

    def test_title_regex_digit_pattern(
        self, audio_track_eng_surround: TrackInfo
    ) -> None:
        """Title regex can match digit patterns."""
        filters = TrackFilters(title=TitleMatch(regex=r"\d\.\d"))

        result = matches_track(audio_track_eng_surround, filters)

        assert result is True  # "English 5.1" matches \d\.\d


# =============================================================================
# T049-T052: Boolean operator tests (AND)
# =============================================================================


class TestAndCondition:
    """Test AND condition combining multiple conditions."""

    def test_and_all_true(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """AND returns True when all conditions are true."""
        condition = AndCondition(
            conditions=(
                ExistsCondition(track_type="video", filters=TrackFilters()),
                ExistsCondition(track_type="audio", filters=TrackFilters()),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True
        assert "and" in reason.lower()

    def test_and_one_false(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """AND returns False when any condition is false."""
        condition = AndCondition(
            conditions=(
                ExistsCondition(track_type="video", filters=TrackFilters()),
                ExistsCondition(track_type="attachment", filters=TrackFilters()),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is False

    def test_and_all_false(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """AND returns False when all conditions are false."""
        condition = AndCondition(
            conditions=(
                ExistsCondition(track_type="attachment", filters=TrackFilters()),
                ExistsCondition(
                    track_type="audio", filters=TrackFilters(language="kor")
                ),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is False

    def test_and_short_circuit(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """AND short-circuits on first False."""
        # First condition is false, so second should not be evaluated
        condition = AndCondition(
            conditions=(
                ExistsCondition(track_type="attachment", filters=TrackFilters()),
                ExistsCondition(track_type="video", filters=TrackFilters()),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is False
        assert "attachment" in reason.lower()


# =============================================================================
# T053-T054: Boolean operator tests (OR)
# =============================================================================


class TestOrCondition:
    """Test OR condition combining multiple conditions."""

    def test_or_one_true(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """OR returns True when any condition is true."""
        condition = OrCondition(
            conditions=(
                ExistsCondition(track_type="attachment", filters=TrackFilters()),
                ExistsCondition(track_type="video", filters=TrackFilters()),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True

    def test_or_all_true(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """OR returns True when all conditions are true."""
        condition = OrCondition(
            conditions=(
                ExistsCondition(track_type="video", filters=TrackFilters()),
                ExistsCondition(track_type="audio", filters=TrackFilters()),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True

    def test_or_all_false(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """OR returns False when all conditions are false."""
        condition = OrCondition(
            conditions=(
                ExistsCondition(track_type="attachment", filters=TrackFilters()),
                ExistsCondition(
                    track_type="audio", filters=TrackFilters(language="kor")
                ),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is False

    def test_or_short_circuit(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """OR short-circuits on first True."""
        condition = OrCondition(
            conditions=(
                ExistsCondition(track_type="video", filters=TrackFilters()),
                ExistsCondition(track_type="attachment", filters=TrackFilters()),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True
        assert "video" in reason.lower()


# =============================================================================
# T055-T056: Boolean operator tests (NOT)
# =============================================================================


class TestNotCondition:
    """Test NOT condition negating a condition."""

    def test_not_negates_true(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """NOT returns False when inner condition is True."""
        condition = NotCondition(
            inner=ExistsCondition(track_type="video", filters=TrackFilters())
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is False
        assert "not" in reason.lower()

    def test_not_negates_false(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """NOT returns True when inner condition is False."""
        condition = NotCondition(
            inner=ExistsCondition(track_type="attachment", filters=TrackFilters())
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True

    def test_double_not(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """Double NOT returns original value."""
        condition = NotCondition(
            inner=NotCondition(
                inner=ExistsCondition(track_type="video", filters=TrackFilters())
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True


# =============================================================================
# T057-T059: Nested boolean conditions
# =============================================================================


class TestNestedBooleanConditions:
    """Test complex nested boolean conditions."""

    def test_and_inside_or(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """OR containing AND conditions."""
        condition = OrCondition(
            conditions=(
                # This AND is false (no attachment)
                AndCondition(
                    conditions=(
                        ExistsCondition(
                            track_type="attachment", filters=TrackFilters()
                        ),
                        ExistsCondition(track_type="video", filters=TrackFilters()),
                    )
                ),
                # This AND is true
                AndCondition(
                    conditions=(
                        ExistsCondition(track_type="audio", filters=TrackFilters()),
                        ExistsCondition(track_type="video", filters=TrackFilters()),
                    )
                ),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True

    def test_not_inside_and(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """AND containing NOT condition."""
        condition = AndCondition(
            conditions=(
                ExistsCondition(track_type="video", filters=TrackFilters()),
                NotCondition(
                    inner=ExistsCondition(
                        track_type="attachment", filters=TrackFilters()
                    )
                ),
            )
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True  # Video exists AND no attachment


# =============================================================================
# T060-T067: Comparison operator tests
# =============================================================================


class TestComparisonOperators:
    """Test numeric comparison operators."""

    def test_height_gte_matches(self, video_track_4k: TrackInfo) -> None:
        """Height GTE comparison matches."""
        filters = TrackFilters(
            height=Comparison(operator=ComparisonOperator.GTE, value=2160)
        )

        result = matches_track(video_track_4k, filters)

        assert result is True

    def test_height_gte_fails(self, video_track_1080p: TrackInfo) -> None:
        """Height GTE comparison fails when below threshold."""
        filters = TrackFilters(
            height=Comparison(operator=ComparisonOperator.GTE, value=2160)
        )

        result = matches_track(video_track_1080p, filters)

        assert result is False

    def test_height_lt_matches(self, video_track_1080p: TrackInfo) -> None:
        """Height LT comparison matches when below threshold."""
        filters = TrackFilters(
            height=Comparison(operator=ComparisonOperator.LT, value=2160)
        )

        result = matches_track(video_track_1080p, filters)

        assert result is True

    def test_channels_eq_matches(self, audio_track_eng_surround: TrackInfo) -> None:
        """Channels EQ comparison matches exact value."""
        filters = TrackFilters(
            channels=Comparison(operator=ComparisonOperator.EQ, value=6)
        )

        result = matches_track(audio_track_eng_surround, filters)

        assert result is True

    def test_channels_gt_matches(self, audio_track_eng_surround: TrackInfo) -> None:
        """Channels GT comparison matches when above threshold."""
        filters = TrackFilters(
            channels=Comparison(operator=ComparisonOperator.GT, value=2)
        )

        result = matches_track(audio_track_eng_surround, filters)

        assert result is True

    def test_channels_lte_matches(self, audio_track_eng_stereo: TrackInfo) -> None:
        """Channels LTE comparison matches when equal to threshold."""
        filters = TrackFilters(
            channels=Comparison(operator=ComparisonOperator.LTE, value=2)
        )

        result = matches_track(audio_track_eng_stereo, filters)

        assert result is True

    def test_width_comparison_in_exists(self, video_track_4k: TrackInfo) -> None:
        """Width comparison works in exists condition."""
        condition = ExistsCondition(
            track_type="video",
            filters=TrackFilters(
                width=Comparison(operator=ComparisonOperator.GTE, value=3840)
            ),
        )

        result, reason = evaluate_exists(condition, [video_track_4k])

        assert result is True

    def test_exact_integer_value_comparison(
        self, audio_track_eng_stereo: TrackInfo
    ) -> None:
        """Direct integer filter value works as equality check."""
        filters = TrackFilters(channels=2)

        result = matches_track(audio_track_eng_stereo, filters)

        assert result is True


# =============================================================================
# T068-T074: Count condition tests
# =============================================================================


class TestCountCondition:
    """Test count condition comparing track counts."""

    def test_count_eq_matches(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """Count EQ matches exact count."""
        # Should have exactly 4 audio tracks
        condition = CountCondition(
            track_type="audio",
            filters=TrackFilters(),
            operator=ComparisonOperator.EQ,
            value=4,
        )

        result, reason = evaluate_count(condition, multi_audio_tracks)

        assert result is True
        assert "count=4" in reason

    def test_count_gt_matches(self, multi_audio_tracks: list[TrackInfo]) -> None:
        """Count GT matches when count exceeds threshold."""
        condition = CountCondition(
            track_type="audio",
            filters=TrackFilters(),
            operator=ComparisonOperator.GT,
            value=2,
        )

        result, reason = evaluate_count(condition, multi_audio_tracks)

        assert result is True

    def test_count_lt_matches(self, basic_tracks: list[TrackInfo]) -> None:
        """Count LT matches when count is below threshold."""
        condition = CountCondition(
            track_type="audio",
            filters=TrackFilters(),
            operator=ComparisonOperator.LT,
            value=3,
        )

        result, reason = evaluate_count(condition, basic_tracks)

        assert result is True

    def test_count_with_language_filter(
        self, multi_audio_tracks: list[TrackInfo]
    ) -> None:
        """Count can filter by language."""
        # Count English audio tracks (should be 3: stereo, surround, commentary)
        condition = CountCondition(
            track_type="audio",
            filters=TrackFilters(language="eng"),
            operator=ComparisonOperator.EQ,
            value=3,
        )

        result, reason = evaluate_count(condition, multi_audio_tracks)

        assert result is True

    def test_count_zero_matches(self, basic_tracks: list[TrackInfo]) -> None:
        """Count EQ 0 matches when no tracks of type exist."""
        condition = CountCondition(
            track_type="attachment",
            filters=TrackFilters(),
            operator=ComparisonOperator.EQ,
            value=0,
        )

        result, reason = evaluate_count(condition, basic_tracks)

        assert result is True

    def test_count_gte_with_complex_filter(
        self, multi_audio_tracks: list[TrackInfo]
    ) -> None:
        """Count GTE with multiple filter criteria."""
        # Count audio tracks with channels > 2
        condition = CountCondition(
            track_type="audio",
            filters=TrackFilters(
                channels=Comparison(operator=ComparisonOperator.GT, value=2)
            ),
            operator=ComparisonOperator.GTE,
            value=1,
        )

        result, reason = evaluate_count(condition, multi_audio_tracks)

        assert result is True

    def test_count_via_evaluate_condition(
        self, multi_audio_tracks: list[TrackInfo]
    ) -> None:
        """Count condition works through evaluate_condition()."""
        condition = CountCondition(
            track_type="subtitle",
            filters=TrackFilters(),
            operator=ComparisonOperator.GTE,
            value=1,
        )

        result, reason = evaluate_condition(condition, multi_audio_tracks)

        assert result is True
