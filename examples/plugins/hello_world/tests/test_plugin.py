"""Tests for Hello World VPO Plugin."""

import pytest

from hello_world import HelloWorldPlugin, plugin


class TestHelloWorldPlugin:
    """Test suite for HelloWorldPlugin."""

    def test_plugin_instance_exists(self):
        """Test that the plugin instance is created."""
        assert plugin is not None
        assert isinstance(plugin, HelloWorldPlugin)

    def test_plugin_manifest(self):
        """Test plugin manifest attributes."""
        assert plugin.name == "hello-world"
        assert plugin.version == "0.1.0"
        assert plugin.description == "Example plugin that greets scanned files"
        assert "file.scanned" in plugin.events

    def test_api_version_compatibility(self):
        """Test API version range is valid."""
        assert plugin.min_api_version == "1.0.0"
        assert plugin.max_api_version == "1.99.99"

    def test_on_file_scanned_returns_metadata(self):
        """Test on_file_scanned returns expected metadata."""
        # Create a mock event using the SDK testing utilities
        try:
            from vpo.plugin_sdk.testing import (
                create_file_scanned_event,
                mock_file_info,
                mock_tracks,
            )

            event = create_file_scanned_event(
                file_info=mock_file_info(path="/test/movie.mkv"),
                tracks=mock_tracks(video=1, audio=2, subtitle=1),
            )

            result = plugin.on_file_scanned(event)

            assert result is not None
            assert result["hello_world_analyzed"] is True
            assert result["hello_world_track_count"] == 4  # 1 + 2 + 1
        except ImportError:
            pytest.skip("VPO not installed - skipping integration test")

    def test_plugin_has_logger(self):
        """Test plugin has a configured logger."""
        assert hasattr(plugin, "logger")
        assert plugin.logger is not None


class TestPluginIntegration:
    """Integration tests requiring VPO to be installed."""

    @pytest.fixture
    def vpo_available(self):
        """Check if VPO is available."""
        try:
            import vpo.plugin_sdk  # noqa: F401

            return True
        except ImportError:
            pytest.skip("VPO not installed")
            return False

    def test_inherits_base_analyzer(self, vpo_available):
        """Test plugin inherits from BaseAnalyzerPlugin."""
        from vpo.plugin_sdk import BaseAnalyzerPlugin

        assert isinstance(plugin, BaseAnalyzerPlugin)
