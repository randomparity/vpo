"""Unit tests for Whisper transcription plugin."""

from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.plugins.whisper_transcriber import (
    PluginDependencyError,
    WhisperTranscriptionPlugin,
)
from video_policy_orchestrator.transcription.interface import TranscriptionError
from video_policy_orchestrator.transcription.models import (
    TranscriptionConfig,
)


class TestWhisperTranscriptionPlugin:
    """Tests for WhisperTranscriptionPlugin class."""

    def test_name_and_version(self):
        """Test plugin name and version properties."""
        plugin = WhisperTranscriptionPlugin()
        assert plugin.name == "whisper-local"
        assert plugin.version == "1.0.0"

    def test_default_config(self):
        """Test plugin with default configuration."""
        plugin = WhisperTranscriptionPlugin()
        assert plugin._config.model_size == "base"
        assert plugin._config.gpu_enabled is True

    def test_custom_config(self):
        """Test plugin with custom configuration."""
        config = TranscriptionConfig(
            model_size="small",
            gpu_enabled=False,
            sample_duration=30,
        )
        plugin = WhisperTranscriptionPlugin(config=config)
        assert plugin._config.model_size == "small"
        assert plugin._config.gpu_enabled is False
        assert plugin._config.sample_duration == 30

    def test_supports_feature(self):
        """Test supports_feature method."""
        plugin = WhisperTranscriptionPlugin()
        assert plugin.supports_feature("transcription") is True
        assert plugin.supports_feature("language_detection") is True
        assert plugin.supports_feature("gpu") is True

    def test_supports_feature_gpu_disabled(self):
        """Test supports_feature when GPU is disabled."""
        config = TranscriptionConfig(gpu_enabled=False)
        plugin = WhisperTranscriptionPlugin(config=config)
        assert plugin.supports_feature("gpu") is False

    def test_supports_unknown_feature(self):
        """Test supports_feature with unknown feature."""
        plugin = WhisperTranscriptionPlugin()
        assert plugin.supports_feature("unknown") is False

    @patch("video_policy_orchestrator.plugins.whisper_transcriber.plugin._get_whisper")
    def test_detect_language_whisper_not_installed(self, mock_get_whisper):
        """Test detect_language when whisper is not installed."""
        mock_get_whisper.side_effect = PluginDependencyError("Not installed")
        plugin = WhisperTranscriptionPlugin()

        with pytest.raises(PluginDependencyError, match="Not installed"):
            plugin.detect_language(b"fake_audio_data")

    @patch("video_policy_orchestrator.plugins.whisper_transcriber.plugin._get_whisper")
    def test_transcribe_whisper_not_installed(self, mock_get_whisper):
        """Test transcribe when whisper is not installed."""
        mock_get_whisper.side_effect = PluginDependencyError("Not installed")
        plugin = WhisperTranscriptionPlugin()

        with pytest.raises(PluginDependencyError, match="Not installed"):
            plugin.transcribe(b"fake_audio_data")


class TestPluginDependencyError:
    """Tests for PluginDependencyError exception."""

    def test_is_transcription_error(self):
        """Test that PluginDependencyError is a TranscriptionError."""
        assert issubclass(PluginDependencyError, TranscriptionError)

    def test_error_message(self):
        """Test error message."""
        error = PluginDependencyError("Package not installed")
        assert str(error) == "Package not installed"


class TestWhisperPluginModelLoading:
    """Tests for Whisper plugin model loading behavior."""

    @patch("video_policy_orchestrator.plugins.whisper_transcriber.plugin._get_whisper")
    def test_model_lazy_loading(self, mock_get_whisper):
        """Test that model is loaded lazily."""
        mock_whisper = MagicMock()
        mock_get_whisper.return_value = mock_whisper
        mock_model = MagicMock()
        mock_model.device = "cpu"
        mock_whisper.load_model.return_value = mock_model

        plugin = WhisperTranscriptionPlugin()

        # Model should not be loaded yet
        assert plugin._model is None
        mock_whisper.load_model.assert_not_called()

        # Trigger model loading
        plugin._load_model()

        # Model should now be loaded
        mock_whisper.load_model.assert_called_once()

    @patch("video_policy_orchestrator.plugins.whisper_transcriber.plugin._get_whisper")
    def test_model_caching(self, mock_get_whisper):
        """Test that model is cached after first load."""
        mock_whisper = MagicMock()
        mock_get_whisper.return_value = mock_whisper
        mock_model = MagicMock()
        mock_model.device = "cpu"
        mock_whisper.load_model.return_value = mock_model

        plugin = WhisperTranscriptionPlugin()

        # Load model twice
        plugin._load_model()
        plugin._load_model()

        # Should only call load_model once
        assert mock_whisper.load_model.call_count == 1

    @patch("video_policy_orchestrator.plugins.whisper_transcriber.plugin._get_whisper")
    def test_model_uses_configured_model_size(self, mock_get_whisper):
        """Test that model loading uses configured model size."""
        mock_whisper = MagicMock()
        mock_get_whisper.return_value = mock_whisper
        mock_model = MagicMock()
        mock_model.device = "cpu"
        mock_whisper.load_model.return_value = mock_model

        config = TranscriptionConfig(model_size="large")
        plugin = WhisperTranscriptionPlugin(config=config)
        plugin._load_model()

        mock_whisper.load_model.assert_called_once_with("large", device="cpu")

    @patch("video_policy_orchestrator.plugins.whisper_transcriber.plugin._get_whisper")
    def test_model_cpu_fallback_when_no_torch(self, mock_get_whisper):
        """Test that model falls back to CPU when torch is not available."""
        mock_whisper = MagicMock()
        mock_get_whisper.return_value = mock_whisper
        mock_model = MagicMock()
        mock_model.device = "cpu"
        mock_whisper.load_model.return_value = mock_model

        # torch import will fail
        with patch.dict("sys.modules", {"torch": None}):
            plugin = WhisperTranscriptionPlugin()
            plugin._load_model()

        # Should fall back to CPU
        mock_whisper.load_model.assert_called_with("base", device="cpu")
