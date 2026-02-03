"""MKV metadata executor using mkvpropedit.

This module provides an executor for changing MKV metadata (flags, titles,
language) using mkvpropedit. This is fast and in-place (no remux needed).
"""

import logging
import subprocess  # nosec B404 - subprocess is required for mkvpropedit execution
import time
from pathlib import Path

from vpo.executor.backup import create_backup, safe_restore_from_backup
from vpo.executor.interface import ExecutorResult, require_tool
from vpo.policy.types import ActionType, Plan, PlannedAction

logger = logging.getLogger(__name__)


class MkvpropeditExecutor:
    """Executor for MKV metadata changes using mkvpropedit.

    This executor handles:
    - SET_DEFAULT / CLEAR_DEFAULT (flag-default)
    - SET_FORCED / CLEAR_FORCED (flag-forced)
    - SET_TITLE (name)
    - SET_LANGUAGE (language)

    It does NOT handle REORDER - that requires mkvmerge.
    """

    DEFAULT_TIMEOUT: int = 300  # 5 minutes

    def __init__(self, timeout: int | None = None) -> None:
        """Initialize the executor.

        Args:
            timeout: Subprocess timeout in seconds. None uses DEFAULT_TIMEOUT.
        """
        self._tool_path: Path | None = None
        self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

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
        if not str(plan.file_path).casefold().endswith((".mkv", ".mka", ".mks")):
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

        # Pre-execution logging
        action_types = [a.action_type.value for a in plan.actions]
        logger.info(
            "Applying metadata changes with mkvpropedit",
            extra={
                "file_path": str(plan.file_path),
                "action_count": len(plan.actions),
                "action_types": action_types,
            },
        )

        # Start timing
        start_time = time.monotonic()

        # Create backup
        try:
            backup_path = create_backup(plan.file_path)
        except (FileNotFoundError, PermissionError) as e:
            return ExecutorResult(
                success=False, message=f"Backup failed for {plan.file_path}: {e}"
            )

        # Build mkvpropedit command
        try:
            cmd = self._build_command(plan)
            logger.debug("mkvpropedit command: %s", " ".join(cmd))
        except ValueError as e:
            return ExecutorResult(
                success=False, message=f"Command build failed for {plan.file_path}: {e}"
            )

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
            # Restore backup on timeout
            elapsed = time.monotonic() - start_time
            safe_restore_from_backup(backup_path)
            timeout_mins = self._timeout // 60 if self._timeout else 0
            logger.warning(
                "mkvpropedit timed out",
                extra={
                    "file_path": str(plan.file_path),
                    "timeout_minutes": timeout_mins,
                    "elapsed_seconds": round(elapsed, 3),
                },
            )
            return ExecutorResult(
                success=False,
                message=f"mkvpropedit timed out after {timeout_mins} min for "
                f"{plan.file_path}",
            )
        except (subprocess.SubprocessError, OSError) as e:
            # Restore backup on subprocess error
            elapsed = time.monotonic() - start_time
            safe_restore_from_backup(backup_path)
            logger.error(
                "mkvpropedit execution failed",
                extra={
                    "file_path": str(plan.file_path),
                    "error": str(e),
                    "elapsed_seconds": round(elapsed, 3),
                },
            )
            return ExecutorResult(
                success=False,
                message=f"mkvpropedit failed for {plan.file_path}: {e}",
            )
        except Exception as e:
            # Restore backup on unexpected error
            elapsed = time.monotonic() - start_time
            logger.exception(
                "Unexpected error during mkvpropedit execution for %s",
                plan.file_path,
                extra={
                    "file_path": str(plan.file_path),
                    "elapsed_seconds": round(elapsed, 3),
                },
            )
            safe_restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"Unexpected error for {plan.file_path}: {e}",
            )

        if result.returncode != 0:
            # Restore backup on failure
            elapsed = time.monotonic() - start_time
            safe_restore_from_backup(backup_path)
            logger.error(
                "mkvpropedit returned non-zero exit code",
                extra={
                    "file_path": str(plan.file_path),
                    "returncode": result.returncode,
                    "elapsed_seconds": round(elapsed, 3),
                },
            )
            return ExecutorResult(
                success=False,
                message=f"mkvpropedit failed for {plan.file_path}: "
                f"{result.stderr or result.stdout}",
            )

        # Success - optionally keep backup
        elapsed = time.monotonic() - start_time
        result_backup_path = backup_path if keep_backup else None
        if not keep_backup:
            backup_path.unlink(missing_ok=True)

        logger.info(
            "Metadata changes applied successfully",
            extra={
                "file_path": str(plan.file_path),
                "changes_applied": len(plan.actions),
                "elapsed_seconds": round(elapsed, 3),
            },
        )

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
        # Container-level metadata uses --edit info (no track_index needed)
        if action.action_type == ActionType.SET_CONTAINER_METADATA:
            field = action.current_value  # field name stored in current_value
            value = action.desired_value
            if value == "":
                # Clear/delete the tag
                return ["--edit", "info", "--delete", field]
            return ["--edit", "info", "--set", f"{field}={value}"]

        if action.track_index is None:
            raise ValueError(f"Action {action.action_type} requires track_index")

        # mkvpropedit uses 1-based track selectors
        track_selector = f"track:{action.track_index + 1}"

        # Map action types to property settings
        flag_actions = {
            ActionType.SET_DEFAULT: "flag-default=1",
            ActionType.CLEAR_DEFAULT: "flag-default=0",
            ActionType.SET_FORCED: "flag-forced=1",
            ActionType.CLEAR_FORCED: "flag-forced=0",
        }

        if action.action_type in flag_actions:
            return ["--edit", track_selector, "--set", flag_actions[action.action_type]]

        if action.action_type == ActionType.SET_TITLE:
            if action.desired_value is None:
                raise ValueError(
                    f"SET_TITLE requires a non-None desired_value "
                    f"for track {action.track_index}"
                )
            return ["--edit", track_selector, "--set", f"name={action.desired_value}"]

        if action.action_type == ActionType.SET_LANGUAGE:
            if action.desired_value is None:
                raise ValueError(
                    f"SET_LANGUAGE requires a non-None desired_value "
                    f"for track {action.track_index}"
                )
            return [
                "--edit",
                track_selector,
                "--set",
                f"language={action.desired_value}",
            ]

        raise ValueError(f"Unsupported action type: {action.action_type}")
