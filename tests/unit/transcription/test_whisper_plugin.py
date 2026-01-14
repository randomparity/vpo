"""Unit tests for Whisper transcription plugin."""

from unittest.mock import MagicMock, patch

import pytest

from vpo.plugins.whisper_transcriber import (
    PluginDependencyError,
    WhisperTranscriptionPlugin,
)
from vpo.transcription.interface import TranscriptionError
from vpo.transcription.models import (
    TranscriptionConfig,
)


class TestWhisperTranscriptionPlugin:
    """Tests for WhisperTranscriptionPlugin class."""

    def test_name_and_version(self):
        """Test plugin name and version attributes."""
        plugin = WhisperTranscriptionPlugin()
        assert plugin.name == "whisper-local"
        assert plugin.version == "1.0.0"

    def test_plugin_metadata_class_attributes(self):
        """Test that plugin metadata are class attributes for plugin system."""
        # These must be class attributes, not instance properties
        assert hasattr(WhisperTranscriptionPlugin, "name")
        assert hasattr(WhisperTranscriptionPlugin, "version")
        assert hasattr(WhisperTranscriptionPlugin, "description")
        assert hasattr(WhisperTranscriptionPlugin, "author")
        assert hasattr(WhisperTranscriptionPlugin, "min_api_version")
        assert hasattr(WhisperTranscriptionPlugin, "max_api_version")
        assert hasattr(WhisperTranscriptionPlugin, "events")

        # Verify values
        assert WhisperTranscriptionPlugin.name == "whisper-local"
        assert WhisperTranscriptionPlugin.version == "1.0.0"
        assert WhisperTranscriptionPlugin.description == (
            "Audio transcription and language detection using OpenAI Whisper"
        )
        assert WhisperTranscriptionPlugin.author == "VPO Team"
        assert WhisperTranscriptionPlugin.min_api_version == "1.0.0"
        assert WhisperTranscriptionPlugin.max_api_version == "1.99.99"
        assert WhisperTranscriptionPlugin.events == ["transcription.requested"]

    def test_events_attribute(self):
        """Test plugin events subscription."""
        plugin = WhisperTranscriptionPlugin()
        assert plugin.events == ["transcription.requested"]

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

    @patch("vpo.plugins.whisper_transcriber.plugin._get_whisper")
    def test_detect_language_whisper_not_installed(self, mock_get_whisper):
        """Test detect_language when whisper is not installed."""
        mock_get_whisper.side_effect = PluginDependencyError("Not installed")
        plugin = WhisperTranscriptionPlugin()

        with pytest.raises(PluginDependencyError, match="Not installed"):
            plugin.detect_language(b"fake_audio_data")

    @patch("vpo.plugins.whisper_transcriber.plugin._get_whisper")
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

    @patch("vpo.plugins.whisper_transcriber.plugin._get_whisper")
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

    @patch("vpo.plugins.whisper_transcriber.plugin._get_whisper")
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

    @patch("vpo.plugins.whisper_transcriber.plugin._get_whisper")
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

    @patch("vpo.plugins.whisper_transcriber.plugin._get_whisper")
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


class TestWhisperPluginInstance:
    """Tests for plugin_instance module-level export."""

    def test_plugin_instance_exported(self):
        """Test that plugin_instance is exported from package."""
        from vpo.plugins.whisper_transcriber import (
            plugin_instance,
        )

        assert plugin_instance is not None
        assert isinstance(plugin_instance, WhisperTranscriptionPlugin)

    def test_plugin_instance_has_required_attributes(self):
        """Test that plugin_instance has all required plugin attributes."""
        from vpo.plugins.whisper_transcriber import (
            plugin_instance,
        )

        # Required for plugin system
        assert hasattr(plugin_instance, "name")
        assert hasattr(plugin_instance, "version")
        assert hasattr(plugin_instance, "events")
        assert hasattr(plugin_instance, "on_transcription_requested")

    def test_plugin_instance_is_same_object(self):
        """Verify plugin_instance is consistent across imports."""
        from vpo.plugins.whisper_transcriber import (
            plugin_instance as p1,
        )
        from vpo.plugins.whisper_transcriber import (
            plugin_instance as p2,
        )

        assert p1 is p2


class TestWhisperPluginRegistration:
    """Tests for whisper plugin registration in PluginRegistry."""

    def test_load_builtin_plugins_includes_whisper(self):
        """Test that load_builtin_plugins loads whisper when available."""
        from vpo.plugin.registry import PluginRegistry

        registry = PluginRegistry()
        loaded = registry.load_builtin_plugins()

        # Should load at least policy-engine, and whisper if available
        plugin_names = [p.name for p in loaded]
        assert "policy-engine" in plugin_names

        # Whisper should be loaded since we can import it
        assert "whisper-local" in plugin_names

    def test_whisper_plugin_is_builtin(self):
        """Test that whisper plugin is marked as built-in."""
        from vpo.plugin.manifest import PluginSource
        from vpo.plugin.registry import PluginRegistry

        registry = PluginRegistry()
        registry.load_builtin_plugins()

        whisper = registry.get("whisper-local")
        assert whisper is not None
        assert whisper.source == PluginSource.BUILTIN

    def test_whisper_plugin_events_registered(self):
        """Test that whisper plugin events are properly registered."""
        from vpo.plugin.registry import PluginRegistry

        registry = PluginRegistry()
        registry.load_builtin_plugins()

        # Should be findable by event
        transcription_plugins = registry.get_by_event("transcription.requested")
        plugin_names = [p.name for p in transcription_plugins]
        assert "whisper-local" in plugin_names

    def test_load_builtin_plugins_graceful_fallback_on_import_error(self, monkeypatch):
        """Test that whisper plugin is gracefully skipped when import fails."""
        import builtins
        import sys

        from vpo.plugin.registry import PluginRegistry

        # Clear any cached imports of whisper_transcriber
        modules_to_remove = [key for key in sys.modules if "whisper_transcriber" in key]
        for mod in modules_to_remove:
            del sys.modules[mod]

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "whisper_transcriber" in name:
                raise ImportError("Mocked: whisper_transcriber not available")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        registry = PluginRegistry()
        loaded = registry.load_builtin_plugins()

        # Should still load policy-engine
        plugin_names = [p.name for p in loaded]
        assert "policy-engine" in plugin_names
        assert "whisper-local" not in plugin_names
