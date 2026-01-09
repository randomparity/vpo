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

from typing import TYPE_CHECKING

import pytest

from vpo.db.models import TrackInfo

if TYPE_CHECKING:
    from vpo.language_analysis.models import (
        LanguageAnalysisResult,
    )

from vpo.policy.conditions import (
    evaluate_condition,
    evaluate_count,
    evaluate_exists,
    matches_track,
)
from vpo.policy.types import (
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


# =============================================================================
# Audio Multi-Language Condition Tests
# =============================================================================


class TestAudioIsMultiLanguageCondition:
    """Test audio_is_multi_language condition evaluation."""

    @pytest.fixture
    def audio_track_with_id(self) -> TrackInfo:
        """Audio track with database ID for language analysis lookup."""
        return TrackInfo(
            id=100,
            index=1,
            track_type="audio",
            codec="aac",
            language="eng",
            title="Main Audio",
            is_default=True,
            is_forced=False,
            channels=2,
            channel_layout="stereo",
            width=None,
            height=None,
            frame_rate=None,
        )

    @pytest.fixture
    def multi_language_result(self) -> "LanguageAnalysisResult":
        """Language analysis result showing multi-language content."""
        from datetime import datetime, timezone

        from vpo.language_analysis.models import (
            AnalysisMetadata,
            LanguageAnalysisResult,
            LanguageClassification,
            LanguagePercentage,
            LanguageSegment,
        )

        now = datetime.now(timezone.utc)
        return LanguageAnalysisResult(
            track_id=100,
            file_hash="test_hash",  # pragma: allowlist secret
            primary_language="eng",
            primary_percentage=0.8,
            secondary_languages=(LanguagePercentage("spa", 0.2),),
            classification=LanguageClassification.MULTI_LANGUAGE,
            segments=(
                LanguageSegment("eng", 0.0, 30.0, 0.95),
                LanguageSegment("spa", 30.0, 60.0, 0.88),
            ),
            metadata=AnalysisMetadata(
                plugin_name="whisper-local",
                plugin_version="1.0.0",
                model_name="whisper-base",
                sample_positions=(0.0, 30.0),
                sample_duration=30.0,
                total_duration=60.0,
                speech_ratio=0.9,
            ),
            created_at=now,
            updated_at=now,
        )

    @pytest.fixture
    def single_language_result(self) -> "LanguageAnalysisResult":
        """Language analysis result showing single language content."""
        from datetime import datetime, timezone

        from vpo.language_analysis.models import (
            AnalysisMetadata,
            LanguageAnalysisResult,
            LanguageClassification,
            LanguageSegment,
        )

        now = datetime.now(timezone.utc)
        return LanguageAnalysisResult(
            track_id=100,
            file_hash="test_hash",  # pragma: allowlist secret
            primary_language="eng",
            primary_percentage=1.0,
            secondary_languages=(),
            classification=LanguageClassification.SINGLE_LANGUAGE,
            segments=(LanguageSegment("eng", 0.0, 60.0, 0.98),),
            metadata=AnalysisMetadata(
                plugin_name="whisper-local",
                plugin_version="1.0.0",
                model_name="whisper-base",
                sample_positions=(0.0, 30.0),
                sample_duration=30.0,
                total_duration=60.0,
                speech_ratio=0.95,
            ),
            created_at=now,
            updated_at=now,
        )

    def test_returns_false_when_no_language_results(
        self, audio_track_with_id: TrackInfo
    ) -> None:
        """Condition returns False when no language analysis available."""
        from vpo.policy.conditions import (
            evaluate_audio_is_multi_language,
        )
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        condition = AudioIsMultiLanguageCondition()
        tracks = [audio_track_with_id]

        result, reason = evaluate_audio_is_multi_language(
            condition, tracks, language_results=None
        )

        assert result is False
        assert "no language analysis available" in reason

    def test_returns_true_for_multi_language_track(
        self,
        audio_track_with_id: TrackInfo,
        multi_language_result: "LanguageAnalysisResult",
    ) -> None:
        """Condition returns True when track has multi-language content."""
        from vpo.policy.conditions import (
            evaluate_audio_is_multi_language,
        )
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        condition = AudioIsMultiLanguageCondition()
        tracks = [audio_track_with_id]
        language_results = {100: multi_language_result}

        result, reason = evaluate_audio_is_multi_language(
            condition, tracks, language_results
        )

        assert result is True
        assert "audio_is_multi_language → True" in reason
        assert "eng" in reason

    def test_returns_false_for_single_language_track(
        self,
        audio_track_with_id: TrackInfo,
        single_language_result: "LanguageAnalysisResult",
    ) -> None:
        """Condition returns False when track has single language content."""
        from vpo.policy.conditions import (
            evaluate_audio_is_multi_language,
        )
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        condition = AudioIsMultiLanguageCondition()
        tracks = [audio_track_with_id]
        language_results = {100: single_language_result}

        result, reason = evaluate_audio_is_multi_language(
            condition, tracks, language_results
        )

        assert result is False
        assert "audio_is_multi_language → False" in reason

    def test_threshold_filters_low_secondary(
        self,
        audio_track_with_id: TrackInfo,
    ) -> None:
        """Condition returns False when secondary language below threshold."""
        from datetime import datetime, timezone

        from vpo.language_analysis.models import (
            AnalysisMetadata,
            LanguageAnalysisResult,
            LanguageClassification,
            LanguagePercentage,
            LanguageSegment,
        )
        from vpo.policy.conditions import (
            evaluate_audio_is_multi_language,
        )
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        now = datetime.now(timezone.utc)
        # Only 3% secondary language (below 5% default threshold)
        result_with_low_secondary = LanguageAnalysisResult(
            track_id=100,
            file_hash="test_hash",  # pragma: allowlist secret
            primary_language="eng",
            primary_percentage=0.97,
            secondary_languages=(LanguagePercentage("spa", 0.03),),
            classification=LanguageClassification.MULTI_LANGUAGE,
            segments=(
                LanguageSegment("eng", 0.0, 58.0, 0.95),
                LanguageSegment("spa", 58.0, 60.0, 0.88),
            ),
            metadata=AnalysisMetadata(
                plugin_name="whisper-local",
                plugin_version="1.0.0",
                model_name="whisper-base",
                sample_positions=(0.0, 30.0),
                sample_duration=30.0,
                total_duration=60.0,
                speech_ratio=0.9,
            ),
            created_at=now,
            updated_at=now,
        )

        condition = AudioIsMultiLanguageCondition(threshold=0.05)
        tracks = [audio_track_with_id]
        language_results = {100: result_with_low_secondary}

        result, reason = evaluate_audio_is_multi_language(
            condition, tracks, language_results
        )

        assert result is False

    def test_primary_language_filter_matches(
        self,
        audio_track_with_id: TrackInfo,
        multi_language_result: "LanguageAnalysisResult",
    ) -> None:
        """Condition matches when primary language filter matches."""
        from vpo.policy.conditions import (
            evaluate_audio_is_multi_language,
        )
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        condition = AudioIsMultiLanguageCondition(primary_language="eng")
        tracks = [audio_track_with_id]
        language_results = {100: multi_language_result}

        result, reason = evaluate_audio_is_multi_language(
            condition, tracks, language_results
        )

        assert result is True

    def test_primary_language_filter_no_match(
        self,
        audio_track_with_id: TrackInfo,
        multi_language_result: "LanguageAnalysisResult",
    ) -> None:
        """Condition returns False when primary language filter doesn't match."""
        from vpo.policy.conditions import (
            evaluate_audio_is_multi_language,
        )
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        condition = AudioIsMultiLanguageCondition(primary_language="jpn")
        tracks = [audio_track_with_id]
        language_results = {100: multi_language_result}

        result, reason = evaluate_audio_is_multi_language(
            condition, tracks, language_results
        )

        assert result is False

    def test_track_index_filter(
        self,
        audio_track_with_id: TrackInfo,
        multi_language_result: "LanguageAnalysisResult",
    ) -> None:
        """Condition filters by specific track index."""
        from vpo.policy.conditions import (
            evaluate_audio_is_multi_language,
        )
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        # Track index is 1
        condition = AudioIsMultiLanguageCondition(track_index=1)
        tracks = [audio_track_with_id]
        language_results = {100: multi_language_result}

        result, reason = evaluate_audio_is_multi_language(
            condition, tracks, language_results
        )

        assert result is True

    def test_track_index_not_found(
        self,
        audio_track_with_id: TrackInfo,
        multi_language_result: "LanguageAnalysisResult",
    ) -> None:
        """Condition returns False when specified track index doesn't exist."""
        from vpo.policy.conditions import (
            evaluate_audio_is_multi_language,
        )
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        condition = AudioIsMultiLanguageCondition(track_index=99)
        tracks = [audio_track_with_id]
        language_results = {100: multi_language_result}

        result, reason = evaluate_audio_is_multi_language(
            condition, tracks, language_results
        )

        assert result is False
        assert "track 99 not found" in reason

    def test_via_evaluate_condition(
        self,
        audio_track_with_id: TrackInfo,
        multi_language_result: "LanguageAnalysisResult",
    ) -> None:
        """Condition works through main evaluate_condition()."""
        from vpo.policy.conditions import evaluate_condition
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        condition = AudioIsMultiLanguageCondition()
        tracks = [audio_track_with_id]
        language_results = {100: multi_language_result}

        result, reason = evaluate_condition(condition, tracks, language_results)

        assert result is True
        assert "audio_is_multi_language" in reason

    def test_in_and_condition(
        self,
        audio_track_with_id: TrackInfo,
        multi_language_result: "LanguageAnalysisResult",
    ) -> None:
        """Multi-language condition works in AND with other conditions."""
        from vpo.policy.conditions import evaluate_condition
        from vpo.policy.types import (
            AudioIsMultiLanguageCondition,
        )

        condition = AndCondition(
            conditions=(
                ExistsCondition(track_type="audio", filters=TrackFilters()),
                AudioIsMultiLanguageCondition(),
            )
        )
        tracks = [audio_track_with_id]
        language_results = {100: multi_language_result}

        result, reason = evaluate_condition(condition, tracks, language_results)

        assert result is True
