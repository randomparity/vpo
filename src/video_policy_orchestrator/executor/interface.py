"""Executor protocol and tool availability utilities.

This module defines the interface for execution adapters and utilities
to check external tool availability.
"""

import shutil
from pathlib import Path
from typing import Protocol

from video_policy_orchestrator.policy.models import Plan


class ExecutorResult:
    """Result of an executor operation."""

    def __init__(
        self,
        success: bool,
        message: str = "",
        backup_path: Path | None = None,
    ) -> None:
        self.success = success
        self.message = message
        self.backup_path = backup_path


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

    def execute(self, plan: Plan, keep_backup: bool = True) -> ExecutorResult:
        """Execute the plan on the target file.

        Args:
            plan: The execution plan to apply.
            keep_backup: Whether to keep the backup file after success.

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

# Module-level registry cache (lazy-loaded)
_tool_registry = None
_config = None


def _get_tool_registry():
    """Get or create the tool registry (lazy initialization).

    Returns:
        ToolRegistry with detected tool capabilities.
    """
    global _tool_registry, _config

    if _tool_registry is None:
        from video_policy_orchestrator.config import get_config
        from video_policy_orchestrator.tools import get_tool_registry

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
    """Force refresh of the tool registry.

    Call this if tool paths or availability may have changed.
    """
    global _tool_registry
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
        from video_policy_orchestrator.tools import get_missing_tool_hints

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


# =============================================================================
# Legacy Compatibility Functions
# =============================================================================
# These provide backwards compatibility with code that directly uses shutil.which


def check_tool_availability_simple() -> dict[str, bool]:
    """Check tool availability using simple PATH lookup (no config).

    This is the original implementation, kept for cases where
    configuration is not yet loaded.

    Returns:
        Dict mapping tool name to availability.
    """
    return {
        "mkvpropedit": shutil.which("mkvpropedit") is not None,
        "mkvmerge": shutil.which("mkvmerge") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
    }


def require_tool_simple(tool_name: str) -> Path:
    """Get path to a tool using simple PATH lookup (no config).

    Args:
        tool_name: Name of the tool.

    Returns:
        Path to the tool.

    Raises:
        RuntimeError: If tool not found.
    """
    tool_path = shutil.which(tool_name)
    if tool_path is None:
        raise RuntimeError(
            f"Required tool not available: {tool_name}. Install mkvtoolnix or ffmpeg."
        )
    return Path(tool_path)
