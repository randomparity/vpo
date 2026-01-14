"""Unit tests verifying operations.py functions do not auto-commit.

These tests ensure that plan and operation CRUD functions in operations.py
do NOT call conn.commit(), allowing callers to manage transactions explicitly.
"""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vpo.db.operations import (
    create_operation,
    create_plan,
    update_operation_status,
    update_plan_status,
)
from vpo.db.schema import create_schema
from vpo.db.types import OperationStatus, PlanStatus


@pytest.fixture
def test_conn() -> sqlite3.Connection:
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def sample_file_id(test_conn: sqlite3.Connection) -> int:
    """Create a sample file and return its ID."""
    test_conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            modified_at, content_hash, container_format,
            scanned_at, scan_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    test_conn.commit()
    return test_conn.execute("SELECT last_insert_rowid()").fetchone()[0]


@pytest.fixture
def sample_plan():
    """Create a mock Plan object."""
    plan = MagicMock()
    plan.file_path = Path("/test/video.mkv")
    plan.policy_version = "12"
    plan.actions = []
    plan.requires_remux = False
    return plan


class TestCreateOperationNoCommit:
    """Tests that create_operation does not auto-commit."""

    def test_create_operation_does_not_commit(
        self,
        test_conn: sqlite3.Connection,
        sample_file_id: int,
        sample_plan,
    ) -> None:
        """create_operation should not commit the transaction."""
        # Create operation
        record = create_operation(
            test_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )
        assert record.id is not None

        # Verify operation exists in current connection
        cursor = test_conn.execute(
            "SELECT id FROM operations WHERE id = ?", (record.id,)
        )
        assert cursor.fetchone() is not None

        # Rollback should undo the create
        test_conn.rollback()

        # Verify operation no longer exists
        cursor = test_conn.execute(
            "SELECT id FROM operations WHERE id = ?", (record.id,)
        )
        assert cursor.fetchone() is None


class TestUpdateOperationStatusNoCommit:
    """Tests that update_operation_status does not auto-commit."""

    def test_update_operation_status_does_not_commit(
        self,
        test_conn: sqlite3.Connection,
        sample_file_id: int,
        sample_plan,
    ) -> None:
        """update_operation_status should not commit the transaction."""
        # Create operation first
        record = create_operation(
            test_conn, sample_plan, sample_file_id, "test-policy.yaml"
        )
        test_conn.commit()

        # Update status
        update_operation_status(test_conn, record.id, OperationStatus.IN_PROGRESS)

        # Verify status is updated in current connection
        cursor = test_conn.execute(
            "SELECT status FROM operations WHERE id = ?", (record.id,)
        )
        row = cursor.fetchone()
        assert row[0] == "IN_PROGRESS"

        # Rollback should undo the update
        test_conn.rollback()

        # Verify status reverted
        cursor = test_conn.execute(
            "SELECT status FROM operations WHERE id = ?", (record.id,)
        )
        row = cursor.fetchone()
        assert row[0] == "PENDING"


class TestCreatePlanNoCommit:
    """Tests that create_plan does not auto-commit."""

    def test_create_plan_does_not_commit(
        self,
        test_conn: sqlite3.Connection,
        sample_file_id: int,
        sample_plan,
    ) -> None:
        """create_plan should not commit the transaction."""
        # Create plan
        record = create_plan(test_conn, sample_plan, sample_file_id, "test-policy.yaml")
        assert record.id is not None

        # Verify plan exists in current connection
        cursor = test_conn.execute("SELECT id FROM plans WHERE id = ?", (record.id,))
        assert cursor.fetchone() is not None

        # Rollback should undo the create
        test_conn.rollback()

        # Verify plan no longer exists
        cursor = test_conn.execute("SELECT id FROM plans WHERE id = ?", (record.id,))
        assert cursor.fetchone() is None


class TestUpdatePlanStatusNoCommit:
    """Tests that update_plan_status does not auto-commit."""

    def test_update_plan_status_does_not_commit(
        self,
        test_conn: sqlite3.Connection,
        sample_file_id: int,
        sample_plan,
    ) -> None:
        """update_plan_status should not commit the transaction."""
        # Create plan first
        record = create_plan(test_conn, sample_plan, sample_file_id, "test-policy.yaml")
        test_conn.commit()

        # Update status
        update_plan_status(test_conn, record.id, PlanStatus.APPROVED)

        # Verify status is updated in current connection
        cursor = test_conn.execute(
            "SELECT status FROM plans WHERE id = ?", (record.id,)
        )
        row = cursor.fetchone()
        assert row[0] == "approved"

        # Rollback should undo the update
        test_conn.rollback()

        # Verify status reverted
        cursor = test_conn.execute(
            "SELECT status FROM plans WHERE id = ?", (record.id,)
        )
        row = cursor.fetchone()
        assert row[0] == "pending"
