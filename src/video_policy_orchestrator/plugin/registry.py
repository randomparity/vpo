"""Plugin registry for managing loaded plugins.

The registry is responsible for tracking loaded plugins and providing
access by name, type, or event.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from video_policy_orchestrator.plugin.interfaces import AnalyzerPlugin, MutatorPlugin
from video_policy_orchestrator.plugin.manifest import PluginManifest, PluginSource
from video_policy_orchestrator.plugin.version import PLUGIN_API_VERSION

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class LoadedPlugin:
    """Runtime representation of a loaded plugin."""

    manifest: PluginManifest
    instance: AnalyzerPlugin | MutatorPlugin
    enabled: bool = True
    load_error: str | None = None
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def name(self) -> str:
        """Plugin name from manifest."""
        return self.manifest.name

    @property
    def version(self) -> str:
        """Plugin version from manifest."""
        return self.manifest.version

    @property
    def source(self) -> PluginSource:
        """Plugin source from manifest."""
        return self.manifest.source

    @property
    def is_analyzer(self) -> bool:
        """True if plugin implements AnalyzerPlugin."""
        return isinstance(self.instance, AnalyzerPlugin)

    @property
    def is_mutator(self) -> bool:
        """True if plugin implements MutatorPlugin."""
        return isinstance(self.instance, MutatorPlugin)

    @property
    def events(self) -> list[str]:
        """Events this plugin handles."""
        return self.manifest.events


class PluginRegistry:
    """Central registry for discovered and loaded plugins.

    The registry manages the lifecycle of plugins including:
    - Tracking loaded plugins
    - Enabling/disabling plugins
    - Providing access by name, type, or event
    """

    def __init__(
        self,
        plugin_dirs: list[Path] | None = None,
        entry_point_group: str = "vpo.plugins",
    ) -> None:
        """Initialize the registry.

        Args:
            plugin_dirs: Directories to search for plugins.
            entry_point_group: Entry point group name for plugin discovery.
        """
        self._plugins: dict[str, LoadedPlugin] = {}
        self._plugin_dirs = plugin_dirs or []
        self._entry_point_group = entry_point_group
        self._api_version = PLUGIN_API_VERSION

    @property
    def api_version(self) -> str:
        """Current core API version."""
        return self._api_version

    @property
    def plugin_dirs(self) -> list[Path]:
        """Configured plugin directories."""
        return self._plugin_dirs

    @property
    def entry_point_group(self) -> str:
        """Entry point group name for plugin discovery."""
        return self._entry_point_group

    def register(self, plugin: LoadedPlugin) -> None:
        """Register a loaded plugin.

        Args:
            plugin: LoadedPlugin to register.

        Raises:
            ValueError: If a plugin with the same name is already registered.
        """
        if plugin.name in self._plugins:
            existing = self._plugins[plugin.name]
            logger.warning(
                "Plugin '%s' already registered (version %s from %s). "
                "Skipping duplicate (version %s from %s).",
                plugin.name,
                existing.version,
                existing.source.value,
                plugin.version,
                plugin.source.value,
            )
            return

        self._plugins[plugin.name] = plugin
        logger.info(
            "Registered plugin: %s v%s (%s)",
            plugin.name,
            plugin.version,
            plugin.source.value,
        )

    def unregister(self, name: str) -> bool:
        """Unregister a plugin by name.

        Args:
            name: Plugin identifier.

        Returns:
            True if plugin was unregistered, False if not found.
        """
        if name in self._plugins:
            del self._plugins[name]
            logger.info("Unregistered plugin: %s", name)
            return True
        return False

    def get(self, name: str) -> LoadedPlugin | None:
        """Get a loaded plugin by name.

        Args:
            name: Plugin identifier.

        Returns:
            LoadedPlugin or None if not loaded.
        """
        return self._plugins.get(name)

    def get_all(self) -> list[LoadedPlugin]:
        """Get all loaded plugins.

        Returns:
            List of all loaded plugins.
        """
        return list(self._plugins.values())

    def get_enabled(self) -> list[LoadedPlugin]:
        """Get all enabled plugins.

        Returns:
            List of enabled plugins only.
        """
        return [p for p in self._plugins.values() if p.enabled]

    def get_by_event(self, event: str) -> list[LoadedPlugin]:
        """Get plugins that handle a specific event.

        Args:
            event: Event name (e.g., 'file.scanned').

        Returns:
            List of enabled plugins registered for this event.
        """
        return [p for p in self._plugins.values() if p.enabled and event in p.events]

    def get_analyzers(self) -> list[LoadedPlugin]:
        """Get all loaded analyzer plugins.

        Returns:
            List of plugins implementing AnalyzerPlugin.
        """
        return [p for p in self._plugins.values() if p.is_analyzer]

    def get_mutators(self) -> list[LoadedPlugin]:
        """Get all loaded mutator plugins.

        Returns:
            List of plugins implementing MutatorPlugin.
        """
        return [p for p in self._plugins.values() if p.is_mutator]

    def enable(self, name: str) -> bool:
        """Enable a loaded plugin.

        Args:
            name: Plugin identifier.

        Returns:
            True if plugin was enabled, False if not found.
        """
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        plugin.enabled = True
        logger.info("Enabled plugin: %s", name)
        return True

    def disable(self, name: str) -> bool:
        """Disable a loaded plugin.

        Args:
            name: Plugin identifier.

        Returns:
            True if plugin was disabled, False if not found.
        """
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        plugin.enabled = False
        logger.info("Disabled plugin: %s", name)
        return True

    def has_conflict(self, name: str) -> bool:
        """Check if registering a plugin would cause a conflict.

        Args:
            name: Plugin identifier to check.

        Returns:
            True if a plugin with this name is already registered.
        """
        return name in self._plugins

    def clear(self) -> None:
        """Clear all registered plugins."""
        self._plugins.clear()
        logger.debug("Cleared all plugins from registry")

    def load_builtin_plugins(self) -> list[LoadedPlugin]:
        """Load and register all built-in plugins.

        Built-in plugins are shipped with VPO and don't require acknowledgment.
        They can be disabled but not uninstalled.

        Returns:
            List of loaded built-in plugins.
        """
        # Import here to avoid circular import
        from video_policy_orchestrator.plugin.loader import create_loaded_plugin

        loaded = []

        # Policy Engine is the only built-in plugin for now
        try:
            from video_policy_orchestrator.plugins.policy_engine import plugin

            builtin_plugin = create_loaded_plugin(
                plugin,
                source=PluginSource.BUILTIN,
                source_path=None,
            )
            self.register(builtin_plugin)
            loaded.append(builtin_plugin)
            logger.info("Loaded built-in plugin: %s", builtin_plugin.name)
        except ImportError as e:
            logger.error("Failed to load built-in policy engine: %s", e)
        except Exception as e:
            logger.error("Error loading built-in plugin: %s", e)

        return loaded

    def get_builtin(self) -> list[LoadedPlugin]:
        """Get all built-in plugins.

        Returns:
            List of plugins with BUILTIN source.
        """
        return [p for p in self._plugins.values() if p.source == PluginSource.BUILTIN]

    def is_builtin(self, name: str) -> bool:
        """Check if a plugin is built-in.

        Args:
            name: Plugin identifier.

        Returns:
            True if plugin is built-in, False otherwise.
        """
        plugin = self._plugins.get(name)
        return plugin is not None and plugin.source == PluginSource.BUILTIN
