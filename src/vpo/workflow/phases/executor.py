"""Phase executor for user-defined phases.

This module provides the PhaseExecutor class that handles execution of
user-defined phases in phased policies. It dispatches operations to existing
executors based on the phase definition.
"""

import json
import logging
import shutil
import subprocess  # nosec B404 - subprocess required for FFmpeg execution
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from vpo.config.loader import get_temp_directory
from vpo.db.queries import get_file_by_path, get_tracks_for_file
from vpo.db.types import (
    FileRecord,
    TrackInfo,
    tracks_to_track_info,
)
from vpo.executor import (
    FfmpegMetadataExecutor,
    FFmpegRemuxExecutor,
    MkvmergeExecutor,
    MkvpropeditExecutor,
    check_tool_availability,
)
from vpo.executor.backup import (
    check_disk_space,
    create_backup,
    restore_from_backup,
)
from vpo.executor.interface import require_tool
from vpo.policy.evaluator import Plan, evaluate_policy
from vpo.policy.exceptions import PolicyError
from vpo.policy.transcode import (
    AudioAction,
    AudioPlan,
    create_audio_plan_v6,
)
from vpo.policy.types import (
    EvaluationPolicy,
    OnErrorMode,
    OperationType,
    PhaseDefinition,
    PhaseExecutionError,
    PhaseResult,
    PolicySchema,
)

if TYPE_CHECKING:
    from vpo.db.types import FileInfo
    from vpo.plugin import PluginRegistry


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

    transcode_skip_reason: str | None = None
    """If transcode was skipped, the reason (for stats tracking)."""


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
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self.policy_name = policy_name
        self._plugin_registry = plugin_registry

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

    def _parse_plugin_metadata(
        self,
        file_record: FileRecord | None,
        file_path: Path,
        file_id: str,
        context: str = "operations",
    ) -> dict | None:
        """Parse plugin metadata JSON from FileRecord.

        Args:
            file_record: File record from database (may be None).
            file_path: Path to file (for error logging).
            file_id: File ID string (for error logging).
            context: Context description for error message.

        Returns:
            Parsed metadata dict, or None if unavailable or corrupted.
        """
        if not file_record or not file_record.plugin_metadata:
            return None

        try:
            return json.loads(file_record.plugin_metadata)
        except json.JSONDecodeError as e:
            logger.error(
                "Corrupted plugin_metadata JSON for file %s (file_id=%s): %s. "
                "Plugin metadata conditions in %s will not be evaluated.",
                file_path,
                file_id,
                e,
                context,
            )
            return None

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
                transcode_skip_reason=state.transcode_skip_reason,
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
            logger.info("Restored %s from backup", state.file_path.name)
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
        except PolicyError as e:
            # Policy constraint violations (e.g., no matching tracks) are
            # informational - the policy is working correctly by not making
            # changes that would violate constraints
            logger.info("Operation %s skipped: %s", op_type.value, e)
            return OperationResult(
                operation=op_type,
                success=False,
                message=str(e),
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

        # Parse plugin metadata from FileRecord
        plugin_metadata = self._parse_plugin_metadata(
            file_record, file_path, file_id, "policy evaluation"
        )

        # Create evaluation policy from phase definition
        eval_policy = EvaluationPolicy.from_phase(phase, self.policy.config)
        plan = evaluate_policy(
            file_id=file_id,
            file_path=file_path,
            container=container,
            tracks=tracks,
            policy=eval_policy,
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
        from vpo.executor.transcode import TranscodeExecutor
        from vpo.policy.types import TranscodePolicyConfig

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
            vt = phase.transcode

            # Build TranscodePolicyConfig from VideoTranscodeConfig
            transcode_policy = TranscodePolicyConfig(
                target_video_codec=vt.target_codec,
                target_crf=vt.quality.crf if vt.quality else None,
                max_resolution=vt.scaling.max_resolution if vt.scaling else None,
            )

            # Get video track info
            video_tracks = [t for t in tracks if t.track_type == "video"]
            if not video_tracks:
                logger.info(
                    "No video track found in %s, skipping transcode", file_path.name
                )
                return 0
            video_track = video_tracks[0]
            audio_tracks = [t for t in tracks if t.track_type == "audio"]

            # Get file record for size info
            file_record = get_file_by_path(self.conn, str(file_path))
            file_size_bytes = file_record.size_bytes if file_record else None

            executor = TranscodeExecutor(
                policy=transcode_policy,
                skip_if=vt.skip_if,
                audio_config=phase.audio_transcode,
                backup_original=True,
                temp_directory=get_temp_directory(),
            )

            # Create plan
            plan = executor.create_plan(
                input_path=file_path,
                output_path=file_path,
                video_codec=video_track.codec,
                video_width=video_track.width,
                video_height=video_track.height,
                duration_seconds=video_track.duration_seconds,
                audio_tracks=audio_tracks,
                all_tracks=tracks,
                file_size_bytes=file_size_bytes,
            )

            # Check if transcoding should be skipped
            if plan.skip_reason:
                logger.info(
                    "Skipping transcode for %s: %s",
                    file_path,
                    plan.skip_reason,
                )
                # Record skip reason for stats tracking
                state.transcode_skip_reason = plan.skip_reason
                return 0

            if self.dry_run:
                logger.info(
                    "[DRY-RUN] Would transcode video to %s",
                    vt.target_codec,
                )
                changes += 1
            else:
                result = executor.execute(plan)
                if not result.success:
                    msg = f"Video transcode failed: {result.error_message}"
                    raise RuntimeError(msg)
                changes += 1

        # Audio transcode (without video transcode)
        elif phase.audio_transcode:
            audio_tracks = [t for t in tracks if t.track_type == "audio"]
            if not audio_tracks:
                logger.info(
                    "No audio tracks found in %s, skipping audio transcode",
                    file_path.name,
                )
                return 0

            # Create audio plan
            audio_plan = create_audio_plan_v6(audio_tracks, phase.audio_transcode)

            # Check if any tracks need transcoding
            transcode_count = sum(
                1 for t in audio_plan.tracks if t.action == AudioAction.TRANSCODE
            )
            if transcode_count == 0:
                logger.info(
                    "All audio tracks already in acceptable codecs, no transcode needed"
                )
                return 0

            if self.dry_run:
                logger.info(
                    "[DRY-RUN] Would transcode %d audio track(s) to %s",
                    transcode_count,
                    phase.audio_transcode.transcode_to,
                )
                changes += transcode_count
            else:
                # Execute audio-only transcode
                result = self._execute_audio_only_transcode(
                    file_path, tracks, audio_plan, phase.audio_transcode.transcode_to
                )
                if not result:
                    raise RuntimeError("Audio transcode failed")
                changes += transcode_count

        return changes

    def _execute_audio_only_transcode(
        self,
        file_path: Path,
        tracks: list[TrackInfo],
        audio_plan: AudioPlan,
        target_codec: str,
    ) -> bool:
        """Execute audio-only transcode using FFmpeg.

        Copies video and subtitle streams unchanged while transcoding
        audio streams according to the audio plan.

        Args:
            file_path: Path to the media file.
            tracks: All tracks in the file.
            audio_plan: Audio transcode plan from create_audio_plan_v6.
            target_codec: Target audio codec name (for logging).

        Returns:
            True if successful, False otherwise.
        """
        # Pre-flight disk space check
        try:
            check_disk_space(file_path)
        except Exception as e:
            logger.error("Insufficient disk space for audio transcode: %s", e)
            return False

        # Get FFmpeg path
        try:
            ffmpeg_path = require_tool("ffmpeg")
        except FileNotFoundError as e:
            logger.error("FFmpeg not available: %s", e)
            return False

        # Create backup
        try:
            backup_path = create_backup(file_path)
        except (FileNotFoundError, PermissionError) as e:
            logger.error("Backup failed for audio transcode: %s", e)
            return False

        # Create temp output file
        temp_dir = get_temp_directory()
        with tempfile.NamedTemporaryFile(
            suffix=file_path.suffix, delete=False, dir=temp_dir or file_path.parent
        ) as tmp:
            temp_path = Path(tmp.name)

        try:
            # Build FFmpeg command
            cmd = self._build_audio_transcode_command(
                ffmpeg_path, file_path, temp_path, tracks, audio_plan
            )

            logger.info(
                "Executing audio transcode to %s for %s",
                target_codec,
                file_path.name,
            )
            logger.debug("FFmpeg command: %s", " ".join(str(c) for c in cmd))

            # Execute FFmpeg
            result = subprocess.run(  # nosec B603 - cmd built from validated inputs
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                logger.error("FFmpeg audio transcode failed: %s", result.stderr)
                temp_path.unlink(missing_ok=True)
                restore_from_backup(backup_path)
                return False

            # Verify output exists and has reasonable size
            if not temp_path.exists() or temp_path.stat().st_size == 0:
                logger.error("Audio transcode produced empty or missing output")
                temp_path.unlink(missing_ok=True)
                restore_from_backup(backup_path)
                return False

            # Atomic replace: move temp to original
            temp_path.replace(file_path)

            # Clean up backup on success
            backup_path.unlink(missing_ok=True)

            logger.info("Audio transcode completed successfully for %s", file_path.name)
            return True

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg audio transcode timed out after 30 minutes")
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return False
        except Exception as e:
            logger.exception("Unexpected error during audio transcode: %s", e)
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return False

    def _build_audio_transcode_command(
        self,
        ffmpeg_path: Path,
        input_path: Path,
        output_path: Path,
        tracks: list[TrackInfo],
        audio_plan: AudioPlan,
    ) -> list[str]:
        """Build FFmpeg command for audio-only transcode.

        Args:
            ffmpeg_path: Path to FFmpeg executable.
            input_path: Path to input file.
            output_path: Path for output file.
            tracks: All tracks in the file.
            audio_plan: Audio transcode plan.

        Returns:
            List of command arguments.
        """
        cmd = [
            str(ffmpeg_path),
            "-i",
            str(input_path),
            "-map",
            "0",  # Copy all streams
            "-c:v",
            "copy",  # Copy video unchanged
            "-c:s",
            "copy",  # Copy subtitles unchanged
        ]

        # Build audio codec args from plan
        output_stream_idx = 0
        for track_plan in audio_plan.tracks:
            if track_plan.action == AudioAction.COPY:
                cmd.extend([f"-c:a:{output_stream_idx}", "copy"])
                output_stream_idx += 1
            elif track_plan.action == AudioAction.TRANSCODE:
                # Map codec name to FFmpeg encoder
                encoder = self._get_audio_encoder(track_plan.target_codec or "aac")
                cmd.extend([f"-c:a:{output_stream_idx}", encoder])
                if track_plan.target_bitrate:
                    cmd.extend([f"-b:a:{output_stream_idx}", track_plan.target_bitrate])
                output_stream_idx += 1
            # AudioAction.REMOVE would exclude the track, but we don't support
            # that in audio-only transcode currently

        # Output file (overwrite if exists)
        cmd.extend(["-y", str(output_path)])

        return cmd

    def _get_audio_encoder(self, codec: str) -> str:
        """Get FFmpeg encoder name for a codec.

        Args:
            codec: Target codec name (e.g., 'aac', 'opus', 'flac').

        Returns:
            FFmpeg encoder name.
        """
        encoders = {
            "aac": "aac",
            "ac3": "ac3",
            "eac3": "eac3",
            "flac": "flac",
            "opus": "libopus",
            "mp3": "libmp3lame",
            "vorbis": "libvorbis",
            "pcm_s16le": "pcm_s16le",
            "pcm_s24le": "pcm_s24le",
        }
        return encoders.get(codec.casefold(), "aac")

    def _execute_audio_synthesis(
        self,
        state: PhaseExecutionState,
        file_info: "FileInfo | None",
    ) -> int:
        """Execute audio synthesis operation."""
        from vpo.policy.synthesis import (
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

        # Parse plugin metadata from FileRecord
        plugin_metadata = self._parse_plugin_metadata(
            file_record, file_path, file_id, "synthesis"
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

        Uses TranscriptionCoordinator to coordinate:
        1. Multi-sample language detection via smart_detect
        2. Track type classification
        3. Database persistence with proper TranscriptionResultRecord
        """
        from vpo.transcription.coordinator import (
            DEFAULT_CONFIDENCE_THRESHOLD,
            NoTranscriptionPluginError,
            TranscriptionCoordinator,
            TranscriptionOptions,
        )
        from vpo.workflow.phases.context import (
            FileOperationContext,
        )

        phase = state.phase
        if not phase.transcription or not phase.transcription.enabled:
            return 0

        # Transcription requires plugin registry
        if self._plugin_registry is None:
            logger.info(
                "Transcription requested but no plugin registry available. "
                "Skipping transcription operation."
            )
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

        # Create coordinator from plugin registry
        coordinator = TranscriptionCoordinator(self._plugin_registry)

        if not coordinator.is_available():
            logger.warning(
                "No transcription plugins available. "
                "Install a transcription plugin (e.g., whisper-local)."
            )
            return 0

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

                # Coordinator handles extraction → detection → persistence
                coordinator.analyze_and_persist(
                    file_path=context.file_path,
                    track=track,
                    track_duration=track.duration_seconds,
                    conn=self.conn,
                    options=options,
                )
                changes += 1

            except NoTranscriptionPluginError as e:
                logger.warning("Transcription plugin not available: %s", e)
                break  # Stop trying other tracks if no plugin
            except Exception as e:
                logger.warning(
                    "Transcription failed for track %d: %s",
                    track.index,
                    e,
                )
                # Continue with other tracks

        return changes
