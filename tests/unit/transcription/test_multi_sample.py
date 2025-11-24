"""Tests for multi-sample audio transcription functionality."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from video_policy_orchestrator.transcription.interface import TranscriptionError
from video_policy_orchestrator.transcription.models import (
    TrackClassification,
    TranscriptionResult,
)
from video_policy_orchestrator.transcription.multi_sample import (
    MultiSampleConfig,
    SampleResult,
    aggregate_results,
    calculate_sample_positions,
    smart_detect,
)


class TestSampleResult:
    """Tests for SampleResult dataclass."""

    def test_basic_creation(self):
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

    def test_with_transcript(self):
        """Test creating a sample result with transcript."""
        result = SampleResult(
            position=30.0,
            language="es",
            confidence=0.88,
            transcript_sample="Hola mundo",
        )
        assert result.transcript_sample == "Hola mundo"


class TestMultiSampleConfig:
    """Tests for MultiSampleConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = MultiSampleConfig()
        assert config.max_samples == 3
        assert config.sample_duration == 30
        assert config.confidence_threshold == 0.85
        assert config.incumbent_bonus == 0.15

    def test_custom_values(self):
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

    def test_max_samples_validation(self):
        """Test max_samples must be at least 1."""
        with pytest.raises(ValueError, match="max_samples must be at least 1"):
            MultiSampleConfig(max_samples=0)

    def test_sample_duration_validation(self):
        """Test sample_duration must be at least 1 second."""
        with pytest.raises(ValueError, match="sample_duration must be at least 1"):
            MultiSampleConfig(sample_duration=0)

    def test_confidence_threshold_validation_low(self):
        """Test confidence_threshold must be >= 0."""
        with pytest.raises(ValueError, match="confidence_threshold must be between"):
            MultiSampleConfig(confidence_threshold=-0.1)

    def test_confidence_threshold_validation_high(self):
        """Test confidence_threshold must be <= 1."""
        with pytest.raises(ValueError, match="confidence_threshold must be between"):
            MultiSampleConfig(confidence_threshold=1.1)

    def test_incumbent_bonus_validation(self):
        """Test incumbent_bonus must be non-negative."""
        with pytest.raises(ValueError, match="incumbent_bonus must be non-negative"):
            MultiSampleConfig(incumbent_bonus=-0.1)


class TestCalculateSamplePositions:
    """Tests for calculate_sample_positions function."""

    def test_single_sample(self):
        """Test single sample returns start position."""
        positions = calculate_sample_positions(
            track_duration=7200.0,  # 2 hours
            num_samples=1,
            sample_duration=30,
        )
        assert positions == [0.0]

    def test_two_samples(self):
        """Test two samples returns start and middle."""
        positions = calculate_sample_positions(
            track_duration=7200.0,  # 2 hours
            num_samples=2,
            sample_duration=30,
        )
        # max_start = 7200 - 30 = 7170
        assert len(positions) == 2
        assert positions[0] == 0.0
        assert positions[1] == 3585.0  # 50% of max_start

    def test_three_samples(self):
        """Test three samples returns start, middle, quarter."""
        positions = calculate_sample_positions(
            track_duration=7200.0,
            num_samples=3,
            sample_duration=30,
        )
        assert len(positions) == 3
        assert positions[0] == 0.0
        # max_start = 7170
        assert positions[1] == pytest.approx(3585.0)  # 50%
        assert positions[2] == pytest.approx(1792.5)  # 25%

    def test_four_samples(self):
        """Test four samples returns start, middle, quarter, three-quarter."""
        positions = calculate_sample_positions(
            track_duration=7200.0,
            num_samples=4,
            sample_duration=30,
        )
        assert len(positions) == 4
        assert positions[0] == 0.0
        # max_start = 7170
        assert positions[1] == pytest.approx(3585.0)  # 50%
        assert positions[2] == pytest.approx(1792.5)  # 25%
        assert positions[3] == pytest.approx(5377.5)  # 75%

    def test_short_track(self):
        """Test track shorter than sample duration."""
        positions = calculate_sample_positions(
            track_duration=20.0,  # Shorter than 30s sample
            num_samples=3,
            sample_duration=30,
        )
        # Should only return start position
        assert positions == [0.0]

    def test_zero_duration(self):
        """Test zero duration track."""
        positions = calculate_sample_positions(
            track_duration=0.0,
            num_samples=3,
            sample_duration=30,
        )
        assert positions == [0.0]

    def test_zero_samples(self):
        """Test requesting zero samples."""
        positions = calculate_sample_positions(
            track_duration=7200.0,
            num_samples=0,
            sample_duration=30,
        )
        assert positions == []

    def test_exact_duration_match(self):
        """Test track duration exactly equal to sample duration."""
        positions = calculate_sample_positions(
            track_duration=30.0,
            num_samples=3,
            sample_duration=30,
        )
        # max_start = 0, so only start position
        assert positions == [0.0]


class TestAggregateResults:
    """Tests for aggregate_results function."""

    def test_empty_samples(self):
        """Test aggregating empty sample list."""
        result = aggregate_results([])
        assert result.language is None
        assert result.confidence == 0.0
        assert result.samples_taken == 0

    def test_single_sample(self):
        """Test aggregating single sample."""
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.95),
        ]
        result = aggregate_results(samples)
        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"
        assert result.confidence == 0.95
        assert result.samples_taken == 1

    def test_majority_vote_unanimous(self):
        """Test majority vote with unanimous agreement."""
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.90),
            SampleResult(position=1000.0, language="en", confidence=0.85),
            SampleResult(position=2000.0, language="en", confidence=0.95),
        ]
        result = aggregate_results(samples)
        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"
        assert result.confidence == pytest.approx(0.9)  # Average of 0.9, 0.85, 0.95

    def test_majority_vote_two_vs_one(self):
        """Test majority vote with 2-1 split."""
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.80),
            SampleResult(position=1000.0, language="es", confidence=0.95),
            SampleResult(position=2000.0, language="en", confidence=0.85),
        ]
        result = aggregate_results(samples)
        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"  # 2 votes vs 1
        assert result.confidence == pytest.approx(0.825)  # Average of 0.80, 0.85

    def test_incumbent_bonus(self):
        """Test incumbent language gets bonus vote."""
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.80),
            SampleResult(position=1000.0, language="es", confidence=0.95),
        ]
        # Without bonus: tie, Counter picks first
        # With bonus for es: es wins
        result = aggregate_results(
            samples, incumbent_language="es", incumbent_bonus=0.5
        )
        # Language is normalized to ISO 639-2/B
        assert result.language == "spa"

    def test_incumbent_bonus_doesnt_add_phantom_votes(self):
        """Test incumbent bonus only applies if language is in votes."""
        samples = [
            SampleResult(position=0.0, language="en", confidence=0.80),
            SampleResult(position=1000.0, language="en", confidence=0.85),
        ]
        # Even though incumbent is "de", it shouldn't appear in results
        result = aggregate_results(
            samples, incumbent_language="de", incumbent_bonus=0.5
        )
        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"

    def test_best_transcript_selected(self):
        """Test highest confidence transcript is selected."""
        samples = [
            SampleResult(
                position=0.0,
                language="en",
                confidence=0.80,
                transcript_sample="Hello world",
            ),
            SampleResult(
                position=1000.0,
                language="en",
                confidence=0.95,
                transcript_sample="Better quality sample",
            ),
        ]
        result = aggregate_results(samples)
        assert result.transcript_sample == "Better quality sample"

    def test_samples_with_none_language(self):
        """Test handling samples with None language."""
        samples = [
            SampleResult(position=0.0, language=None, confidence=0.30),
            SampleResult(position=1000.0, language="en", confidence=0.85),
        ]
        result = aggregate_results(samples)
        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"
        assert result.samples_taken == 2

    def test_all_none_languages(self):
        """Test all samples having None language."""
        samples = [
            SampleResult(position=0.0, language=None, confidence=0.30),
            SampleResult(position=1000.0, language=None, confidence=0.25),
        ]
        result = aggregate_results(samples)
        assert result.language is None
        assert result.confidence == 0.0


class TestSmartDetect:
    """Tests for smart_detect function."""

    def _create_mock_transcriber(self, results: list[tuple[str, float]]):
        """Create a mock transcriber that returns specified results in sequence."""
        mock = Mock()
        mock.name = "test-plugin"

        call_count = [0]

        def transcribe_side_effect(audio_data):
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(results):
                lang, conf = results[idx]
            else:
                lang, conf = results[-1]  # Repeat last result

            return TranscriptionResult(
                track_id=1,
                detected_language=lang,
                confidence_score=conf,
                track_type=TrackClassification.MAIN,
                transcript_sample=f"Sample {idx}",
                plugin_name="test-plugin",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        mock.transcribe.side_effect = transcribe_side_effect
        return mock

    @patch("video_policy_orchestrator.transcription.multi_sample.extract_audio_stream")
    def test_early_exit_high_confidence(self, mock_extract):
        """Test early exit when first sample has high confidence."""
        mock_extract.return_value = b"fake audio data"
        transcriber = self._create_mock_transcriber([("en", 0.95)])

        config = MultiSampleConfig(
            max_samples=3,
            confidence_threshold=0.85,
        )

        result = smart_detect(
            file_path=Path("/fake/video.mkv"),
            track_index=1,
            track_duration=7200.0,
            transcriber=transcriber,
            config=config,
        )

        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"
        assert result.samples_taken == 1
        # Should only call transcribe once due to early exit
        assert transcriber.transcribe.call_count == 1

    @patch("video_policy_orchestrator.transcription.multi_sample.extract_audio_stream")
    def test_multiple_samples_low_confidence(self, mock_extract):
        """Test taking multiple samples when confidence is low."""
        mock_extract.return_value = b"fake audio data"
        transcriber = self._create_mock_transcriber(
            [
                ("en", 0.70),
                ("en", 0.75),
                ("en", 0.80),
            ]
        )

        config = MultiSampleConfig(
            max_samples=3,
            confidence_threshold=0.85,
        )

        result = smart_detect(
            file_path=Path("/fake/video.mkv"),
            track_index=1,
            track_duration=7200.0,
            transcriber=transcriber,
            config=config,
        )

        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"
        assert result.samples_taken == 3
        assert transcriber.transcribe.call_count == 3

    @patch("video_policy_orchestrator.transcription.multi_sample.extract_audio_stream")
    def test_incumbent_language_passed(self, mock_extract):
        """Test incumbent language is passed to aggregation."""
        mock_extract.return_value = b"fake audio data"
        # First sample detects "es", second detects "en"
        # With incumbent "en", tie should break to "en"
        transcriber = self._create_mock_transcriber(
            [
                ("es", 0.50),
                ("en", 0.50),
            ]
        )

        config = MultiSampleConfig(
            max_samples=2,
            confidence_threshold=0.85,
            incumbent_bonus=0.5,
        )

        result = smart_detect(
            file_path=Path("/fake/video.mkv"),
            track_index=1,
            track_duration=7200.0,
            transcriber=transcriber,
            config=config,
            incumbent_language="en",
        )

        # With 0.5 bonus for incumbent "en", it should win
        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"

    @patch("video_policy_orchestrator.transcription.multi_sample.extract_audio_stream")
    def test_extraction_failure_continues(self, mock_extract):
        """Test that extraction failures don't stop processing."""
        from video_policy_orchestrator.transcription.audio_extractor import (
            AudioExtractionError,
        )

        # First call fails, second succeeds
        mock_extract.side_effect = [
            AudioExtractionError("Failed"),
            b"fake audio data",
        ]
        transcriber = self._create_mock_transcriber([("en", 0.90)])

        config = MultiSampleConfig(
            max_samples=2,
            confidence_threshold=0.85,
        )

        result = smart_detect(
            file_path=Path("/fake/video.mkv"),
            track_index=1,
            track_duration=7200.0,
            transcriber=transcriber,
            config=config,
        )

        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"
        assert result.samples_taken == 1

    @patch("video_policy_orchestrator.transcription.multi_sample.extract_audio_stream")
    def test_all_extractions_fail(self, mock_extract):
        """Test that all extraction failures raises error."""
        from video_policy_orchestrator.transcription.audio_extractor import (
            AudioExtractionError,
        )

        mock_extract.side_effect = AudioExtractionError("Failed")
        transcriber = self._create_mock_transcriber([])

        config = MultiSampleConfig(max_samples=3)

        with pytest.raises(TranscriptionError, match="All .* samples failed"):
            smart_detect(
                file_path=Path("/fake/video.mkv"),
                track_index=1,
                track_duration=7200.0,
                transcriber=transcriber,
                config=config,
            )

    @patch("video_policy_orchestrator.transcription.multi_sample.extract_audio_stream")
    def test_default_config(self, mock_extract):
        """Test using default config when none provided."""
        mock_extract.return_value = b"fake audio data"
        transcriber = self._create_mock_transcriber([("en", 0.95)])

        result = smart_detect(
            file_path=Path("/fake/video.mkv"),
            track_index=1,
            track_duration=7200.0,
            transcriber=transcriber,
            config=None,  # Use defaults
        )

        # Language is normalized to ISO 639-2/B
        assert result.language == "eng"

    @patch("video_policy_orchestrator.transcription.multi_sample.extract_audio_stream")
    def test_sample_positions_used(self, mock_extract):
        """Test that calculated sample positions are passed to extract."""
        mock_extract.return_value = b"fake audio data"
        transcriber = self._create_mock_transcriber(
            [
                ("en", 0.60),
                ("en", 0.65),
            ]
        )

        config = MultiSampleConfig(
            max_samples=2,
            sample_duration=30,
            confidence_threshold=0.85,
        )

        smart_detect(
            file_path=Path("/fake/video.mkv"),
            track_index=1,
            track_duration=7200.0,
            transcriber=transcriber,
            config=config,
        )

        # Check that extract was called with correct start_offset values
        calls = mock_extract.call_args_list
        assert len(calls) == 2
        # First call should be at position 0
        assert calls[0].kwargs.get("start_offset", 0) == 0.0
        # Second call should be at ~50% (3585.0)
        assert calls[1].kwargs.get("start_offset", 0) == pytest.approx(3585.0)
