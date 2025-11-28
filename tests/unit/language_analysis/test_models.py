"""Unit tests for language analysis domain models."""

from datetime import datetime, timezone

import pytest

from video_policy_orchestrator.db.types import (
    LanguageAnalysisResultRecord,
    LanguageSegmentRecord,
)
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


class TestLanguageSegmentSerialization:
    """Tests for LanguageSegment serialization methods."""

    def test_from_record(self) -> None:
        """Test creating LanguageSegment from database record."""
        record = LanguageSegmentRecord(
            id=1,
            analysis_id=10,
            language_code="eng",
            start_time=5.0,
            end_time=10.0,
            confidence=0.95,
        )
        segment = LanguageSegment.from_record(record)

        assert segment.language_code == "eng"
        assert segment.start_time == 5.0
        assert segment.end_time == 10.0
        assert segment.confidence == 0.95

    def test_from_detection_result_with_speech(self) -> None:
        """Test creating LanguageSegment from detection result with speech."""
        from video_policy_orchestrator.transcription.interface import (
            MultiLanguageDetectionResult,
        )

        detection = MultiLanguageDetectionResult(
            position=30.0,
            language="eng",
            confidence=0.92,
            has_speech=True,
        )
        segment = LanguageSegment.from_detection_result(detection, sample_duration=5.0)

        assert segment is not None
        assert segment.language_code == "eng"
        assert segment.start_time == 30.0
        assert segment.end_time == 35.0
        assert segment.confidence == 0.92

    def test_from_detection_result_no_speech(self) -> None:
        """Test that detection with no speech returns None."""
        from video_policy_orchestrator.transcription.interface import (
            MultiLanguageDetectionResult,
        )

        detection = MultiLanguageDetectionResult(
            position=30.0,
            language=None,
            confidence=0.0,
            has_speech=False,
        )
        segment = LanguageSegment.from_detection_result(detection, sample_duration=5.0)

        assert segment is None


class TestAnalysisMetadataSerialization:
    """Tests for AnalysisMetadata serialization methods."""

    def test_to_dict(self) -> None:
        """Test converting metadata to dictionary."""
        metadata = AnalysisMetadata(
            plugin_name="whisper",
            plugin_version="1.0.0",
            model_name="base",
            sample_positions=(30.0, 60.0, 90.0),
            sample_duration=5.0,
            total_duration=120.0,
            speech_ratio=0.8,
        )
        d = metadata.to_dict()

        assert d["plugin_name"] == "whisper"
        assert d["plugin_version"] == "1.0.0"
        assert d["model_name"] == "base"
        assert d["sample_positions"] == [30.0, 60.0, 90.0]
        assert d["sample_duration"] == 5.0
        assert d["total_duration"] == 120.0
        assert d["speech_ratio"] == 0.8

    def test_from_dict(self) -> None:
        """Test creating metadata from dictionary."""
        d = {
            "plugin_name": "whisper",
            "plugin_version": "2.0.0",
            "model_name": "large",
            "sample_positions": [10.0, 20.0],
            "sample_duration": 10.0,
            "total_duration": 60.0,
            "speech_ratio": 0.9,
        }
        metadata = AnalysisMetadata.from_dict(d)

        assert metadata.plugin_name == "whisper"
        assert metadata.plugin_version == "2.0.0"
        assert metadata.model_name == "large"
        assert metadata.sample_positions == (10.0, 20.0)
        assert metadata.sample_duration == 10.0
        assert metadata.total_duration == 60.0
        assert metadata.speech_ratio == 0.9

    def test_from_dict_with_defaults(self) -> None:
        """Test that missing keys get default values."""
        metadata = AnalysisMetadata.from_dict({})

        assert metadata.plugin_name == "unknown"
        assert metadata.plugin_version == "0.0.0"
        assert metadata.model_name == "unknown"
        assert metadata.sample_positions == ()
        assert metadata.sample_duration == 30.0
        assert metadata.total_duration == 1.0
        assert metadata.speech_ratio == 0.0

    def test_to_json_and_from_json_roundtrip(self) -> None:
        """Test JSON serialization roundtrip."""
        original = AnalysisMetadata(
            plugin_name="test-plugin",
            plugin_version="3.0.0",
            model_name="medium",
            sample_positions=(15.0, 45.0, 75.0),
            sample_duration=15.0,
            total_duration=90.0,
            speech_ratio=0.75,
        )
        json_str = original.to_json()
        restored = AnalysisMetadata.from_json(json_str)

        assert restored.plugin_name == original.plugin_name
        assert restored.plugin_version == original.plugin_version
        assert restored.model_name == original.model_name
        assert restored.sample_positions == original.sample_positions
        assert restored.sample_duration == original.sample_duration
        assert restored.total_duration == original.total_duration
        assert restored.speech_ratio == original.speech_ratio

    def test_from_json_none(self) -> None:
        """Test that from_json(None) returns defaults."""
        metadata = AnalysisMetadata.from_json(None)
        assert metadata.plugin_name == "unknown"


class TestLanguageAnalysisResultSerialization:
    """Tests for LanguageAnalysisResult serialization methods."""

    @pytest.fixture
    def sample_result(self) -> LanguageAnalysisResult:
        """Create a sample result for testing."""
        metadata = AnalysisMetadata(
            plugin_name="whisper",
            plugin_version="1.0.0",
            model_name="base",
            sample_positions=(30.0, 60.0),
            sample_duration=5.0,
            total_duration=90.0,
            speech_ratio=0.8,
        )
        segments = [
            LanguageSegment("eng", 30.0, 35.0, 0.95),
            LanguageSegment("eng", 60.0, 65.0, 0.92),
        ]
        return LanguageAnalysisResult.from_segments(
            track_id=42,
            file_hash="hash123",
            segments=segments,
            metadata=metadata,
        )

    def test_to_records(self, sample_result: LanguageAnalysisResult) -> None:
        """Test converting result to database records."""
        main_record, segment_records = sample_result.to_records()

        assert main_record.track_id == 42
        assert main_record.file_hash == "hash123"
        assert main_record.primary_language == "eng"
        assert main_record.primary_percentage == 1.0
        assert main_record.classification == "SINGLE_LANGUAGE"
        assert main_record.id is None  # Not yet persisted

        assert len(segment_records) == 2
        assert all(sr.analysis_id == 0 for sr in segment_records)  # To be filled
        assert segment_records[0].language_code == "eng"
        assert segment_records[0].start_time == 30.0

    def test_from_record(self) -> None:
        """Test creating result from database records."""
        import json

        metadata_json = json.dumps(
            {
                "plugin_name": "whisper",
                "plugin_version": "1.0.0",
                "model_name": "base",
                "sample_positions": [30.0, 60.0],
                "sample_duration": 5.0,
                "total_duration": 90.0,
                "speech_ratio": 0.8,
            }
        )

        main_record = LanguageAnalysisResultRecord(
            id=100,
            track_id=42,
            file_hash="hash123",
            primary_language="eng",
            primary_percentage=0.8,
            classification="MULTI_LANGUAGE",
            analysis_metadata=metadata_json,
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-02T00:00:00+00:00",
        )

        segment_records = [
            LanguageSegmentRecord(
                id=1,
                analysis_id=100,
                language_code="eng",
                start_time=30.0,
                end_time=35.0,
                confidence=0.95,
            ),
            LanguageSegmentRecord(
                id=2,
                analysis_id=100,
                language_code="fre",
                start_time=60.0,
                end_time=65.0,
                confidence=0.88,
            ),
        ]

        result = LanguageAnalysisResult.from_record(main_record, segment_records)

        assert result.track_id == 42
        assert result.file_hash == "hash123"
        assert result.primary_language == "eng"
        assert result.primary_percentage == 0.8
        assert result.classification == LanguageClassification.MULTI_LANGUAGE
        assert len(result.segments) == 2
        assert len(result.secondary_languages) == 1
        assert result.secondary_languages[0].language_code == "fre"
        assert result.metadata.plugin_name == "whisper"
        assert result.created_at.year == 2024

    def test_roundtrip_preserves_data(
        self, sample_result: LanguageAnalysisResult
    ) -> None:
        """Test that to_records -> from_record preserves key data."""
        main_record, segment_records = sample_result.to_records()

        # Simulate database assignment of IDs
        main_record.id = 999
        for i, sr in enumerate(segment_records):
            sr.id = i + 1
            sr.analysis_id = 999

        restored = LanguageAnalysisResult.from_record(main_record, segment_records)

        assert restored.track_id == sample_result.track_id
        assert restored.file_hash == sample_result.file_hash
        assert restored.primary_language == sample_result.primary_language
        assert restored.primary_percentage == sample_result.primary_percentage
        assert restored.classification == sample_result.classification
        assert len(restored.segments) == len(sample_result.segments)
