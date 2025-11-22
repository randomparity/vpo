"""Integration tests for plugin discovery end-to-end.

These tests verify the complete plugin discovery flow:
1. Plugin file creation in directory
2. Discovery by PluginLoader
3. Validation and loading
4. Registration in PluginRegistry
5. Plugin acknowledgment flow for directory plugins
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from video_policy_orchestrator.db.schema import create_schema
from video_policy_orchestrator.plugin.loader import (
    PluginLoader,
    discover_directory_plugins,
    load_plugin_from_path,
)
from video_policy_orchestrator.plugin.manifest import PluginSource
from video_policy_orchestrator.plugin.registry import PluginRegistry

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

VALID_MUTATOR_PLUGIN = '''
"""Test mutator plugin."""

class TestMutatorPlugin:
    """A valid mutator plugin for testing."""

    name = "test-mutator"
    version = "1.0.0"
    description = "Test mutator plugin"
    events = ["plan.before_execute"]
    min_api_version = "1.0.0"
    max_api_version = "1.99.99"

    def on_plan_execute(self, event):
        return None

    def execute(self, plan):
        return None

    def rollback(self, plan):
        return None

plugin = TestMutatorPlugin()
'''

INVALID_PLUGIN_NO_NAME = '''
"""Invalid plugin without name."""

class NoNamePlugin:
    version = "1.0.0"
    events = ["file.scanned"]

    def on_file_scanned(self, event):
        return None

    def on_policy_evaluate(self, event):
        pass

    def on_plan_complete(self, event):
        pass

plugin = NoNamePlugin()
'''

INVALID_PLUGIN_NO_PROTOCOL = '''
"""Invalid plugin not implementing any protocol."""

class NotAProtocolPlugin:
    name = "not-a-protocol"
    version = "1.0.0"
    events = ["file.scanned"]
    # Missing required protocol methods

plugin = NotAProtocolPlugin()
'''


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """Create a temporary plugin directory."""
    plugin_path = tmp_path / "plugins"
    plugin_path.mkdir()
    return plugin_path


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    return conn


@pytest.fixture
def registry(plugin_dir: Path) -> PluginRegistry:
    """Create a PluginRegistry with the test plugin directory."""
    return PluginRegistry(plugin_dirs=[plugin_dir])


class TestPluginDiscoveryE2E:
    """End-to-end tests for plugin discovery."""

    def test_discover_single_file_plugin(self, plugin_dir: Path):
        """Discover a single .py file plugin in directory."""
        # Create a plugin file
        plugin_file = plugin_dir / "my_analyzer.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        # Discover plugins
        discovered = discover_directory_plugins([plugin_dir])

        assert len(discovered) == 1
        path, module_name = discovered[0]
        assert path == plugin_file
        assert module_name == "my_analyzer"

    def test_discover_package_plugin(self, plugin_dir: Path):
        """Discover a package-style plugin with __init__.py."""
        # Create a plugin package
        pkg_dir = plugin_dir / "my_package_plugin"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(VALID_ANALYZER_PLUGIN)
        (pkg_dir / "utils.py").write_text("# Utility module")

        # Discover plugins
        discovered = discover_directory_plugins([plugin_dir])

        assert len(discovered) == 1
        path, module_name = discovered[0]
        assert path == pkg_dir
        assert module_name == "my_package_plugin"

    def test_discover_multiple_plugins(self, plugin_dir: Path):
        """Discover multiple plugins in the same directory."""
        # Create multiple plugin files
        (plugin_dir / "analyzer.py").write_text(VALID_ANALYZER_PLUGIN)
        (plugin_dir / "mutator.py").write_text(VALID_MUTATOR_PLUGIN)

        # Discover plugins
        discovered = discover_directory_plugins([plugin_dir])

        assert len(discovered) == 2
        names = {d[1] for d in discovered}
        assert names == {"analyzer", "mutator"}

    def test_load_valid_analyzer_plugin(self, plugin_dir: Path):
        """Load and validate a valid analyzer plugin."""
        plugin_file = plugin_dir / "analyzer.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        plugin_obj = load_plugin_from_path(plugin_file, "analyzer")

        assert plugin_obj.name == "test-analyzer"
        assert plugin_obj.version == "1.0.0"
        assert "file.scanned" in plugin_obj.events

    def test_load_valid_mutator_plugin(self, plugin_dir: Path):
        """Load and validate a valid mutator plugin."""
        plugin_file = plugin_dir / "mutator.py"
        plugin_file.write_text(VALID_MUTATOR_PLUGIN)

        plugin_obj = load_plugin_from_path(plugin_file, "mutator")

        assert plugin_obj.name == "test-mutator"
        assert plugin_obj.version == "1.0.0"
        assert "plan.before_execute" in plugin_obj.events


class TestPluginLoaderE2E:
    """End-to-end tests for PluginLoader."""

    def test_full_discovery_and_load_without_db(
        self,
        plugin_dir: Path,
        registry: PluginRegistry,
    ):
        """E2E: discover and load a plugin without DB (force_load bypasses ack)."""
        # Create a plugin file
        plugin_file = plugin_dir / "my_plugin.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        # Create loader without DB - force_load bypasses acknowledgment check
        loader = PluginLoader(
            registry=registry,
            db_conn=None,
            force_load=True,
            interactive=False,
        )

        # Load all plugins
        loaded = loader.load_all()

        assert len(loaded) == 1
        assert loaded[0].name == "test-analyzer"
        assert loaded[0].version == "1.0.0"
        assert loaded[0].source == PluginSource.DIRECTORY
        assert loaded[0].enabled is True

    def test_full_discovery_and_load_with_acknowledgment(
        self,
        plugin_dir: Path,
        db_conn: sqlite3.Connection,
        registry: PluginRegistry,
    ):
        """Complete E2E: discover, acknowledge, and load a plugin with DB."""
        # Create a plugin file
        plugin_file = plugin_dir / "my_plugin.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        # First load the plugin to get its name
        plugin_obj = load_plugin_from_path(plugin_file, "my_plugin")

        # Create loader with DB
        loader = PluginLoader(
            registry=registry,
            db_conn=db_conn,
            force_load=False,
            interactive=False,
        )

        # Acknowledge the plugin first
        loader.acknowledge_plugin(plugin_obj.name, plugin_file)

        # Now load all plugins
        loaded = loader.load_all()

        assert len(loaded) == 1
        assert loaded[0].name == "test-analyzer"
        assert loaded[0].version == "1.0.0"
        assert loaded[0].source == PluginSource.DIRECTORY
        assert loaded[0].enabled is True

    def test_directory_plugin_requires_acknowledgment(
        self,
        plugin_dir: Path,
        db_conn: sqlite3.Connection,
        registry: PluginRegistry,
    ):
        """Directory plugins require acknowledgment when not force_load."""
        # Create a plugin file
        plugin_file = plugin_dir / "unacknowledged.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        # Create loader without force_load
        loader = PluginLoader(
            registry=registry,
            db_conn=db_conn,
            force_load=False,
            interactive=False,  # Non-interactive mode
        )

        # Load should fail due to lack of acknowledgment
        loaded = loader.load_all()

        # Plugin was discovered but not loaded (warning logged)
        assert len(loaded) == 0

    def test_acknowledge_and_load_plugin(
        self,
        plugin_dir: Path,
        db_conn: sqlite3.Connection,
        registry: PluginRegistry,
    ):
        """Acknowledge a plugin then successfully load it."""
        # Create a plugin file
        plugin_file = plugin_dir / "to_acknowledge.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        # First, load the plugin object to get its name
        plugin_obj = load_plugin_from_path(plugin_file, "to_acknowledge")

        # Create loader
        loader = PluginLoader(
            registry=registry,
            db_conn=db_conn,
            force_load=False,
            interactive=False,
        )

        # Acknowledge the plugin
        success = loader.acknowledge_plugin(plugin_obj.name, plugin_file)
        assert success is True

        # Now loading should succeed
        loaded = loader.load_all()

        assert len(loaded) == 1
        assert loaded[0].name == "test-analyzer"

    def test_plugin_registered_in_registry(
        self,
        plugin_dir: Path,
        registry: PluginRegistry,
    ):
        """Loaded plugins are registered in the registry."""
        # Create a plugin file
        plugin_file = plugin_dir / "registered.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        # Create loader without DB, force_load to bypass acknowledgment
        loader = PluginLoader(
            registry=registry,
            db_conn=None,
            force_load=True,
            interactive=False,
        )

        # Load all plugins
        loader.load_all()

        # Verify plugin is in registry
        plugin = registry.get("test-analyzer")
        assert plugin is not None
        assert plugin.name == "test-analyzer"
        assert plugin.is_analyzer is True
        assert plugin.is_mutator is False

    def test_registry_get_by_event(
        self,
        plugin_dir: Path,
        registry: PluginRegistry,
    ):
        """Can retrieve plugins by event they handle."""
        # Create analyzer plugin
        analyzer_file = plugin_dir / "analyzer.py"
        analyzer_file.write_text(VALID_ANALYZER_PLUGIN)

        # Create loader without DB, force_load to bypass acknowledgment
        loader = PluginLoader(
            registry=registry,
            db_conn=None,
            force_load=True,
            interactive=False,
        )
        loader.load_all()

        # Query by event
        scanned_plugins = registry.get_by_event("file.scanned")
        assert len(scanned_plugins) == 1
        assert scanned_plugins[0].name == "test-analyzer"

        # Query for event not handled
        execute_plugins = registry.get_by_event("plan.before_execute")
        assert len(execute_plugins) == 0


class TestPluginValidationE2E:
    """End-to-end tests for plugin validation."""

    def test_invalid_plugin_missing_name_not_loaded(
        self,
        plugin_dir: Path,
        db_conn: sqlite3.Connection,
        registry: PluginRegistry,
    ):
        """Plugin without required 'name' attribute fails validation."""
        # Create invalid plugin
        plugin_file = plugin_dir / "no_name.py"
        plugin_file.write_text(INVALID_PLUGIN_NO_NAME)

        # Create loader
        loader = PluginLoader(
            registry=registry,
            db_conn=db_conn,
            force_load=True,
            interactive=False,
        )

        # Load all - should not load invalid plugin
        loaded = loader.load_all()

        assert len(loaded) == 0
        assert registry.get("no-name") is None

    def test_invalid_plugin_no_protocol_not_loaded(
        self,
        plugin_dir: Path,
        db_conn: sqlite3.Connection,
        registry: PluginRegistry,
    ):
        """Plugin not implementing any protocol fails validation."""
        # Create invalid plugin
        plugin_file = plugin_dir / "no_protocol.py"
        plugin_file.write_text(INVALID_PLUGIN_NO_PROTOCOL)

        # Create loader
        loader = PluginLoader(
            registry=registry,
            db_conn=db_conn,
            force_load=True,
            interactive=False,
        )

        # Load all - should not load invalid plugin
        loaded = loader.load_all()

        assert len(loaded) == 0


class TestPluginConflictDetection:
    """Tests for plugin conflict detection."""

    def test_duplicate_plugin_name_detected(
        self,
        plugin_dir: Path,
        registry: PluginRegistry,
    ):
        """Second plugin with same name is rejected."""
        # Create two plugins with the same name
        (plugin_dir / "first.py").write_text(VALID_ANALYZER_PLUGIN)
        (plugin_dir / "second.py").write_text(VALID_ANALYZER_PLUGIN)

        # Create loader without DB, force_load to bypass acknowledgment
        loader = PluginLoader(
            registry=registry,
            db_conn=None,
            force_load=True,
            interactive=False,
        )

        # Load all
        loaded = loader.load_all()

        # Only one should be loaded
        assert len(loaded) == 1
        assert loaded[0].name == "test-analyzer"

        # Verify only one in registry
        all_plugins = registry.get_all()
        assert len(all_plugins) == 1


class TestPluginEnableDisable:
    """Tests for plugin enable/disable functionality."""

    def test_disable_plugin(
        self,
        plugin_dir: Path,
        registry: PluginRegistry,
    ):
        """Can disable a loaded plugin."""
        # Create and load plugin
        (plugin_dir / "plugin.py").write_text(VALID_ANALYZER_PLUGIN)

        loader = PluginLoader(
            registry=registry,
            db_conn=None,
            force_load=True,
            interactive=False,
        )
        loader.load_all()

        # Initially enabled
        plugin = registry.get("test-analyzer")
        assert plugin is not None
        assert plugin.enabled is True

        # Disable
        result = registry.disable("test-analyzer")
        assert result is True
        assert plugin.enabled is False

        # Should not appear in get_by_event
        assert len(registry.get_by_event("file.scanned")) == 0

    def test_enable_disabled_plugin(
        self,
        plugin_dir: Path,
        registry: PluginRegistry,
    ):
        """Can re-enable a disabled plugin."""
        # Create and load plugin
        (plugin_dir / "plugin.py").write_text(VALID_ANALYZER_PLUGIN)

        loader = PluginLoader(
            registry=registry,
            db_conn=None,
            force_load=True,
            interactive=False,
        )
        loader.load_all()

        # Disable then enable
        registry.disable("test-analyzer")
        result = registry.enable("test-analyzer")

        assert result is True
        plugin = registry.get("test-analyzer")
        assert plugin is not None
        assert plugin.enabled is True

        # Should appear in get_by_event again
        assert len(registry.get_by_event("file.scanned")) == 1


class TestMultiplePluginDirectories:
    """Tests for multiple plugin directories."""

    def test_discover_from_multiple_directories(self, tmp_path: Path):
        """Can discover plugins from multiple directories."""
        # Create two plugin directories
        dir1 = tmp_path / "plugins1"
        dir2 = tmp_path / "plugins2"
        dir1.mkdir()
        dir2.mkdir()

        # Different plugin in each
        analyzer_code = VALID_ANALYZER_PLUGIN
        mutator_code = VALID_MUTATOR_PLUGIN

        (dir1 / "analyzer.py").write_text(analyzer_code)
        (dir2 / "mutator.py").write_text(mutator_code)

        # Discover from both
        discovered = discover_directory_plugins([dir1, dir2])

        assert len(discovered) == 2
        names = {d[1] for d in discovered}
        assert names == {"analyzer", "mutator"}

    def test_load_from_multiple_directories(
        self,
        tmp_path: Path,
    ):
        """Can load plugins from multiple directories."""
        # Create two plugin directories
        dir1 = tmp_path / "plugins1"
        dir2 = tmp_path / "plugins2"
        dir1.mkdir()
        dir2.mkdir()

        (dir1 / "analyzer.py").write_text(VALID_ANALYZER_PLUGIN)
        (dir2 / "mutator.py").write_text(VALID_MUTATOR_PLUGIN)

        # Create registry with both directories
        registry = PluginRegistry(plugin_dirs=[dir1, dir2])

        # Create loader without DB, force_load to bypass acknowledgment
        loader = PluginLoader(
            registry=registry,
            db_conn=None,
            force_load=True,
            interactive=False,
        )
        loaded = loader.load_all()

        assert len(loaded) == 2

        # Both should be in registry
        assert registry.get("test-analyzer") is not None
        assert registry.get("test-mutator") is not None


class TestPluginHashTracking:
    """Tests for plugin hash tracking in acknowledgments."""

    def test_acknowledgment_tied_to_hash(
        self,
        plugin_dir: Path,
        db_conn: sqlite3.Connection,
        registry: PluginRegistry,
    ):
        """Acknowledgment is tied to specific plugin hash."""
        # Create and acknowledge a plugin
        plugin_file = plugin_dir / "versioned.py"
        plugin_file.write_text(VALID_ANALYZER_PLUGIN)

        plugin_obj = load_plugin_from_path(plugin_file, "versioned")

        loader = PluginLoader(
            registry=registry,
            db_conn=db_conn,
            force_load=False,
            interactive=False,
        )

        # Acknowledge
        loader.acknowledge_plugin(plugin_obj.name, plugin_file)

        # Load succeeds
        loaded = loader.load_all()
        assert len(loaded) == 1

        # Now modify the plugin
        registry.clear()
        modified_code = VALID_ANALYZER_PLUGIN.replace("1.0.0", "2.0.0")
        plugin_file.write_text(modified_code)

        # Create new loader (need fresh registry)
        registry2 = PluginRegistry(plugin_dirs=[plugin_dir])
        loader2 = PluginLoader(
            registry=registry2,
            db_conn=db_conn,
            force_load=False,
            interactive=False,
        )

        # Load should fail - hash changed
        loaded2 = loader2.load_all()
        assert len(loaded2) == 0
