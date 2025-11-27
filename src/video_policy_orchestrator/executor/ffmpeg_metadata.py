"""FFmpeg metadata executor for non-MKV containers.

This module provides an executor for changing metadata in non-MKV containers
(MP4, AVI, etc.) using ffmpeg with stream copy.
"""

import logging
import subprocess  # nosec B404 - subprocess is required for ffmpeg execution
import tempfile
from pathlib import Path

from video_policy_orchestrator.executor.backup import (
    InsufficientDiskSpaceError,
    check_disk_space,
    create_backup,
    restore_from_backup,
)
from video_policy_orchestrator.executor.interface import ExecutorResult, require_tool
from video_policy_orchestrator.policy.models import ActionType, Plan, PlannedAction

logger = logging.getLogger(__name__)


class FfmpegMetadataExecutor:
    """Executor for non-MKV metadata changes using ffmpeg.

    This executor handles:
    - SET_DEFAULT / CLEAR_DEFAULT (disposition)
    - SET_TITLE (metadata:s:INDEX title=)
    - SET_LANGUAGE (metadata:s:INDEX language=)

    Note: ffmpeg cannot modify files in-place, so this executor:
    1. Creates a backup
    2. Writes to a temp file with -c copy
    3. Atomically replaces the original

    Limitations:
    - MP4 has partial track title support
    - AVI has very limited metadata support
    - Forced flag is buggy in some containers
    """

    DEFAULT_TIMEOUT: int = 600  # 10 minutes

    def __init__(self, timeout: int | None = None) -> None:
        """Initialize the executor.

        Args:
            timeout: Subprocess timeout in seconds. None uses DEFAULT_TIMEOUT.
        """
        self._tool_path: Path | None = None
        self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

    @property
    def tool_path(self) -> Path:
        """Get path to ffmpeg, verifying availability."""
        if self._tool_path is None:
            self._tool_path = require_tool("ffmpeg")
        return self._tool_path

    def can_handle(self, plan: Plan) -> bool:
        """Check if this executor can handle the given plan.

        Returns True if:
        - File is NOT MKV format
        - Plan contains only metadata changes (no REORDER)
        """
        suffix = plan.file_path.suffix.lower()
        if suffix in (".mkv", ".mka", ".mks"):
            return False

        # Check that no actions require remux
        for action in plan.actions:
            if action.action_type == ActionType.REORDER:
                return False

        return True

    def execute(
        self,
        plan: Plan,
        keep_backup: bool = True,
        keep_original: bool = False,  # Not used - metadata edits don't change file path
    ) -> ExecutorResult:
        """Execute metadata changes using ffmpeg.

        Args:
            plan: The execution plan to apply.
            keep_backup: Whether to keep the backup file after success.
            keep_original: Not used for metadata changes (file path unchanged).

        Returns:
            ExecutorResult with success status.
        """
        del keep_original  # Unused - metadata changes don't create new files
        if plan.is_empty:
            return ExecutorResult(success=True, message="No changes to apply")

        # Pre-flight disk space check (needs ~2x file size for backup + temp)
        try:
            check_disk_space(plan.file_path, multiplier=2.0)
        except InsufficientDiskSpaceError as e:
            return ExecutorResult(success=False, message=str(e))

        # Create backup
        try:
            backup_path = create_backup(plan.file_path)
        except (FileNotFoundError, PermissionError) as e:
            return ExecutorResult(success=False, message=f"Backup failed: {e}")

        # Create temp output file
        suffix = plan.file_path.suffix
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False, dir=plan.file_path.parent
        ) as tmp:
            temp_path = Path(tmp.name)

        # Build ffmpeg command
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
                message=f"ffmpeg timed out after {timeout_mins} minutes",
            )
        except (subprocess.SubprocessError, OSError) as e:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"ffmpeg execution failed: {e}",
            )
        except Exception as e:
            logger.exception("Unexpected error during ffmpeg execution")
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"Unexpected error during ffmpeg execution: {e}",
            )

        if result.returncode != 0:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"ffmpeg failed: {result.stderr}",
            )

        # Atomic replace: move temp to original
        try:
            temp_path.replace(plan.file_path)
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"Failed to replace original file: {e}",
            )

        # Success - optionally keep backup
        result_backup_path = backup_path if keep_backup else None
        if not keep_backup:
            backup_path.unlink(missing_ok=True)

        return ExecutorResult(
            success=True,
            message=f"Applied {len(plan.actions)} metadata changes",
            backup_path=result_backup_path,
        )

    def _build_command(self, plan: Plan, output_path: Path) -> list[str]:
        """Build ffmpeg command for the plan."""
        cmd = [
            str(self.tool_path),
            "-i",
            str(plan.file_path),
            "-map",
            "0",  # Copy all streams
            "-c",
            "copy",  # No re-encoding
        ]

        # Add metadata and disposition options for each action
        for action in plan.actions:
            cmd.extend(self._action_to_args(action))

        # Output file
        cmd.extend(["-y", str(output_path)])  # -y to overwrite

        return cmd

    def _action_to_args(self, action: PlannedAction) -> list[str]:
        """Convert a PlannedAction to ffmpeg arguments."""
        if action.track_index is None:
            raise ValueError(f"Action {action.action_type} requires track_index")

        idx = action.track_index

        if action.action_type == ActionType.SET_DEFAULT:
            return [f"-disposition:{idx}", "default"]
        elif action.action_type == ActionType.CLEAR_DEFAULT:
            return [f"-disposition:{idx}", "none"]
        elif action.action_type == ActionType.SET_FORCED:
            return [f"-disposition:{idx}", "forced"]
        elif action.action_type == ActionType.CLEAR_FORCED:
            # Clear forced but keep other dispositions
            return [f"-disposition:{idx}", "0"]
        elif action.action_type == ActionType.SET_TITLE:
            if action.desired_value is None:
                raise ValueError(
                    f"SET_TITLE requires a non-None desired_value for track {idx}"
                )
            return [f"-metadata:s:{idx}", f"title={action.desired_value}"]
        elif action.action_type == ActionType.SET_LANGUAGE:
            if action.desired_value is None:
                raise ValueError(
                    f"SET_LANGUAGE requires a non-None desired_value for track {idx}"
                )
            return [f"-metadata:s:{idx}", f"language={action.desired_value}"]
        else:
            raise ValueError(f"Unsupported action type: {action.action_type}")
