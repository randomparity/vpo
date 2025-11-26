"""MKV metadata executor using mkvpropedit.

This module provides an executor for changing MKV metadata (flags, titles,
language) using mkvpropedit. This is fast and in-place (no remux needed).
"""

import subprocess  # nosec B404 - subprocess is required for mkvpropedit execution
from pathlib import Path

from video_policy_orchestrator.executor.backup import create_backup, restore_from_backup
from video_policy_orchestrator.executor.interface import ExecutorResult, require_tool
from video_policy_orchestrator.policy.models import ActionType, Plan, PlannedAction


class MkvpropeditExecutor:
    """Executor for MKV metadata changes using mkvpropedit.

    This executor handles:
    - SET_DEFAULT / CLEAR_DEFAULT (flag-default)
    - SET_FORCED / CLEAR_FORCED (flag-forced)
    - SET_TITLE (name)
    - SET_LANGUAGE (language)

    It does NOT handle REORDER - that requires mkvmerge.
    """

    def __init__(self) -> None:
        """Initialize the executor."""
        self._tool_path: Path | None = None

    @property
    def tool_path(self) -> Path:
        """Get path to mkvpropedit, verifying availability."""
        if self._tool_path is None:
            self._tool_path = require_tool("mkvpropedit")
        return self._tool_path

    def can_handle(self, plan: Plan) -> bool:
        """Check if this executor can handle the given plan.

        Returns True if:
        - File is MKV format
        - Plan contains only metadata changes (no REORDER)
        """
        if not str(plan.file_path).lower().endswith((".mkv", ".mka", ".mks")):
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
        """Execute metadata changes on an MKV file.

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

        # Create backup
        try:
            backup_path = create_backup(plan.file_path)
        except (FileNotFoundError, PermissionError) as e:
            return ExecutorResult(success=False, message=f"Backup failed: {e}")

        # Build mkvpropedit command
        try:
            cmd = self._build_command(plan)
        except ValueError as e:
            return ExecutorResult(success=False, message=str(e))

        # Execute command
        try:
            result = subprocess.run(  # nosec B603 - cmd from validated policy
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
        except subprocess.TimeoutExpired:
            # Restore backup on timeout
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message="mkvpropedit timed out after 5 minutes",
            )
        except Exception as e:
            # Restore backup on error
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"mkvpropedit execution failed: {e}",
            )

        if result.returncode != 0:
            # Restore backup on failure
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"mkvpropedit failed: {result.stderr or result.stdout}",
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

    def _build_command(self, plan: Plan) -> list[str]:
        """Build mkvpropedit command for the plan."""
        cmd = [str(self.tool_path), str(plan.file_path)]

        for action in plan.actions:
            cmd.extend(self._action_to_args(action))

        return cmd

    def _action_to_args(self, action: PlannedAction) -> list[str]:
        """Convert a PlannedAction to mkvpropedit arguments."""
        if action.track_index is None:
            raise ValueError(f"Action {action.action_type} requires track_index")

        # mkvpropedit uses 1-based track selectors
        # Format: --edit track:TYPE_INDEX --set PROPERTY=VALUE
        # We need to determine the track type from context
        # For now, we use track:NUMBER which is 1-based global index
        track_selector = f"track:{action.track_index + 1}"

        if action.action_type == ActionType.SET_DEFAULT:
            return ["--edit", track_selector, "--set", "flag-default=1"]
        elif action.action_type == ActionType.CLEAR_DEFAULT:
            return ["--edit", track_selector, "--set", "flag-default=0"]
        elif action.action_type == ActionType.SET_FORCED:
            return ["--edit", track_selector, "--set", "flag-forced=1"]
        elif action.action_type == ActionType.CLEAR_FORCED:
            return ["--edit", track_selector, "--set", "flag-forced=0"]
        elif action.action_type == ActionType.SET_TITLE:
            return ["--edit", track_selector, "--set", f"name={action.desired_value}"]
        elif action.action_type == ActionType.SET_LANGUAGE:
            return [
                "--edit",
                track_selector,
                "--set",
                f"language={action.desired_value}",
            ]
        else:
            raise ValueError(f"Unsupported action type: {action.action_type}")
