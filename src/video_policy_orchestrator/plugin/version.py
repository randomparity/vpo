"""Plugin API version handling.

This module provides version parsing and compatibility checking for the
plugin API versioning system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Current plugin API version
PLUGIN_API_VERSION = "1.0.0"


@dataclass(frozen=True)
class APIVersion:
    """Semantic version for plugin API compatibility.

    Follows semver conventions:
    - MAJOR: Breaking changes
    - MINOR: New features (backward compatible)
    - PATCH: Bug fixes
    """

    major: int
    minor: int
    patch: int

    _VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-.*)?$")

    @classmethod
    def parse(cls, version_str: str) -> APIVersion:
        """Parse a semver string into an APIVersion.

        Args:
            version_str: Version string like "1.0.0" or "1.2.3-beta".

        Returns:
            Parsed APIVersion.

        Raises:
            ValueError: If version string is invalid.
        """
        match = cls._VERSION_PATTERN.match(version_str.strip())
        if not match:
            raise ValueError(f"Invalid version string: {version_str}")

        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
        )

    @classmethod
    def current(cls) -> APIVersion:
        """Get the current plugin API version."""
        return cls.parse(PLUGIN_API_VERSION)

    def __str__(self) -> str:
        """Format as semver string."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: APIVersion) -> bool:
        """Compare versions for ordering."""
        return (self.major, self.minor, self.patch) < (
            other.major,
            other.minor,
            other.patch,
        )

    def __le__(self, other: APIVersion) -> bool:
        """Compare versions for ordering."""
        return (self.major, self.minor, self.patch) <= (
            other.major,
            other.minor,
            other.patch,
        )

    def __gt__(self, other: APIVersion) -> bool:
        """Compare versions for ordering."""
        return (self.major, self.minor, self.patch) > (
            other.major,
            other.minor,
            other.patch,
        )

    def __ge__(self, other: APIVersion) -> bool:
        """Compare versions for ordering."""
        return (self.major, self.minor, self.patch) >= (
            other.major,
            other.minor,
            other.patch,
        )


def is_compatible(
    plugin_min: str | APIVersion,
    plugin_max: str | APIVersion,
    core_version: str | APIVersion | None = None,
) -> bool:
    """Check if plugin version range is compatible with core.

    Args:
        plugin_min: Minimum API version plugin supports.
        plugin_max: Maximum API version plugin supports.
        core_version: Core API version to check against.
                     Defaults to current PLUGIN_API_VERSION.

    Returns:
        True if core version is within plugin's supported range.
    """
    if core_version is None:
        core = APIVersion.current()
    elif isinstance(core_version, str):
        core = APIVersion.parse(core_version)
    else:
        core = core_version

    min_ver = (
        plugin_min
        if isinstance(plugin_min, APIVersion)
        else APIVersion.parse(plugin_min)
    )
    max_ver = (
        plugin_max
        if isinstance(plugin_max, APIVersion)
        else APIVersion.parse(plugin_max)
    )

    return min_ver <= core <= max_ver
