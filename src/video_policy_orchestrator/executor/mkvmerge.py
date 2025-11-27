"""MKV track reordering and filtering executor using mkvmerge.

This module provides an executor for reordering and filtering tracks in MKV files
using mkvmerge's --track-order and --audio-tracks/--subtitle-tracks options.
This requires a remux (no re-encoding).
"""

import logging
import subprocess  # nosec B404 - subprocess is required for mkvmerge execution
import tempfile
from pathlib import Path

from video_policy_orchestrator.executor.backup import (
    InsufficientDiskSpaceError,
    check_disk_space,
    create_backup,
    restore_from_backup,
)
from video_policy_orchestrator.executor.interface import ExecutorResult, require_tool
from video_policy_orchestrator.policy.models import ActionType, Plan, TrackDisposition

logger = logging.getLogger(__name__)


class MkvmergeExecutor:
    """Executor for MKV track reordering and filtering using mkvmerge.

    This executor handles:
    - REORDER (via --track-order)
    - Track filtering (via --audio-tracks, --subtitle-tracks, --no-attachments)

    It can also apply metadata changes during remux:
    - SET_DEFAULT / CLEAR_DEFAULT (--default-track-flag)

    Note: This performs a lossless remux - no re-encoding occurs.
    The process writes to a temp file and atomically replaces the original.
    """

    DEFAULT_TIMEOUT: int = 1800  # 30 minutes

    def __init__(self, timeout: int | None = None) -> None:
        """Initialize the executor.

        Args:
            timeout: Subprocess timeout in seconds. None uses DEFAULT_TIMEOUT.
        """
        self._tool_path: Path | None = None
        self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

    @property
    def tool_path(self) -> Path:
        """Get path to mkvmerge, verifying availability."""
        if self._tool_path is None:
            self._tool_path = require_tool("mkvmerge")
        return self._tool_path

    def can_handle(self, plan: Plan) -> bool:
        """Check if this executor can handle the given plan.

        Returns True if:
        - Plan has container_change with target=mkv (any input format)
        - File is MKV format AND (has REORDER action OR track filtering)
        """
        # Container conversion to MKV - we handle any input format
        if plan.container_change is not None:
            if plan.container_change.target_format == "mkv":
                return True

        # For non-conversion operations, only handle MKV files
        if not str(plan.file_path).lower().endswith((".mkv", ".mka", ".mks")):
            return False

        # We handle plans that need remuxing (have REORDER action)
        for action in plan.actions:
            if action.action_type == ActionType.REORDER:
                return True

        # We also handle track filtering (indicated by tracks_removed > 0)
        if plan.tracks_removed > 0:
            return True

        return False

    def execute(
        self,
        plan: Plan,
        keep_backup: bool = True,
        keep_original: bool = False,
    ) -> ExecutorResult:
        """Execute track reordering or container conversion on a media file.

        Args:
            plan: The execution plan to apply.
            keep_backup: Whether to keep the backup file after success.
            keep_original: Whether to keep the original file after container
                conversion (only applies when output path differs from input).

        Returns:
            ExecutorResult with success status.
        """
        if plan.is_empty:
            return ExecutorResult(success=True, message="No changes to apply")

        # Pre-flight disk space check
        try:
            check_disk_space(plan.file_path)
        except InsufficientDiskSpaceError as e:
            return ExecutorResult(success=False, message=str(e))

        # Determine if this is a container conversion
        is_container_conversion = (
            plan.container_change is not None
            and plan.container_change.target_format == "mkv"
        )

        # Compute output path - may be different if container is changing
        if is_container_conversion:
            # Output path has .mkv extension
            output_path = plan.file_path.with_suffix(".mkv")
        else:
            output_path = plan.file_path

        # Create backup
        try:
            backup_path = create_backup(plan.file_path)
        except (FileNotFoundError, PermissionError) as e:
            return ExecutorResult(success=False, message=f"Backup failed: {e}")

        # Create temp output file
        with tempfile.NamedTemporaryFile(
            suffix=".mkv", delete=False, dir=plan.file_path.parent
        ) as tmp:
            temp_path = Path(tmp.name)

        # Build mkvmerge command
        try:
            cmd = self._build_command(plan, temp_path)
        except ValueError as e:
            temp_path.unlink(missing_ok=True)
            return ExecutorResult(success=False, message=str(e))

        # Execute command
        try:
            result = subprocess.run(  # nosec B603 - cmd from validated policy
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout if self._timeout > 0 else None,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            timeout_mins = self._timeout // 60 if self._timeout else 0
            return ExecutorResult(
                success=False,
                message=f"mkvmerge timed out after {timeout_mins} minutes",
            )
        except (subprocess.SubprocessError, OSError) as e:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"mkvmerge execution failed: {e}",
            )
        except Exception as e:
            logger.exception("Unexpected error during mkvmerge execution")
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"Unexpected error during mkvmerge execution: {e}",
            )

        # mkvmerge returns 0 for success, 1 for warnings, 2 for errors
        if result.returncode == 2:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"mkvmerge failed: {result.stderr or result.stdout}",
            )

        # Atomic move: move temp to output path
        try:
            temp_path.replace(output_path)
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"Failed to move output file: {e}",
            )

        # Delete original file if extension changed (container conversion)
        # unless keep_original is True
        if output_path != plan.file_path and not keep_original:
            plan.file_path.unlink(missing_ok=True)

        # Success - optionally keep backup
        result_backup_path = backup_path if keep_backup else None
        if not keep_backup:
            backup_path.unlink(missing_ok=True)

        # Build success message
        action_count = len(plan.actions)
        if is_container_conversion:
            src = plan.container_change.source_format
            message = f"Converted {src} → mkv"
            if action_count > 0:
                message += f" with {action_count} additional changes"
        else:
            message = f"Applied {action_count} changes via remux"

        return ExecutorResult(
            success=True,
            message=message,
            backup_path=result_backup_path,
        )

    def _build_track_selection_args(
        self,
        track_dispositions: tuple[TrackDisposition, ...],
    ) -> list[str]:
        """Build mkvmerge track selection arguments from dispositions.

        Args:
            track_dispositions: Tuple of track dispositions from the plan.

        Returns:
            List of command line arguments for track selection.
        """
        args: list[str] = []

        if not track_dispositions:
            return args

        # Group kept track indices by type
        keep_audio: list[int] = []
        keep_subtitle: list[int] = []
        remove_attachments = False

        for disp in track_dispositions:
            if disp.action == "KEEP":
                if disp.track_type == "audio":
                    keep_audio.append(disp.track_index)
                elif disp.track_type == "subtitle":
                    keep_subtitle.append(disp.track_index)
            elif disp.action == "REMOVE":
                if disp.track_type == "attachment":
                    remove_attachments = True

        # Check if we need to filter audio tracks
        # (only add argument if some audio tracks are being removed)
        audio_dispositions = [d for d in track_dispositions if d.track_type == "audio"]
        if audio_dispositions and len(keep_audio) < len(audio_dispositions):
            if keep_audio:
                # Keep specified tracks
                args.extend(["--audio-tracks", ",".join(str(i) for i in keep_audio)])
            else:
                # Remove all audio (this should be blocked by validation)
                args.append("--no-audio")

        # Check if we need to filter subtitle tracks
        sub_dispositions = [d for d in track_dispositions if d.track_type == "subtitle"]
        if sub_dispositions and len(keep_subtitle) < len(sub_dispositions):
            if keep_subtitle:
                track_list = ",".join(str(i) for i in keep_subtitle)
                args.extend(["--subtitle-tracks", track_list])
            else:
                args.append("--no-subtitles")

        # Handle attachment removal
        if remove_attachments:
            args.append("--no-attachments")

        return args

    def _build_command(self, plan: Plan, output_path: Path) -> list[str]:
        """Build mkvmerge command for the plan."""
        cmd = [
            str(self.tool_path),
            "--output",
            str(output_path),
        ]

        # Find REORDER action and extract track order
        track_order = None
        for action in plan.actions:
            if action.action_type == ActionType.REORDER:
                track_order = action.desired_value
                break

        if track_order:
            # Format: --track-order 0:idx1,0:idx2,0:idx3,...
            # 0: means first (and only) input file
            order_spec = ",".join(f"0:{idx}" for idx in track_order)
            cmd.extend(["--track-order", order_spec])

        # Add default flag changes
        for action in plan.actions:
            if action.action_type == ActionType.SET_DEFAULT:
                # --default-track-flag TRACK_ID:1
                cmd.extend(["--default-track-flag", f"{action.track_index}:1"])
            elif action.action_type == ActionType.CLEAR_DEFAULT:
                # --default-track-flag TRACK_ID:0
                cmd.extend(["--default-track-flag", f"{action.track_index}:0"])

        # Add track selection arguments for filtering
        if plan.track_dispositions:
            selection_args = self._build_track_selection_args(plan.track_dispositions)
            cmd.extend(selection_args)

        # Add input file
        cmd.append(str(plan.file_path))

        return cmd
