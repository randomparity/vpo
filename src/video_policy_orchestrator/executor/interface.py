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


def check_tool_availability() -> dict[str, bool]:
    """Check which external tools are available on the system.

    Returns:
        Dict mapping tool name to availability (True if installed and in PATH).
    """
    return {
        "mkvpropedit": shutil.which("mkvpropedit") is not None,
        "mkvmerge": shutil.which("mkvmerge") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
    }


def get_available_tools() -> list[str]:
    """Get list of available external tools.

    Returns:
        List of tool names that are available on the system.
    """
    availability = check_tool_availability()
    return [tool for tool, available in availability.items() if available]


def require_tool(tool_name: str) -> Path:
    """Get path to a required tool, raising an error if not available.

    Args:
        tool_name: Name of the tool to find.

    Returns:
        Path to the tool executable.

    Raises:
        RuntimeError: If the tool is not available.
    """
    tool_path = shutil.which(tool_name)
    if tool_path is None:
        raise RuntimeError(
            f"Required tool not available: {tool_name}. Install mkvtoolnix or ffmpeg."
        )
    return Path(tool_path)
