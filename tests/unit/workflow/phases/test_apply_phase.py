"""Unit tests for ApplyPhase."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.schema import create_schema
from vpo.db.types import OperationStatus
from vpo.executor.backup import FileLockError
from vpo.policy.models import (
    PolicySchema,
    ProcessingPhase,
)
from vpo.workflow.phases.apply import ApplyPhase
from vpo.workflow.processor import PhaseError


@pytest.fixture
def db_conn():
    """Create in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def base_policy():
    """Create a minimal policy for testing."""
    return PolicySchema(schema_version=12)


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 100)
    return f


def insert_test_file(conn, file_path: Path) -> int:
    """Insert a test file record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            container_format, modified_at, scanned_at, scan_status
        )
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'complete')
        """,
        (
            str(file_path),
            file_path.name,
            str(file_path.parent),
            file_path.suffix,
            100,
            "mkv",
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_test_track(conn, file_id: int, track_type: str = "video") -> int:
    """Insert a test track record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO tracks (
            file_id, track_index, track_type, codec, language
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (file_id, 0, track_type, "h264" if track_type == "video" else "aac", "eng"),
    )
    conn.commit()
    return cursor.lastrowid


class TestApplyPhaseInit:
    """Tests for ApplyPhase initialization."""

    def test_init_with_defaults(self, db_conn, base_policy):
        """ApplyPhase initializes with default values."""
        phase = ApplyPhase(conn=db_conn, policy=base_policy)

        assert phase.conn is db_conn
        assert phase.policy is base_policy
        assert phase.dry_run is False
        assert phase.verbose is False
        assert phase.policy_name == "workflow"

    def test_init_with_policy_name(self, db_conn, base_policy):
        """ApplyPhase accepts custom policy_name."""
        phase = ApplyPhase(
            conn=db_conn,
            policy=base_policy,
            policy_name="custom_policy.yaml",
        )

        assert phase.policy_name == "custom_policy.yaml"


class TestApplyPhaseRun:
    """Tests for ApplyPhase.run() method."""

    def test_run_raises_for_missing_file(self, db_conn, base_policy, test_file):
        """run() raises PhaseError when file not in database."""
        phase = ApplyPhase(conn=db_conn, policy=base_policy)

        with pytest.raises(PhaseError) as exc_info:
            phase.run(test_file)

        assert "not found in database" in str(exc_info.value)
        assert exc_info.value.phase == ProcessingPhase.APPLY

    def test_run_raises_for_no_tracks(self, db_conn, base_policy, test_file):
        """run() raises PhaseError when file has no tracks."""
        insert_test_file(db_conn, test_file)

        phase = ApplyPhase(conn=db_conn, policy=base_policy)

        with pytest.raises(PhaseError) as exc_info:
            phase.run(test_file)

        assert "No tracks found" in str(exc_info.value)

    @patch("vpo.workflow.phases.apply.file_lock")
    @patch("vpo.workflow.phases.apply.create_operation")
    @patch("vpo.workflow.phases.apply.update_operation_status")
    @patch("vpo.plugins.policy_engine.plugin.PolicyEnginePlugin")
    def test_run_acquires_file_lock(
        self,
        mock_engine_cls,
        mock_update_status,
        mock_create_op,
        mock_file_lock,
        db_conn,
        base_policy,
        test_file,
    ):
        """run() acquires file lock before executing."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_operation = MagicMock()
        mock_operation.id = "test-op-id"
        mock_create_op.return_value = mock_operation

        mock_engine = MagicMock()
        mock_plan = MagicMock()
        mock_plan.is_empty = False
        mock_plan.actions = []  # Empty list to avoid JSON serialization issues
        mock_plan.tracks_removed = 1
        mock_engine.evaluate.return_value = mock_plan

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.backup_path = None
        mock_engine.execute.return_value = mock_result

        mock_engine_cls.return_value = mock_engine
        mock_file_lock.return_value.__enter__ = MagicMock()
        mock_file_lock.return_value.__exit__ = MagicMock(return_value=False)

        phase = ApplyPhase(conn=db_conn, policy=base_policy)
        phase._policy_engine = mock_engine

        phase.run(test_file)

        # Verify file_lock was called with the file path
        mock_file_lock.assert_called_once_with(test_file)


class TestApplyPhaseFileLocking:
    """Tests for file locking behavior."""

    @patch("vpo.workflow.phases.apply.file_lock")
    @patch("vpo.workflow.phases.apply.create_operation")
    @patch("vpo.plugins.policy_engine.plugin.PolicyEnginePlugin")
    def test_file_lock_error_raises_phase_error(
        self,
        mock_engine_cls,
        mock_create_op,
        mock_file_lock,
        db_conn,
        base_policy,
        test_file,
    ):
        """FileLockError is converted to PhaseError."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_operation = MagicMock()
        mock_operation.id = "test-op-id"
        mock_create_op.return_value = mock_operation

        mock_engine = MagicMock()
        mock_plan = MagicMock()
        mock_plan.is_empty = False
        mock_plan.actions = []  # Empty list to avoid JSON issues
        mock_plan.tracks_removed = 1
        mock_engine.evaluate.return_value = mock_plan
        mock_engine_cls.return_value = mock_engine

        mock_file_lock.side_effect = FileLockError("File is locked")

        phase = ApplyPhase(conn=db_conn, policy=base_policy)
        phase._policy_engine = mock_engine

        with pytest.raises(PhaseError) as exc_info:
            phase.run(test_file)

        assert "Cannot acquire file lock" in str(exc_info.value)
        assert exc_info.value.phase == ProcessingPhase.APPLY


class TestApplyPhaseDryRun:
    """Tests for dry-run mode."""

    @patch("vpo.plugins.policy_engine.plugin.PolicyEnginePlugin")
    def test_dry_run_does_not_execute(
        self, mock_engine_cls, db_conn, base_policy, test_file
    ):
        """dry_run=True evaluates but does not execute."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_engine = MagicMock()
        mock_plan = MagicMock()
        mock_plan.is_empty = False
        mock_plan.actions = [MagicMock(), MagicMock()]
        mock_plan.tracks_removed = 1
        mock_engine.evaluate.return_value = mock_plan
        mock_engine_cls.return_value = mock_engine

        phase = ApplyPhase(conn=db_conn, policy=base_policy, dry_run=True)
        phase._policy_engine = mock_engine

        changes = phase.run(test_file)

        # Should return change count but not call execute
        assert changes == 3  # 2 actions + 1 track removed
        mock_engine.execute.assert_not_called()

    @patch("vpo.plugins.policy_engine.plugin.PolicyEnginePlugin")
    def test_no_changes_returns_zero(
        self, mock_engine_cls, db_conn, base_policy, test_file
    ):
        """Empty plan returns 0 changes."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_engine = MagicMock()
        mock_plan = MagicMock()
        mock_plan.is_empty = True
        mock_engine.evaluate.return_value = mock_plan
        mock_engine_cls.return_value = mock_engine

        phase = ApplyPhase(conn=db_conn, policy=base_policy)
        phase._policy_engine = mock_engine

        changes = phase.run(test_file)

        assert changes == 0
        mock_engine.execute.assert_not_called()


class TestApplyPhaseOperationTracking:
    """Tests for operation record creation."""

    @patch("vpo.workflow.phases.apply.file_lock")
    @patch("vpo.workflow.phases.apply.create_operation")
    @patch("vpo.workflow.phases.apply.update_operation_status")
    @patch("vpo.plugins.policy_engine.plugin.PolicyEnginePlugin")
    def test_operation_created_and_completed(
        self,
        mock_engine_cls,
        mock_update_status,
        mock_create_op,
        mock_file_lock,
        db_conn,
        base_policy,
        test_file,
    ):
        """Operation record is created and marked completed on success."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_operation = MagicMock()
        mock_operation.id = "test-op-id"
        mock_create_op.return_value = mock_operation

        mock_engine = MagicMock()
        mock_plan = MagicMock()
        mock_plan.is_empty = False
        mock_plan.actions = [MagicMock()]
        mock_plan.tracks_removed = 0
        mock_engine.evaluate.return_value = mock_plan

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.backup_path = Path("/backup/test.mkv")
        mock_engine.execute.return_value = mock_result
        mock_engine_cls.return_value = mock_engine

        mock_file_lock.return_value.__enter__ = MagicMock()
        mock_file_lock.return_value.__exit__ = MagicMock(return_value=False)

        phase = ApplyPhase(conn=db_conn, policy=base_policy)
        phase._policy_engine = mock_engine

        phase.run(test_file)

        # Verify operation was created
        mock_create_op.assert_called_once()

        # Verify operation was marked completed
        mock_update_status.assert_called()
        call_args = mock_update_status.call_args
        assert call_args[0][1] == "test-op-id"
        assert call_args[0][2] == OperationStatus.COMPLETED

    @patch("vpo.workflow.phases.apply.file_lock")
    @patch("vpo.workflow.phases.apply.create_operation")
    @patch("vpo.workflow.phases.apply.update_operation_status")
    @patch("vpo.plugins.policy_engine.plugin.PolicyEnginePlugin")
    def test_operation_marked_failed_on_error(
        self,
        mock_engine_cls,
        mock_update_status,
        mock_create_op,
        mock_file_lock,
        db_conn,
        base_policy,
        test_file,
    ):
        """Operation record is marked failed on execution error."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_operation = MagicMock()
        mock_operation.id = "test-op-id"
        mock_create_op.return_value = mock_operation

        mock_engine = MagicMock()
        mock_plan = MagicMock()
        mock_plan.is_empty = False
        mock_plan.actions = [MagicMock()]
        mock_plan.tracks_removed = 0
        mock_engine.evaluate.return_value = mock_plan

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.message = "Execution failed"
        mock_engine.execute.return_value = mock_result
        mock_engine_cls.return_value = mock_engine

        mock_file_lock.return_value.__enter__ = MagicMock()
        mock_file_lock.return_value.__exit__ = MagicMock(return_value=False)

        phase = ApplyPhase(conn=db_conn, policy=base_policy)
        phase._policy_engine = mock_engine

        with pytest.raises(PhaseError):
            phase.run(test_file)

        # Verify operation was marked failed
        mock_update_status.assert_called()
        call_args = mock_update_status.call_args
        assert call_args[0][2] == OperationStatus.FAILED
