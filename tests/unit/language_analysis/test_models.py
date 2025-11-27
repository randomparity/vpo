"""Unit tests for language analysis domain models."""

from datetime import datetime, timezone

import pytest

from video_policy_orchestrator.language_analysis.models import (
    AnalysisMetadata,
    LanguageAnalysisResult,
    LanguageClassification,
    LanguagePercentage,
    LanguageSegment,
)


class TestLanguageSegment:
    """Tests for LanguageSegment dataclass."""

    def test_valid_segment(self) -> None:
        """Test creating a valid language segment."""
        segment = LanguageSegment(
            language_code="eng",
            start_time=0.0,
            end_time=5.0,
            confidence=0.95,
        )
        assert segment.language_code == "eng"
        assert segment.start_time == 0.0
        assert segment.end_time == 5.0
        assert segment.confidence == 0.95

    def test_duration_property(self) -> None:
        """Test the duration property calculation."""
        segment = LanguageSegment(
            language_code="eng",
            start_time=10.0,
            end_time=25.0,
            confidence=0.9,
        )
        assert segment.duration == 15.0

    def test_invalid_end_time_before_start(self) -> None:
        """Test that end_time must be greater than start_time."""
        with pytest.raises(
            ValueError, match="end_time.*must be greater than.*start_time"
        ):
            LanguageSegment(
                language_code="eng",
                start_time=10.0,
                end_time=5.0,  # Invalid: before start_time
                confidence=0.9,
            )

    def test_invalid_end_time_equals_start(self) -> None:
        """Test that end_time must be strictly greater than start_time."""
        with pytest.raises(
            ValueError, match="end_time.*must be greater than.*start_time"
        ):
            LanguageSegment(
                language_code="eng",
                start_time=5.0,
                end_time=5.0,  # Invalid: equals start_time
                confidence=0.9,
            )

    def test_invalid_confidence_above_1(self) -> None:
        """Test that confidence must be <= 1.0."""
        with pytest.raises(ValueError, match="confidence.*must be between 0.0 and 1.0"):
            LanguageSegment(
                language_code="eng",
                start_time=0.0,
                end_time=5.0,
                confidence=1.5,  # Invalid: above 1.0
            )

    def test_invalid_confidence_negative(self) -> None:
        """Test that confidence must be >= 0.0."""
        with pytest.raises(ValueError, match="confidence.*must be between 0.0 and 1.0"):
            LanguageSegment(
                language_code="eng",
                start_time=0.0,
                end_time=5.0,
                confidence=-0.1,  # Invalid: negative
            )

    def test_boundary_confidence_values(self) -> None:
        """Test valid boundary confidence values 0.0 and 1.0."""
        segment_zero = LanguageSegment(
            language_code="eng",
            start_time=0.0,
            end_time=5.0,
            confidence=0.0,
        )
        assert segment_zero.confidence == 0.0

        segment_one = LanguageSegment(
            language_code="eng",
            start_time=0.0,
            end_time=5.0,
            confidence=1.0,
        )
        assert segment_one.confidence == 1.0

    def test_segment_is_frozen(self) -> None:
        """Test that segment is immutable (frozen dataclass)."""
        segment = LanguageSegment(
            language_code="eng",
            start_time=0.0,
            end_time=5.0,
            confidence=0.9,
        )
        with pytest.raises(AttributeError):
            segment.language_code = "fre"  # type: ignore[misc]


class TestLanguagePercentage:
    """Tests for LanguagePercentage dataclass."""

    def test_valid_percentage(self) -> None:
        """Test creating a valid language percentage."""
        lp = LanguagePercentage(language_code="eng", percentage=0.75)
        assert lp.language_code == "eng"
        assert lp.percentage == 0.75

    def test_invalid_percentage_above_1(self) -> None:
        """Test that percentage must be <= 1.0."""
        with pytest.raises(ValueError, match="percentage.*must be between 0.0 and 1.0"):
            LanguagePercentage(language_code="eng", percentage=1.5)

    def test_invalid_percentage_negative(self) -> None:
        """Test that percentage must be >= 0.0."""
        with pytest.raises(ValueError, match="percentage.*must be between 0.0 and 1.0"):
            LanguagePercentage(language_code="eng", percentage=-0.1)


class TestAnalysisMetadata:
    """Tests for AnalysisMetadata dataclass."""

    def test_valid_metadata(self) -> None:
        """Test creating valid analysis metadata."""
        metadata = AnalysisMetadata(
            plugin_name="whisper-transcriber",
            plugin_version="1.0.0",
            model_name="whisper-base",
            sample_positions=(30.0, 630.0, 1230.0),
            sample_duration=5.0,
            total_duration=1800.0,
            speech_ratio=0.85,
        )
        assert metadata.plugin_name == "whisper-transcriber"
        assert metadata.model_name == "whisper-base"
        assert len(metadata.sample_positions) == 3
        assert metadata.speech_ratio == 0.85

    def test_invalid_speech_ratio_above_1(self) -> None:
        """Test that speech_ratio must be <= 1.0."""
        with pytest.raises(
            ValueError, match="speech_ratio.*must be between 0.0 and 1.0"
        ):
            AnalysisMetadata(
                plugin_name="test",
                plugin_version="1.0.0",
                model_name="test",
                sample_positions=(30.0,),
                sample_duration=5.0,
                total_duration=100.0,
                speech_ratio=1.5,
            )

    def test_invalid_sample_duration(self) -> None:
        """Test that sample_duration must be positive."""
        with pytest.raises(ValueError, match="sample_duration.*must be positive"):
            AnalysisMetadata(
                plugin_name="test",
                plugin_version="1.0.0",
                model_name="test",
                sample_positions=(30.0,),
                sample_duration=0.0,
                total_duration=100.0,
                speech_ratio=0.5,
            )

    def test_invalid_total_duration(self) -> None:
        """Test that total_duration must be positive."""
        with pytest.raises(ValueError, match="total_duration.*must be positive"):
            AnalysisMetadata(
                plugin_name="test",
                plugin_version="1.0.0",
                model_name="test",
                sample_positions=(30.0,),
                sample_duration=5.0,
                total_duration=-10.0,
                speech_ratio=0.5,
            )


class TestLanguageClassification:
    """Tests for LanguageClassification enum."""

    def test_enum_values(self) -> None:
        """Test enum has expected values."""
        assert LanguageClassification.SINGLE_LANGUAGE.value == "SINGLE_LANGUAGE"
        assert LanguageClassification.MULTI_LANGUAGE.value == "MULTI_LANGUAGE"

    def test_enum_from_string(self) -> None:
        """Test creating enum from string value."""
        single = LanguageClassification("SINGLE_LANGUAGE")
        multi = LanguageClassification("MULTI_LANGUAGE")
        assert single == LanguageClassification.SINGLE_LANGUAGE
        assert multi == LanguageClassification.MULTI_LANGUAGE


class TestLanguageAnalysisResult:
    """Tests for LanguageAnalysisResult dataclass."""

    @pytest.fixture
    def sample_metadata(self) -> AnalysisMetadata:
        """Create sample metadata for tests."""
        return AnalysisMetadata(
            plugin_name="whisper-transcriber",
            plugin_version="1.0.0",
            model_name="whisper-base",
            sample_positions=(30.0, 630.0, 1230.0),
            sample_duration=5.0,
            total_duration=1800.0,
            speech_ratio=0.85,
        )

    @pytest.fixture
    def sample_segments(self) -> list[LanguageSegment]:
        """Create sample segments for tests."""
        return [
            LanguageSegment("eng", 30.0, 35.0, 0.95),
            LanguageSegment("eng", 630.0, 635.0, 0.92),
            LanguageSegment("eng", 1230.0, 1235.0, 0.94),
        ]

    def test_from_segments_single_language(
        self, sample_metadata: AnalysisMetadata, sample_segments: list[LanguageSegment]
    ) -> None:
        """Test from_segments with all same language (single-language result)."""
        result = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=sample_segments,
            metadata=sample_metadata,
        )

        assert result.track_id == 1
        assert result.file_hash == "abc123"
        assert result.primary_language == "eng"
        assert result.primary_percentage == 1.0
        assert len(result.secondary_languages) == 0
        assert result.classification == LanguageClassification.SINGLE_LANGUAGE
        assert not result.is_multi_language

    def test_from_segments_multi_language(
        self, sample_metadata: AnalysisMetadata
    ) -> None:
        """Test from_segments with multiple languages (multi-language result)."""
        # Create segments: 80% English, 20% French
        segments = [
            LanguageSegment("eng", 0.0, 5.0, 0.95),
            LanguageSegment("eng", 10.0, 15.0, 0.92),
            LanguageSegment("eng", 20.0, 25.0, 0.94),
            LanguageSegment("eng", 30.0, 35.0, 0.91),
            LanguageSegment("fre", 40.0, 45.0, 0.88),  # 20% French
        ]

        result = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=segments,
            metadata=sample_metadata,
        )

        assert result.primary_language == "eng"
        assert result.primary_percentage == 0.8
        assert len(result.secondary_languages) == 1
        assert result.secondary_languages[0].language_code == "fre"
        assert result.secondary_languages[0].percentage == 0.2
        assert result.classification == LanguageClassification.MULTI_LANGUAGE
        assert result.is_multi_language

    def test_from_segments_exactly_95_percent(
        self, sample_metadata: AnalysisMetadata
    ) -> None:
        """Test that 95% exactly is classified as single-language."""
        # Create segments: 95% English, 5% French
        segments = [
            LanguageSegment("eng", 0.0, 19.0, 0.95),  # 19 seconds
            LanguageSegment("fre", 19.0, 20.0, 0.88),  # 1 second (5%)
        ]

        result = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=segments,
            metadata=sample_metadata,
        )

        assert result.primary_percentage == 0.95
        assert result.classification == LanguageClassification.SINGLE_LANGUAGE

    def test_from_segments_just_under_95_percent(
        self, sample_metadata: AnalysisMetadata
    ) -> None:
        """Test that just under 95% is classified as multi-language."""
        # Create segments: ~94.7% English, ~5.3% French (18 vs 1.1 seconds)
        segments = [
            LanguageSegment("eng", 0.0, 18.0, 0.95),
            LanguageSegment("fre", 18.0, 19.1, 0.88),
        ]

        result = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=segments,
            metadata=sample_metadata,
        )

        assert result.primary_percentage < 0.95
        assert result.classification == LanguageClassification.MULTI_LANGUAGE

    def test_from_segments_empty_raises_error(
        self, sample_metadata: AnalysisMetadata
    ) -> None:
        """Test that empty segments list raises ValueError."""
        with pytest.raises(ValueError, match="At least one segment is required"):
            LanguageAnalysisResult.from_segments(
                track_id=1,
                file_hash="abc123",
                segments=[],
                metadata=sample_metadata,
            )

    def test_from_segments_multiple_secondary_languages(
        self, sample_metadata: AnalysisMetadata
    ) -> None:
        """Test from_segments with multiple secondary languages."""
        # Create segments: 60% English, 25% French, 15% German
        segments = [
            LanguageSegment("eng", 0.0, 5.0, 0.95),
            LanguageSegment("eng", 10.0, 17.0, 0.92),  # 12 seconds eng total (60%)
            LanguageSegment("fre", 20.0, 25.0, 0.88),  # 5 seconds fre (25%)
            LanguageSegment("ger", 30.0, 33.0, 0.85),  # 3 seconds ger (15%)
        ]

        result = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=segments,
            metadata=sample_metadata,
        )

        assert result.primary_language == "eng"
        assert result.primary_percentage == 0.6
        assert len(result.secondary_languages) == 2

        # Secondary languages should be sorted by percentage descending
        secondary_codes = [lp.language_code for lp in result.secondary_languages]
        assert "fre" in secondary_codes
        assert "ger" in secondary_codes

    def test_has_secondary_language_above_threshold(
        self, sample_metadata: AnalysisMetadata
    ) -> None:
        """Test has_secondary_language_above_threshold method."""
        segments = [
            LanguageSegment("eng", 0.0, 16.0, 0.95),  # 80%
            LanguageSegment("fre", 16.0, 20.0, 0.88),  # 20%
        ]

        result = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=segments,
            metadata=sample_metadata,
        )

        # 20% French should be above 5% threshold
        assert result.has_secondary_language_above_threshold(0.05)
        assert result.has_secondary_language_above_threshold(0.10)
        assert result.has_secondary_language_above_threshold(0.15)
        assert result.has_secondary_language_above_threshold(0.20)
        # 20% should not be above 25% threshold
        assert not result.has_secondary_language_above_threshold(0.25)

    def test_timestamps_set_automatically(
        self, sample_metadata: AnalysisMetadata, sample_segments: list[LanguageSegment]
    ) -> None:
        """Test that created_at and updated_at are set automatically."""
        before = datetime.now(timezone.utc)

        result = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=sample_segments,
            metadata=sample_metadata,
        )

        after = datetime.now(timezone.utc)

        assert before <= result.created_at <= after
        assert before <= result.updated_at <= after
        assert result.created_at == result.updated_at

    def test_custom_threshold(self, sample_metadata: AnalysisMetadata) -> None:
        """Test from_segments with custom single-language threshold."""
        # Create segments: 90% English, 10% French
        segments = [
            LanguageSegment("eng", 0.0, 18.0, 0.95),  # 90%
            LanguageSegment("fre", 18.0, 20.0, 0.88),  # 10%
        ]

        # With default 95% threshold: multi-language
        result_default = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=segments,
            metadata=sample_metadata,
        )
        assert result_default.classification == LanguageClassification.MULTI_LANGUAGE

        # With 85% threshold: single-language
        result_custom = LanguageAnalysisResult.from_segments(
            track_id=1,
            file_hash="abc123",
            segments=segments,
            metadata=sample_metadata,
            single_language_threshold=0.85,
        )
        assert result_custom.classification == LanguageClassification.SINGLE_LANGUAGE
