"""Unit tests for is_original and is_dubbed policy conditions."""

import pytest

from vpo.db.types import (
    DetectionMethod,
    OriginalDubbedStatus,
    TrackInfo,
)
from vpo.policy.conditions import (
    evaluate_condition,
    evaluate_is_dubbed,
    evaluate_is_original,
)
from vpo.policy.models import (
    IsDubbedCondition,
    IsOriginalCondition,
)
from vpo.track_classification.models import (
    TrackClassificationResult,
)


@pytest.fixture
def sample_audio_tracks():
    """Create sample audio tracks for testing."""
    return [
        TrackInfo(
            index=0,
            track_type="video",
            id=1,
            codec="hevc",
            width=1920,
            height=1080,
            frame_rate="23.976",
            is_default=True,
        ),
        TrackInfo(
            index=1,
            track_type="audio",
            id=2,
            codec="aac",
            language="jpn",
            title="Japanese (Original)",
            is_default=True,
            channels=2,
            channel_layout="stereo",
        ),
        TrackInfo(
            index=2,
            track_type="audio",
            id=3,
            codec="aac",
            language="eng",
            title="English (Dubbed)",
            is_default=False,
            channels=2,
            channel_layout="stereo",
        ),
    ]


@pytest.fixture
def classification_results():
    """Create classification results for the sample tracks."""
    return {
        2: TrackClassificationResult(
            track_id=2,
            file_hash="abc123",
            original_dubbed_status=OriginalDubbedStatus.ORIGINAL,
            commentary_status=None,
            confidence=0.85,
            detection_method=DetectionMethod.METADATA,
            acoustic_profile=None,
            language="jpn",
        ),
        3: TrackClassificationResult(
            track_id=3,
            file_hash="abc123",
            original_dubbed_status=OriginalDubbedStatus.DUBBED,
            commentary_status=None,
            confidence=0.80,
            detection_method=DetectionMethod.METADATA,
            acoustic_profile=None,
            language="eng",
        ),
    }


class TestIsOriginalCondition:
    """Tests for is_original condition evaluation."""

    def test_returns_false_when_no_classification_results(self, sample_audio_tracks):
        """Should return False when no classification results available."""
        condition = IsOriginalCondition(value=True)
        result, reason = evaluate_is_original(
            condition, sample_audio_tracks, classification_results=None
        )
        assert result is False
        assert "no classification results available" in reason

    def test_matches_original_track(self, sample_audio_tracks, classification_results):
        """Should match track classified as original."""
        condition = IsOriginalCondition(value=True)
        result, reason = evaluate_is_original(
            condition, sample_audio_tracks, classification_results
        )
        assert result is True
        assert "original" in reason
        assert "track[1]" in reason  # Track index 1 is Japanese

    def test_matches_not_original(self, sample_audio_tracks, classification_results):
        """Should match when looking for non-original (dubbed) track."""
        condition = IsOriginalCondition(value=False)
        result, reason = evaluate_is_original(
            condition, sample_audio_tracks, classification_results
        )
        assert result is True
        assert "dubbed" in reason

    def test_respects_min_confidence(self, sample_audio_tracks, classification_results):
        """Should respect min_confidence threshold."""
        # Japanese track has 0.85 confidence
        condition = IsOriginalCondition(value=True, min_confidence=0.90)
        result, reason = evaluate_is_original(
            condition, sample_audio_tracks, classification_results
        )
        assert result is False
        assert "no original tracks found" in reason

    def test_filters_by_language(self, sample_audio_tracks, classification_results):
        """Should filter by language when specified."""
        # English track is dubbed, not original
        condition = IsOriginalCondition(value=True, language="eng")
        result, reason = evaluate_is_original(
            condition, sample_audio_tracks, classification_results
        )
        assert result is False

        # Japanese track is original
        condition = IsOriginalCondition(value=True, language="jpn")
        result, reason = evaluate_is_original(
            condition, sample_audio_tracks, classification_results
        )
        assert result is True

    def test_via_evaluate_condition(self, sample_audio_tracks, classification_results):
        """Should work through main evaluate_condition function."""
        condition = IsOriginalCondition(value=True)
        result, reason = evaluate_condition(
            condition,
            sample_audio_tracks,
            classification_results=classification_results,
        )
        assert result is True


class TestIsDubbedCondition:
    """Tests for is_dubbed condition evaluation."""

    def test_returns_false_when_no_classification_results(self, sample_audio_tracks):
        """Should return False when no classification results available."""
        condition = IsDubbedCondition(value=True)
        result, reason = evaluate_is_dubbed(
            condition, sample_audio_tracks, classification_results=None
        )
        assert result is False
        assert "no classification results available" in reason

    def test_matches_dubbed_track(self, sample_audio_tracks, classification_results):
        """Should match track classified as dubbed."""
        condition = IsDubbedCondition(value=True)
        result, reason = evaluate_is_dubbed(
            condition, sample_audio_tracks, classification_results
        )
        assert result is True
        assert "dubbed" in reason
        assert "track[2]" in reason  # Track index 2 is English dubbed

    def test_matches_not_dubbed(self, sample_audio_tracks, classification_results):
        """Should match when looking for non-dubbed (original) track."""
        condition = IsDubbedCondition(value=False)
        result, reason = evaluate_is_dubbed(
            condition, sample_audio_tracks, classification_results
        )
        assert result is True
        assert "original" in reason

    def test_respects_min_confidence(self, sample_audio_tracks, classification_results):
        """Should respect min_confidence threshold."""
        # English dubbed track has 0.80 confidence
        condition = IsDubbedCondition(value=True, min_confidence=0.85)
        result, reason = evaluate_is_dubbed(
            condition, sample_audio_tracks, classification_results
        )
        assert result is False
        assert "no dubbed tracks found" in reason

    def test_filters_by_language(self, sample_audio_tracks, classification_results):
        """Should filter by language when specified."""
        # Japanese track is original, not dubbed
        condition = IsDubbedCondition(value=True, language="jpn")
        result, reason = evaluate_is_dubbed(
            condition, sample_audio_tracks, classification_results
        )
        assert result is False

        # English track is dubbed
        condition = IsDubbedCondition(value=True, language="eng")
        result, reason = evaluate_is_dubbed(
            condition, sample_audio_tracks, classification_results
        )
        assert result is True

    def test_via_evaluate_condition(self, sample_audio_tracks, classification_results):
        """Should work through main evaluate_condition function."""
        condition = IsDubbedCondition(value=True)
        result, reason = evaluate_condition(
            condition,
            sample_audio_tracks,
            classification_results=classification_results,
        )
        assert result is True


class TestClassificationConditionsInCompound:
    """Tests for is_original/is_dubbed in compound conditions."""

    def test_in_and_condition(self, sample_audio_tracks, classification_results):
        """Should work in AND conditions."""
        from vpo.policy.models import (
            AndCondition,
            ExistsCondition,
            TrackFilters,
        )

        # AND: has original audio AND has video track
        condition = AndCondition(
            conditions=(
                IsOriginalCondition(value=True),
                ExistsCondition(track_type="video", filters=TrackFilters()),
            )
        )
        result, reason = evaluate_condition(
            condition,
            sample_audio_tracks,
            classification_results=classification_results,
        )
        assert result is True
        assert "and → True" in reason

    def test_in_or_condition(self, sample_audio_tracks, classification_results):
        """Should work in OR conditions."""
        from vpo.policy.models import OrCondition

        # OR: has original OR has dubbed
        condition = OrCondition(
            conditions=(
                IsOriginalCondition(value=True, language="fra"),  # No French
                IsDubbedCondition(value=True, language="eng"),  # English dubbed
            )
        )
        result, reason = evaluate_condition(
            condition,
            sample_audio_tracks,
            classification_results=classification_results,
        )
        assert result is True
        assert "or → True" in reason

    def test_in_not_condition(self, sample_audio_tracks, classification_results):
        """Should work in NOT conditions."""
        from vpo.policy.models import NotCondition

        # NOT: has no dubbed Spanish audio
        condition = NotCondition(inner=IsDubbedCondition(value=True, language="spa"))
        result, reason = evaluate_condition(
            condition,
            sample_audio_tracks,
            classification_results=classification_results,
        )
        assert result is True
        assert "not(" in reason
