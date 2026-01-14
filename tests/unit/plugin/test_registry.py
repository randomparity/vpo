"""Unit tests for plugin registry."""

from datetime import datetime, timezone
from pathlib import Path

from vpo.plugin.manifest import (
    PluginManifest,
    PluginSource,
    PluginType,
)
from vpo.plugin.registry import LoadedPlugin, PluginRegistry


class MockAnalyzerPlugin:
    """Mock analyzer plugin for testing."""

    name = "mock-analyzer"
    version = "1.0.0"
    events = ["file.scanned"]

    def on_file_scanned(self, event):
        return None

    def on_policy_evaluate(self, event):
        pass

    def on_plan_complete(self, event):
        pass


class MockMutatorPlugin:
    """Mock mutator plugin for testing."""

    name = "mock-mutator"
    version = "1.0.0"
    events = ["plan.before_execute"]

    def on_plan_execute(self, event):
        return None

    def execute(self, plan):
        return {"success": True}

    def rollback(self, plan):
        return {"success": True}


def create_loaded_plugin(
    name: str,
    version: str = "1.0.0",
    plugin_type: PluginType = PluginType.ANALYZER,
    events: list[str] | None = None,
    source: PluginSource = PluginSource.ENTRY_POINT,
    enabled: bool = True,
) -> LoadedPlugin:
    """Create a LoadedPlugin for testing."""
    if events is None:
        events = ["file.scanned"]

    manifest = PluginManifest(
        name=name,
        version=version,
        plugin_type=plugin_type,
        events=events,
        source=source,
    )

    if plugin_type == PluginType.MUTATOR:
        instance = MockMutatorPlugin()
        instance.name = name
    else:
        instance = MockAnalyzerPlugin()
        instance.name = name

    return LoadedPlugin(
        manifest=manifest,
        instance=instance,
        enabled=enabled,
        loaded_at=datetime.now(timezone.utc),
    )


class TestLoadedPlugin:
    """Tests for LoadedPlugin class."""

    def test_properties(self):
        """Test LoadedPlugin properties."""
        plugin = create_loaded_plugin("test-plugin", "2.0.0")

        assert plugin.name == "test-plugin"
        assert plugin.version == "2.0.0"
        assert plugin.source == PluginSource.ENTRY_POINT
        assert plugin.events == ["file.scanned"]

    def test_is_analyzer(self):
        """Test is_analyzer property."""
        plugin = create_loaded_plugin("test", plugin_type=PluginType.ANALYZER)
        assert plugin.is_analyzer is True

    def test_is_mutator(self):
        """Test is_mutator property."""
        plugin = create_loaded_plugin("test", plugin_type=PluginType.MUTATOR)
        assert plugin.is_mutator is True


class TestPluginRegistry:
    """Tests for PluginRegistry class."""

    def test_register_plugin(self):
        """Register a plugin."""
        registry = PluginRegistry()
        plugin = create_loaded_plugin("test-plugin")

        registry.register(plugin)

        assert registry.get("test-plugin") == plugin

    def test_register_duplicate_warns(self):
        """Registering duplicate plugin logs warning."""
        registry = PluginRegistry()
        plugin1 = create_loaded_plugin("test-plugin", "1.0.0")
        plugin2 = create_loaded_plugin("test-plugin", "2.0.0")

        registry.register(plugin1)
        registry.register(plugin2)  # Should log warning

        # First one wins
        assert registry.get("test-plugin").version == "1.0.0"

    def test_unregister_plugin(self):
        """Unregister a plugin."""
        registry = PluginRegistry()
        plugin = create_loaded_plugin("test-plugin")
        registry.register(plugin)

        result = registry.unregister("test-plugin")

        assert result is True
        assert registry.get("test-plugin") is None

    def test_unregister_nonexistent(self):
        """Unregister non-existent plugin returns False."""
        registry = PluginRegistry()

        result = registry.unregister("nonexistent")

        assert result is False

    def test_get_all(self):
        """Get all registered plugins."""
        registry = PluginRegistry()
        registry.register(create_loaded_plugin("plugin-a"))
        registry.register(create_loaded_plugin("plugin-b"))

        all_plugins = registry.get_all()

        assert len(all_plugins) == 2

    def test_get_enabled(self):
        """Get only enabled plugins."""
        registry = PluginRegistry()
        registry.register(create_loaded_plugin("enabled", enabled=True))
        registry.register(create_loaded_plugin("disabled", enabled=False))

        enabled = registry.get_enabled()

        assert len(enabled) == 1
        assert enabled[0].name == "enabled"

    def test_get_by_event(self):
        """Get plugins by event."""
        registry = PluginRegistry()
        registry.register(create_loaded_plugin("scanned", events=["file.scanned"]))
        registry.register(
            create_loaded_plugin("evaluate", events=["policy.before_evaluate"])
        )

        scanned_plugins = registry.get_by_event("file.scanned")

        assert len(scanned_plugins) == 1
        assert scanned_plugins[0].name == "scanned"

    def test_get_by_event_excludes_disabled(self):
        """Get by event excludes disabled plugins."""
        registry = PluginRegistry()
        registry.register(
            create_loaded_plugin("enabled", events=["file.scanned"], enabled=True)
        )
        registry.register(
            create_loaded_plugin("disabled", events=["file.scanned"], enabled=False)
        )

        plugins = registry.get_by_event("file.scanned")

        assert len(plugins) == 1
        assert plugins[0].name == "enabled"

    def test_get_analyzers(self):
        """Get analyzer plugins."""
        registry = PluginRegistry()
        registry.register(
            create_loaded_plugin("analyzer", plugin_type=PluginType.ANALYZER)
        )
        registry.register(
            create_loaded_plugin("mutator", plugin_type=PluginType.MUTATOR)
        )

        analyzers = registry.get_analyzers()

        assert len(analyzers) == 1
        assert analyzers[0].name == "analyzer"

    def test_get_mutators(self):
        """Get mutator plugins."""
        registry = PluginRegistry()
        registry.register(
            create_loaded_plugin("analyzer", plugin_type=PluginType.ANALYZER)
        )
        registry.register(
            create_loaded_plugin("mutator", plugin_type=PluginType.MUTATOR)
        )

        mutators = registry.get_mutators()

        assert len(mutators) == 1
        assert mutators[0].name == "mutator"

    def test_enable_plugin(self):
        """Enable a disabled plugin."""
        registry = PluginRegistry()
        plugin = create_loaded_plugin("test", enabled=False)
        registry.register(plugin)

        result = registry.enable("test")

        assert result is True
        assert registry.get("test").enabled is True

    def test_enable_nonexistent(self):
        """Enable non-existent plugin returns False."""
        registry = PluginRegistry()

        result = registry.enable("nonexistent")

        assert result is False

    def test_disable_plugin(self):
        """Disable an enabled plugin."""
        registry = PluginRegistry()
        plugin = create_loaded_plugin("test", enabled=True)
        registry.register(plugin)

        result = registry.disable("test")

        assert result is True
        assert registry.get("test").enabled is False

    def test_has_conflict(self):
        """Check for registration conflicts."""
        registry = PluginRegistry()
        registry.register(create_loaded_plugin("existing"))

        assert registry.has_conflict("existing") is True
        assert registry.has_conflict("new") is False

    def test_clear(self):
        """Clear all plugins."""
        registry = PluginRegistry()
        registry.register(create_loaded_plugin("plugin-a"))
        registry.register(create_loaded_plugin("plugin-b"))

        registry.clear()

        assert len(registry.get_all()) == 0

    def test_properties(self):
        """Test registry properties."""
        plugin_dirs = [Path("/test/plugins")]
        registry = PluginRegistry(
            plugin_dirs=plugin_dirs,
            entry_point_group="test.plugins",
        )

        assert registry.plugin_dirs == plugin_dirs
        assert registry.entry_point_group == "test.plugins"
        assert registry.api_version == "1.0.0"


class TestBuiltinPlugins:
    """Tests for built-in plugin functionality."""

    def test_load_builtin_plugins(self):
        """Load built-in plugins into registry."""
        registry = PluginRegistry()

        loaded = registry.load_builtin_plugins()

        # policy-engine is always loaded; whisper-local is loaded when available
        plugin_names = [p.name for p in loaded]
        assert "policy-engine" in plugin_names
        # All loaded plugins should be marked as builtin
        for plugin in loaded:
            assert plugin.source == PluginSource.BUILTIN

    def test_get_builtin(self):
        """Get built-in plugins from registry."""
        registry = PluginRegistry()
        registry.load_builtin_plugins()
        # Add a non-builtin plugin
        registry.register(
            create_loaded_plugin("external", source=PluginSource.DIRECTORY)
        )

        builtins = registry.get_builtin()
        builtin_names = [p.name for p in builtins]

        # policy-engine is always built-in
        assert "policy-engine" in builtin_names
        # external should not be in builtins
        assert "external" not in builtin_names

    def test_is_builtin(self):
        """Check if plugin is built-in."""
        registry = PluginRegistry()
        registry.load_builtin_plugins()
        registry.register(
            create_loaded_plugin("external", source=PluginSource.DIRECTORY)
        )

        assert registry.is_builtin("policy-engine") is True
        assert registry.is_builtin("external") is False
        assert registry.is_builtin("nonexistent") is False

    def test_builtin_can_be_disabled(self):
        """Built-in plugins can be disabled."""
        registry = PluginRegistry()
        registry.load_builtin_plugins()

        # Initially enabled
        plugin = registry.get("policy-engine")
        assert plugin is not None
        assert plugin.enabled is True

        # Can be disabled
        result = registry.disable("policy-engine")
        assert result is True
        assert plugin.enabled is False

        # Should not appear in get_by_event when disabled
        assert len(registry.get_by_event("policy.before_evaluate")) == 0

    def test_builtin_can_be_re_enabled(self):
        """Disabled built-in plugins can be re-enabled."""
        registry = PluginRegistry()
        registry.load_builtin_plugins()

        registry.disable("policy-engine")
        result = registry.enable("policy-engine")

        assert result is True
        plugin = registry.get("policy-engine")
        assert plugin is not None
        assert plugin.enabled is True
