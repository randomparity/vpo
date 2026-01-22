"""File modification time utilities.

This module provides functions for getting and setting file modification times.
These are used by the file_timestamp policy operation to preserve or set
file mtimes after processing.
"""

from __future__ import annotations

import os
from pathlib import Path


def get_file_mtime(file_path: Path) -> float:
    """Get file modification time as Unix timestamp.

    Args:
        file_path: Path to the file.

    Returns:
        Modification time as seconds since epoch.

    Raises:
        FileNotFoundError: If file does not exist.
        OSError: If file stats cannot be read.
    """
    return file_path.stat().st_mtime


def set_file_mtime(file_path: Path, mtime: float) -> None:
    """Set file modification time using os.utime().

    Preserves the access time and only updates the modification time.

    Args:
        file_path: Path to the file.
        mtime: Modification time as seconds since epoch.

    Raises:
        FileNotFoundError: If file does not exist.
        OSError: If file times cannot be set.
    """
    # Get current access time to preserve it
    stat_result = file_path.stat()
    atime = stat_result.st_atime
    # Set times: (atime, mtime)
    os.utime(file_path, (atime, mtime))


def copy_file_mtime(source: Path, target: Path) -> None:
    """Copy modification time from source to target file.

    Args:
        source: Path to source file to read mtime from.
        target: Path to target file to update.

    Raises:
        FileNotFoundError: If either file does not exist.
        OSError: If times cannot be read or set.
    """
    mtime = get_file_mtime(source)
    set_file_mtime(target, mtime)
