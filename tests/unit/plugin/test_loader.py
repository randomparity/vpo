"""Unit tests for plugin loader."""

from pathlib import Path

import pytest

from video_policy_orchestrator.plugin.loader import (
    compute_plugin_hash,
    discover_directory_plugins,
    load_plugin_from_path,
    validate_plugin,
)


class TestComputePluginHash:
    """Tests for compute_plugin_hash function."""

    def test_hash_single_file(self, tmp_path: Path):
        """Hash a single Python file."""
        plugin_file = tmp_path / "plugin.py"
        plugin_file.write_text("plugin = 'test'")

        hash1 = compute_plugin_hash(plugin_file)
        assert len(hash1) == 64  # SHA-256 hex

        # Same content = same hash
        hash2 = compute_plugin_hash(plugin_file)
        assert hash1 == hash2

    def test_hash_changes_with_content(self, tmp_path: Path):
        """Hash changes when content changes."""
        plugin_file = tmp_path / "plugin.py"

        plugin_file.write_text("plugin = 'test1'")
        hash1 = compute_plugin_hash(plugin_file)

        plugin_file.write_text("plugin = 'test2'")
        hash2 = compute_plugin_hash(plugin_file)

        assert hash1 != hash2

    def test_hash_directory(self, tmp_path: Path):
        """Hash a plugin directory."""
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("plugin = 'test'")
        (plugin_dir / "utils.py").write_text("# utils")

        hash1 = compute_plugin_hash(plugin_dir)
        assert len(hash1) == 64

    def test_hash_nonexistent_raises(self, tmp_path: Path):
        """Non-existent path raises ValueError."""
        with pytest.raises(ValueError, match="Path does not exist"):
            compute_plugin_hash(tmp_path / "nonexistent")


class TestDiscoverDirectoryPlugins:
    """Tests for discover_directory_plugins function."""

    def test_discovers_py_files(self, tmp_path: Path):
        """Discovers .py files in plugin directory."""
        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text("plugin = 'test'")

        discovered = discover_directory_plugins([tmp_path])

        assert len(discovered) == 1
        assert discovered[0][0] == plugin_file
        assert discovered[0][1] == "my_plugin"

    def test_discovers_packages(self, tmp_path: Path):
        """Discovers package directories with __init__.py."""
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("plugin = 'test'")

        discovered = discover_directory_plugins([tmp_path])

        assert len(discovered) == 1
        assert discovered[0][0] == plugin_dir
        assert discovered[0][1] == "my_plugin"

    def test_ignores_underscore_files(self, tmp_path: Path):
        """Ignores files starting with underscore."""
        (tmp_path / "_private.py").write_text("plugin = 'test'")
        (tmp_path / "__pycache__").mkdir()

        discovered = discover_directory_plugins([tmp_path])
        assert len(discovered) == 0

    def test_handles_nonexistent_directory(self, tmp_path: Path):
        """Handles non-existent plugin directory gracefully."""
        discovered = discover_directory_plugins([tmp_path / "nonexistent"])
        assert discovered == []


class TestLoadPluginFromPath:
    """Tests for load_plugin_from_path function."""

    def test_loads_single_file_plugin(self, tmp_path: Path):
        """Loads a plugin from a single .py file."""
        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text("""
class MyPlugin:
    name = "my-plugin"
    version = "1.0.0"
    events = ["file.scanned"]

    def on_file_scanned(self, event):
        return None

    def on_policy_evaluate(self, event):
        pass

    def on_plan_complete(self, event):
        pass

plugin = MyPlugin()
""")

        plugin_obj = load_plugin_from_path(plugin_file, "my_plugin")
        assert plugin_obj.name == "my-plugin"
        assert plugin_obj.version == "1.0.0"

    def test_loads_package_plugin(self, tmp_path: Path):
        """Loads a plugin from a package directory."""
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("""
class MyPlugin:
    name = "my-plugin"
    version = "1.0.0"
    events = ["file.scanned"]

    def on_file_scanned(self, event):
        return None

    def on_policy_evaluate(self, event):
        pass

    def on_plan_complete(self, event):
        pass

plugin = MyPlugin()
""")

        plugin_obj = load_plugin_from_path(plugin_dir, "my_plugin")
        assert plugin_obj.name == "my-plugin"

    def test_raises_if_no_plugin_variable(self, tmp_path: Path):
        """Raises error if module has no 'plugin' variable."""
        from video_policy_orchestrator.plugin.exceptions import PluginLoadError

        plugin_file = tmp_path / "bad_plugin.py"
        plugin_file.write_text("x = 1")

        with pytest.raises(
            PluginLoadError, match="does not export a 'plugin' variable"
        ):
            load_plugin_from_path(plugin_file, "bad_plugin")


class TestValidatePlugin:
    """Tests for validate_plugin function."""

    def test_valid_analyzer_plugin(self):
        """Valid analyzer plugin passes validation."""

        class ValidPlugin:
            name = "valid-plugin"
            version = "1.0.0"
            events = ["file.scanned"]

            def on_file_scanned(self, event):
                return None

            def on_policy_evaluate(self, event):
                pass

            def on_plan_complete(self, event):
                pass

        errors = validate_plugin(ValidPlugin, "valid-plugin")
        assert errors == []

    def test_missing_name_fails(self):
        """Plugin without name attribute fails validation."""

        class MissingName:
            version = "1.0.0"
            events = ["file.scanned"]

            def on_file_scanned(self, event):
                return None

            def on_policy_evaluate(self, event):
                pass

            def on_plan_complete(self, event):
                pass

        errors = validate_plugin(MissingName, "test")
        assert "Missing required attribute: name" in errors

    def test_missing_events_fails(self):
        """Plugin without events attribute fails validation."""

        class MissingEvents:
            name = "test"
            version = "1.0.0"

            def on_file_scanned(self, event):
                return None

            def on_policy_evaluate(self, event):
                pass

            def on_plan_complete(self, event):
                pass

        errors = validate_plugin(MissingEvents, "test")
        assert "Missing required attribute: events" in errors

    def test_non_protocol_fails(self):
        """Class not implementing protocol fails validation."""

        class NotAPlugin:
            name = "not-a-plugin"
            version = "1.0.0"
            events = ["file.scanned"]

        errors = validate_plugin(NotAPlugin, "test")
        assert any("protocol" in e.lower() for e in errors)
