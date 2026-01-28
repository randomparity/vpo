"""Move executor for file organization.

This module provides file movement functionality for organizing
output files based on metadata-driven destination templates.

Design Note:
    MoveExecutor intentionally does not implement the Executor protocol
    defined in interface.py. The Executor protocol is designed for media
    file modification operations (metadata changes, transcoding, container
    conversion), while MoveExecutor handles post-processing file organization.
    The different interfaces reflect distinct responsibilities:
    - Executor: operates on Plan, returns ExecutorResult
    - MoveExecutor: operates on MovePlan, returns MoveResult
"""

import errno
import logging
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class MoveErrorType(Enum):
    """Categorization of move operation errors.

    Enables future retry logic by distinguishing transient from permanent failures.
    """

    DISK_SPACE = "disk_space"
    PERMISSION = "permission"
    NOT_FOUND = "not_found"
    CROSS_DEVICE = "cross_device"
    IO_ERROR = "io_error"
    UNKNOWN = "unknown"


@dataclass
class MoveResult:
    """Result of a move operation."""

    success: bool
    source_path: Path
    destination_path: Path | None = None
    error_message: str | None = None
    error_type: MoveErrorType | None = None


@dataclass
class MovePlan:
    """Plan for moving a file."""

    source_path: Path
    destination_path: Path
    create_directories: bool = True
    overwrite: bool = False


class MoveExecutor:
    """Executor for file movement operations."""

    def __init__(
        self,
        create_directories: bool = True,
        overwrite: bool = False,
    ) -> None:
        """Initialize the move executor.

        Args:
            create_directories: Create destination directories if needed.
            overwrite: Overwrite existing files at destination.
        """
        self.create_directories = create_directories
        self.overwrite = overwrite

    def create_plan(
        self,
        source_path: Path,
        destination_path: Path,
    ) -> MovePlan:
        """Create a move plan.

        Args:
            source_path: Path to source file.
            destination_path: Target destination path.

        Returns:
            MovePlan with operation details.
        """
        return MovePlan(
            source_path=source_path,
            destination_path=destination_path,
            create_directories=self.create_directories,
            overwrite=self.overwrite,
        )

    def validate(self, plan: MovePlan) -> list[str]:
        """Validate a move plan.

        Args:
            plan: Move plan to validate.

        Returns:
            List of validation errors (empty if valid).
        """
        errors = []

        # Check source exists
        if not plan.source_path.exists():
            errors.append(f"Source file does not exist: {plan.source_path}")

        # Check source is a file
        if plan.source_path.exists() and not plan.source_path.is_file():
            errors.append(f"Source is not a file: {plan.source_path}")

        # Check destination doesn't exist (unless overwrite enabled)
        if plan.destination_path.exists() and not plan.overwrite:
            errors.append(
                f"Destination already exists: {plan.destination_path}. "
                "Use overwrite=True to replace."
            )

        # Check destination directory exists (or can be created)
        dest_dir = plan.destination_path.parent
        if not dest_dir.exists() and not plan.create_directories:
            errors.append(
                f"Destination directory does not exist: {dest_dir}. "
                "Use create_directories=True to create."
            )

        # Check disk space if source and destination directory exist
        if plan.source_path.exists():
            source_size = plan.source_path.stat().st_size
            # Check destination directory or first existing parent
            check_dir = dest_dir
            while not check_dir.exists() and check_dir.parent != check_dir:
                check_dir = check_dir.parent
            if check_dir.exists():
                try:
                    free_space = shutil.disk_usage(check_dir).free
                    if source_size > free_space:
                        errors.append(
                            f"Insufficient disk space: need {source_size} bytes, "
                            f"have {free_space} bytes"
                        )
                except OSError:
                    # Cannot check disk space, skip validation
                    pass

        return errors

    def execute(self, plan: MovePlan) -> MoveResult:
        """Execute a move plan.

        Args:
            plan: The move plan to execute.

        Returns:
            MoveResult with success status and details.
        """
        # Validate first
        errors = self.validate(plan)
        if errors:
            return MoveResult(
                success=False,
                source_path=plan.source_path,
                error_message="; ".join(errors),
            )

        try:
            # Create destination directory if needed
            if plan.create_directories:
                plan.destination_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            logger.info(
                "Moving file: %s -> %s", plan.source_path, plan.destination_path
            )
            shutil.move(str(plan.source_path), str(plan.destination_path))

            logger.info("Move completed: %s", plan.destination_path)
            return MoveResult(
                success=True,
                source_path=plan.source_path,
                destination_path=plan.destination_path,
            )

        except OSError as e:
            # Categorize error by errno for future retry logic
            errno_to_type = {
                errno.ENOSPC: MoveErrorType.DISK_SPACE,
                errno.EACCES: MoveErrorType.PERMISSION,
                errno.EPERM: MoveErrorType.PERMISSION,
                errno.ENOENT: MoveErrorType.NOT_FOUND,
                errno.EXDEV: MoveErrorType.CROSS_DEVICE,
                errno.EIO: MoveErrorType.IO_ERROR,
                errno.EROFS: MoveErrorType.IO_ERROR,
            }
            error_type = errno_to_type.get(e.errno, MoveErrorType.UNKNOWN)

            logger.error("Move failed (%s): %s", error_type.value, e)
            return MoveResult(
                success=False,
                source_path=plan.source_path,
                error_message=str(e),
                error_type=error_type,
            )

    def dry_run(self, plan: MovePlan) -> dict:
        """Generate dry-run output showing what would be done.

        Args:
            plan: The move plan.

        Returns:
            Dictionary with planned operation.
        """
        errors = self.validate(plan)

        return {
            "source": str(plan.source_path),
            "destination": str(plan.destination_path),
            "create_directories": plan.create_directories,
            "overwrite": plan.overwrite,
            "would_create_dirs": not plan.destination_path.parent.exists(),
            "valid": len(errors) == 0,
            "errors": errors,
        }


# Maximum number of suffix attempts before giving up
MAX_UNIQUE_PATH_ATTEMPTS = 10000


def ensure_unique_path(
    path: Path, max_attempts: int = MAX_UNIQUE_PATH_ATTEMPTS
) -> Path:
    """Ensure a path is unique by adding a suffix if needed.

    If the path already exists, adds (1), (2), etc. until unique.

    Args:
        path: Desired path.
        max_attempts: Maximum number of attempts before raising error.

    Returns:
        Unique path that doesn't exist.

    Raises:
        RuntimeError: If no unique path found within max_attempts.
    """
    if not path.exists():
        return path

    base = path.stem
    suffix = path.suffix
    parent = path.parent

    for counter in range(1, max_attempts + 1):
        new_path = parent / f"{base} ({counter}){suffix}"
        if not new_path.exists():
            return new_path

    raise RuntimeError(
        f"Could not find unique path after {max_attempts} attempts: {path}"
    )
