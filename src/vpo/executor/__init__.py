"""Execution layer module for Video Policy Orchestrator.

This module provides adapters for external tools:
- interface: Executor protocol and tool availability checks
- mkvpropedit: MKV metadata changes (flags, titles, language)
- mkvmerge: MKV track reordering via remux
- ffmpeg_metadata: Non-MKV metadata changes
- ffmpeg_remux: Container conversion to MP4
- ffmpeg_base: Base class for FFmpeg-based executors
- ffmpeg_utils: Shared utilities for FFmpeg executors
- backup: Backup creation, restoration, and cleanup utilities
"""

from vpo.executor import ffmpeg_utils
from vpo.executor.backup import (
    BACKUP_SUFFIX,
    FileLockError,
    cleanup_backup,
    create_backup,
    file_lock,
    get_backup_path,
    has_backup,
    restore_from_backup,
)
from vpo.executor.ffmpeg_base import FFmpegExecutorBase
from vpo.executor.ffmpeg_metadata import FfmpegMetadataExecutor
from vpo.executor.ffmpeg_remux import FFmpegRemuxExecutor
from vpo.executor.interface import (
    Executor,
    ExecutorResult,
    check_tool_availability,
    get_available_tools,
    require_tool,
)
from vpo.executor.mkvmerge import MkvmergeExecutor
from vpo.executor.mkvpropedit import MkvpropeditExecutor

__all__ = [
    # Interface
    "Executor",
    "ExecutorResult",
    "check_tool_availability",
    "get_available_tools",
    "require_tool",
    # Executors
    "MkvpropeditExecutor",
    "MkvmergeExecutor",
    "FfmpegMetadataExecutor",
    "FFmpegRemuxExecutor",
    # Base class
    "FFmpegExecutorBase",
    # Utilities
    "ffmpeg_utils",
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
