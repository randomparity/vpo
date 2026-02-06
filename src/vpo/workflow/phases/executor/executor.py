"""Phase executor for user-defined phases.

This module provides the PhaseExecutor class that handles execution of
user-defined phases in phased policies. It dispatches operations to existing
executors based on the phase definition.
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from vpo.core.file_utils import get_file_mtime
from vpo.db.queries import get_file_by_path
from vpo.policy.evaluator import Plan
from vpo.policy.types import (
    OnErrorMode,
    OperationType,
    PhaseDefinition,
    PhaseExecutionError,
    PhaseResult,
    PolicySchema,
)
from vpo.tools.ffmpeg_progress import FFmpegProgress

from .backup import cleanup_backup, create_backup, handle_phase_failure
from .helpers import get_tools, get_tracks, parse_plugin_metadata, select_executor
from .types import OperationResult, PhaseExecutionState

if TYPE_CHECKING:
    from vpo.db.types import FileInfo
    from vpo.executor import (
        FfmpegMetadataExecutor,
        FFmpegRemuxExecutor,
        MkvmergeExecutor,
        MkvpropeditExecutor,
    )
    from vpo.plugin import PluginRegistry


logger = logging.getLogger(__name__)


class PhaseExecutor:
    """Executor for user-defined phases.

    This class handles the execution of a single phase, dispatching
    operations to existing executors in canonical order.
    """

    def __init__(
        self,
        conn: Connection,
        policy: PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
        policy_name: str = "workflow",
        plugin_registry: "PluginRegistry | None" = None,
        ffmpeg_progress_callback: Callable[[FFmpegProgress], None] | None = None,
    ) -> None:
        """Initialize the phase executor.

        Args:
            conn: Database connection.
            policy: PolicySchema configuration.
            dry_run: If True, preview without making changes.
            verbose: If True, emit detailed logging.
            policy_name: Name of the policy for audit records.
            plugin_registry: Optional plugin registry for transcription.
                If provided, uses TranscriptionCoordinator for transcription
                operations. If None, transcription operations will be skipped.
            ffmpeg_progress_callback: Optional callback for FFmpeg progress updates.
                Used during container conversion with audio transcoding.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self.policy_name = policy_name
        self._plugin_registry = plugin_registry
        self._ffmpeg_progress_callback = ffmpeg_progress_callback

        # Cache tool availability
        self._tools: dict[str, bool] | None = None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_tools(self) -> dict[str, bool]:
        """Get tool availability, caching the result."""
        if self._tools is None:
            self._tools = get_tools(None)
        return self._tools

    def _get_tracks(self, file_path: Path):
        """Get tracks from database for a file.

        Args:
            file_path: Path to the media file.

        Returns:
            List of TrackInfo for the file.

        Raises:
            ValueError: If file is not in database.
        """

        file_record = get_file_by_path(self.conn, str(file_path))
        if file_record is None:
            raise ValueError(f"File not in database: {file_path}")
        return get_tracks(self.conn, file_record.id)

    def _parse_plugin_metadata(
        self,
        file_record,
        file_path: Path,
        file_id: str,
        context: str = "operations",
    ):
        """Parse plugin metadata JSON from FileRecord."""
        return parse_plugin_metadata(file_record, file_path, file_id, context)

    def _select_executor(
        self, plan: Plan, container: str
    ) -> (
        "MkvpropeditExecutor"
        "| MkvmergeExecutor"
        "| FFmpegRemuxExecutor"
        "| FfmpegMetadataExecutor"
        "| None"
    ):
        """Select appropriate executor based on plan and container."""
        tools = self._get_tools()
        return select_executor(plan, container, tools, self._ffmpeg_progress_callback)

    # =========================================================================
    # Phase Execution
    # =========================================================================

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
        original_file_path = file_path  # Capture for tracking path changes
        state = PhaseExecutionState(file_path=file_path, phase=phase)

        # Capture original file mtime for file_timestamp preserve mode
        # Do this before any operations modify the file
        if phase.file_timestamp is not None:
            try:
                state.original_mtime = get_file_mtime(file_path)
                logger.debug(
                    "Captured original file mtime: %s",
                    state.original_mtime,
                )
            except OSError as e:
                if phase.file_timestamp.mode == "preserve":
                    # Fail loudly - user explicitly requested preservation
                    raise PhaseExecutionError(
                        phase_name=phase.name,
                        operation=None,
                        message=f"Cannot capture mtime for preserve mode: {e}",
                    ) from e
                logger.warning(
                    "Failed to capture mtime (mode=%s): %s",
                    phase.file_timestamp.mode,
                    e,
                )

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
            "Executing phase '%s' with %d operation(s) on %s: %s",
            phase.name,
            len(operations),
            file_path.name,
            ", ".join(op.value for op in operations),
        )

        # Create backup before making changes (unless dry-run)
        if not self.dry_run:
            state.backup_path = create_backup(file_path)
            if state.backup_path is None:
                raise PhaseExecutionError(
                    phase_name=phase.name,
                    operation=None,
                    message="Cannot proceed: backup creation failed "
                    "(check disk space/permissions)",
                )
            logger.debug(
                "Created backup for %s at %s", file_path.name, state.backup_path
            )

        try:
            # Execute operations in canonical order
            for op_type in operations:
                op_result = self._execute_operation(op_type, state, file_info)

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
                        # Capture the failure before breaking
                        state.operation_failures.append(
                            (op_type.value, op_result.message or "Operation failed")
                        )
                        break
                    # OnErrorMode.CONTINUE - proceed to next operation
                    # Capture failure for logging
                    state.operation_failures.append(
                        (op_type.value, op_result.message or "Operation failed")
                    )

            # Clean up backup on success
            cleanup_backup(state)

            duration = time.time() - start_time

            # Build track order change tuple if we have before/after data
            track_order_change = None
            if state.track_order_before and state.track_order_after:
                track_order_change = (state.track_order_before, state.track_order_after)

            # Determine if path changed during phase execution
            result_output_path = (
                state.file_path if state.file_path != original_file_path else None
            )

            return PhaseResult(
                phase_name=phase.name,
                success=True,
                duration_seconds=duration,
                operations_executed=tuple(state.operations_completed),
                changes_made=state.total_changes,
                message=f"Completed {len(state.operations_completed)} operation(s)",
                transcode_skip_reason=state.transcode_skip_reason,
                transcode_reasons=tuple(state.transcode_reasons),
                encoding_fps=state.encoding_fps,
                encoding_bitrate_kbps=state.encoding_bitrate_kbps,
                total_frames=state.total_frames,
                encoder_type=state.encoder_type,
                # Enhanced workflow logging fields
                track_dispositions=tuple(state.track_dispositions),
                container_change=state.container_change,
                track_order_change=track_order_change,
                size_before=state.size_before,
                size_after=state.size_after,
                video_source_codec=state.video_source_codec,
                video_target_codec=state.video_target_codec,
                audio_synthesis_created=tuple(state.audio_synthesis_created),
                transcription_results=tuple(state.transcription_results),
                operation_failures=tuple(state.operation_failures),
                output_path=result_output_path,
            )

        except PhaseExecutionError:
            raise
        except Exception as e:
            # Unexpected error - attempt rollback
            handle_phase_failure(state, e)
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
        from .backup import rollback_phase as do_rollback

        return do_rollback(state)

    def _create_backup(self, file_path: Path) -> Path | None:
        """Create a backup of the file before modifications.

        Args:
            file_path: Path to the file to backup.

        Returns:
            Path to the backup file, or None if backup failed.
        """
        return create_backup(file_path)

    # =========================================================================
    # Operation Execution (wrapper methods for testability)
    # =========================================================================

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
        import time

        from vpo.policy.exceptions import PolicyError

        start_time = time.time()
        logger.debug(
            "Executing operation %s on %s", op_type.value, state.file_path.name
        )

        try:
            changes = self._dispatch_operation(op_type, state, file_info)
            return OperationResult(
                operation=op_type,
                success=True,
                changes_made=changes,
                duration_seconds=time.time() - start_time,
            )
        except PolicyError as e:
            # Policy constraint violations (e.g., no matching tracks) are
            # informational - the policy is working correctly by not making
            # changes that would violate constraints. This is NOT a failure.
            logger.info("Operation %s skipped (constraint): %s", op_type.value, e)
            return OperationResult(
                operation=op_type,
                success=True,  # Constraint skip is not a failure
                constraint_skipped=True,
                message=str(e),
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error(
                "Operation %s failed on %s: %s", op_type.value, state.file_path.name, e
            )
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

        Filter operations (audio_filter, subtitle_filter, attachment_filter) are
        consolidated: the first filter dispatched executes all filters in one
        pass via execute_with_plan(). Subsequent filter dispatches return 0.

        Args:
            op_type: The type of operation.
            state: Current execution state.
            file_info: FileInfo from database.

        Returns:
            Number of changes made.
        """
        # Consolidate filter operations into a single execution
        _FILTER_OPS = {
            OperationType.AUDIO_FILTER,
            OperationType.SUBTITLE_FILTER,
            OperationType.ATTACHMENT_FILTER,
        }
        if op_type in _FILTER_OPS:
            if state.filters_executed:
                return 0
            result = self._execute_filters(state, file_info)
            state.filters_executed = True
            return result

        # Route to instance methods for testability (allows patching)
        handlers = {
            OperationType.CONTAINER: self._execute_container,
            OperationType.TRACK_ORDER: self._execute_track_order,
            OperationType.DEFAULT_FLAGS: self._execute_default_flags,
            OperationType.CONDITIONAL: self._execute_conditional,
            OperationType.AUDIO_SYNTHESIS: self._execute_audio_synthesis,
            OperationType.TRANSCODE: self._execute_transcode,
            OperationType.FILE_TIMESTAMP: self._execute_file_timestamp,
            OperationType.TRANSCRIPTION: self._execute_transcription,
        }

        handler = handlers.get(op_type)
        if handler is None:
            logger.warning("Unknown operation type: %s", op_type)
            return 0

        return handler(state, file_info)

    # =========================================================================
    # Operation Handlers (wrapper methods for testability)
    # =========================================================================

    def _execute_container(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute container conversion operation."""
        from .plan_operations import execute_container

        tools = self._get_tools()
        return execute_container(
            state,
            file_info,
            self.conn,
            self.policy,
            self.dry_run,
            tools,
            ffmpeg_progress_callback=self._ffmpeg_progress_callback,
        )

    def _execute_audio_filter(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute audio filter operation."""
        from .plan_operations import execute_audio_filter

        tools = self._get_tools()
        return execute_audio_filter(
            state, file_info, self.conn, self.policy, self.dry_run, tools
        )

    def _execute_subtitle_filter(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute subtitle filter operation."""
        from .plan_operations import execute_subtitle_filter

        tools = self._get_tools()
        return execute_subtitle_filter(
            state, file_info, self.conn, self.policy, self.dry_run, tools
        )

    def _execute_attachment_filter(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute attachment filter operation."""
        from .plan_operations import execute_attachment_filter

        tools = self._get_tools()
        return execute_attachment_filter(
            state, file_info, self.conn, self.policy, self.dry_run, tools
        )

    def _execute_filters(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute all filter operations in a single consolidated pass."""
        from .plan_operations import execute_filters

        tools = self._get_tools()
        return execute_filters(
            state, file_info, self.conn, self.policy, self.dry_run, tools
        )

    def _execute_track_order(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute track ordering operation."""
        from .plan_operations import execute_track_order

        tools = self._get_tools()
        return execute_track_order(
            state, file_info, self.conn, self.policy, self.dry_run, tools
        )

    def _execute_default_flags(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute default flags operation."""
        from .plan_operations import execute_default_flags

        tools = self._get_tools()
        return execute_default_flags(
            state, file_info, self.conn, self.policy, self.dry_run, tools
        )

    def _execute_conditional(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute conditional rules operation."""
        from .plan_operations import execute_conditional

        tools = self._get_tools()
        return execute_conditional(
            state, file_info, self.conn, self.policy, self.dry_run, tools
        )

    def _execute_transcode(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute video/audio transcode operation."""
        from .transcode_ops import execute_transcode

        return execute_transcode(state, file_info, self.conn, self.dry_run)

    def _execute_file_timestamp(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute file timestamp operation."""
        from .timestamp_ops import execute_file_timestamp

        return execute_file_timestamp(state, file_info, self.conn, self.dry_run)

    def _execute_audio_synthesis(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute audio synthesis operation."""
        from .advanced_ops import execute_audio_synthesis

        return execute_audio_synthesis(
            state, file_info, self.conn, self.policy, self.dry_run
        )

    def _execute_transcription(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute transcription analysis operation."""
        from .advanced_ops import execute_transcription

        return execute_transcription(
            state, file_info, self.conn, self.dry_run, self._plugin_registry
        )
