"""Unit tests for transcription plugin registry."""

from unittest.mock import MagicMock

import pytest

from video_policy_orchestrator.transcription.registry import (
    PluginNotFoundError,
    TranscriptionRegistry,
)


def _create_mock_plugin(name: str = "test-plugin") -> MagicMock:
    """Create a mock transcription plugin."""
    plugin = MagicMock()
    plugin.name = name
    plugin.version = "1.0.0"
    return plugin


class TestTranscriptionRegistry:
    """Tests for TranscriptionRegistry class."""

    def test_register_plugin(self):
        """Test registering a plugin."""
        registry = TranscriptionRegistry()
        plugin = _create_mock_plugin()

        registry.register(plugin)

        assert len(registry) == 1
        assert registry.has_plugin("test-plugin")

    def test_register_multiple_plugins(self):
        """Test registering multiple plugins."""
        registry = TranscriptionRegistry()
        plugin1 = _create_mock_plugin("plugin-1")
        plugin2 = _create_mock_plugin("plugin-2")

        registry.register(plugin1)
        registry.register(plugin2)

        assert len(registry) == 2
        assert registry.has_plugin("plugin-1")
        assert registry.has_plugin("plugin-2")

    def test_get_registered_plugin(self):
        """Test retrieving a registered plugin."""
        registry = TranscriptionRegistry()
        plugin = _create_mock_plugin()
        registry.register(plugin)

        result = registry.get("test-plugin")

        assert result is plugin

    def test_get_nonexistent_plugin(self):
        """Test that getting nonexistent plugin raises error."""
        registry = TranscriptionRegistry()

        with pytest.raises(PluginNotFoundError, match="not found"):
            registry.get("nonexistent")

    def test_get_default_returns_first(self):
        """Test that get_default returns first registered plugin."""
        registry = TranscriptionRegistry()
        plugin1 = _create_mock_plugin("plugin-1")
        plugin2 = _create_mock_plugin("plugin-2")

        registry.register(plugin1)
        registry.register(plugin2)

        result = registry.get_default()

        assert result is plugin1

    def test_get_default_empty_registry(self):
        """Test that get_default returns None for empty registry."""
        registry = TranscriptionRegistry()

        result = registry.get_default()

        assert result is None

    def test_list_plugins(self):
        """Test listing registered plugin names."""
        registry = TranscriptionRegistry()
        registry.register(_create_mock_plugin("plugin-a"))
        registry.register(_create_mock_plugin("plugin-b"))

        names = registry.list_plugins()

        assert set(names) == {"plugin-a", "plugin-b"}

    def test_unregister_plugin(self):
        """Test unregistering a plugin."""
        registry = TranscriptionRegistry()
        plugin = _create_mock_plugin()
        registry.register(plugin)

        result = registry.unregister("test-plugin")

        assert result is True
        assert len(registry) == 0
        assert not registry.has_plugin("test-plugin")

    def test_unregister_nonexistent(self):
        """Test unregistering a plugin that doesn't exist."""
        registry = TranscriptionRegistry()

        result = registry.unregister("nonexistent")

        assert result is False

    def test_has_plugin(self):
        """Test has_plugin method."""
        registry = TranscriptionRegistry()
        registry.register(_create_mock_plugin())

        assert registry.has_plugin("test-plugin") is True
        assert registry.has_plugin("nonexistent") is False

    def test_len(self):
        """Test __len__ method."""
        registry = TranscriptionRegistry()

        assert len(registry) == 0

        registry.register(_create_mock_plugin("p1"))
        assert len(registry) == 1

        registry.register(_create_mock_plugin("p2"))
        assert len(registry) == 2


class TestPluginNotFoundError:
    """Tests for PluginNotFoundError exception."""

    def test_error_message(self):
        """Test that error message includes available plugins."""
        registry = TranscriptionRegistry()
        registry.register(_create_mock_plugin("available-plugin"))

        try:
            registry.get("missing")
        except PluginNotFoundError as e:
            assert "missing" in str(e)
            assert "available-plugin" in str(e)
