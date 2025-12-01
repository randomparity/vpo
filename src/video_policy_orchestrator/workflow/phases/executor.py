"""V11 phase executor for user-defined phases.

This module provides the PhaseExecutor class that handles execution of
user-defined phases in V11 policies. It dispatches operations to existing
executors based on the phase definition.
"""

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from video_policy_orchestrator.policy.models import (
    OnErrorMode,
    OperationType,
    PhaseDefinition,
    PhaseExecutionError,
    PhaseResult,
    V11PolicySchema,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.db.types import FileInfo


logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
    """Result of executing a single operation within a phase."""

    operation: OperationType
    success: bool
    changes_made: int = 0
    message: str | None = None
    duration_seconds: float = 0.0


@dataclass
class PhaseExecutionState:
    """Mutable state during phase execution."""

    file_path: Path
    """Path to the media file being processed."""

    phase: PhaseDefinition
    """The phase definition being executed."""

    backup_path: Path | None = None
    """Path to backup file created at phase start."""

    operations_completed: list[str] = field(default_factory=list)
    """List of operation names completed in this phase."""

    file_modified: bool = False
    """True if any operation in this phase modified the file."""

    total_changes: int = 0
    """Total changes made in this phase."""


class V11PhaseExecutor:
    """Executor for V11 user-defined phases.

    This class handles the execution of a single phase, dispatching
    operations to existing executors in canonical order.
    """

    def __init__(
        self,
        conn: Connection,
        policy: V11PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
        policy_name: str = "workflow",
    ) -> None:
        """Initialize the phase executor.

        Args:
            conn: Database connection.
            policy: V11PolicySchema configuration.
            dry_run: If True, preview without making changes.
            verbose: If True, emit detailed logging.
            policy_name: Name of the policy for audit records.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self.policy_name = policy_name

        # Lazy-loaded operation handlers
        self._handlers: dict[OperationType, object] = {}

    def execute_phase(
        self,
        phase: PhaseDefinition,
        file_path: Path,
        file_info: "FileInfo | None" = None,
    ) -> PhaseResult:
        """Execute a single phase on a file.

        Args:
            phase: The phase definition to execute.
            file_path: Path to the media file.
            file_info: Optional FileInfo from database.

        Returns:
            PhaseResult with execution status and details.
        """
        start_time = time.time()
        state = PhaseExecutionState(file_path=file_path, phase=phase)

        # Get operations to execute
        operations = phase.get_operations()
        if not operations:
            # Empty phase - nothing to do
            return PhaseResult(
                phase_name=phase.name,
                success=True,
                duration_seconds=time.time() - start_time,
                operations_executed=(),
                changes_made=0,
                message="Phase has no operations defined",
            )

        logger.info(
            "Executing phase '%s' with %d operation(s): %s",
            phase.name,
            len(operations),
            ", ".join(op.value for op in operations),
        )

        # Create backup before making changes (unless dry-run)
        if not self.dry_run:
            state.backup_path = self._create_backup(file_path)
            if state.backup_path:
                logger.debug("Created backup at %s", state.backup_path)

        try:
            # Execute operations in canonical order
            operation_results: list[OperationResult] = []
            for op_type in operations:
                op_result = self._execute_operation(op_type, state, file_info)
                operation_results.append(op_result)

                if op_result.success:
                    state.operations_completed.append(op_type.value)
                    state.total_changes += op_result.changes_made
                    if op_result.changes_made > 0:
                        state.file_modified = True
                else:
                    # Operation failed - check error handling mode
                    on_error = self.policy.config.on_error
                    if on_error == OnErrorMode.FAIL:
                        raise PhaseExecutionError(
                            phase_name=phase.name,
                            operation=op_type.value,
                            message=op_result.message or "Operation failed",
                        )
                    elif on_error == OnErrorMode.SKIP:
                        # Skip remaining operations in this phase
                        logger.warning(
                            "Operation %s failed in phase '%s', "
                            "skipping remaining operations",
                            op_type.value,
                            phase.name,
                        )
                        break
                    # OnErrorMode.CONTINUE - proceed to next operation

            # Clean up backup on success
            self._cleanup_backup(state)

            duration = time.time() - start_time
            return PhaseResult(
                phase_name=phase.name,
                success=True,
                duration_seconds=duration,
                operations_executed=tuple(state.operations_completed),
                changes_made=state.total_changes,
                message=f"Completed {len(state.operations_completed)} operation(s)",
            )

        except PhaseExecutionError:
            raise
        except Exception as e:
            # Unexpected error - attempt rollback
            duration = time.time() - start_time
            self._handle_phase_failure(state, e)
            raise PhaseExecutionError(
                phase_name=phase.name,
                operation=None,
                message=str(e),
                cause=e,
            ) from e

    def rollback_phase(self, state: PhaseExecutionState) -> bool:
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
            logger.info("Restored %s from backup", state.file_path)
            return True
        except Exception as e:
            logger.error("Failed to restore from backup: %s", e)
            return False

    def _create_backup(self, file_path: Path) -> Path | None:
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

    def _handle_phase_failure(
        self,
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
            if self.rollback_phase(state):
                logger.info("Rollback successful")
            else:
                logger.error("Rollback failed - file may be in inconsistent state")

    def _cleanup_backup(self, state: PhaseExecutionState) -> None:
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

    def _execute_operation(
        self,
        op_type: OperationType,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> OperationResult:
        """Execute a single operation.

        Args:
            op_type: The type of operation to execute.
            state: Current execution state.
            file_info: FileInfo from database.

        Returns:
            OperationResult with execution status.
        """
        start_time = time.time()
        logger.debug("Executing operation: %s", op_type.value)

        try:
            changes = self._dispatch_operation(op_type, state, file_info)
            return OperationResult(
                operation=op_type,
                success=True,
                changes_made=changes,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error("Operation %s failed: %s", op_type.value, e)
            return OperationResult(
                operation=op_type,
                success=False,
                message=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _dispatch_operation(
        self,
        op_type: OperationType,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Dispatch an operation to the appropriate handler.

        Args:
            op_type: The type of operation.
            state: Current execution state.
            file_info: FileInfo from database.

        Returns:
            Number of changes made.

        Note:
            This is a placeholder implementation. Full implementation
            requires integration with existing executors.
        """
        phase = state.phase

        # For now, log what would be executed
        # Full implementation will integrate with existing executors
        if op_type == OperationType.CONTAINER and phase.container:
            logger.info(
                "[%s] Container conversion to %s",
                "DRY-RUN" if self.dry_run else "EXEC",
                phase.container.target,
            )
            return 0  # TODO: implement

        elif op_type == OperationType.AUDIO_FILTER and phase.audio_filter:
            logger.info(
                "[%s] Audio filter: languages=%s",
                "DRY-RUN" if self.dry_run else "EXEC",
                phase.audio_filter.languages,
            )
            return 0  # TODO: implement

        elif op_type == OperationType.SUBTITLE_FILTER and phase.subtitle_filter:
            logger.info(
                "[%s] Subtitle filter: languages=%s",
                "DRY-RUN" if self.dry_run else "EXEC",
                phase.subtitle_filter.languages,
            )
            return 0  # TODO: implement

        elif op_type == OperationType.ATTACHMENT_FILTER and phase.attachment_filter:
            logger.info(
                "[%s] Attachment filter: remove_all=%s",
                "DRY-RUN" if self.dry_run else "EXEC",
                phase.attachment_filter.remove_all,
            )
            return 0  # TODO: implement

        elif op_type == OperationType.TRACK_ORDER and phase.track_order:
            logger.info(
                "[%s] Track ordering: %s",
                "DRY-RUN" if self.dry_run else "EXEC",
                [t.value for t in phase.track_order],
            )
            return 0  # TODO: implement

        elif op_type == OperationType.DEFAULT_FLAGS and phase.default_flags:
            logger.info(
                "[%s] Default flags configuration",
                "DRY-RUN" if self.dry_run else "EXEC",
            )
            return 0  # TODO: implement

        elif op_type == OperationType.CONDITIONAL and phase.conditional:
            logger.info(
                "[%s] Conditional rules: %d rule(s)",
                "DRY-RUN" if self.dry_run else "EXEC",
                len(phase.conditional),
            )
            return 0  # TODO: implement

        elif op_type == OperationType.AUDIO_SYNTHESIS and phase.audio_synthesis:
            logger.info(
                "[%s] Audio synthesis: %d track(s)",
                "DRY-RUN" if self.dry_run else "EXEC",
                len(phase.audio_synthesis.tracks),
            )
            return 0  # TODO: implement

        elif op_type == OperationType.TRANSCODE:
            if phase.transcode:
                logger.info(
                    "[%s] Video transcode: target=%s",
                    "DRY-RUN" if self.dry_run else "EXEC",
                    phase.transcode.target_codec,
                )
            if phase.audio_transcode:
                logger.info(
                    "[%s] Audio transcode: target=%s",
                    "DRY-RUN" if self.dry_run else "EXEC",
                    phase.audio_transcode.transcode_to,
                )
            return 0  # TODO: implement

        elif op_type == OperationType.TRANSCRIPTION and phase.transcription:
            logger.info(
                "[%s] Transcription analysis: enabled=%s",
                "DRY-RUN" if self.dry_run else "EXEC",
                phase.transcription.enabled,
            )
            return 0  # TODO: implement

        return 0
