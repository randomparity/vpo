"""Unit tests for plugin_sdk transcription module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vpo.plugin_sdk.transcription import (
    AggregatedResult,
    MultiSampleConfig,
    SampleResult,
    TrackClassification,
    TranscriptionPluginBase,
    TranscriptionResult,
    aggregate_results,
    calculate_sample_positions,
)


class ConcreteTranscriptionPlugin(TranscriptionPluginBase):
    """Concrete implementation for testing the abstract base class."""

    def detect_language(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """Test implementation of detect_language."""
        return self.create_result(
            detected_language="en",
            confidence_score=0.95,
        )

    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Test implementation of transcribe."""
        return self.create_result(
            detected_language=language or "en",
            confidence_score=0.9,
            transcript_sample="Hello world",
        )


class TestTranscriptionPluginBase:
    """Tests for TranscriptionPluginBase abstract class."""

    def test_abstract_class_cannot_instantiate(self) -> None:
        """Cannot instantiate TranscriptionPluginBase directly."""
        with pytest.raises(TypeError):
            TranscriptionPluginBase(  # type: ignore[abstract]
                name="test", version="1.0.0"
            )

    def test_name_property(self) -> None:
        """name property returns initialized name."""
        plugin = ConcreteTranscriptionPlugin(name="test-plugin", version="1.0.0")
        assert plugin.name == "test-plugin"

    def test_version_property(self) -> None:
        """version property returns initialized version."""
        plugin = ConcreteTranscriptionPlugin(name="test-plugin", version="2.0.1")
        assert plugin.version == "2.0.1"

    def test_default_supported_features(self) -> None:
        """Default features include 'language_detection'."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        assert plugin.supports_feature("language_detection") is True

    def test_custom_supported_features(self) -> None:
        """Can specify custom features set."""
        plugin = ConcreteTranscriptionPlugin(
            name="test",
            version="1.0",
            supported_features={"transcription", "gpu"},
        )
        assert plugin.supports_feature("transcription") is True
        assert plugin.supports_feature("gpu") is True
        assert plugin.supports_feature("language_detection") is False

    def test_supports_feature_returns_true(self) -> None:
        """supports_feature returns True for supported features."""
        plugin = ConcreteTranscriptionPlugin(
            name="test",
            version="1.0",
            supported_features={"feature_a", "feature_b"},
        )
        assert plugin.supports_feature("feature_a") is True

    def test_supports_feature_returns_false(self) -> None:
        """supports_feature returns False for unsupported features."""
        plugin = ConcreteTranscriptionPlugin(
            name="test",
            version="1.0",
            supported_features={"feature_a"},
        )
        assert plugin.supports_feature("feature_b") is False


class TestCreateResult:
    """Tests for create_result helper method."""

    def test_creates_transcription_result(self) -> None:
        """create_result returns TranscriptionResult."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.create_result(
            detected_language="en",
            confidence_score=0.9,
        )
        assert isinstance(result, TranscriptionResult)

    def test_sets_plugin_name(self) -> None:
        """create_result sets plugin_name from self.name."""
        plugin = ConcreteTranscriptionPlugin(name="my-plugin", version="1.0")
        result = plugin.create_result(
            detected_language="en",
            confidence_score=0.9,
        )
        assert result.plugin_name == "my-plugin"

    def test_sets_current_timestamps(self) -> None:
        """create_result sets created_at and updated_at to now."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        before = datetime.now(timezone.utc)
        result = plugin.create_result(
            detected_language="en",
            confidence_score=0.9,
        )
        after = datetime.now(timezone.utc)

        assert before <= result.created_at <= after
        assert before <= result.updated_at <= after

    def test_track_id_defaults_to_zero(self) -> None:
        """track_id is 0 (caller should set)."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.create_result(
            detected_language="en",
            confidence_score=0.9,
        )
        assert result.track_id == 0

    def test_default_track_type_is_main(self) -> None:
        """Default track_type is TrackClassification.MAIN."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.create_result(
            detected_language="en",
            confidence_score=0.9,
        )
        assert result.track_type == TrackClassification.MAIN

    def test_custom_track_type(self) -> None:
        """Can specify custom track_type."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.create_result(
            detected_language="en",
            confidence_score=0.9,
            track_type=TrackClassification.COMMENTARY,
        )
        assert result.track_type == TrackClassification.COMMENTARY

    def test_confidence_score_passed_through(self) -> None:
        """confidence_score parameter passed to result."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.create_result(
            detected_language="en",
            confidence_score=0.75,
        )
        assert result.confidence_score == 0.75

    def test_detected_language_passed_through(self) -> None:
        """detected_language parameter passed to result."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.create_result(
            detected_language="fr",
            confidence_score=0.9,
        )
        assert result.detected_language == "fr"

    def test_transcript_sample_passed_through(self) -> None:
        """transcript_sample parameter passed to result."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.create_result(
            detected_language="en",
            confidence_score=0.9,
            transcript_sample="Hello world",
        )
        assert result.transcript_sample == "Hello world"


class TestConcreteImplementation:
    """Tests for concrete subclass implementation."""

    def test_concrete_class_can_instantiate(self) -> None:
        """Concrete subclass with abstract methods can instantiate."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        assert plugin is not None

    def test_detect_language_callable(self) -> None:
        """detect_language can be called."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.detect_language(b"audio data")
        assert result.detected_language == "en"

    def test_transcribe_callable(self) -> None:
        """transcribe can be called."""
        plugin = ConcreteTranscriptionPlugin(name="test", version="1.0")
        result = plugin.transcribe(b"audio data", language="fr")
        assert result.detected_language == "fr"
        assert result.transcript_sample == "Hello world"


# =============================================================================
# Multi-Sample Detection Tests
# =============================================================================


class TestSampleResult:
    """Tests for SampleResult dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a basic sample result."""
        result = SampleResult(
            position=0.0,
            language="en",
            confidence=0.95,
        )
        assert result.position == 0.0
        assert result.language == "en"
        assert result.confidence == 0.95
        assert result.transcript_sample is None

    def test_with_transcript(self) -> None:
        """Test creating a sample result with transcript."""
        result = SampleResult(
            position=30.0,
            language="es",
            confidence=0.88,
            transcript_sample="Hola mundo",
        )
        assert result.transcript_sample == "Hola mundo"

    def test_none_language(self) -> None:
        """Test sample result with no detected language."""
        result = SampleResult(
            position=60.0,
            language=None,
            confidence=0.0,
        )
        assert result.language is None


class TestMultiSampleConfig:
    """Tests for MultiSampleConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default configuration values."""
        config = MultiSampleConfig()
        assert config.max_samples == 3
        assert config.sample_duration == 30
        assert config.confidence_threshold == 0.85
        assert config.incumbent_bonus == 0.15

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = MultiSampleConfig(
            max_samples=5,
            sample_duration=60,
            confidence_threshold=0.9,
            incumbent_bonus=0.2,
        )
        assert config.max_samples == 5
        assert config.sample_duration == 60
        assert config.confidence_threshold == 0.9
        assert config.incumbent_bonus == 0.2

    def test_validation_max_samples_zero(self) -> None:
        """Test max_samples must be at least 1."""
        with pytest.raises(ValueError, match="max_samples must be at least 1"):
            MultiSampleConfig(max_samples=0)

    def test_validation_max_samples_negative(self) -> None:
        """Test max_samples cannot be negative."""
        with pytest.raises(ValueError, match="max_samples must be at least 1"):
            MultiSampleConfig(max_samples=-1)

    def test_validation_sample_duration_zero(self) -> None:
        """Test sample_duration must be at least 1."""
        with pytest.raises(ValueError, match="sample_duration must be at least 1"):
            MultiSampleConfig(sample_duration=0)

    def test_validation_confidence_threshold_negative(self) -> None:
        """Test confidence_threshold must be in [0.0, 1.0]."""
        with pytest.raises(
            ValueError, match="confidence_threshold must be between 0.0 and 1.0"
        ):
            MultiSampleConfig(confidence_threshold=-0.1)

    def test_validation_confidence_threshold_too_high(self) -> None:
        """Test confidence_threshold must be at most 1.0."""
        with pytest.raises(
            ValueError, match="confidence_threshold must be between 0.0 and 1.0"
        ):
            MultiSampleConfig(confidence_threshold=1.1)

    def test_validation_incumbent_bonus_negative(self) -> None:
        """Test incumbent_bonus must be non-negative."""
        with pytest.raises(ValueError, match="incumbent_bonus must be non-negative"):
            MultiSampleConfig(incumbent_bonus=-0.1)


class TestAggregatedResult:
    """Tests for AggregatedResult dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating an aggregated result."""
        result = AggregatedResult(
            language="eng",
            confidence=0.9,
            samples_taken=3,
        )
        assert result.language == "eng"
        assert result.confidence == 0.9
        assert result.samples_taken == 3
        assert result.sample_results == []
        assert result.transcript_sample is None

    def test_with_sample_results(self) -> None:
        """Test aggregated result with sample details."""
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.9),
            SampleResult(position=1000.0, language="en", confidence=0.85),
        ]
        result = AggregatedResult(
            language="eng",
            confidence=0.875,
            samples_taken=2,
            sample_results=samples,
        )
        assert len(result.sample_results) == 2

    def test_none_language(self) -> None:
        """Test aggregated result with no detected language."""
        result = AggregatedResult(
            language=None,
            confidence=0.0,
            samples_taken=3,
        )
        assert result.language is None


class TestCalculateSamplePositions:
    """Tests for calculate_sample_positions function."""

    def test_single_sample(self) -> None:
        """Test single sample returns start position."""
        positions = calculate_sample_positions(7200.0, 1, 30)
        assert positions == [0.0]

    def test_two_samples(self) -> None:
        """Test two samples returns start and middle."""
        positions = calculate_sample_positions(7200.0, 2, 30)
        assert len(positions) == 2
        assert positions[0] == 0.0
        # Middle position: (7200 - 30) * 0.5 = 3585
        assert positions[1] == pytest.approx(3585.0)

    def test_three_samples(self) -> None:
        """Test three samples returns start, middle, quarter."""
        positions = calculate_sample_positions(7200.0, 3, 30)
        assert len(positions) == 3
        assert positions[0] == 0.0
        assert positions[1] == pytest.approx(3585.0)  # Middle
        assert positions[2] == pytest.approx(1792.5)  # Quarter

    def test_four_samples(self) -> None:
        """Test four samples returns start, middle, quarter, three-quarter."""
        positions = calculate_sample_positions(7200.0, 4, 30)
        assert len(positions) == 4
        assert positions[0] == 0.0
        assert positions[1] == pytest.approx(3585.0)  # Middle
        assert positions[2] == pytest.approx(1792.5)  # Quarter
        assert positions[3] == pytest.approx(5377.5)  # Three-quarters

    def test_zero_samples(self) -> None:
        """Test requesting zero samples."""
        positions = calculate_sample_positions(7200.0, 0, 30)
        assert positions == []

    def test_short_track(self) -> None:
        """Test track shorter than sample duration."""
        positions = calculate_sample_positions(20.0, 3, 30)
        assert positions == [0.0]

    def test_zero_duration(self) -> None:
        """Test zero duration track."""
        positions = calculate_sample_positions(0.0, 3, 30)
        assert positions == [0.0]

    def test_exact_sample_duration(self) -> None:
        """Test track exactly equals sample duration."""
        positions = calculate_sample_positions(30.0, 3, 30)
        # max_start = 0, so only start position
        assert positions == [0.0]

    def test_negative_sample_duration_raises(self) -> None:
        """Test negative sample_duration raises ValueError."""
        with pytest.raises(ValueError, match="sample_duration must be non-negative"):
            calculate_sample_positions(7200.0, 3, -10)


class TestAggregateResults:
    """Tests for aggregate_results function."""

    def test_empty_samples(self) -> None:
        """Test aggregating empty sample list."""
        result = aggregate_results([])
        assert result.language is None
        assert result.confidence == 0.0
        assert result.samples_taken == 0

    def test_single_sample(self) -> None:
        """Test aggregating single sample."""
        samples = [SampleResult(position=0.0, language="en", confidence=0.95)]
        result = aggregate_results(samples)
        # Language should be normalized to ISO 639-2/B
        assert result.language == "eng"
        assert result.confidence == 0.95
        assert result.samples_taken == 1

    def test_unanimous_samples(self) -> None:
        """Test aggregating samples with same language."""
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.90),
            SampleResult(position=1000.0, language="en", confidence=0.85),
            SampleResult(position=2000.0, language="en", confidence=0.95),
        ]
        result = aggregate_results(samples)
        assert result.language == "eng"
        # Average confidence: (0.90 + 0.85 + 0.95) / 3 = 0.9
        assert result.confidence == pytest.approx(0.9)
        assert result.samples_taken == 3

    def test_majority_voting(self) -> None:
        """Test majority voting when samples differ."""
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.85),
            SampleResult(position=1000.0, language="en", confidence=0.90),
            SampleResult(position=2000.0, language="es", confidence=0.70),
        ]
        result = aggregate_results(samples)
        # en wins: 2 samples with total weight 0.85 + 0.90 = 1.75
        # es has: 1 sample with weight 0.70
        assert result.language == "eng"

    def test_incumbent_bonus(self) -> None:
        """Test incumbent language gets bonus vote."""
        # Without bonus, es would win (higher confidence)
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.80),
            SampleResult(position=1000.0, language="es", confidence=0.95),
        ]
        # With incumbent bonus of 0.5, en gets 0.80 + 0.5 = 1.30 vs es 0.95
        result = aggregate_results(
            samples, incumbent_language="en", incumbent_bonus=0.5
        )
        assert result.language == "eng"

    def test_all_none_language(self) -> None:
        """Test when all samples have None language."""
        samples = [
            SampleResult(position=0.0, language=None, confidence=0.0),
            SampleResult(position=1000.0, language=None, confidence=0.0),
        ]
        result = aggregate_results(samples)
        assert result.language is None
        assert result.confidence == 0.0
        assert result.samples_taken == 2

    def test_best_transcript_selected(self) -> None:
        """Test highest-confidence transcript is selected."""
        samples = [
            SampleResult(
                position=0.0,
                language="en",
                confidence=0.80,
                transcript_sample="First sample",
            ),
            SampleResult(
                position=1000.0,
                language="en",
                confidence=0.95,
                transcript_sample="Second sample - best",
            ),
            SampleResult(
                position=2000.0,
                language="en",
                confidence=0.85,
                transcript_sample="Third sample",
            ),
        ]
        result = aggregate_results(samples)
        assert result.transcript_sample == "Second sample - best"


class TestMultiSampleSdkImports:
    """Tests to verify multi-sample SDK imports work correctly."""

    def test_import_from_plugin_sdk(self) -> None:
        """Verify utilities can be imported from plugin_sdk."""
        from vpo.plugin_sdk import (
            AggregatedResult,
            MultiSampleConfig,
            SampleResult,
            aggregate_results,
            calculate_sample_positions,
        )

        # Just verify they're callable/types
        assert callable(aggregate_results)
        assert callable(calculate_sample_positions)
        assert SampleResult is not None
        assert MultiSampleConfig is not None
        assert AggregatedResult is not None

    def test_import_from_transcription_module(self) -> None:
        """Verify utilities can be imported from transcription submodule."""
        from vpo.plugin_sdk.transcription import (
            AggregatedResult,
            MultiSampleConfig,
            SampleResult,
            aggregate_results,
            calculate_sample_positions,
        )

        assert callable(aggregate_results)
        assert callable(calculate_sample_positions)
        assert SampleResult is not None
        assert MultiSampleConfig is not None
        assert AggregatedResult is not None
