"""Operations repository for policy operation audit logging."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from video_policy_orchestrator.db.models import OperationRecord, OperationStatus
from video_policy_orchestrator.policy.models import Plan, PlannedAction


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
    conn.commit()

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
    conn.commit()


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

    return OperationRecord(
        id=row[0],
        file_id=row[1],
        file_path=row[2],
        policy_name=row[3],
        policy_version=row[4],
        actions_json=row[5],
        status=OperationStatus(row[6]),
        error_message=row[7],
        backup_path=row[8],
        started_at=row[9],
        completed_at=row[10],
    )


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

    operations = []
    for row in cursor.fetchall():
        operations.append(
            OperationRecord(
                id=row[0],
                file_id=row[1],
                file_path=row[2],
                policy_name=row[3],
                policy_version=row[4],
                actions_json=row[5],
                status=OperationStatus(row[6]),
                error_message=row[7],
                backup_path=row[8],
                started_at=row[9],
                completed_at=row[10],
            )
        )

    return operations


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

    operations = []
    for row in cursor.fetchall():
        operations.append(
            OperationRecord(
                id=row[0],
                file_id=row[1],
                file_path=row[2],
                policy_name=row[3],
                policy_version=row[4],
                actions_json=row[5],
                status=OperationStatus(row[6]),
                error_message=row[7],
                backup_path=row[8],
                started_at=row[9],
                completed_at=row[10],
            )
        )

    return operations


def _action_to_dict(action: PlannedAction) -> dict:
    """Convert a PlannedAction to a JSON-serializable dict."""
    return {
        "action_type": action.action_type.value,
        "track_index": action.track_index,
        "track_id": action.track_id,
        "current_value": action.current_value,
        "desired_value": action.desired_value,
    }
