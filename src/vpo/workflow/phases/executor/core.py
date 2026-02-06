"""Core execution orchestration.

This module contains the main operation execution loop and dispatch logic.
"""

import logging
import time
from sqlite3 import Connection
from typing import TYPE_CHECKING

from vpo.policy.exceptions import PolicyError
from vpo.policy.types import OperationType, PolicySchema

from .advanced_ops import execute_audio_synthesis, execute_transcription
from .plan_operations import (
    execute_conditional,
    execute_container,
    execute_default_flags,
    execute_filters,
    execute_track_order,
)
from .timestamp_ops import execute_file_timestamp
from .transcode_ops import execute_transcode
from .types import FILTER_OPS, OperationResult, PhaseExecutionState

if TYPE_CHECKING:
    from vpo.db.types import FileInfo
    from vpo.plugin import PluginRegistry

logger = logging.getLogger(__name__)


def execute_operation(
    op_type: OperationType,
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
    plugin_registry: "PluginRegistry | None",
) -> OperationResult:
    """Execute a single operation.

    Args:
        op_type: The type of operation to execute.
        state: Current execution state.
        file_info: FileInfo from database.
        conn: Database connection.
        policy: PolicySchema configuration.
        dry_run: If True, preview without making changes.
        tools: Dict of tool availability.
        plugin_registry: Optional plugin registry for transcription.

    Returns:
        OperationResult with execution status.
    """
    start_time = time.time()
    logger.debug("Executing operation: %s", op_type.value)

    try:
        changes = dispatch_operation(
            op_type, state, file_info, conn, policy, dry_run, tools, plugin_registry
        )
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
        logger.error("Operation %s failed: %s", op_type.value, e)
        return OperationResult(
            operation=op_type,
            success=False,
            message=str(e),
            duration_seconds=time.time() - start_time,
        )


def dispatch_operation(
    op_type: OperationType,
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
    tools: dict[str, bool],
    plugin_registry: "PluginRegistry | None",
) -> int:
    """Dispatch an operation to the appropriate handler.

    Args:
        op_type: The type of operation.
        state: Current execution state.
        file_info: FileInfo from database.
        conn: Database connection.
        policy: PolicySchema configuration.
        dry_run: If True, preview without making changes.
        tools: Dict of tool availability.
        plugin_registry: Optional plugin registry for transcription.

    Returns:
        Number of changes made.
    """
    # Plan-based operations share common args
    plan_args = (state, file_info, conn, policy, dry_run, tools)

    # Consolidate filter operations into a single execution
    if op_type in FILTER_OPS:
        if state.filters_executed:
            return 0
        result = execute_filters(*plan_args)
        state.filters_executed = True
        return result

    if op_type == OperationType.CONTAINER:
        return execute_container(*plan_args)
    elif op_type == OperationType.TRACK_ORDER:
        return execute_track_order(*plan_args)
    elif op_type == OperationType.DEFAULT_FLAGS:
        return execute_default_flags(*plan_args)
    elif op_type == OperationType.CONDITIONAL:
        return execute_conditional(*plan_args)
    elif op_type == OperationType.TRANSCODE:
        return execute_transcode(state, file_info, conn, dry_run)
    elif op_type == OperationType.AUDIO_SYNTHESIS:
        return execute_audio_synthesis(state, file_info, conn, policy, dry_run)
    elif op_type == OperationType.FILE_TIMESTAMP:
        return execute_file_timestamp(state, file_info, conn, dry_run)
    elif op_type == OperationType.TRANSCRIPTION:
        return execute_transcription(state, file_info, conn, dry_run, plugin_registry)
    else:
        logger.warning("Unknown operation type: %s", op_type)
        return 0
