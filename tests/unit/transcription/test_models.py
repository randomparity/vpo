"""Unit tests for transcription models."""

from datetime import datetime, timezone

import pytest

from video_policy_orchestrator.transcription.models import (
    COMMENTARY_KEYWORDS,
    TrackClassification,
    TranscriptionConfig,
    TranscriptionResult,
)


class TestTrackClassification:
    """Tests for TrackClassification enum."""

    def test_values(self):
        """Test enum values match expected strings."""
        assert TrackClassification.MAIN.value == "main"
        assert TrackClassification.COMMENTARY.value == "commentary"
        assert TrackClassification.ALTERNATE.value == "alternate"

    def test_from_string(self):
        """Test creating enum from string value."""
        assert TrackClassification("main") == TrackClassification.MAIN
        assert TrackClassification("commentary") == TrackClassification.COMMENTARY
        assert TrackClassification("alternate") == TrackClassification.ALTERNATE


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid transcription result."""
        now = datetime.now(timezone.utc)
        result = TranscriptionResult(
            track_id=1,
            detected_language="en",
            confidence_score=0.95,
            track_type=TrackClassification.MAIN,
            transcript_sample="Hello world...",
            plugin_name="whisper-local",
            created_at=now,
            updated_at=now,
        )
        assert result.track_id == 1
        assert result.detected_language == "en"
        assert result.confidence_score == 0.95
        assert result.track_type == TrackClassification.MAIN
        assert result.transcript_sample == "Hello world..."
        assert result.plugin_name == "whisper-local"

    def test_none_language(self):
        """Test result with no detected language."""
        now = datetime.now(timezone.utc)
        result = TranscriptionResult(
            track_id=1,
            detected_language=None,
            confidence_score=0.0,
            track_type=TrackClassification.MAIN,
            transcript_sample=None,
            plugin_name="test-plugin",
            created_at=now,
            updated_at=now,
        )
        assert result.detected_language is None
        assert result.transcript_sample is None

    def test_confidence_score_validation_too_low(self):
        """Test that confidence score below 0 raises error."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence_score must be between"):
            TranscriptionResult(
                track_id=1,
                detected_language="en",
                confidence_score=-0.1,
                track_type=TrackClassification.MAIN,
                transcript_sample=None,
                plugin_name="test",
                created_at=now,
                updated_at=now,
            )

    def test_confidence_score_validation_too_high(self):
        """Test that confidence score above 1 raises error."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence_score must be between"):
            TranscriptionResult(
                track_id=1,
                detected_language="en",
                confidence_score=1.5,
                track_type=TrackClassification.MAIN,
                transcript_sample=None,
                plugin_name="test",
                created_at=now,
                updated_at=now,
            )

    def test_confidence_score_boundary_values(self):
        """Test boundary values for confidence score."""
        now = datetime.now(timezone.utc)
        # 0.0 should be valid
        result_zero = TranscriptionResult(
            track_id=1,
            detected_language=None,
            confidence_score=0.0,
            track_type=TrackClassification.MAIN,
            transcript_sample=None,
            plugin_name="test",
            created_at=now,
            updated_at=now,
        )
        assert result_zero.confidence_score == 0.0

        # 1.0 should be valid
        result_one = TranscriptionResult(
            track_id=2,
            detected_language="en",
            confidence_score=1.0,
            track_type=TrackClassification.MAIN,
            transcript_sample=None,
            plugin_name="test",
            created_at=now,
            updated_at=now,
        )
        assert result_one.confidence_score == 1.0

    def test_empty_plugin_name_raises_error(self):
        """Test that empty plugin name raises error."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="plugin_name must be non-empty"):
            TranscriptionResult(
                track_id=1,
                detected_language="en",
                confidence_score=0.5,
                track_type=TrackClassification.MAIN,
                transcript_sample=None,
                plugin_name="",
                created_at=now,
                updated_at=now,
            )

    def test_from_record(self):
        """Test creating domain model from database record."""
        from video_policy_orchestrator.db.models import TranscriptionResultRecord

        record = TranscriptionResultRecord(
            id=1,
            track_id=42,
            detected_language="fr",
            confidence_score=0.87,
            track_type="commentary",
            transcript_sample="Bonjour...",
            plugin_name="whisper-local",
            created_at="2025-01-15T10:30:00+00:00",
            updated_at="2025-01-15T10:30:00+00:00",
        )

        result = TranscriptionResult.from_record(record)

        assert result.track_id == 42
        assert result.detected_language == "fr"
        assert result.confidence_score == 0.87
        assert result.track_type == TrackClassification.COMMENTARY
        assert result.transcript_sample == "Bonjour..."
        assert result.plugin_name == "whisper-local"
        assert result.created_at == datetime(
            2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc
        )


class TestTranscriptionConfig:
    """Tests for TranscriptionConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = TranscriptionConfig()
        assert config.enabled_plugin is None
        assert config.model_size == "base"
        assert config.sample_duration == 30
        assert config.gpu_enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = TranscriptionConfig(
            enabled_plugin="whisper-local",
            model_size="small",
            sample_duration=120,
            gpu_enabled=False,
        )
        assert config.enabled_plugin == "whisper-local"
        assert config.model_size == "small"
        assert config.sample_duration == 120
        assert config.gpu_enabled is False

    def test_valid_model_sizes(self):
        """Test all valid model sizes."""
        for size in ["tiny", "base", "small", "medium", "large"]:
            config = TranscriptionConfig(model_size=size)
            assert config.model_size == size

    def test_invalid_model_size(self):
        """Test that invalid model size raises error."""
        with pytest.raises(ValueError, match="model_size must be one of"):
            TranscriptionConfig(model_size="invalid")

    def test_negative_sample_duration(self):
        """Test that negative sample duration raises error."""
        with pytest.raises(ValueError, match="sample_duration must be non-negative"):
            TranscriptionConfig(sample_duration=-1)

    def test_zero_sample_duration_valid(self):
        """Test that zero sample duration is valid (means full track)."""
        config = TranscriptionConfig(sample_duration=0)
        assert config.sample_duration == 0


class TestCommentaryKeywords:
    """Tests for commentary detection keywords."""

    def test_keywords_exist(self):
        """Test that commentary keywords list is not empty."""
        assert len(COMMENTARY_KEYWORDS) > 0

    def test_expected_keywords_present(self):
        """Test that expected keywords are in the list."""
        expected = ["commentary", "director", "cast", "crew"]
        for keyword in expected:
            assert keyword in COMMENTARY_KEYWORDS
