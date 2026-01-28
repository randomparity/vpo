"""Operations repository for policy operation audit logging."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from vpo.db.types import (
    OperationRecord,
    OperationStatus,
    PlanRecord,
    PlanStatus,
)

if TYPE_CHECKING:
    from vpo.policy.types import Plan, PlannedAction


def _row_to_operation_record(row: sqlite3.Row) -> OperationRecord:
    """Convert a database row to OperationRecord using named columns.

    Args:
        row: sqlite3.Row from a SELECT query on the operations table.

    Returns:
        OperationRecord instance populated from the row.
    """
    return OperationRecord(
        id=row["id"],
        file_id=row["file_id"],
        file_path=row["file_path"],
        policy_name=row["policy_name"],
        policy_version=row["policy_version"],
        actions_json=row["actions_json"],
        status=OperationStatus(row["status"]),
        error_message=row["error_message"],
        backup_path=row["backup_path"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _row_to_plan_record(row: sqlite3.Row) -> PlanRecord:
    """Convert a database row to PlanRecord using named columns.

    Args:
        row: sqlite3.Row from a SELECT query on the plans table.

    Returns:
        PlanRecord instance populated from the row.
    """
    return PlanRecord(
        id=row["id"],
        file_id=row["file_id"],
        file_path=row["file_path"],
        policy_name=row["policy_name"],
        policy_version=row["policy_version"],
        job_id=row["job_id"],
        actions_json=row["actions_json"],
        action_count=row["action_count"],
        requires_remux=bool(row["requires_remux"]),
        status=PlanStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_operation(
    conn: sqlite3.Connection,
    plan: Plan,
    file_id: int,
    policy_name: str,
) -> OperationRecord:
    """Create a new operation record in PENDING status.

    Args:
        conn: Database connection.
        plan: The execution plan for this operation.
        file_id: Database ID of the file being modified.
        policy_name: Name/path of the policy being applied.

    Returns:
        The created OperationRecord.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    operation_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    # Serialize actions to JSON
    actions_json = json.dumps([_action_to_dict(a) for a in plan.actions])

    record = OperationRecord(
        id=operation_id,
        file_id=file_id,
        file_path=str(plan.file_path),
        policy_name=policy_name,
        policy_version=plan.policy_version,
        actions_json=actions_json,
        status=OperationStatus.PENDING,
        started_at=started_at,
    )

    conn.execute(
        """
        INSERT INTO operations (
            id, file_id, file_path, policy_name, policy_version,
            actions_json, status, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.file_id,
            record.file_path,
            record.policy_name,
            record.policy_version,
            record.actions_json,
            record.status.value,
            record.started_at,
        ),
    )

    return record


def update_operation_status(
    conn: sqlite3.Connection,
    operation_id: str,
    status: OperationStatus,
    error_message: str | None = None,
    backup_path: str | None = None,
) -> None:
    """Update the status of an operation.

    Args:
        conn: Database connection.
        operation_id: ID of the operation to update.
        status: New status.
        error_message: Error message if status is FAILED.
        backup_path: Path to backup file if retained.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    completed_at = None
    if status in (
        OperationStatus.COMPLETED,
        OperationStatus.FAILED,
        OperationStatus.ROLLED_BACK,
    ):
        completed_at = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        UPDATE operations SET
            status = ?,
            error_message = ?,
            backup_path = ?,
            completed_at = ?
        WHERE id = ?
        """,
        (status.value, error_message, backup_path, completed_at, operation_id),
    )


def get_operation(
    conn: sqlite3.Connection, operation_id: str
) -> OperationRecord | None:
    """Get an operation record by ID.

    Args:
        conn: Database connection.
        operation_id: ID of the operation.

    Returns:
        OperationRecord if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, file_id, file_path, policy_name, policy_version,
               actions_json, status, error_message, backup_path,
               started_at, completed_at
        FROM operations WHERE id = ?
        """,
        (operation_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_operation_record(row)


def get_pending_operations(conn: sqlite3.Connection) -> list[OperationRecord]:
    """Get all operations in PENDING or IN_PROGRESS status.

    Args:
        conn: Database connection.

    Returns:
        List of OperationRecord objects.
    """
    cursor = conn.execute(
        """
        SELECT id, file_id, file_path, policy_name, policy_version,
               actions_json, status, error_message, backup_path,
               started_at, completed_at
        FROM operations
        WHERE status IN ('PENDING', 'IN_PROGRESS')
        ORDER BY started_at
        """,
    )
    return [_row_to_operation_record(row) for row in cursor.fetchall()]


def get_operations_for_file(
    conn: sqlite3.Connection, file_id: int
) -> list[OperationRecord]:
    """Get all operations for a specific file.

    Args:
        conn: Database connection.
        file_id: Database ID of the file.

    Returns:
        List of OperationRecord objects ordered by started_at descending.
    """
    cursor = conn.execute(
        """
        SELECT id, file_id, file_path, policy_name, policy_version,
               actions_json, status, error_message, backup_path,
               started_at, completed_at
        FROM operations
        WHERE file_id = ?
        ORDER BY started_at DESC
        """,
        (file_id,),
    )
    return [_row_to_operation_record(row) for row in cursor.fetchall()]


def _action_to_dict(action: PlannedAction) -> dict:
    """Convert a PlannedAction to a JSON-serializable dict."""
    return {
        "action_type": action.action_type.value,
        "track_index": action.track_index,
        "track_id": action.track_id,
        "current_value": action.current_value,
        "desired_value": action.desired_value,
    }


# ==========================================================================
# Plan CRUD Operations (026-plans-list-view)
# ==========================================================================

# Valid state transitions for PlanStatus
PLAN_STATUS_TRANSITIONS: dict[PlanStatus, set[PlanStatus]] = {
    PlanStatus.PENDING: {PlanStatus.APPROVED, PlanStatus.REJECTED, PlanStatus.CANCELED},
    PlanStatus.APPROVED: {PlanStatus.APPLIED, PlanStatus.CANCELED},
    PlanStatus.REJECTED: set(),  # Terminal state
    PlanStatus.APPLIED: set(),  # Terminal state
    PlanStatus.CANCELED: set(),  # Terminal state
}


class InvalidPlanTransitionError(Exception):
    """Raised when attempting an invalid plan status transition."""

    def __init__(self, current: PlanStatus, target: PlanStatus):
        self.current = current
        self.target = target
        super().__init__(
            f"Cannot transition plan from '{current.value}' to '{target.value}'"
        )


def create_plan(
    conn: sqlite3.Connection,
    plan: Plan,
    file_id: int | None,
    policy_name: str,
    job_id: str | None = None,
) -> PlanRecord:
    """Create a new plan record in PENDING status.

    Args:
        conn: Database connection.
        plan: The execution plan to persist.
        file_id: Database ID of the file (nullable for deleted files).
        policy_name: Name of the policy that generated the plan.
        job_id: Optional reference to originating batch job.

    Returns:
        The created PlanRecord.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    plan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Serialize actions to JSON
    actions_json = json.dumps([_action_to_dict(a) for a in plan.actions])

    record = PlanRecord(
        id=plan_id,
        file_id=file_id,
        file_path=str(plan.file_path),
        policy_name=policy_name,
        policy_version=plan.policy_version,
        job_id=job_id,
        actions_json=actions_json,
        action_count=len(plan.actions),
        requires_remux=plan.requires_remux,
        status=PlanStatus.PENDING,
        created_at=now,
        updated_at=now,
    )

    conn.execute(
        """
        INSERT INTO plans (
            id, file_id, file_path, policy_name, policy_version,
            job_id, actions_json, action_count, requires_remux,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.file_id,
            record.file_path,
            record.policy_name,
            record.policy_version,
            record.job_id,
            record.actions_json,
            record.action_count,
            1 if record.requires_remux else 0,
            record.status.value,
            record.created_at,
            record.updated_at,
        ),
    )

    return record


def get_plan_by_id(conn: sqlite3.Connection, plan_id: str) -> PlanRecord | None:
    """Get a plan record by ID.

    Args:
        conn: Database connection.
        plan_id: UUID of the plan.

    Returns:
        PlanRecord if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, file_id, file_path, policy_name, policy_version,
               job_id, actions_json, action_count, requires_remux,
               status, created_at, updated_at
        FROM plans WHERE id = ?
        """,
        (plan_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_plan_record(row)


def get_plans_filtered(
    conn: sqlite3.Connection,
    status: PlanStatus | None = None,
    since: str | None = None,
    policy_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    return_total: bool = False,
) -> list[PlanRecord] | tuple[list[PlanRecord], int]:
    """Get plans with optional filtering and pagination.

    Args:
        conn: Database connection.
        status: Filter by plan status.
        since: Filter by created_at >= this ISO-8601 timestamp.
        policy_name: Filter by policy name.
        limit: Maximum number of records to return.
        offset: Number of records to skip.
        return_total: If True, also return total count for pagination.

    Returns:
        List of PlanRecord objects, or tuple of (records, total_count)
        if return_total is True.
    """
    conditions = []
    params: list = []

    if status is not None:
        conditions.append("status = ?")
        params.append(status.value)

    if since is not None:
        conditions.append("created_at >= ?")
        params.append(since)

    if policy_name is not None:
        conditions.append("policy_name = ?")
        params.append(policy_name)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    # Get total count if requested
    total = 0
    if return_total:
        count_cursor = conn.execute(
            f"SELECT COUNT(*) FROM plans{where_clause}",
            params,
        )
        total = count_cursor.fetchone()[0]

    # Main query with pagination
    cursor = conn.execute(
        f"""
        SELECT id, file_id, file_path, policy_name, policy_version,
               job_id, actions_json, action_count, requires_remux,
               status, created_at, updated_at
        FROM plans{where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    plans = [_row_to_plan_record(row) for row in cursor.fetchall()]

    if return_total:
        return plans, total
    return plans


def update_plan_status(
    conn: sqlite3.Connection,
    plan_id: str,
    new_status: PlanStatus,
) -> PlanRecord | None:
    """Update the status of a plan with state machine validation.

    Uses atomic UPDATE with WHERE clause to prevent race conditions.
    The status validation is performed in the UPDATE statement itself,
    ensuring concurrent updates cannot bypass the state machine.

    Args:
        conn: Database connection.
        plan_id: UUID of the plan to update.
        new_status: Target status.

    Returns:
        Updated PlanRecord if successful, None if plan not found.

    Raises:
        InvalidPlanTransitionError: If the transition is not allowed.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    # Build list of valid source states for the target status
    valid_source_states = [
        status
        for status, targets in PLAN_STATUS_TRANSITIONS.items()
        if new_status in targets
    ]

    if not valid_source_states:
        # No valid transitions to this status exist - check if plan exists
        plan = get_plan_by_id(conn, plan_id)
        if plan is None:
            return None
        raise InvalidPlanTransitionError(plan.status, new_status)

    # Atomic update with state validation in WHERE clause
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" * len(valid_source_states))
    cursor = conn.execute(
        f"""
        UPDATE plans SET status = ?, updated_at = ?
        WHERE id = ? AND status IN ({placeholders})
        """,
        (new_status.value, now, plan_id, *[s.value for s in valid_source_states]),
    )

    if cursor.rowcount == 0:
        # Either plan doesn't exist or transition invalid
        plan = get_plan_by_id(conn, plan_id)
        if plan is None:
            return None
        # Plan exists but status didn't match - invalid transition
        raise InvalidPlanTransitionError(plan.status, new_status)

    # Return updated record
    return get_plan_by_id(conn, plan_id)
