"""Plugin manifest definitions.

This module defines the data structures for plugin metadata and source types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PluginType(Enum):
    """Type of plugin based on capabilities."""

    ANALYZER = "analyzer"
    MUTATOR = "mutator"
    BOTH = "both"


class PluginSource(Enum):
    """Source where plugin was discovered."""

    ENTRY_POINT = "entry_point"
    DIRECTORY = "directory"
    BUILTIN = "builtin"


# Plugin name validation pattern: kebab-case, 2+ characters minimum.
# Rules:
#   - Must start with a lowercase letter
#   - May contain lowercase letters, digits, and hyphens
#   - Must end with a letter or digit (no trailing hyphen)
#   - Minimum 2 characters (single-character names are not allowed)
# Examples: "my-plugin", "analyzer", "foo-bar-v2"
# Invalid: "a", "My-Plugin", "plugin_name", "plugin-"
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]{2,}$")


@dataclass
class PluginManifest:
    """Metadata describing a plugin.

    This is immutable after loading and contains all the information
    needed to identify and validate a plugin.
    """

    name: str
    version: str
    plugin_type: PluginType
    events: list[str]
    min_api_version: str = "1.0.0"
    max_api_version: str = "1.99.99"
    description: str = ""
    author: str = ""
    source: PluginSource = PluginSource.DIRECTORY
    source_path: Path | None = None

    def __post_init__(self) -> None:
        """Validate manifest fields after initialization."""
        errors = self.validate()
        if errors:
            raise ValueError(f"Invalid manifest: {'; '.join(errors)}")

    def validate(self) -> list[str]:
        """Validate manifest fields.

        Returns:
            List of validation error messages (empty if valid).

        """
        errors: list[str] = []

        # Validate name
        if not self.name:
            errors.append("name is required")
        elif not _NAME_PATTERN.match(self.name):
            errors.append(f"name must be kebab-case (2+ chars): {self.name}")

        # Validate version
        if not self.version:
            errors.append("version is required")

        # Validate events
        if not self.events:
            errors.append("events list cannot be empty")

        # Validate API version range
        from video_policy_orchestrator.plugin.version import APIVersion

        try:
            min_ver = APIVersion.parse(self.min_api_version)
            max_ver = APIVersion.parse(self.max_api_version)
            if min_ver > max_ver:
                errors.append(
                    f"min_api_version ({self.min_api_version}) > "
                    f"max_api_version ({self.max_api_version})"
                )
        except ValueError as e:
            errors.append(str(e))

        return errors

    @classmethod
    def from_plugin_class(
        cls,
        plugin_class: type,
        source: PluginSource = PluginSource.DIRECTORY,
        source_path: Path | None = None,
    ) -> PluginManifest:
        """Extract manifest from a plugin class's attributes.

        Args:
            plugin_class: Plugin class with manifest attributes.
            source: Where the plugin was discovered.
            source_path: Path to plugin file (for directory plugins).

        Returns:
            PluginManifest extracted from class.

        Raises:
            ValueError: If required attributes are missing or invalid.

        """
        # Required attributes
        name = getattr(plugin_class, "name", None)
        version = getattr(plugin_class, "version", None)
        events = getattr(plugin_class, "events", None)

        if name is None:
            raise ValueError("Plugin class missing 'name' attribute")
        if version is None:
            raise ValueError("Plugin class missing 'version' attribute")
        if events is None:
            raise ValueError("Plugin class missing 'events' attribute")

        # Determine plugin type from class hierarchy
        from video_policy_orchestrator.plugin.interfaces import (
            AnalyzerPlugin,
            MutatorPlugin,
        )

        is_analyzer = isinstance(plugin_class, type) and (
            hasattr(plugin_class, "on_file_scanned")
            or hasattr(plugin_class, "on_policy_evaluate")
            or hasattr(plugin_class, "on_plan_complete")
        )
        is_mutator = isinstance(plugin_class, type) and (
            hasattr(plugin_class, "on_plan_execute") or hasattr(plugin_class, "execute")
        )

        # Also check protocol compliance
        try:
            is_analyzer = is_analyzer or isinstance(plugin_class(), AnalyzerPlugin)
        except (TypeError, Exception):
            pass
        try:
            is_mutator = is_mutator or isinstance(plugin_class(), MutatorPlugin)
        except (TypeError, Exception):
            pass

        if is_analyzer and is_mutator:
            plugin_type = PluginType.BOTH
        elif is_mutator:
            plugin_type = PluginType.MUTATOR
        else:
            plugin_type = PluginType.ANALYZER

        return cls(
            name=name,
            version=version,
            plugin_type=plugin_type,
            events=list(events),
            min_api_version=getattr(plugin_class, "min_api_version", "1.0.0"),
            max_api_version=getattr(plugin_class, "max_api_version", "1.99.99"),
            description=getattr(plugin_class, "description", ""),
            author=getattr(plugin_class, "author", ""),
            source=source,
            source_path=source_path,
        )
