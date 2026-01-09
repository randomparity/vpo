"""Helper functions for plugin development.

These utilities provide convenient access to VPO internals and
common plugin development patterns.
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path
from typing import Any


def get_logger(plugin_name: str) -> logging.Logger:
    """Get a logger configured for a plugin.

    Loggers are named 'plugin.<plugin_name>' and inherit from the
    root VPO logger configuration.

    Args:
        plugin_name: Plugin identifier (used in log messages).

    Returns:
        Configured Logger instance.

    Example:
        logger = get_logger("my-plugin")
        logger.info("Plugin initialized")

    """
    return logging.getLogger(f"plugin.{plugin_name}")


def get_config() -> dict[str, Any]:
    """Get the current VPO configuration.

    Returns a read-only view of the configuration. Plugins should
    not modify this dict.

    Returns:
        Dict containing VPO configuration values.

    Example:
        config = get_config()
        plugin_dirs = config.get("plugin_dirs", [])

    """
    try:
        from video_policy_orchestrator.config.loader import get_config as load_config

        config = load_config()
        return {
            "plugin_dirs": [str(p) for p in (config.plugin_dirs or [])],
            "data_dir": str(config.data_dir) if config.data_dir else None,
        }
    except Exception:
        # Return minimal config if loading fails
        return {
            "plugin_dirs": [],
            "data_dir": None,
        }


def get_data_dir() -> Path:
    """Get the VPO data directory.

    This is typically ~/.vpo/ and contains the database, logs, and
    plugin storage.

    Returns:
        Path to the VPO data directory.

    Example:
        data_dir = get_data_dir()
        my_cache = data_dir / "plugins" / "my-plugin" / "cache"

    """
    try:
        from video_policy_orchestrator.config.loader import get_config as load_config

        config = load_config()
        if config.data_dir:
            return config.data_dir
    except Exception:  # nosec B110 - intentional fallback to default
        pass

    # Default to ~/.vpo/
    return Path.home() / ".vpo"


def get_plugin_storage_dir(plugin_name: str) -> Path:
    """Get a storage directory for a plugin.

    Creates the directory if it doesn't exist. Use this for plugin-specific
    data like caches, state files, or outputs.

    Args:
        plugin_name: Plugin identifier.

    Returns:
        Path to the plugin's storage directory.

    Example:
        storage = get_plugin_storage_dir("my-plugin")
        cache_file = storage / "cache.json"

    """
    storage_dir = get_data_dir() / "plugins" / plugin_name
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def normalize_path(path: str | Path) -> Path:
    """Normalize a file path.

    Expands user (~) and resolves to absolute path.

    Args:
        path: Path string or Path object.

    Returns:
        Normalized Path object.

    """
    return Path(path).expanduser().resolve()


def normalize_path_for_matching(path: str) -> str:
    """Normalize a file path for consistent matching.

    Used by metadata plugins to match file paths from external APIs
    (Radarr, Sonarr) with local file paths.

    Args:
        path: File path to normalize.

    Returns:
        Normalized path string without trailing slashes.
    """
    p = Path(path)
    try:
        # Try to resolve symlinks if the path exists
        resolved = p.resolve()
    except OSError:
        # Path doesn't exist or is inaccessible, use absolute
        resolved = p.absolute()
    # Strip trailing slashes for consistency
    return str(resolved).rstrip("/")


def is_supported_container(container: str) -> bool:
    """Check if a container format is supported by VPO.

    Args:
        container: Container format (mkv, mp4, etc.).

    Returns:
        True if supported, False otherwise.

    """
    supported = {"mkv", "matroska", "mp4", "m4v", "avi", "mov"}
    return container.casefold() in supported


def is_mkv_container(container: str) -> bool:
    """Check if a container is MKV/Matroska.

    MKV has full support for track manipulation.

    Args:
        container: Container format.

    Returns:
        True if MKV/Matroska.

    """
    return container.casefold() in {"mkv", "matroska"}


def get_host_identifier() -> str:
    """Get a host identifier for acknowledgment records.

    Returns the hostname of the current machine. Used to track which
    machine acknowledged a plugin for security auditing.

    Returns:
        Hostname string.

    """
    return socket.gethostname()
