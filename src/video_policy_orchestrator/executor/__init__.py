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
    FileLockError,
    cleanup_backup,
    create_backup,
    file_lock,
    get_backup_path,
    has_backup,
    restore_from_backup,
)
from video_policy_orchestrator.executor.ffmpeg_metadata import FfmpegMetadataExecutor
from video_policy_orchestrator.executor.interface import (
    Executor,
    ExecutorResult,
    check_tool_availability,
    get_available_tools,
    require_tool,
)
from video_policy_orchestrator.executor.mkvpropedit import MkvpropeditExecutor

__all__ = [
    # Interface
    "Executor",
    "ExecutorResult",
    "check_tool_availability",
    "get_available_tools",
    "require_tool",
    # Executors
    "MkvpropeditExecutor",
    "FfmpegMetadataExecutor",
    # Backup
    "BACKUP_SUFFIX",
    "FileLockError",
    "create_backup",
    "restore_from_backup",
    "cleanup_backup",
    "get_backup_path",
    "has_backup",
    "file_lock",
]
