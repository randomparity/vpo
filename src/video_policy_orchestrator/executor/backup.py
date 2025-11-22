"""Backup creation, restoration, and cleanup utilities.

This module provides file backup functionality for safe media file modifications.
"""

import fcntl
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Backup file suffix
BACKUP_SUFFIX = ".vpo-backup"

# Lock file suffix
LOCK_SUFFIX = ".vpo-lock"


class FileLockError(Exception):
    """Error acquiring file lock (file is being modified by another operation)."""

    pass


@contextmanager
def file_lock(file_path: Path) -> Iterator[None]:
    """Context manager for acquiring an exclusive lock on a file.

    This prevents concurrent modifications to the same file.
    The lock is non-blocking - if the file is already locked, this
    raises FileLockError immediately rather than waiting.

    Args:
        file_path: Path to the file to lock.

    Yields:
        None when lock is acquired.

    Raises:
        FileLockError: If the lock cannot be acquired (file is in use).
    """
    lock_path = file_path.with_suffix(file_path.suffix + LOCK_SUFFIX)
    lock_file = None

    try:
        # Create lock file
        lock_file = open(lock_path, "w")

        try:
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as e:
            raise FileLockError(
                f"File is being modified by another operation: {file_path}"
            ) from e

        try:
            yield
        finally:
            # Release lock
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except FileLockError:
        raise
    finally:
        # Always clean up: close file handle and remove lock file
        if lock_file is not None:
            lock_file.close()
        lock_path.unlink(missing_ok=True)


def create_backup(file_path: Path) -> Path:
    """Create a backup of a file before modification.

    Args:
        file_path: Path to the file to backup.

    Returns:
        Path to the created backup file.

    Raises:
        FileNotFoundError: If the source file does not exist.
        PermissionError: If backup cannot be created due to permissions.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot backup: file not found: {file_path}")

    backup_path = file_path.with_suffix(file_path.suffix + BACKUP_SUFFIX)

    # If a backup already exists, remove it first
    if backup_path.exists():
        backup_path.unlink()

    shutil.copy2(file_path, backup_path)
    return backup_path


def restore_from_backup(backup_path: Path, original_path: Path | None = None) -> Path:
    """Restore a file from its backup.

    Args:
        backup_path: Path to the backup file.
        original_path: Path to restore to. If None, inferred from backup path.

    Returns:
        Path to the restored file.

    Raises:
        FileNotFoundError: If the backup file does not exist.
        PermissionError: If restoration cannot be performed due to permissions.
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    if original_path is None:
        # Remove the .vpo-backup suffix to get original path
        original_str = str(backup_path)
        if original_str.endswith(BACKUP_SUFFIX):
            original_path = Path(original_str[: -len(BACKUP_SUFFIX)])
        else:
            raise ValueError(f"Cannot infer original path from backup: {backup_path}")

    # If original exists, remove it first
    if original_path.exists():
        original_path.unlink()

    shutil.move(str(backup_path), str(original_path))
    return original_path


def cleanup_backup(backup_path: Path) -> None:
    """Remove a backup file after successful operation.

    Args:
        backup_path: Path to the backup file to remove.

    Note:
        This is a no-op if the backup file does not exist.
    """
    if backup_path.exists():
        backup_path.unlink()


def get_backup_path(file_path: Path) -> Path:
    """Get the backup path for a given file.

    Args:
        file_path: Path to the original file.

    Returns:
        Path where the backup would be stored.
    """
    return file_path.with_suffix(file_path.suffix + BACKUP_SUFFIX)


def has_backup(file_path: Path) -> bool:
    """Check if a backup exists for a file.

    Args:
        file_path: Path to the original file.

    Returns:
        True if a backup file exists.
    """
    return get_backup_path(file_path).exists()
