"""Plugin discovery and loading.

This module handles discovering plugins from:
1. Python entry points (installed packages)
2. Directory scanning (~/.vpo/plugins/)

And loading them into the plugin registry.

Note on imports:
    Some imports from db.models are deferred to inside methods to avoid circular
    imports. The plugin system is imported early in the application lifecycle,
    before the database layer is fully initialized. By deferring these imports
    to runtime (when the methods are called), we ensure the database module is
    available. This pattern is intentional - do not move these imports to module
    level.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vpo.plugin.exceptions import (
    PluginLoadError,
    PluginNotAcknowledgedError,
    PluginValidationError,
    PluginVersionError,
)
from vpo.plugin.interfaces import AnalyzerPlugin, MutatorPlugin
from vpo.plugin.manifest import (
    PluginManifest,
    PluginSource,
)
from vpo.plugin.registry import LoadedPlugin, PluginRegistry
from vpo.plugin.version import PLUGIN_API_VERSION, is_compatible

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


def compute_plugin_hash(path: Path) -> str:
    """Compute SHA-256 hash of a plugin file or directory.

    For single files, hashes the file content.
    For directories, hashes all .py files sorted by name.

    Args:
        path: Path to plugin file or directory.

    Returns:
        Hex-encoded SHA-256 hash.

    """
    hasher = hashlib.sha256()

    if path.is_file():
        hasher.update(path.read_bytes())
    elif path.is_dir():
        # Hash all Python files in sorted order for determinism
        py_files = sorted(path.rglob("*.py"))
        for py_file in py_files:
            hasher.update(py_file.read_bytes())
    else:
        raise ValueError(f"Path does not exist: {path}")

    return hasher.hexdigest()


def discover_entry_point_plugins(
    entry_point_group: str = "vpo.plugins",
) -> list[tuple[str, Any, PluginSource]]:
    """Discover plugins from Python entry points.

    Args:
        entry_point_group: Entry point group name.

    Returns:
        List of (name, plugin_class_or_instance, source) tuples.

    """
    discovered: list[tuple[str, Any, PluginSource]] = []

    try:
        from importlib.metadata import entry_points

        eps = entry_points(group=entry_point_group)

        for ep in eps:
            try:
                plugin_obj = ep.load()
                discovered.append((ep.name, plugin_obj, PluginSource.ENTRY_POINT))
                logger.debug("Discovered entry point plugin: %s", ep.name)
            except Exception as e:
                logger.warning("Failed to load entry point '%s': %s", ep.name, e)

    except Exception as e:
        logger.warning("Failed to enumerate entry points: %s", e)

    return discovered


def discover_directory_plugins(
    plugin_dirs: list[Path],
) -> list[tuple[Path, str]]:
    """Discover plugins from directories.

    Looks for:
    - Single .py files with a 'plugin' variable
    - Directories with __init__.py containing a 'plugin' variable

    Args:
        plugin_dirs: List of directories to search.

    Returns:
        List of (path, module_name) tuples for discovered plugins.

    """
    discovered: list[tuple[Path, str]] = []

    for plugin_dir in plugin_dirs:
        if not plugin_dir.exists():
            logger.debug("Plugin directory does not exist: %s", plugin_dir)
            continue

        # Look for single .py files
        for py_file in plugin_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            module_name = py_file.stem
            discovered.append((py_file, module_name))
            logger.debug("Discovered directory plugin file: %s", py_file)

        # Look for package directories
        for subdir in plugin_dir.iterdir():
            if not subdir.is_dir():
                continue
            if subdir.name.startswith("_"):
                continue
            init_file = subdir / "__init__.py"
            if init_file.exists():
                discovered.append((subdir, subdir.name))
                logger.debug("Discovered directory plugin package: %s", subdir)

    return discovered


def load_plugin_from_path(path: Path, module_name: str) -> Any:
    """Load a plugin module from a file path.

    Args:
        path: Path to .py file or package directory.
        module_name: Name to use for the module.

    Returns:
        The loaded plugin object (class or instance).

    Raises:
        PluginLoadError: If loading fails.

    """
    try:
        if path.is_file():
            spec = importlib.util.spec_from_file_location(module_name, path)
        else:
            init_path = path / "__init__.py"
            spec = importlib.util.spec_from_file_location(
                module_name, init_path, submodule_search_locations=[str(path)]
            )

        if spec is None or spec.loader is None:
            raise PluginLoadError(
                module_name, f"Could not create module spec for {path}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Look for 'plugin' variable
        if not hasattr(module, "plugin"):
            raise PluginLoadError(
                module_name, "Module does not export a 'plugin' variable"
            )

        return module.plugin

    except PluginLoadError:
        raise
    except Exception as e:
        raise PluginLoadError(module_name, str(e)) from e


def get_plugin_instance(plugin_obj: Any) -> Any:
    """Get a plugin instance from a class or return the instance directly.

    This helper centralizes the logic for getting an instance from a plugin
    object, which may be either a class or an already-instantiated object.

    Args:
        plugin_obj: Plugin class or instance.

    Returns:
        The plugin instance.

    Raises:
        Exception: If instantiation fails.

    """
    if isinstance(plugin_obj, type):
        return plugin_obj()
    return plugin_obj


def validate_plugin(plugin_obj: Any, name: str) -> list[str]:
    """Validate a plugin object.

    Args:
        plugin_obj: Plugin class or instance.
        name: Plugin name for error messages.

    Returns:
        List of validation errors (empty if valid).

    """
    errors: list[str] = []

    # Get the instance
    try:
        instance = get_plugin_instance(plugin_obj)
    except Exception as e:
        errors.append(f"Failed to instantiate plugin class: {e}")
        return errors

    # Check required attributes
    if not hasattr(instance, "name"):
        errors.append("Missing required attribute: name")
    if not hasattr(instance, "version"):
        errors.append("Missing required attribute: version")
    if not hasattr(instance, "events"):
        errors.append("Missing required attribute: events")

    # Check interface compliance
    is_analyzer = isinstance(instance, AnalyzerPlugin)
    is_mutator = isinstance(instance, MutatorPlugin)

    if not is_analyzer and not is_mutator:
        errors.append(
            "Plugin does not implement AnalyzerPlugin or MutatorPlugin protocol"
        )

    return errors


def create_loaded_plugin(
    plugin_obj: Any,
    source: PluginSource,
    source_path: Path | None = None,
    instance: Any | None = None,
) -> LoadedPlugin:
    """Create a LoadedPlugin from a plugin object.

    Args:
        plugin_obj: Plugin class or instance.
        source: Where the plugin was discovered.
        source_path: Path to plugin (for directory plugins).
        instance: Pre-instantiated plugin instance (avoids re-instantiation).

    Returns:
        LoadedPlugin ready for registration.

    """
    # Use provided instance or create one
    if instance is None:
        instance = get_plugin_instance(plugin_obj)

    # Build manifest from instance
    manifest = PluginManifest.from_plugin_class(type(instance), source, source_path)

    return LoadedPlugin(
        manifest=manifest,
        instance=instance,
        enabled=True,
        loaded_at=datetime.now(timezone.utc),
    )


class PluginLoader:
    """Handles plugin discovery, validation, and loading."""

    def __init__(
        self,
        registry: PluginRegistry,
        db_conn: sqlite3.Connection | None = None,
        force_load: bool = False,
        interactive: bool = True,
    ) -> None:
        """Initialize the loader.

        Args:
            registry: Plugin registry to load into.
            db_conn: Database connection for acknowledgment storage.
            force_load: If True, load plugins even if version incompatible.
            interactive: If True, prompt for directory plugin acknowledgment.

        """
        self._registry = registry
        self._db_conn = db_conn
        self._force_load = force_load
        self._interactive = interactive

    def discover_all(self) -> list[tuple[Any, PluginSource, Path | None]]:
        """Discover all available plugins.

        Returns:
            List of (plugin_obj, source, path) tuples.

        """
        discovered: list[tuple[Any, PluginSource, Path | None]] = []

        # Entry points first (higher trust)
        for name, plugin_obj, source in discover_entry_point_plugins(
            self._registry.entry_point_group
        ):
            discovered.append((plugin_obj, source, None))

        # Then directory plugins
        for path, module_name in discover_directory_plugins(self._registry.plugin_dirs):
            try:
                plugin_obj = load_plugin_from_path(path, module_name)
                discovered.append((plugin_obj, PluginSource.DIRECTORY, path))
            except PluginLoadError as e:
                logger.warning("Failed to load directory plugin: %s", e)

        return discovered

    def load_all(self) -> list[LoadedPlugin]:
        """Discover and load all plugins.

        Returns:
            List of successfully loaded plugins.

        """
        loaded: list[LoadedPlugin] = []

        for plugin_obj, source, path in self.discover_all():
            try:
                plugin = self.load_plugin(plugin_obj, source, path)
                if plugin is not None:
                    loaded.append(plugin)
            except Exception as e:
                logger.warning("Failed to load plugin: %s", e)

        return loaded

    def load_plugin(
        self,
        plugin_obj: Any,
        source: PluginSource,
        path: Path | None = None,
    ) -> LoadedPlugin | None:
        """Load a single plugin.

        Args:
            plugin_obj: Plugin class or instance.
            source: Where the plugin was discovered.
            path: Path to plugin (for directory plugins).

        Returns:
            LoadedPlugin if successful, None if skipped.

        Raises:
            PluginLoadError: If loading fails.
            PluginValidationError: If validation fails.
            PluginVersionError: If version is incompatible.
            PluginNotAcknowledgedError: If directory plugin not acknowledged.

        """
        # Get name for error messages (try without instantiation first)
        name = getattr(plugin_obj, "name", None)
        if name is None:
            name = str(path) if path else "unknown"

        # Validate plugin
        errors = validate_plugin(plugin_obj, name)
        if errors:
            raise PluginValidationError(name, errors)

        # Get instance once for all subsequent operations
        # This avoids redundant instantiation throughout the load process
        instance = get_plugin_instance(plugin_obj)
        name = instance.name

        # Check for conflicts
        if self._registry.has_conflict(name):
            logger.warning(
                "Plugin '%s' conflicts with already registered plugin, skipping", name
            )
            return None

        # Check version compatibility
        min_ver = getattr(instance, "min_api_version", "1.0.0")
        max_ver = getattr(instance, "max_api_version", "1.99.99")

        if not is_compatible(min_ver, max_ver) and not self._force_load:
            raise PluginVersionError(name, (min_ver, max_ver), PLUGIN_API_VERSION)

        # Check acknowledgment for directory plugins
        if source == PluginSource.DIRECTORY and path is not None:
            if not self._check_acknowledgment(name, path):
                raise PluginNotAcknowledgedError(name, str(path))

        # Create and register, passing the already-instantiated instance
        loaded = create_loaded_plugin(plugin_obj, source, path, instance=instance)
        self._registry.register(loaded)

        return loaded

    def _check_acknowledgment(self, name: str, path: Path) -> bool:
        """Check if a directory plugin has been acknowledged.

        Args:
            name: Plugin name.
            path: Path to plugin.

        Returns:
            True if acknowledged or if running non-interactively with force.

        """
        if self._db_conn is None:
            logger.warning(
                "No database connection, cannot check plugin acknowledgment for '%s'",
                name,
            )
            return self._force_load

        plugin_hash = compute_plugin_hash(path)

        from vpo.db.models import is_plugin_acknowledged

        return is_plugin_acknowledged(self._db_conn, name, plugin_hash)

    def acknowledge_plugin(self, name: str, path: Path) -> bool:
        """Record user acknowledgment for a directory plugin.

        Args:
            name: Plugin name.
            path: Path to plugin.

        Returns:
            True if acknowledgment was recorded.

        """
        if self._db_conn is None:
            logger.error("No database connection, cannot acknowledge plugin '%s'", name)
            return False

        plugin_hash = compute_plugin_hash(path)

        from vpo.db.models import (
            PluginAcknowledgment,
            insert_plugin_acknowledgment,
        )
        from vpo.plugin_sdk.helpers import get_host_identifier

        record = PluginAcknowledgment(
            id=None,
            plugin_name=name,
            plugin_hash=plugin_hash,
            acknowledged_at=datetime.now(timezone.utc).isoformat(),
            acknowledged_by=get_host_identifier(),
        )

        insert_plugin_acknowledgment(self._db_conn, record)
        logger.info("Acknowledged plugin '%s' (hash: %s...)", name, plugin_hash[:12])
        return True
