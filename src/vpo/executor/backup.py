"""Backup creation, restoration, and cleanup utilities.

This module provides file backup functionality for safe media file modifications.
"""

import fcntl
import logging
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

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
    lock_acquired = False

    try:
        # Create lock file
        lock_file = open(lock_path, "w", encoding="utf-8")

        try:
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_acquired = True
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
        # Always clean up: close file handle
        if lock_file is not None:
            lock_file.close()
        # Only remove lock file if WE acquired the lock (prevents race condition
        # where a failed acquisition would delete another process's lock file)
        if lock_acquired:
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
        logger.debug(
            "Removed existing backup",
            extra={"backup_path": str(backup_path)},
        )

    file_size = file_path.stat().st_size
    logger.debug(
        "Creating backup",
        extra={
            "source_path": str(file_path),
            "backup_path": str(backup_path),
            "file_size_bytes": file_size,
        },
    )

    shutil.copy2(file_path, backup_path)

    logger.debug(
        "Backup created successfully",
        extra={"backup_path": str(backup_path)},
    )
    return backup_path


class BackupRestorationError(Exception):
    """Raised when backup restoration fails verification."""

    pass


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
        BackupRestorationError: If restoration fails verification (file missing
            or empty after move).
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

    logger.info(
        "Restoring from backup",
        extra={
            "backup_path": str(backup_path),
            "target_path": str(original_path),
        },
    )

    # If original exists, remove it first
    if original_path.exists():
        original_path.unlink()

    shutil.move(str(backup_path), str(original_path))

    # Verify restoration succeeded
    if not original_path.exists():
        raise BackupRestorationError(
            f"Restoration failed: {original_path} does not exist after move"
        )
    if original_path.stat().st_size == 0:
        raise BackupRestorationError(
            f"Restoration failed: {original_path} is empty after move"
        )

    logger.info(
        "Backup restored successfully",
        extra={"restored_path": str(original_path)},
    )
    return original_path


def safe_restore_from_backup(
    backup_path: Path, original_path: Path | None = None
) -> bool:
    """Safely restore a file from backup, logging any errors.

    This is a wrapper around restore_from_backup() that catches and logs
    any restoration errors instead of propagating them. Use this in error
    handlers where restoration failure shouldn't mask the original error.

    Args:
        backup_path: Path to the backup file.
        original_path: Path to restore to. If None, inferred from backup path.

    Returns:
        True if restoration succeeded, False otherwise.
    """
    try:
        restore_from_backup(backup_path, original_path)
        return True
    except Exception as e:
        logger.error(
            "Failed to restore backup %s: %s. "
            "Original file may be corrupted or missing.",
            backup_path,
            e,
        )
        return False


def cleanup_backup(backup_path: Path) -> None:
    """Remove a backup file after successful operation.

    Args:
        backup_path: Path to the backup file to remove.

    Note:
        This is a no-op if the backup file does not exist.
    """
    if backup_path.exists():
        logger.debug(
            "Cleaning up backup",
            extra={"backup_path": str(backup_path)},
        )
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


class InsufficientDiskSpaceError(Exception):
    """Raised when there is not enough disk space for the operation."""

    pass


def check_min_free_disk_percent(
    directory: Path,
    required_bytes: int,
    min_free_percent: float,
) -> str | None:
    """Check if operation would violate minimum free space threshold.

    This check ensures the filesystem maintains a safety buffer of free space
    after the operation completes. This is different from check_disk_space(),
    which only checks if there's enough space for the operation itself.

    Args:
        directory: Directory where the operation will occur.
        required_bytes: Estimated bytes the operation will use.
        min_free_percent: Minimum percentage of disk that must remain free (0-100).
            Set to 0 to disable the check.

    Returns:
        Error message if threshold would be violated, None if OK.
    """
    # Check disabled
    if min_free_percent <= 0:
        return None

    try:
        stat = shutil.disk_usage(directory)
    except PermissionError:
        logger.warning("Cannot check disk usage for %s: permission denied", directory)
        return None
    except OSError as e:
        logger.warning("Cannot check disk usage for %s: %s", directory, e)
        return None

    total = stat.total
    current_free = stat.free

    # Calculate what free space would be after operation
    post_operation_free = current_free - required_bytes
    if post_operation_free < 0:
        post_operation_free = 0

    # Calculate percentage that would remain free
    post_operation_free_percent = (post_operation_free / total) * 100

    if post_operation_free_percent < min_free_percent:
        # Format sizes for human-readable message
        def format_size(size: int) -> str:
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} PB"

        current_free_percent = current_free / total * 100
        return (
            f"Operation would leave only {post_operation_free_percent:.1f}% "
            f"free disk space (threshold: {min_free_percent:.1f}%). "
            f"Currently {current_free_percent:.1f}% free "
            f"({format_size(current_free)} of {format_size(total)}). "
            f"Free up space or adjust min_free_disk_percent in config."
        )


def check_disk_space(
    file_path: Path,
    multiplier: float = 2.5,
) -> None:
    """Pre-flight check for sufficient disk space before backup+remux operations.

    Use this function when you need a STRICT check before operations that
    create backups (e.g., container remux). This function raises an exception
    if space is insufficient, stopping the operation before it starts.

    This check ensures there's enough space for:
    - The backup file (1x original size)
    - The temporary output file (1x original size)
    - Some buffer for safety (0.5x original size)

    For codec-aware transcode operations where output may be smaller than
    input, use ffmpeg_utils.check_disk_space_for_transcode() instead,
    which returns an error message string (or None) and estimates space
    based on target codec compression ratios.

    Args:
        file_path: Path to the file being processed.
        multiplier: Multiplier for required space (default 2.5x file size).

    Raises:
        InsufficientDiskSpaceError: If not enough disk space is available.
        FileNotFoundError: If the file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = file_path.stat().st_size
    required_space = int(file_size * multiplier)

    # Get available space on the filesystem containing the file
    stat = shutil.disk_usage(file_path.parent)
    available_space = stat.free

    if available_space < required_space:
        # Format sizes for human-readable message
        def format_size(size: int) -> str:
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} PB"

        raise InsufficientDiskSpaceError(
            f"Insufficient disk space for remux operation. "
            f"Required: {format_size(required_space)}, "
            f"Available: {format_size(available_space)}. "
            f"Free up space or move file to a filesystem with more space."
        )
