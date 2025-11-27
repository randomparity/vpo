"""Tests for transcription/factory.py module."""

from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.transcription.factory import (
    TranscriberFactory,
    TranscriberUnavailableError,
    get_transcriber,
    get_transcriber_or_raise,
)

# Patch location for get_registry (imported inside the function)
REGISTRY_PATCH = "video_policy_orchestrator.transcription.registry.get_registry"


@pytest.fixture(autouse=True)
def reset_factory():
    """Reset the factory state before and after each test."""
    TranscriberFactory.reset()
    yield
    TranscriberFactory.reset()


class TestTranscriberUnavailableError:
    """Tests for TranscriberUnavailableError exception."""

    def test_error_message(self) -> None:
        """Error should include reason in message."""
        error = TranscriberUnavailableError("No plugins available")
        assert "No plugins available" in str(error)
        assert error.reason == "No plugins available"


class TestTranscriberFactory:
    """Tests for TranscriberFactory class."""

    def test_get_transcriber_returns_none_when_no_plugins(self) -> None:
        """Should return None when no plugins available."""
        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = None
            mock_get_registry.return_value = mock_registry

            result = TranscriberFactory.get_transcriber()
            assert result is None

    def test_get_transcriber_returns_plugin(self) -> None:
        """Should return plugin when available."""
        mock_plugin = MagicMock()
        mock_plugin.name = "mock-transcriber"
        mock_plugin.version = "1.0.0"
        mock_plugin.supports_feature.return_value = True

        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = mock_plugin
            mock_get_registry.return_value = mock_registry

            result = TranscriberFactory.get_transcriber()
            assert result is mock_plugin

    def test_get_transcriber_caches_result(self) -> None:
        """Should cache and reuse the same plugin instance."""
        mock_plugin = MagicMock()
        mock_plugin.name = "mock-transcriber"
        mock_plugin.version = "1.0.0"
        mock_plugin.supports_feature.return_value = True

        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = mock_plugin
            mock_get_registry.return_value = mock_registry

            result1 = TranscriberFactory.get_transcriber()
            result2 = TranscriberFactory.get_transcriber()

            assert result1 is result2
            # Registry should only be called once
            assert mock_get_registry.call_count == 1

    def test_get_transcriber_require_multi_language(self) -> None:
        """Should check for multi_language_detection feature when required."""
        mock_plugin = MagicMock()
        mock_plugin.name = "mock-transcriber"
        mock_plugin.version = "1.0.0"
        mock_plugin.supports_feature.return_value = False

        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = mock_plugin
            mock_get_registry.return_value = mock_registry

            result = TranscriberFactory.get_transcriber(require_multi_language=True)
            assert result is None
            mock_plugin.supports_feature.assert_called_with("multi_language_detection")

    def test_get_transcriber_or_raise_raises_on_none(self) -> None:
        """Should raise TranscriberUnavailableError when no plugin."""
        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = None
            mock_get_registry.return_value = mock_registry

            with pytest.raises(TranscriberUnavailableError) as exc_info:
                TranscriberFactory.get_transcriber_or_raise()

            assert "unavailable" in str(exc_info.value).lower()

    def test_get_transcriber_or_raise_returns_plugin(self) -> None:
        """Should return plugin when available."""
        mock_plugin = MagicMock()
        mock_plugin.name = "mock-transcriber"
        mock_plugin.version = "1.0.0"
        mock_plugin.supports_feature.return_value = True

        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = mock_plugin
            mock_get_registry.return_value = mock_registry

            result = TranscriberFactory.get_transcriber_or_raise()
            assert result is mock_plugin

    def test_is_available(self) -> None:
        """is_available should return True when plugin available."""
        mock_plugin = MagicMock()
        mock_plugin.name = "mock-transcriber"
        mock_plugin.version = "1.0.0"
        mock_plugin.supports_feature.return_value = True

        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = mock_plugin
            mock_get_registry.return_value = mock_registry

            assert TranscriberFactory.is_available() is True

    def test_get_error_returns_error_message(self) -> None:
        """get_error should return initialization error if any."""
        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = None
            mock_get_registry.return_value = mock_registry

            TranscriberFactory.get_transcriber()
            error = TranscriberFactory.get_error()
            assert error is not None

    def test_reset_clears_state(self) -> None:
        """reset should clear cached instance and error."""
        mock_plugin = MagicMock()
        mock_plugin.name = "mock-transcriber"
        mock_plugin.version = "1.0.0"
        mock_plugin.supports_feature.return_value = True

        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = mock_plugin
            mock_get_registry.return_value = mock_registry

            TranscriberFactory.get_transcriber()
            TranscriberFactory.reset()

            assert TranscriberFactory._instance is None
            assert TranscriberFactory._initialization_error is None
            assert TranscriberFactory._initialized is False


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_transcriber_function(self) -> None:
        """get_transcriber should delegate to TranscriberFactory."""
        mock_plugin = MagicMock()
        mock_plugin.name = "mock-transcriber"
        mock_plugin.version = "1.0.0"
        mock_plugin.supports_feature.return_value = True

        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = mock_plugin
            mock_get_registry.return_value = mock_registry

            result = get_transcriber()
            assert result is mock_plugin

    def test_get_transcriber_or_raise_function(self) -> None:
        """get_transcriber_or_raise should delegate to TranscriberFactory."""
        with patch(REGISTRY_PATCH) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_default.return_value = None
            mock_get_registry.return_value = mock_registry

            with pytest.raises(TranscriberUnavailableError):
                get_transcriber_or_raise()
