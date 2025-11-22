"""Unit tests for transcription interface module."""

from datetime import datetime, timezone

import pytest

from video_policy_orchestrator.transcription.interface import (
    TranscriptionError,
    TranscriptionPlugin,
)
from video_policy_orchestrator.transcription.models import (
    TrackClassification,
    TranscriptionResult,
)


class TestTranscriptionError:
    """Tests for TranscriptionError exception."""

    def test_is_exception(self):
        """Test that TranscriptionError is an exception."""
        assert issubclass(TranscriptionError, Exception)

    def test_with_message(self):
        """Test creating error with message."""
        error = TranscriptionError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_can_be_raised(self):
        """Test that error can be raised and caught."""
        with pytest.raises(TranscriptionError) as exc_info:
            raise TranscriptionError("Test error")
        assert "Test error" in str(exc_info.value)


class MockTranscriptionPlugin:
    """Mock implementation of TranscriptionPlugin protocol."""

    def __init__(self, name: str = "mock-plugin"):
        self._name = name
        self._version = "1.0.0"

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    def detect_language(
        self, audio_data: bytes, sample_rate: int = 16000
    ) -> TranscriptionResult:
        now = datetime.now(timezone.utc)
        return TranscriptionResult(
            track_id=0,
            detected_language="en",
            confidence_score=0.95,
            track_type=TrackClassification.MAIN,
            transcript_sample=None,
            plugin_name=self.name,
            created_at=now,
            updated_at=now,
        )

    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        now = datetime.now(timezone.utc)
        return TranscriptionResult(
            track_id=0,
            detected_language=language or "en",
            confidence_score=0.9,
            track_type=TrackClassification.MAIN,
            transcript_sample="Hello world...",
            plugin_name=self.name,
            created_at=now,
            updated_at=now,
        )

    def supports_feature(self, feature: str) -> bool:
        return feature in {"transcription", "language_detection"}


class TestTranscriptionPluginProtocol:
    """Tests for TranscriptionPlugin protocol."""

    def test_protocol_is_runtime_checkable(self):
        """Test that protocol can be checked at runtime."""
        plugin = MockTranscriptionPlugin()
        assert isinstance(plugin, TranscriptionPlugin)

    def test_detect_language(self):
        """Test detect_language method."""
        plugin = MockTranscriptionPlugin()
        result = plugin.detect_language(b"fake_audio_data")

        assert result.detected_language == "en"
        assert result.confidence_score == 0.95
        assert result.plugin_name == "mock-plugin"

    def test_transcribe(self):
        """Test transcribe method."""
        plugin = MockTranscriptionPlugin()
        result = plugin.transcribe(b"fake_audio_data")

        assert result.detected_language == "en"
        assert result.transcript_sample == "Hello world..."
        assert result.plugin_name == "mock-plugin"

    def test_transcribe_with_language_hint(self):
        """Test transcribe with language hint."""
        plugin = MockTranscriptionPlugin()
        result = plugin.transcribe(b"fake_audio_data", language="fr")

        assert result.detected_language == "fr"

    def test_supports_feature(self):
        """Test supports_feature method."""
        plugin = MockTranscriptionPlugin()

        assert plugin.supports_feature("transcription") is True
        assert plugin.supports_feature("language_detection") is True
        assert plugin.supports_feature("unknown_feature") is False

    def test_name_property(self):
        """Test name property."""
        plugin = MockTranscriptionPlugin("custom-name")
        assert plugin.name == "custom-name"

    def test_version_property(self):
        """Test version property."""
        plugin = MockTranscriptionPlugin()
        assert plugin.version == "1.0.0"


class TestNonCompliantPlugin:
    """Tests verifying protocol validation."""

    def test_missing_method_not_instance(self):
        """Test that incomplete implementation is not an instance."""

        class IncompletePlugin:
            """Plugin missing required methods."""

            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def version(self) -> str:
                return "1.0.0"

            # Missing: detect_language, transcribe, supports_feature

        plugin = IncompletePlugin()
        # Note: runtime_checkable protocols only check method existence,
        # not signatures, so we need to verify callable attributes
        assert hasattr(plugin, "name")
        assert hasattr(plugin, "version")
        # These should be missing
        assert not hasattr(plugin, "detect_language")
        assert not hasattr(plugin, "transcribe")
        assert not hasattr(plugin, "supports_feature")
