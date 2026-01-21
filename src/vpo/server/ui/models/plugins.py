"""Plugin data browser view models.

This module defines models for the plugin list and data browser views.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PluginInfo:
    """Information about a registered plugin.

    Attributes:
        name: Plugin identifier (e.g., "whisper-transcriber").
        version: Plugin version string.
        enabled: Whether the plugin is currently enabled.
        is_builtin: True if this is a built-in plugin.
        events: List of events this plugin handles.
    """

    name: str
    version: str
    enabled: bool
    is_builtin: bool
    events: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "is_builtin": self.is_builtin,
            "events": self.events,
        }


@dataclass
class PluginListResponse:
    """API response wrapper for /api/plugins.

    Attributes:
        plugins: List of registered plugins.
        total: Total number of plugins.
    """

    plugins: list[PluginInfo]
    total: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "plugins": [p.to_dict() for p in self.plugins],
            "total": self.total,
        }


@dataclass
class PluginFileItem:
    """File item with plugin-specific data.

    Attributes:
        id: File ID.
        filename: File name.
        path: Full file path.
        scan_status: Scan status (ok/error).
        plugin_data: Plugin-specific metadata.
    """

    id: int
    filename: str
    path: str
    scan_status: str
    plugin_data: dict

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "filename": self.filename,
            "path": self.path,
            "scan_status": self.scan_status,
            "plugin_data": self.plugin_data,
        }


@dataclass
class PluginFilesResponse:
    """API response wrapper for /api/plugins/{name}/files.

    Attributes:
        plugin_name: Name of the plugin.
        files: List of files with plugin data.
        total: Total number of files with data from this plugin.
        limit: Page size.
        offset: Current offset.
    """

    plugin_name: str
    files: list[PluginFileItem]
    total: int
    limit: int
    offset: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "plugin_name": self.plugin_name,
            "files": [f.to_dict() for f in self.files],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass
class FilePluginDataResponse:
    """API response wrapper for /api/files/{id}/plugin-data.

    Attributes:
        file_id: ID of the file.
        filename: File name.
        plugin_data: Dictionary of plugin name -> plugin data.
    """

    file_id: int
    filename: str
    plugin_data: dict[str, dict]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "plugin_data": self.plugin_data,
        }


@dataclass
class PluginDataContext:
    """Template context for plugin_data.html.

    Attributes:
        file_id: ID of the file.
        filename: File name.
        file_path: Full file path.
        plugin_data: Dictionary of plugin name -> plugin data.
        plugin_count: Number of plugins with data for this file.
    """

    file_id: int
    filename: str
    file_path: str
    plugin_data: dict[str, dict]
    plugin_count: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "plugin_data": self.plugin_data,
            "plugin_count": self.plugin_count,
        }
