"""Execution layer module for Video Policy Orchestrator.

This module provides adapters for external tools:
- interface: Executor protocol and tool availability checks
- mkvpropedit: MKV metadata changes (flags, titles, language)
- mkvmerge: MKV track reordering via remux
- ffmpeg_metadata: Non-MKV metadata changes
- backup: Backup creation, restoration, and cleanup utilities
"""

from video_policy_orchestrator.executor.backup import (
    BACKUP_SUFFIX,
    cleanup_backup,
    create_backup,
    get_backup_path,
    has_backup,
    restore_from_backup,
)
from video_policy_orchestrator.executor.interface import (
    Executor,
    ExecutorResult,
    check_tool_availability,
    get_available_tools,
    require_tool,
)

__all__ = [
    # Interface
    "Executor",
    "ExecutorResult",
    "check_tool_availability",
    "get_available_tools",
    "require_tool",
    # Backup
    "BACKUP_SUFFIX",
    "create_backup",
    "restore_from_backup",
    "cleanup_backup",
    "get_backup_path",
    "has_backup",
]
