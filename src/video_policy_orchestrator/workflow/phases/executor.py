"""V11 phase executor for user-defined phases.

This module provides the PhaseExecutor class that handles execution of
user-defined phases in V11 policies. It dispatches operations to existing
executors based on the phase definition.
"""

import json
import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from video_policy_orchestrator.db.queries import get_file_by_path, get_tracks_for_file
from video_policy_orchestrator.db.types import TrackInfo, tracks_to_track_info
from video_policy_orchestrator.executor import (
    FfmpegMetadataExecutor,
    FFmpegRemuxExecutor,
    MkvmergeExecutor,
    MkvpropeditExecutor,
    check_tool_availability,
)
from video_policy_orchestrator.policy.evaluator import Plan, evaluate_policy
from video_policy_orchestrator.policy.loader import load_policy_from_dict
from video_policy_orchestrator.policy.models import (
    OnErrorMode,
    OperationType,
    PhaseDefinition,
    PhaseExecutionError,
    PhaseResult,
    PolicySchema,
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

        # Cache tool availability
        self._tools: dict[str, bool] | None = None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_tools(self) -> dict[str, bool]:
        """Get tool availability, caching the result."""
        if self._tools is None:
            self._tools = check_tool_availability()
        return self._tools

    def _get_tracks(self, file_path: Path) -> list[TrackInfo]:
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
        track_records = get_tracks_for_file(self.conn, file_record.id)
        return tracks_to_track_info(track_records)

    def _build_virtual_policy(self, phase: PhaseDefinition) -> PolicySchema:
        """Build a V1-V10 compatible policy from phase config for evaluation.

        This creates a "virtual" policy that contains only the configuration
        relevant to the current phase, allowing reuse of the existing
        evaluate_policy() function.

        Args:
            phase: The phase definition to build a policy for.

        Returns:
            PolicySchema suitable for evaluate_policy().
        """
        # Start with base policy structure
        policy_dict: dict = {
            "schema_version": 10,
            "track_order": (
                [t.value for t in phase.track_order]
                if phase.track_order
                else ["video", "audio_main", "audio_alternate", "subtitle_main"]
            ),
            "audio_language_preference": list(
                self.policy.config.audio_language_preference
            ),
            "subtitle_language_preference": list(
                self.policy.config.subtitle_language_preference
            ),
            "commentary_patterns": list(self.policy.config.commentary_patterns),
            "default_flags": {},
        }

        # Add phase-specific configs
        if phase.audio_filter:
            policy_dict["audio_filter"] = {
                "languages": list(phase.audio_filter.languages),
            }

        if phase.subtitle_filter:
            policy_dict["subtitle_filter"] = {
                "languages": list(phase.subtitle_filter.languages),
            }

        if phase.attachment_filter:
            policy_dict["attachment_filter"] = {
                "remove_all": phase.attachment_filter.remove_all,
            }

        if phase.container:
            policy_dict["container"] = {
                "target": phase.container.target,
            }

        if phase.default_flags:
            df = phase.default_flags
            policy_dict["default_flags"] = {
                "set_first_video_default": df.set_first_video_default,
                "set_preferred_audio_default": df.set_preferred_audio_default,
                "set_preferred_subtitle_default": df.set_preferred_subtitle_default,
                "clear_other_defaults": df.clear_other_defaults,
            }

        if phase.conditional:
            # Convert conditional rules to dict format
            policy_dict["conditional"] = [
                self._conditional_rule_to_dict(rule) for rule in phase.conditional
            ]

        return load_policy_from_dict(policy_dict)

    def _conditional_rule_to_dict(self, rule) -> dict:
        """Convert a ConditionalRule to dict format for policy loading."""
        result: dict = {}

        # Convert 'when' condition
        if rule.when:
            result["when"] = self._condition_to_dict(rule.when)

        # Convert 'then' actions
        if rule.then:
            result["then"] = [self._action_to_dict(a) for a in rule.then]

        # Convert 'else' actions
        if rule.else_actions:
            result["else"] = [self._action_to_dict(a) for a in rule.else_actions]

        return result

    def _condition_to_dict(self, condition) -> dict:
        """Convert a Condition to dict format."""
        result: dict = {}

        if condition.track_type:
            result["track_type"] = condition.track_type.value
        if condition.language:
            result["language"] = condition.language
        if condition.language_in:
            result["language_in"] = list(condition.language_in)
        if condition.codec:
            result["codec"] = condition.codec
        if condition.codec_in:
            result["codec_in"] = list(condition.codec_in)
        if condition.is_commentary is not None:
            result["is_commentary"] = condition.is_commentary
        if condition.is_default is not None:
            result["is_default"] = condition.is_default
        if condition.is_forced is not None:
            result["is_forced"] = condition.is_forced
        if condition.title_matches:
            result["title_matches"] = condition.title_matches
        if condition.audio_is_multi_language is not None:
            result["audio_is_multi_language"] = condition.audio_is_multi_language

        return result

    def _action_to_dict(self, action) -> dict:
        """Convert an Action to dict format."""
        result: dict = {}

        if action.set_default is not None:
            result["set_default"] = action.set_default
        if action.set_forced is not None:
            result["set_forced"] = action.set_forced
        if action.set_language:
            result["set_language"] = action.set_language
        if action.set_title:
            result["set_title"] = action.set_title
        if action.remove is not None:
            result["remove"] = action.remove

        return result

    def _select_executor(
        self, plan: Plan, container: str
    ) -> (
        MkvpropeditExecutor
        | MkvmergeExecutor
        | FFmpegRemuxExecutor
        | FfmpegMetadataExecutor
        | None
    ):
        """Select appropriate executor based on plan and container.

        Args:
            plan: The execution plan.
            container: The file container format.

        Returns:
            Appropriate executor instance, or None if no tool available.
        """
        tools = self._get_tools()

        # Container conversion takes priority
        if plan.container_change:
            target = plan.container_change.target_format
            if target == "mp4":
                if tools.get("ffmpeg"):
                    return FFmpegRemuxExecutor()
            elif target in ("mkv", "matroska"):
                if tools.get("mkvmerge"):
                    return MkvmergeExecutor()
            return None

        # Track filtering or reordering requires remux
        if plan.tracks_removed > 0 or plan.requires_remux:
            if container in ("mkv", "matroska") and tools.get("mkvmerge"):
                return MkvmergeExecutor()
            elif tools.get("ffmpeg"):
                return FFmpegRemuxExecutor()
            return None

        # Metadata-only changes
        if container in ("mkv", "matroska") and tools.get("mkvpropedit"):
            return MkvpropeditExecutor()
        elif tools.get("ffmpeg"):
            return FfmpegMetadataExecutor()

        return None

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
        """
        handlers: dict[
            OperationType, Callable[[PhaseExecutionState, FileInfo | None], int]
        ] = {
            OperationType.CONTAINER: self._execute_container,
            OperationType.AUDIO_FILTER: self._execute_audio_filter,
            OperationType.SUBTITLE_FILTER: self._execute_subtitle_filter,
            OperationType.ATTACHMENT_FILTER: self._execute_attachment_filter,
            OperationType.TRACK_ORDER: self._execute_track_order,
            OperationType.DEFAULT_FLAGS: self._execute_default_flags,
            OperationType.CONDITIONAL: self._execute_conditional,
            OperationType.AUDIO_SYNTHESIS: self._execute_audio_synthesis,
            OperationType.TRANSCODE: self._execute_transcode,
            OperationType.TRANSCRIPTION: self._execute_transcription,
        }

        handler = handlers.get(op_type)
        if handler is None:
            logger.warning("Unknown operation type: %s", op_type)
            return 0

        return handler(state, file_info)

    # =========================================================================
    # Operation Handlers
    # =========================================================================

    def _execute_with_plan(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
        operation_name: str,
    ) -> int:
        """Common execution flow for plan-based operations.

        Args:
            state: Current execution state.
            file_info: FileInfo from database.
            operation_name: Name of the operation for logging.

        Returns:
            Number of changes made.
        """
        phase = state.phase
        file_path = state.file_path

        # Get tracks and container format
        # Note: FileInfo has container_format (not container), and no file_id
        # We must look up file_id from the database for audit trail
        if file_info is not None:
            tracks = list(file_info.tracks)
            container = file_info.container_format or file_path.suffix.lstrip(".")
        else:
            tracks = self._get_tracks(file_path)
            container = file_path.suffix.lstrip(".")

        # Get file_id from database for audit trail
        file_record = get_file_by_path(self.conn, str(file_path))
        file_id = str(file_record.id) if file_record else "unknown"

        # Parse plugin metadata from FileRecord (stored as JSON string)
        plugin_metadata: dict | None = None
        if file_record and file_record.plugin_metadata:
            try:
                plugin_metadata = json.loads(file_record.plugin_metadata)
            except json.JSONDecodeError as e:
                logger.error(
                    "Corrupted plugin_metadata JSON for file %s (file_id=%s): %s. "
                    "Plugin metadata conditions will not be evaluated.",
                    file_path,
                    file_id,
                    e,
                )

        # Build virtual policy and evaluate
        virtual_policy = self._build_virtual_policy(phase)
        plan = evaluate_policy(
            file_id=file_id,
            file_path=file_path,
            container=container,
            tracks=tracks,
            policy=virtual_policy,
            plugin_metadata=plugin_metadata,
        )

        # Count changes
        changes = len(plan.actions) + plan.tracks_removed
        if changes == 0:
            logger.debug("No changes needed for %s", operation_name)
            return 0

        # Dry-run: just log
        if self.dry_run:
            logger.info(
                "[DRY-RUN] Would apply %d changes for %s",
                changes,
                operation_name,
            )
            return changes

        # Select and run executor
        executor = self._select_executor(plan, container)
        if executor is None:
            raise ValueError(
                f"No executor available for {operation_name} (container={container})"
            )

        logger.info(
            "Executing %s with %s (%d actions, %d tracks removed)",
            operation_name,
            type(executor).__name__,
            len(plan.actions),
            plan.tracks_removed,
        )

        # Phase manages backup, so tell executor not to create one
        result = executor.execute(plan, keep_backup=False)
        if not result.success:
            raise RuntimeError(f"Executor failed: {result.message}")

        return changes

    def _execute_container(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute container conversion operation."""
        if not state.phase.container:
            return 0
        return self._execute_with_plan(state, file_info, "container conversion")

    def _execute_audio_filter(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute audio filter operation."""
        if not state.phase.audio_filter:
            return 0
        return self._execute_with_plan(state, file_info, "audio filter")

    def _execute_subtitle_filter(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute subtitle filter operation."""
        if not state.phase.subtitle_filter:
            return 0
        return self._execute_with_plan(state, file_info, "subtitle filter")

    def _execute_attachment_filter(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute attachment filter operation."""
        if not state.phase.attachment_filter:
            return 0
        return self._execute_with_plan(state, file_info, "attachment filter")

    def _execute_track_order(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute track ordering operation."""
        if not state.phase.track_order:
            return 0
        return self._execute_with_plan(state, file_info, "track ordering")

    def _execute_default_flags(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute default flags operation."""
        if not state.phase.default_flags:
            return 0
        return self._execute_with_plan(state, file_info, "default flags")

    def _execute_conditional(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute conditional rules operation."""
        if not state.phase.conditional:
            return 0
        return self._execute_with_plan(state, file_info, "conditional rules")

    def _execute_transcode(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute video/audio transcode operation."""
        from video_policy_orchestrator.executor.transcode import TranscodeExecutor

        phase = state.phase
        if not phase.transcode and not phase.audio_transcode:
            return 0

        file_path = state.file_path

        # Get tracks
        if file_info is not None:
            tracks = list(file_info.tracks)
        else:
            tracks = self._get_tracks(file_path)

        changes = 0

        # Video transcode
        if phase.transcode:
            if self.dry_run:
                logger.info(
                    "[DRY-RUN] Would transcode video to %s",
                    phase.transcode.target_codec,
                )
                changes += 1
            else:
                executor = TranscodeExecutor()
                # Build transcode config dict
                transcode_config = {
                    "video": {
                        "target_codec": phase.transcode.target_codec,
                    }
                }
                if phase.transcode.quality:
                    transcode_config["video"]["quality"] = {
                        "mode": phase.transcode.quality.mode,
                        "crf": phase.transcode.quality.crf,
                        "preset": phase.transcode.quality.preset,
                    }

                result = executor.execute_transcode(
                    file_path=file_path,
                    tracks=tracks,
                    transcode_config=transcode_config,
                    dry_run=False,
                )
                if not result.success:
                    raise RuntimeError(
                        f"Video transcode failed: {result.error_message}"
                    )
                changes += 1

        # Audio transcode
        if phase.audio_transcode:
            if self.dry_run:
                logger.info(
                    "[DRY-RUN] Would transcode audio to %s",
                    phase.audio_transcode.transcode_to,
                )
                changes += 1
            else:
                # TODO: Audio transcode via phase executor not yet fully implemented
                # This needs integration with evaluate_policy to build proper plan
                logger.warning(
                    "Audio transcode to %s requested but not yet implemented "
                    "in V11 phase executor",
                    phase.audio_transcode.transcode_to,
                )
                # Don't increment changes since we didn't do anything

        return changes

    def _execute_audio_synthesis(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute audio synthesis operation."""
        from video_policy_orchestrator.policy.synthesis import (
            execute_synthesis_plan,
            plan_synthesis,
        )

        phase = state.phase
        if not phase.audio_synthesis:
            return 0

        file_path = state.file_path

        # Get tracks
        # Note: FileInfo has no file_id attribute, we must look it up
        if file_info is not None:
            tracks = list(file_info.tracks)
        else:
            tracks = self._get_tracks(file_path)

        # Get file_id from database for audit trail
        file_record = get_file_by_path(self.conn, str(file_path))
        file_id = str(file_record.id) if file_record else "unknown"

        # Parse plugin metadata from FileRecord (stored as JSON string)
        plugin_metadata: dict | None = None
        if file_record and file_record.plugin_metadata:
            try:
                plugin_metadata = json.loads(file_record.plugin_metadata)
            except json.JSONDecodeError as e:
                logger.error(
                    "Corrupted plugin_metadata JSON for file %s (file_id=%s): %s. "
                    "Plugin metadata conditions in synthesis will not be evaluated.",
                    file_path,
                    file_id,
                    e,
                )

        # Plan synthesis
        synthesis_plan = plan_synthesis(
            file_id=file_id,
            file_path=file_path,
            tracks=tracks,
            synthesis_config=phase.audio_synthesis,
            commentary_patterns=self.policy.config.commentary_patterns,
            plugin_metadata=plugin_metadata,
        )

        if not synthesis_plan.operations:
            logger.debug("No synthesis operations needed")
            return 0

        changes = len(synthesis_plan.operations)

        if self.dry_run:
            logger.info(
                "[DRY-RUN] Would synthesize %d audio track(s)",
                changes,
            )
            return changes

        # Execute synthesis
        logger.info("Executing audio synthesis: %d track(s)", changes)
        result = execute_synthesis_plan(
            synthesis_plan,
            keep_backup=False,  # Phase manages backup
            dry_run=False,
        )
        if not result.success:
            raise RuntimeError(f"Audio synthesis failed: {result.message}")

        return result.tracks_created

    def _execute_transcription(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute transcription analysis operation.

        Uses TranscriptionService to coordinate:
        1. Multi-sample language detection via smart_detect
        2. Track type classification
        3. Database persistence with proper TranscriptionResultRecord
        """
        from video_policy_orchestrator.transcription.factory import TranscriberFactory
        from video_policy_orchestrator.transcription.service import (
            DEFAULT_CONFIDENCE_THRESHOLD,
            TranscriptionOptions,
            TranscriptionService,
        )
        from video_policy_orchestrator.workflow.phases.context import (
            FileOperationContext,
        )

        phase = state.phase
        if not phase.transcription or not phase.transcription.enabled:
            return 0

        file_path = state.file_path

        # Build operation context (handles FileInfo → DB ID mapping)
        # This ensures tracks have their database IDs populated
        if file_info is not None:
            context = FileOperationContext.from_file_info(file_info, self.conn)
        else:
            context = FileOperationContext.from_file_path(file_path, self.conn)

        # Filter to audio tracks with duration
        audio_tracks = [
            t
            for t in context.tracks
            if t.track_type == "audio" and t.duration_seconds is not None
        ]

        if not audio_tracks:
            logger.debug("No audio tracks with duration to transcribe")
            return 0

        if self.dry_run:
            logger.info(
                "[DRY-RUN] Would analyze %d audio track(s)",
                len(audio_tracks),
            )
            return len(audio_tracks)

        # Get transcriber and create service
        transcriber = TranscriberFactory.get_transcriber_or_raise()
        service = TranscriptionService(transcriber)

        # Build options from policy config
        confidence_threshold = (
            phase.transcription.confidence_threshold
            if phase.transcription.confidence_threshold is not None
            else DEFAULT_CONFIDENCE_THRESHOLD
        )
        options = TranscriptionOptions(confidence_threshold=confidence_threshold)

        # Analyze each track
        changes = 0
        for track in audio_tracks:
            try:
                logger.debug("Analyzing track %d", track.index)

                # Service handles extraction → detection → persistence
                service.analyze_and_persist(
                    file_path=context.file_path,
                    track=track,
                    track_duration=track.duration_seconds,
                    conn=self.conn,
                    options=options,
                )
                changes += 1

            except Exception as e:
                logger.warning(
                    "Transcription failed for track %d: %s",
                    track.index,
                    e,
                )
                # Continue with other tracks

        return changes
