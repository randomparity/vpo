"""Plugin Registry Contract.

This file defines the interface for the plugin registry that manages
discovery, loading, and access to plugins.

API Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

from plugin_interfaces import (
    AnalyzerPlugin,
    MutatorPlugin,
    PluginManifest,
)


class PluginSource(Enum):
    """Source of plugin discovery."""

    ENTRY_POINT = "entry_point"
    DIRECTORY = "directory"
    BUILTIN = "builtin"


class PluginState(Enum):
    """Plugin lifecycle state."""

    DISCOVERED = "discovered"
    LOADING = "loading"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    LOAD_FAILED = "load_failed"
    ERROR = "error"


@dataclass
class LoadedPlugin:
    """Runtime representation of a loaded plugin."""

    manifest: PluginManifest
    instance: AnalyzerPlugin | MutatorPlugin
    source: PluginSource
    state: PluginState = PluginState.LOADED
    enabled: bool = True
    load_error: str | None = None
    loaded_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def name(self) -> str:
        """Plugin name from manifest."""
        return self.manifest.name

    @property
    def version(self) -> str:
        """Plugin version from manifest."""
        return self.manifest.version

    @property
    def is_analyzer(self) -> bool:
        """True if plugin implements AnalyzerPlugin."""
        return isinstance(self.instance, AnalyzerPlugin)

    @property
    def is_mutator(self) -> bool:
        """True if plugin implements MutatorPlugin."""
        return isinstance(self.instance, MutatorPlugin)


class PluginRegistry(Protocol):
    """Protocol for the plugin registry.

    The registry is responsible for:
    - Discovering plugins from configured sources
    - Loading and validating plugins
    - Managing plugin lifecycle (enable/disable)
    - Providing access to plugins by name or event
    """

    @property
    def api_version(self) -> str:
        """Current core API version."""
        ...

    @property
    def plugin_dirs(self) -> list[Path]:
        """Configured plugin directories."""
        ...

    @property
    def entry_point_group(self) -> str:
        """Entry point group name for plugin discovery."""
        ...

    def discover(self) -> list[PluginManifest]:
        """Discover all available plugins.

        Searches entry points and plugin directories.
        Does not load plugins, only reads manifests.

        Returns:
            List of discovered plugin manifests.
        """
        ...

    def load(self, name: str, force: bool = False) -> LoadedPlugin:
        """Load a specific plugin by name.

        Args:
            name: Plugin identifier.
            force: If True, load even if version incompatible.

        Returns:
            LoadedPlugin instance.

        Raises:
            PluginNotFoundError: If plugin not discovered.
            PluginLoadError: If loading fails.
            PluginVersionError: If version incompatible and force=False.
        """
        ...

    def load_all(self, force: bool = False) -> list[LoadedPlugin]:
        """Load all discovered plugins.

        Args:
            force: If True, load even if version incompatible.

        Returns:
            List of LoadedPlugin instances (includes failed loads).
        """
        ...

    def get(self, name: str) -> LoadedPlugin | None:
        """Get a loaded plugin by name.

        Args:
            name: Plugin identifier.

        Returns:
            LoadedPlugin or None if not loaded.
        """
        ...

    def get_all(self) -> list[LoadedPlugin]:
        """Get all loaded plugins.

        Returns:
            List of all loaded plugins.
        """
        ...

    def get_enabled(self) -> list[LoadedPlugin]:
        """Get all enabled plugins.

        Returns:
            List of enabled plugins only.
        """
        ...

    def get_by_event(self, event: str) -> list[LoadedPlugin]:
        """Get plugins that handle a specific event.

        Args:
            event: Event name (e.g., 'file.scanned').

        Returns:
            List of enabled plugins registered for this event.
        """
        ...

    def get_analyzers(self) -> list[LoadedPlugin]:
        """Get all loaded analyzer plugins.

        Returns:
            List of plugins implementing AnalyzerPlugin.
        """
        ...

    def get_mutators(self) -> list[LoadedPlugin]:
        """Get all loaded mutator plugins.

        Returns:
            List of plugins implementing MutatorPlugin.
        """
        ...

    def enable(self, name: str) -> bool:
        """Enable a loaded plugin.

        Args:
            name: Plugin identifier.

        Returns:
            True if plugin was enabled, False if not found.
        """
        ...

    def disable(self, name: str) -> bool:
        """Disable a loaded plugin.

        Args:
            name: Plugin identifier.

        Returns:
            True if plugin was disabled, False if not found.
        """
        ...

    def unload(self, name: str) -> bool:
        """Unload a plugin from memory.

        Args:
            name: Plugin identifier.

        Returns:
            True if plugin was unloaded, False if not found.
        """
        ...

    def is_acknowledged(self, name: str, plugin_hash: str) -> bool:
        """Check if a directory plugin has been acknowledged.

        Args:
            name: Plugin identifier.
            plugin_hash: SHA-256 hash of plugin files.

        Returns:
            True if previously acknowledged.
        """
        ...

    def acknowledge(self, name: str, plugin_hash: str) -> None:
        """Record user acknowledgment for a directory plugin.

        Args:
            name: Plugin identifier.
            plugin_hash: SHA-256 hash of plugin files.
        """
        ...


# =============================================================================
# Exceptions
# =============================================================================


class PluginError(Exception):
    """Base exception for plugin errors."""

    pass


class PluginNotFoundError(PluginError):
    """Plugin not found in discovery."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Plugin not found: {name}")


class PluginLoadError(PluginError):
    """Failed to load plugin."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Failed to load plugin '{name}': {reason}")


class PluginVersionError(PluginError):
    """Plugin version incompatible with core."""

    def __init__(
        self,
        name: str,
        plugin_range: tuple[str, str],
        core_version: str,
    ) -> None:
        self.name = name
        self.plugin_range = plugin_range
        self.core_version = core_version
        super().__init__(
            f"Plugin '{name}' requires API {plugin_range[0]}-{plugin_range[1]}, "
            f"but core is {core_version}"
        )


class PluginValidationError(PluginError):
    """Plugin failed validation."""

    def __init__(self, name: str, errors: list[str]) -> None:
        self.name = name
        self.errors = errors
        super().__init__(f"Plugin '{name}' validation failed: {'; '.join(errors)}")
