"""MKV track reordering executor using mkvmerge.

This module provides an executor for reordering tracks in MKV files
using mkvmerge's --track-order option. This requires a remux (no re-encoding).
"""

import subprocess
import tempfile
from pathlib import Path

from video_policy_orchestrator.executor.backup import create_backup, restore_from_backup
from video_policy_orchestrator.executor.interface import ExecutorResult, require_tool
from video_policy_orchestrator.policy.models import ActionType, Plan


class MkvmergeExecutor:
    """Executor for MKV track reordering using mkvmerge.

    This executor handles:
    - REORDER (via --track-order)

    It can also apply metadata changes during remux:
    - SET_DEFAULT / CLEAR_DEFAULT (--default-track-flag)

    Note: This performs a lossless remux - no re-encoding occurs.
    The process writes to a temp file and atomically replaces the original.
    """

    def __init__(self) -> None:
        """Initialize the executor."""
        self._tool_path: Path | None = None

    @property
    def tool_path(self) -> Path:
        """Get path to mkvmerge, verifying availability."""
        if self._tool_path is None:
            self._tool_path = require_tool("mkvmerge")
        return self._tool_path

    def can_handle(self, plan: Plan) -> bool:
        """Check if this executor can handle the given plan.

        Returns True if:
        - File is MKV format
        - Plan contains REORDER action (this is our specialty)
        """
        if not str(plan.file_path).lower().endswith((".mkv", ".mka", ".mks")):
            return False

        # We handle plans that need remuxing (have REORDER action)
        for action in plan.actions:
            if action.action_type == ActionType.REORDER:
                return True

        return False

    def execute(self, plan: Plan, keep_backup: bool = True) -> ExecutorResult:
        """Execute track reordering on an MKV file.

        Args:
            plan: The execution plan to apply.
            keep_backup: Whether to keep the backup file after success.

        Returns:
            ExecutorResult with success status.
        """
        if plan.is_empty:
            return ExecutorResult(success=True, message="No changes to apply")

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
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout for large files
            )
        except subprocess.TimeoutExpired:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message="mkvmerge timed out after 30 minutes",
            )
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"mkvmerge execution failed: {e}",
            )

        # mkvmerge returns 0 for success, 1 for warnings, 2 for errors
        if result.returncode == 2:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"mkvmerge failed: {result.stderr or result.stdout}",
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
            message=f"Applied {len(plan.actions)} changes via remux",
            backup_path=result_backup_path,
        )

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

        # Add input file
        cmd.append(str(plan.file_path))

        return cmd
