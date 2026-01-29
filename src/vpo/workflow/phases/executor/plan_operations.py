"""Plan-based operation handlers.

This module contains handlers for operations that use the policy evaluation
and plan execution flow: container conversion, filters, track ordering,
default flags, and conditional rules.
"""

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from vpo.db.queries import get_file_by_path, update_file_path
from vpo.db.types import TrackInfo
from vpo.policy.evaluator import evaluate_policy
from vpo.policy.types import ActionType, EvaluationPolicy, PolicySchema
from vpo.tools.ffmpeg_progress import FFmpegProgress

from .helpers import (
    get_language_results_for_tracks,
    get_tracks,
    parse_plugin_metadata,
    select_executor,
)
from .types import PhaseExecutionState

if TYPE_CHECKING:
    from vpo.db.types import FileInfo

logger = logging.getLogger(__name__)


def execute_with_plan(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    operation_name: str,
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
    ffmpeg_progress_callback: Callable[[FFmpegProgress], None] | None = None,
) -> int:
    """Common execution flow for plan-based operations.

    Args:
        state: Current execution state.
        file_info: FileInfo from database.
        operation_name: Name of the operation for logging.
        conn: Database connection.
        policy: PolicySchema configuration.
        dry_run: If True, preview without making changes.
        tools: Dict of tool availability.
        ffmpeg_progress_callback: Optional callback for FFmpeg progress updates.
            Used during container conversion with audio transcoding.

    Returns:
        Number of changes made.
    """
    phase = state.phase
    file_path = state.file_path

    # Get tracks and container format
    # Note: FileInfo has container_format (not container), and no file_id
    # We must look up file_id from the database for audit trail
    if file_info is not None:
        tracks: list[TrackInfo] = list(file_info.tracks)
        container = file_info.container_format or file_path.suffix.lstrip(".")
    else:
        file_record = get_file_by_path(conn, str(file_path))
        if file_record is None:
            raise ValueError(f"File not in database: {file_path}")
        tracks = get_tracks(conn, file_record.id)
        container = file_path.suffix.lstrip(".")

    # Get file_id from database for audit trail
    file_record = get_file_by_path(conn, str(file_path))
    file_id = str(file_record.id) if file_record else "unknown"

    # Parse plugin metadata from FileRecord
    plugin_metadata = parse_plugin_metadata(
        file_record, file_path, file_id, "policy evaluation"
    )

    # Get language analysis results for audio tracks
    language_results = get_language_results_for_tracks(conn, tracks)

    # Create evaluation policy from phase definition
    eval_policy = EvaluationPolicy.from_phase(phase, policy.config)
    plan = evaluate_policy(
        file_id=file_id,
        file_path=file_path,
        container=container,
        tracks=tracks,
        policy=eval_policy,
        plugin_metadata=plugin_metadata,
        language_results=language_results,
    )

    # Capture plan details in state for enhanced logging
    _capture_plan_details(state, plan)

    # Count changes
    changes = len(plan.actions) + plan.tracks_removed
    if changes == 0:
        logger.debug("No changes needed for %s", operation_name)
        return 0

    # Dry-run: just log
    if dry_run:
        logger.info(
            "[DRY-RUN] Would apply %d changes for %s",
            changes,
            operation_name,
        )
        return changes

    # Select and run executor
    executor = select_executor(plan, container, tools, ffmpeg_progress_callback)
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

    # Handle path change from container conversion
    if result.output_path is not None and result.output_path != state.file_path:
        _handle_path_change(state, result.output_path, conn)

    return changes


def _handle_path_change(
    state: PhaseExecutionState,
    new_path: Path,
    conn: Connection,
) -> None:
    """Update state and database after container conversion.

    Args:
        state: Execution state to update.
        new_path: New file path after container conversion.
        conn: Database connection for updating file record.

    Raises:
        ValueError: If old path not found in database or new path already exists.
        RuntimeError: If database update fails.

    Note:
        This function does NOT commit. Caller manages transactions.
    """
    old_path = state.file_path

    # Look up file record by old path
    file_record = get_file_by_path(conn, str(old_path))
    if file_record is None:
        raise ValueError(f"Cannot update path: file not in database ({old_path})")

    # Update database FIRST (fail-fast)
    try:
        updated = update_file_path(conn, file_record.id, str(new_path))
        if not updated:
            raise RuntimeError(
                f"Database update returned False for file_id={file_record.id}"
            )
    except sqlite3.IntegrityError as e:
        if "already exists" in str(e).lower():
            raise ValueError(
                f"Cannot update path: {new_path} already exists in database"
            ) from e
        raise RuntimeError(f"Database integrity error: {e}") from e
    except sqlite3.Error as e:
        raise RuntimeError(f"Database update failed: {e}") from e

    # Only update state AFTER successful DB update
    state.file_path = new_path
    logger.info("Updated file path: %s -> %s", old_path.name, new_path.name)


def execute_container(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
    ffmpeg_progress_callback: Callable[[FFmpegProgress], None] | None = None,
) -> int:
    """Execute container conversion operation.

    Args:
        state: Current execution state.
        file_info: FileInfo from database.
        conn: Database connection.
        policy: PolicySchema configuration.
        dry_run: If True, preview without making changes.
        tools: Dict of tool availability.
        ffmpeg_progress_callback: Optional callback for FFmpeg progress updates.
            Used during container conversion with audio transcoding.

    Returns:
        Number of changes made.
    """
    if not state.phase.container:
        return 0
    return execute_with_plan(
        state,
        file_info,
        "container conversion",
        conn,
        policy,
        dry_run,
        tools,
        ffmpeg_progress_callback,
    )


def execute_audio_filter(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
) -> int:
    """Execute audio filter operation."""
    if not state.phase.audio_filter:
        return 0
    return execute_with_plan(
        state, file_info, "audio filter", conn, policy, dry_run, tools
    )


def execute_subtitle_filter(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
) -> int:
    """Execute subtitle filter operation."""
    if not state.phase.subtitle_filter:
        return 0
    return execute_with_plan(
        state, file_info, "subtitle filter", conn, policy, dry_run, tools
    )


def execute_attachment_filter(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
) -> int:
    """Execute attachment filter operation."""
    if not state.phase.attachment_filter:
        return 0
    return execute_with_plan(
        state, file_info, "attachment filter", conn, policy, dry_run, tools
    )


def execute_track_order(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
) -> int:
    """Execute track ordering operation."""
    if not state.phase.track_order:
        return 0
    return execute_with_plan(
        state, file_info, "track ordering", conn, policy, dry_run, tools
    )


def execute_default_flags(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
) -> int:
    """Execute default flags operation."""
    if not state.phase.default_flags:
        return 0
    return execute_with_plan(
        state, file_info, "default flags", conn, policy, dry_run, tools
    )


def execute_conditional(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
) -> int:
    """Execute conditional rules operation."""
    if not state.phase.conditional:
        return 0
    return execute_with_plan(
        state, file_info, "conditional rules", conn, policy, dry_run, tools
    )


def _capture_plan_details(state: PhaseExecutionState, plan) -> None:
    """Capture plan details in state for enhanced workflow logging.

    Args:
        state: Execution state to populate.
        plan: Evaluated policy plan with track dispositions, actions, etc.
    """
    from vpo.policy.types import Plan

    if not isinstance(plan, Plan):
        return

    # Capture track dispositions (for filter operations)
    if plan.track_dispositions:
        # Extend rather than replace - multiple filter ops might run
        state.track_dispositions.extend(plan.track_dispositions)

    # Capture container change info
    if plan.container_change:
        state.container_change = plan.container_change

    # Capture track reorder info from REORDER action
    for action in plan.actions:
        if action.action_type == ActionType.REORDER:
            # current_value and desired_value are the before/after track orders
            if isinstance(action.current_value, (list, tuple)):
                state.track_order_before = tuple(action.current_value)
            if isinstance(action.desired_value, (list, tuple)):
                state.track_order_after = tuple(action.desired_value)
