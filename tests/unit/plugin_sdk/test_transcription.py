"""Unit tests for plugin_sdk transcription module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from video_policy_orchestrator.plugin_sdk.transcription import (
    TrackClassification,
    TranscriptionPluginBase,
    TranscriptionResult,
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
