"""Executor protocol and tool availability utilities.

This module defines the interface for execution adapters and utilities
to check external tool availability.
"""

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vpo.policy.types import Plan


@dataclass(frozen=True)
class ExecutorResult:
    """Result of an executor operation.

    This is a frozen dataclass to ensure immutability and consistency
    with project dataclass patterns (Constitution Principle IV).
    """

    success: bool
    """True if the operation succeeded."""

    message: str = ""
    """Human-readable message describing the result."""

    backup_path: Path | None = None
    """Path to backup file, if one was created."""


class Executor(Protocol):
    """Protocol for execution adapters.

    Executors are responsible for applying planned actions to media files.
    Each executor handles a specific type of operation (metadata changes,
    track reordering) for specific container formats.
    """

    def can_handle(self, plan: Plan) -> bool:
        """Check if this executor can handle the given plan.

        Args:
            plan: The execution plan to check.

        Returns:
            True if this executor can apply the plan.
        """
        ...

    def execute(
        self,
        plan: Plan,
        keep_backup: bool = True,
        keep_original: bool = False,
    ) -> ExecutorResult:
        """Execute the plan on the target file.

        Args:
            plan: The execution plan to apply.
            keep_backup: Whether to keep the backup file after success.
            keep_original: Whether to keep the original file after container
                conversion (only applies when output path differs from input).

        Returns:
            ExecutorResult with success status and optional backup path.
        """
        ...


# =============================================================================
# Tool Resolution Functions
# =============================================================================
# These functions provide tool path resolution with support for:
# - Configured paths (via config file or environment variables)
# - System PATH fallback
# - Capability-aware tool registry integration

# Thread-safe module-level registry cache (lazy-loaded)
_tool_registry = None
_config = None
_registry_lock = threading.Lock()


def _get_tool_registry():
    """Get or create the tool registry (thread-safe lazy initialization).

    Returns:
        ToolRegistry with detected tool capabilities.
    """
    global _tool_registry, _config

    # Fast path: if already initialized, return without lock
    if _tool_registry is not None:
        return _tool_registry

    # Slow path: acquire lock and initialize
    with _registry_lock:
        # Double-check after acquiring lock
        if _tool_registry is not None:
            return _tool_registry

        from vpo.config import get_config
        from vpo.tools import get_tool_registry

        _config = get_config()
        _tool_registry = get_tool_registry(
            ffmpeg_path=_config.tools.ffmpeg,
            ffprobe_path=_config.tools.ffprobe,
            mkvmerge_path=_config.tools.mkvmerge,
            mkvpropedit_path=_config.tools.mkvpropedit,
            ttl_hours=_config.detection.cache_ttl_hours,
        )

    return _tool_registry


def refresh_tool_registry() -> None:
    """Force refresh of the tool registry (thread-safe).

    Call this if tool paths or availability may have changed.
    """
    global _tool_registry
    with _registry_lock:
        _tool_registry = None


def check_tool_availability() -> dict[str, bool]:
    """Check which external tools are available on the system.

    Uses the tool registry for config-aware detection.

    Returns:
        Dict mapping tool name to availability (True if installed and usable).
    """
    registry = _get_tool_registry()
    return {
        "mkvpropedit": registry.is_available("mkvpropedit"),
        "mkvmerge": registry.is_available("mkvmerge"),
        "ffmpeg": registry.is_available("ffmpeg"),
        "ffprobe": registry.is_available("ffprobe"),
    }


def get_available_tools() -> list[str]:
    """Get list of available external tools.

    Returns:
        List of tool names that are available on the system.
    """
    registry = _get_tool_registry()
    return registry.get_available_tools()


def get_missing_tools() -> list[str]:
    """Get list of missing external tools.

    Returns:
        List of tool names that are not available.
    """
    registry = _get_tool_registry()
    return registry.get_missing_tools()


def get_tool_version(tool_name: str) -> str | None:
    """Get version string for a tool.

    Args:
        tool_name: Name of the tool.

    Returns:
        Version string or None if not available.
    """
    registry = _get_tool_registry()
    tool = registry.get_tool(tool_name)
    return tool.version if tool else None


def require_tool(tool_name: str) -> Path:
    """Get path to a required tool, raising an error if not available.

    Uses the tool registry to respect configured paths.

    Args:
        tool_name: Name of the tool to find.

    Returns:
        Path to the tool executable.

    Raises:
        RuntimeError: If the tool is not available.
    """
    registry = _get_tool_registry()
    tool = registry.get_tool(tool_name)

    if tool is None or not tool.is_available() or tool.path is None:
        # Provide helpful error message with install hints
        from vpo.tools import get_missing_tool_hints

        hints = get_missing_tool_hints(registry)
        hint = hints.get(tool_name, "")

        raise RuntimeError(f"Required tool not available: {tool_name}. {hint}")

    return tool.path


def get_tool_path(tool_name: str) -> Path | None:
    """Get path to a tool, or None if not available.

    Unlike require_tool, this doesn't raise an error.

    Args:
        tool_name: Name of the tool.

    Returns:
        Path to the tool or None if not available.
    """
    registry = _get_tool_registry()
    tool = registry.get_tool(tool_name)
    if tool and tool.is_available():
        return tool.path
    return None
