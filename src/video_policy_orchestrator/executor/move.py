"""Move executor for file organization.

This module provides file movement functionality for organizing
output files based on metadata-driven destination templates.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MoveResult:
    """Result of a move operation."""

    success: bool
    source_path: Path
    destination_path: Path | None = None
    error_message: str | None = None


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
            logger.error("Move failed: %s", e)
            return MoveResult(
                success=False,
                source_path=plan.source_path,
                error_message=str(e),
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


def ensure_unique_path(path: Path) -> Path:
    """Ensure a path is unique by adding a suffix if needed.

    If the path already exists, adds (1), (2), etc. until unique.

    Args:
        path: Desired path.

    Returns:
        Unique path that doesn't exist.
    """
    if not path.exists():
        return path

    base = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        new_path = parent / f"{base} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1
