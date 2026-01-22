"""Backup and rollback logic for phase execution.

This module handles backup creation, rollback on failure, and cleanup.
"""

import logging
import shutil
from pathlib import Path

from .types import PhaseExecutionState

logger = logging.getLogger(__name__)


def rollback_phase(state: PhaseExecutionState) -> bool:
    """Rollback a phase by restoring from backup.

    Args:
        state: The execution state containing backup path.

    Returns:
        True if rollback was successful, False otherwise.
    """
    if state.backup_path is None:
        logger.warning("No backup available for rollback")
        return False

    if not state.backup_path.exists():
        logger.warning("Backup file not found: %s", state.backup_path)
        return False

    try:
        # Restore original file from backup
        shutil.copy2(state.backup_path, state.file_path)
        logger.info("Restored %s from backup", state.file_path.name)
        return True
    except Exception as e:
        logger.error("Failed to restore from backup: %s", e)
        return False


def create_backup(file_path: Path) -> Path | None:
    """Create a backup of the file before modifications.

    Args:
        file_path: Path to the file to backup.

    Returns:
        Path to the backup file, or None if backup failed.
    """
    backup_path = file_path.with_suffix(file_path.suffix + ".vpo-backup")
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception as e:
        logger.warning("Failed to create backup: %s", e)
        return None


def handle_phase_failure(
    state: PhaseExecutionState,
    error: Exception,
) -> None:
    """Handle a phase failure by attempting rollback.

    Args:
        state: The execution state.
        error: The exception that caused the failure.
    """
    logger.error(
        "Phase '%s' failed: %s",
        state.phase.name,
        error,
    )

    if state.file_modified and state.backup_path:
        logger.info("Attempting rollback...")
        if rollback_phase(state):
            logger.info("Rollback successful")
        else:
            logger.error("Rollback failed - file may be in inconsistent state")


def cleanup_backup(state: PhaseExecutionState) -> None:
    """Remove backup file after successful phase completion.

    Args:
        state: The execution state containing backup path.
    """
    if state.backup_path is None:
        return

    if not state.backup_path.exists():
        return

    try:
        state.backup_path.unlink()
        logger.debug("Removed backup file: %s", state.backup_path)
    except Exception as e:
        logger.warning("Failed to remove backup file: %s", e)
