"""File modification time utilities.

This module provides functions for getting and setting file modification times.
These are used by the file_timestamp policy operation to preserve or set
file mtimes after processing.
"""

from __future__ import annotations

import os
import time
from pathlib import Path


class FileTimestampError(OSError):
    """Error setting or getting file timestamps with context.

    Wraps underlying OSError with contextual information about the
    file operation that failed and recovery guidance.
    """


# Timestamp validation constants
MIN_TIMESTAMP = 0.0  # Unix epoch (1970-01-01)
MAX_TIMESTAMP_YEARS_AHEAD = 100  # Maximum years in the future


def _get_max_timestamp() -> float:
    """Calculate maximum allowed timestamp (100 years from now)."""
    return time.time() + (MAX_TIMESTAMP_YEARS_AHEAD * 365.25 * 24 * 60 * 60)


def get_file_mtime(file_path: Path) -> float:
    """Get file modification time as Unix timestamp.

    Args:
        file_path: Path to the file.

    Returns:
        Modification time as seconds since epoch.

    Raises:
        FileTimestampError: If file does not exist or stats cannot be read.
    """
    try:
        return file_path.stat().st_mtime
    except FileNotFoundError as e:
        raise FileTimestampError(
            f"Cannot read mtime: file not found: {file_path}"
        ) from e
    except PermissionError as e:
        raise FileTimestampError(
            f"Cannot read mtime: permission denied for {file_path}. "
            "Check file permissions or run with elevated privileges."
        ) from e
    except OSError as e:
        raise FileTimestampError(f"Cannot read mtime for {file_path}: {e}") from e


def set_file_mtime(file_path: Path, mtime: float) -> None:
    """Set file modification time using os.utime().

    Preserves the access time and only updates the modification time.

    Args:
        file_path: Path to the file.
        mtime: Modification time as seconds since epoch. Must be between
               Unix epoch (0) and 100 years in the future.

    Raises:
        FileTimestampError: If file does not exist, times cannot be set,
                           or timestamp is out of valid bounds.
    """
    # Validate timestamp bounds
    if mtime < MIN_TIMESTAMP:
        raise FileTimestampError(
            f"Invalid timestamp {mtime}: cannot be before Unix epoch (1970-01-01)"
        )
    max_ts = _get_max_timestamp()
    if mtime > max_ts:
        raise FileTimestampError(
            f"Invalid timestamp {mtime}: cannot be more than "
            f"{MAX_TIMESTAMP_YEARS_AHEAD} years in the future"
        )

    try:
        # Get current access time to preserve it
        stat_result = file_path.stat()
        atime = stat_result.st_atime
        # Set times: (atime, mtime)
        os.utime(file_path, (atime, mtime))
    except FileNotFoundError as e:
        raise FileTimestampError(
            f"Cannot set mtime: file not found: {file_path}"
        ) from e
    except PermissionError as e:
        raise FileTimestampError(
            f"Cannot set mtime: permission denied for {file_path}. "
            "Check file permissions or run with elevated privileges."
        ) from e
    except OSError as e:
        raise FileTimestampError(f"Cannot set mtime for {file_path}: {e}") from e


def copy_file_mtime(source: Path, target: Path) -> None:
    """Copy modification time from source to target file.

    Args:
        source: Path to source file to read mtime from.
        target: Path to target file to update.

    Raises:
        FileTimestampError: If either file does not exist or times cannot
                           be read or set.
    """
    mtime = get_file_mtime(source)
    set_file_mtime(target, mtime)
