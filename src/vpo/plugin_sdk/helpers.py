"""Helper functions for plugin development.

These utilities provide convenient access to VPO internals and
common plugin development patterns.
"""

from __future__ import annotations

import logging
import re
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

# Pattern for validating date format YYYY-MM-DD
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
        from vpo.config.loader import get_config as load_config

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
        from vpo.config.loader import get_config as load_config

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


def extract_date_from_iso(datetime_str: str | None) -> str | None:
    """Extract and validate date from ISO 8601 datetime string.

    Extracts the date portion (YYYY-MM-DD) from an ISO 8601 datetime string
    and validates that it represents a valid calendar date.

    This is the canonical function for parsing dates from external APIs
    like Radarr and Sonarr. Use this instead of duplicating the parsing logic.

    Args:
        datetime_str: ISO 8601 datetime string (e.g., "2024-06-15T00:00:00Z")
                     or date-only string (e.g., "2024-06-15").
                     Can be None.

    Returns:
        Date portion only (e.g., "2024-06-15") or None if:
        - Input is None or empty
        - Input doesn't match expected format
        - Date is not a valid calendar date (e.g., "2024-02-30")

    Example:
        >>> extract_date_from_iso("2024-06-15T00:00:00Z")
        '2024-06-15'
        >>> extract_date_from_iso("2024-06-15")
        '2024-06-15'
        >>> extract_date_from_iso("TBD")
        None
        >>> extract_date_from_iso("2024-13-45")
        None

    """
    if not datetime_str:
        return None

    # Extract the date portion
    if "T" in datetime_str:
        date_str = datetime_str.split("T")[0]
    elif len(datetime_str) >= 10:
        date_str = datetime_str[:10]
    else:
        return None

    # Validate format matches YYYY-MM-DD
    if not DATE_PATTERN.match(date_str):
        return None

    # Validate it's a real calendar date (e.g., not 2024-02-30)
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    return date_str
