"""Integration tests for plugin CLI commands.

These tests verify the CLI commands for plugin management work correctly
using click's CliRunner.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from vpo.cli import main
from vpo.db.schema import create_schema

# Sample valid plugin code for testing
VALID_ANALYZER_PLUGIN = '''
"""Test analyzer plugin."""

class TestAnalyzerPlugin:
    """A valid analyzer plugin for testing."""

    name = "test-analyzer"
    version = "1.0.0"
    description = "Test analyzer plugin"
    events = ["file.scanned"]
    min_api_version = "1.0.0"
    max_api_version = "1.99.99"

    def on_file_scanned(self, event):
        return None

    def on_policy_evaluate(self, event):
        pass

    def on_plan_complete(self, event):
        pass

plugin = TestAnalyzerPlugin()
'''


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """Create a temporary plugin directory."""
    plugin_path = tmp_path / "plugins"
    plugin_path.mkdir()
    return plugin_path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a database with schema."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    create_schema(conn)
    conn.close()
    return db_file


class TestPluginListCommand:
    """Tests for 'vpo plugins list' command."""

    def test_plugins_list_no_plugins(
        self, runner: CliRunner, plugin_dir: Path, monkeypatch
    ):
        """List plugins when no plugins exist."""
        # Patch the plugin dirs to use our empty test dir
        monkeypatch.setattr(
            "vpo.config.loader.DEFAULT_PLUGINS_DIR",
            plugin_dir,
        )

        result = runner.invoke(main, ["plugins", "list"])

        assert result.exit_code == 0
        has_no_plugins = "No plugins found" in result.output
        has_installed = "Installed Plugins" in result.output
        assert has_no_plugins or has_installed

    def test_plugins_list_with_plugin(
        self, runner: CliRunner, plugin_dir: Path, monkeypatch
    ):
        """List plugins when a plugin exists."""
        # Create a plugin file
        plugin_file = plugin_dir / "my_analyzer.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        # Patch config to use our test directory
        def mock_get_config():
            from vpo.config.models import PluginConfig, VPOConfig

            return VPOConfig(plugins=PluginConfig(plugin_dirs=[plugin_dir]))

        monkeypatch.setattr("vpo.cli.plugins.get_config", mock_get_config)

        result = runner.invoke(main, ["plugins", "list"])

        assert result.exit_code == 0
        assert "test-analyzer" in result.output

    def test_plugins_list_verbose(
        self, runner: CliRunner, plugin_dir: Path, monkeypatch
    ):
        """List plugins with verbose output."""
        # Create a plugin file
        plugin_file = plugin_dir / "my_analyzer.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        # Patch config to use our test directory
        def mock_get_config():
            from vpo.config.models import PluginConfig, VPOConfig

            return VPOConfig(plugins=PluginConfig(plugin_dirs=[plugin_dir]))

        monkeypatch.setattr("vpo.cli.plugins.get_config", mock_get_config)

        result = runner.invoke(main, ["plugins", "list", "-v"])

        assert result.exit_code == 0
        assert "test-analyzer" in result.output
        assert "1.0.0" in result.output
        # Verbose mode shows more details
        assert "Type:" in result.output or "analyzer" in result.output


class TestPluginAcknowledgeCommand:
    """Tests for 'vpo plugins acknowledge' command."""

    def test_acknowledge_plugin_not_found(self, runner: CliRunner, monkeypatch):
        """Acknowledge a plugin that doesn't exist."""
        # Create in-memory database for the test
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        def mock_get_config():
            from vpo.config.models import PluginConfig, VPOConfig

            return VPOConfig(plugins=PluginConfig(plugin_dirs=[]))

        monkeypatch.setattr("vpo.cli.plugins.get_config", mock_get_config)

        result = runner.invoke(
            main,
            ["plugins", "acknowledge", "nonexistent-plugin"],
            obj={"db_conn": conn},
        )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_acknowledge_requires_db(
        self, runner: CliRunner, plugin_dir: Path, monkeypatch
    ):
        """Acknowledge requires database connection."""
        # Create a plugin file
        plugin_file = plugin_dir / "my_analyzer.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        def mock_get_config():
            from vpo.config.models import PluginConfig, VPOConfig

            return VPOConfig(plugins=PluginConfig(plugin_dirs=[plugin_dir]))

        monkeypatch.setattr("vpo.cli.plugins.get_config", mock_get_config)

        # Ensure db_conn is None (simulating missing database)
        result = runner.invoke(main, ["plugins", "acknowledge", "test-analyzer"])

        # Should fail because db_conn is None in the test context
        assert result.exit_code == 1
        has_db_error = "database" in result.output.lower()
        has_not_found = "not found" in result.output.lower()
        assert has_db_error or has_not_found


class TestPluginEnableDisableCommands:
    """Tests for 'vpo plugins enable/disable' commands."""

    def test_enable_plugin(self, runner: CliRunner):
        """Enable a plugin (placeholder command)."""
        result = runner.invoke(main, ["plugins", "enable", "some-plugin"])

        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

    def test_disable_plugin(self, runner: CliRunner):
        """Disable a plugin (placeholder command)."""
        result = runner.invoke(main, ["plugins", "disable", "some-plugin"])

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()


class TestForceLoadPluginsFlag:
    """Tests for --force-load-plugins global flag."""

    def test_force_load_flag_sets_context(self, runner: CliRunner):
        """The --force-load-plugins flag should set context correctly."""
        # This tests that the flag is parsed correctly
        result = runner.invoke(main, ["--force-load-plugins", "plugins", "list"])

        # Should not error out due to the flag
        assert result.exit_code == 0


class TestPluginListInvalidPlugin:
    """Tests for listing plugins when some are invalid."""

    def test_list_with_invalid_plugin(
        self, runner: CliRunner, plugin_dir: Path, monkeypatch
    ):
        """List plugins when one plugin is invalid."""
        # Create an invalid plugin file (missing required attributes)
        invalid_plugin = plugin_dir / "bad_plugin.py"
        invalid_plugin.write_text(
            """
class BadPlugin:
    # Missing name, version, events
    pass

plugin = BadPlugin()
"""
        )

        # Create a valid plugin too
        valid_plugin = plugin_dir / "good_plugin.py"
        valid_plugin.write_text(VALID_ANALYZER_PLUGIN)

        def mock_get_config():
            from vpo.config.models import PluginConfig, VPOConfig

            return VPOConfig(plugins=PluginConfig(plugin_dirs=[plugin_dir]))

        monkeypatch.setattr("vpo.cli.plugins.get_config", mock_get_config)

        result = runner.invoke(main, ["plugins", "list"])

        # Should still succeed and show valid plugins
        assert result.exit_code == 0
        assert "test-analyzer" in result.output
        # Invalid plugin should show as invalid or error
        assert "bad_plugin" in result.output or "invalid" in result.output.lower()
