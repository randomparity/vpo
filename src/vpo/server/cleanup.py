"""Temp file cleanup utilities for daemon startup.

This module provides functions to clean up orphaned temp files that may
accumulate if the process is killed unexpectedly (SIGKILL, OOM, crash).

Temp file patterns:
- .vpo_temp_* : Partial transcode outputs
- vpo_passlog_* : FFmpeg two-pass encoding logs
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_orphaned_temp_files(
    search_dirs: list[Path] | None = None,
    max_age_hours: float = 1.0,
) -> int:
    """Clean up orphaned VPO temp files.

    Removes temp files that are older than max_age_hours to avoid
    deleting files from currently-running operations.

    Args:
        search_dirs: Directories to search. Defaults to ~/.vpo/
        max_age_hours: Only clean files older than this (safety buffer).
            Default is 1 hour.

    Returns:
        Number of files cleaned up.
    """
    if search_dirs is None:
        search_dirs = [Path.home() / ".vpo"]

    cleaned = 0
    cutoff_time = time.time() - (max_age_hours * 3600)

    patterns = [".vpo_temp_*", "vpo_passlog_*"]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        for pattern in patterns:
            # Search recursively for temp files
            for temp_file in search_dir.rglob(pattern):
                if not temp_file.is_file():
                    continue

                try:
                    mtime = temp_file.stat().st_mtime
                    if mtime < cutoff_time:
                        temp_file.unlink()
                        logger.info("Cleaned orphaned temp file: %s", temp_file)
                        cleaned += 1
                except OSError as e:
                    logger.warning("Could not clean temp file %s: %s", temp_file, e)

    return cleaned
