"""Unit tests for database operations module."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from video_policy_orchestrator.db.models import OperationStatus
from video_policy_orchestrator.db.operations import (
    create_operation,
    get_operation,
    get_operations_for_file,
    get_pending_operations,
    update_operation_status,
)
from video_policy_orchestrator.db.schema import create_schema
from video_policy_orchestrator.policy.models import ActionType, Plan, PlannedAction

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def db_conn(temp_db: Path) -> sqlite3.Connection:
    """Create an in-memory database with schema for testing."""
    conn = sqlite3.connect(str(temp_db))
    create_schema(conn)
    return conn


@pytest.fixture
def sample_plan() -> Plan:
    """Create a sample execution plan for testing."""
    return Plan(
        file_id="test-file-id",
        file_path=Path("/test/video.mkv"),
        policy_version=1,
        actions=(
            PlannedAction(
                action_type=ActionType.SET_DEFAULT,
                track_index=0,
                current_value=False,
                desired_value=True,
            ),
            PlannedAction(
                action_type=ActionType.CLEAR_DEFAULT,
                track_index=1,
                current_value=True,
                desired_value=False,
            ),
        ),
        requires_remux=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_file_id(db_conn: sqlite3.Connection) -> int:
    """Insert a sample file record and return its ID."""
    db_conn.execute(
        """
        INSERT INTO files (path, filename, directory, extension, size_bytes,
                          modified_at, content_hash, container_format, scanned_at,
                          scan_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/test/video.mkv",
            "video.mkv",
            "/test",
            ".mkv",
            1000000,
            "2024-01-01T00:00:00Z",
            "abc123",
            "matroska",
            "2024-01-01T00:00:00Z",
            "completed",
        ),
    )
    db_conn.commit()
    return db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# =============================================================================
# create_operation() Tests
# =============================================================================


class TestCreateOperation:
    """Tests for create_operation function."""

    def test_create_operation_success(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should create an operation record in PENDING status."""
        operation = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        assert operation.id is not None
        assert len(operation.id) == 36  # UUID format
        assert operation.file_id == sample_file_id
        assert operation.file_path == str(sample_plan.file_path)
        assert operation.policy_name == "test-policy.yaml"
        assert operation.policy_version == 1
        assert operation.status == OperationStatus.PENDING
        assert operation.started_at is not None
        assert operation.error_message is None
        assert operation.backup_path is None
        assert operation.completed_at is None

    def test_create_operation_serializes_actions(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should serialize actions to JSON."""
        import json

        operation = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        # Parse the JSON to verify it's valid
        actions = json.loads(operation.actions_json)
        assert len(actions) == 2
        # stored as lowercase enum value
        assert actions[0]["action_type"] == "set_default"
        assert actions[0]["track_index"] == 0
        assert actions[1]["action_type"] == "clear_default"
        assert actions[1]["track_index"] == 1

    def test_create_operation_persists_to_db(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should persist operation to database."""
        operation = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        # Verify in database
        cursor = db_conn.execute(
            "SELECT id, status FROM operations WHERE id = ?", (operation.id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == operation.id
        assert row[1] == "PENDING"


# =============================================================================
# update_operation_status() Tests
# =============================================================================


class TestUpdateOperationStatus:
    """Tests for update_operation_status function."""

    def test_update_to_in_progress(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should update status to IN_PROGRESS."""
        operation = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        update_operation_status(db_conn, operation.id, OperationStatus.IN_PROGRESS)

        # Verify in database
        cursor = db_conn.execute(
            "SELECT status, completed_at FROM operations WHERE id = ?", (operation.id,)
        )
        row = cursor.fetchone()
        assert row[0] == "IN_PROGRESS"
        assert row[1] is None  # No completed_at for IN_PROGRESS

    def test_update_to_completed(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should update status to COMPLETED with completed_at timestamp."""
        operation = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        update_operation_status(db_conn, operation.id, OperationStatus.COMPLETED)

        cursor = db_conn.execute(
            "SELECT status, completed_at FROM operations WHERE id = ?", (operation.id,)
        )
        row = cursor.fetchone()
        assert row[0] == "COMPLETED"
        assert row[1] is not None  # Should have completed_at

    def test_update_to_failed_with_error(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should update status to FAILED with error message."""
        operation = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        update_operation_status(
            db_conn,
            operation.id,
            OperationStatus.FAILED,
            error_message="Something went wrong",
        )

        cursor = db_conn.execute(
            "SELECT status, error_message, completed_at FROM operations WHERE id = ?",
            (operation.id,),
        )
        row = cursor.fetchone()
        assert row[0] == "FAILED"
        assert row[1] == "Something went wrong"
        assert row[2] is not None

    def test_update_to_rolled_back(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should update status to ROLLED_BACK."""
        operation = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        update_operation_status(
            db_conn,
            operation.id,
            OperationStatus.ROLLED_BACK,
            error_message="Rollback triggered",
        )

        cursor = db_conn.execute(
            "SELECT status, error_message FROM operations WHERE id = ?", (operation.id,)
        )
        row = cursor.fetchone()
        assert row[0] == "ROLLED_BACK"
        assert row[1] == "Rollback triggered"

    def test_update_with_backup_path(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should update backup_path when provided."""
        operation = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        update_operation_status(
            db_conn,
            operation.id,
            OperationStatus.COMPLETED,
            backup_path="/test/video.mkv.vpo-backup",
        )

        cursor = db_conn.execute(
            "SELECT backup_path FROM operations WHERE id = ?", (operation.id,)
        )
        row = cursor.fetchone()
        assert row[0] == "/test/video.mkv.vpo-backup"


# =============================================================================
# get_operation() Tests
# =============================================================================


class TestGetOperation:
    """Tests for get_operation function."""

    def test_get_operation_found(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should return operation record when found."""
        created = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )

        retrieved = get_operation(db_conn, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.file_id == sample_file_id
        assert retrieved.policy_name == "test-policy.yaml"
        assert retrieved.status == OperationStatus.PENDING

    def test_get_operation_not_found(self, db_conn: sqlite3.Connection) -> None:
        """Should return None when operation not found."""
        result = get_operation(db_conn, "nonexistent-id")
        assert result is None

    def test_get_operation_with_updated_fields(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should return operation with all updated fields."""
        created = create_operation(
            db_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )
        update_operation_status(
            db_conn,
            created.id,
            OperationStatus.COMPLETED,
            backup_path="/test/backup.mkv",
        )

        retrieved = get_operation(db_conn, created.id)

        assert retrieved is not None
        assert retrieved.status == OperationStatus.COMPLETED
        assert retrieved.backup_path == "/test/backup.mkv"
        assert retrieved.completed_at is not None


# =============================================================================
# get_pending_operations() Tests
# =============================================================================


class TestGetPendingOperations:
    """Tests for get_pending_operations function."""

    def test_get_pending_returns_pending(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should return operations in PENDING status."""
        op1 = create_operation(db_conn, sample_plan, sample_file_id, "policy1.yaml")

        pending = get_pending_operations(db_conn)

        assert len(pending) == 1
        assert pending[0].id == op1.id
        assert pending[0].status == OperationStatus.PENDING

    def test_get_pending_returns_in_progress(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should return operations in IN_PROGRESS status."""
        op1 = create_operation(db_conn, sample_plan, sample_file_id, "policy1.yaml")
        update_operation_status(db_conn, op1.id, OperationStatus.IN_PROGRESS)

        pending = get_pending_operations(db_conn)

        assert len(pending) == 1
        assert pending[0].status == OperationStatus.IN_PROGRESS

    def test_get_pending_excludes_completed(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should NOT return operations in COMPLETED status."""
        op1 = create_operation(db_conn, sample_plan, sample_file_id, "policy1.yaml")
        update_operation_status(db_conn, op1.id, OperationStatus.COMPLETED)

        pending = get_pending_operations(db_conn)

        assert len(pending) == 0

    def test_get_pending_excludes_failed(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should NOT return operations in FAILED status."""
        op1 = create_operation(db_conn, sample_plan, sample_file_id, "policy1.yaml")
        update_operation_status(db_conn, op1.id, OperationStatus.FAILED)

        pending = get_pending_operations(db_conn)

        assert len(pending) == 0

    def test_get_pending_ordered_by_started_at(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should return operations ordered by started_at."""
        import time

        op1 = create_operation(db_conn, sample_plan, sample_file_id, "policy1.yaml")
        time.sleep(0.01)  # Small delay to ensure different timestamps
        op2 = create_operation(db_conn, sample_plan, sample_file_id, "policy2.yaml")

        pending = get_pending_operations(db_conn)

        assert len(pending) == 2
        assert pending[0].id == op1.id  # First one started earlier
        assert pending[1].id == op2.id


# =============================================================================
# get_operations_for_file() Tests
# =============================================================================


class TestGetOperationsForFile:
    """Tests for get_operations_for_file function."""

    def test_get_operations_for_file_found(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should return all operations for a specific file."""
        op1 = create_operation(db_conn, sample_plan, sample_file_id, "policy1.yaml")
        op2 = create_operation(db_conn, sample_plan, sample_file_id, "policy2.yaml")

        operations = get_operations_for_file(db_conn, sample_file_id)

        assert len(operations) == 2
        ids = [op.id for op in operations]
        assert op1.id in ids
        assert op2.id in ids

    def test_get_operations_for_file_empty(self, db_conn: sqlite3.Connection) -> None:
        """Should return empty list when no operations for file."""
        operations = get_operations_for_file(db_conn, 99999)
        assert operations == []

    def test_get_operations_for_file_ordered_desc(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should return operations ordered by started_at descending."""
        import time

        op1 = create_operation(db_conn, sample_plan, sample_file_id, "policy1.yaml")
        time.sleep(0.01)
        op2 = create_operation(db_conn, sample_plan, sample_file_id, "policy2.yaml")

        operations = get_operations_for_file(db_conn, sample_file_id)

        # Descending order: newest first
        assert operations[0].id == op2.id
        assert operations[1].id == op1.id

    def test_get_operations_for_file_only_target_file(
        self, db_conn: sqlite3.Connection, sample_plan: Plan, sample_file_id: int
    ) -> None:
        """Should only return operations for the specified file."""
        # Create another file
        db_conn.execute(
            """
            INSERT INTO files (path, filename, directory, extension, size_bytes,
                              modified_at, content_hash, container_format, scanned_at,
                              scan_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "/test/other.mkv",
                "other.mkv",
                "/test",
                ".mkv",
                2000000,
                "2024-01-01T00:00:00Z",
                "def456",
                "matroska",
                "2024-01-01T00:00:00Z",
                "completed",
            ),
        )
        db_conn.commit()
        other_file_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create operations for both files
        create_operation(db_conn, sample_plan, sample_file_id, "policy1.yaml")
        create_operation(db_conn, sample_plan, other_file_id, "policy2.yaml")

        # Get operations for first file only
        operations = get_operations_for_file(db_conn, sample_file_id)

        assert len(operations) == 1
        assert operations[0].file_id == sample_file_id


# =============================================================================
# Database Configuration Tests
# =============================================================================


class TestDatabaseConfiguration:
    """Tests for database connection configuration and PRAGMAs."""

    def test_wal_mode_enabled(self, temp_db: Path) -> None:
        """Should enable WAL journal mode for better concurrency."""
        from video_policy_orchestrator.db.connection import get_connection

        with get_connection(temp_db) as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            assert journal_mode.lower() == "wal"

    def test_foreign_keys_enabled(self, temp_db: Path) -> None:
        """Should enable foreign key enforcement."""
        from video_policy_orchestrator.db.connection import get_connection

        with get_connection(temp_db) as conn:
            cursor = conn.execute("PRAGMA foreign_keys")
            fk_enabled = cursor.fetchone()[0]
            assert fk_enabled == 1

    def test_synchronous_normal(self, temp_db: Path) -> None:
        """Should set synchronous to NORMAL for safety with WAL."""
        from video_policy_orchestrator.db.connection import get_connection

        with get_connection(temp_db) as conn:
            cursor = conn.execute("PRAGMA synchronous")
            # NORMAL = 1
            synchronous = cursor.fetchone()[0]
            assert synchronous == 1

    def test_busy_timeout_configured(self, temp_db: Path) -> None:
        """Should set busy_timeout for lock contention handling."""
        from video_policy_orchestrator.db.connection import get_connection

        with get_connection(temp_db) as conn:
            cursor = conn.execute("PRAGMA busy_timeout")
            timeout = cursor.fetchone()[0]
            assert timeout == 10000  # 10 seconds

    def test_foreign_key_enforcement(self, db_conn: sqlite3.Connection) -> None:
        """Should enforce foreign key constraints."""
        # Enable foreign keys (may be disabled in in-memory test connection)
        db_conn.execute("PRAGMA foreign_keys = ON")
        # Try to insert a track referencing a non-existent file
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                """
                INSERT INTO tracks (file_id, track_index, track_type, codec,
                                   language, title, is_default, is_forced)
                VALUES (99999, 0, 'video', 'h264', 'eng', 'Test', 0, 0)
                """
            )
            db_conn.commit()


# =============================================================================
# Limit Parameter Validation Tests
# =============================================================================


class TestLimitParameterValidation:
    """Tests for limit parameter validation in query functions."""

    def test_get_queued_jobs_rejects_negative_limit(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Should reject negative limit values."""
        from video_policy_orchestrator.db.models import get_queued_jobs

        with pytest.raises(ValueError, match="Invalid limit value"):
            get_queued_jobs(db_conn, limit=-1)

    def test_get_queued_jobs_rejects_zero_limit(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Should reject zero limit value."""
        from video_policy_orchestrator.db.models import get_queued_jobs

        with pytest.raises(ValueError, match="Invalid limit value"):
            get_queued_jobs(db_conn, limit=0)

    def test_get_queued_jobs_rejects_excessive_limit(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Should reject limit values over 10000."""
        from video_policy_orchestrator.db.models import get_queued_jobs

        with pytest.raises(ValueError, match="Invalid limit value"):
            get_queued_jobs(db_conn, limit=10001)

    def test_get_jobs_by_status_rejects_invalid_limit(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Should reject invalid limit in get_jobs_by_status."""
        from video_policy_orchestrator.db.models import JobStatus, get_jobs_by_status

        with pytest.raises(ValueError, match="Invalid limit value"):
            get_jobs_by_status(db_conn, JobStatus.QUEUED, limit=-5)

    def test_get_all_jobs_rejects_invalid_limit(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Should reject invalid limit in get_all_jobs."""
        from video_policy_orchestrator.db.models import get_all_jobs

        with pytest.raises(ValueError, match="Invalid limit value"):
            get_all_jobs(db_conn, limit=0)

    def test_valid_limit_accepted(self, db_conn: sqlite3.Connection) -> None:
        """Should accept valid limit values."""
        from video_policy_orchestrator.db.models import get_queued_jobs

        # Should not raise
        result = get_queued_jobs(db_conn, limit=100)
        assert isinstance(result, list)

    def test_none_limit_returns_all(self, db_conn: sqlite3.Connection) -> None:
        """Should return all results when limit is None."""
        from video_policy_orchestrator.db.models import get_queued_jobs

        # Should not raise
        result = get_queued_jobs(db_conn, limit=None)
        assert isinstance(result, list)
