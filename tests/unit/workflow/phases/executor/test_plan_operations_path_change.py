"""Tests for _handle_path_change function in plan_operations.py.

These tests verify proper error handling, state/DB ordering, and
transaction management for container conversion path updates.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from vpo.db.queries import get_file_by_path, insert_file
from vpo.db.types import FileRecord
from vpo.policy.types import PhaseDefinition
from vpo.workflow.phases.executor.plan_operations import _handle_path_change
from vpo.workflow.phases.executor.types import PhaseExecutionState


@pytest.fixture
def test_phase():
    """Create a test PhaseDefinition."""
    return PhaseDefinition(name="test")


def create_file_record(
    conn: sqlite3.Connection,
    path: str,
    extension: str = "avi",
) -> int:
    """Create a file record and return its ID."""
    p = Path(path)
    record = FileRecord(
        id=None,
        path=str(p),
        filename=p.name,
        directory=str(p.parent),
        extension=extension,
        size_bytes=1000000,
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_hash="hash123",
        container_format="avi",
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scan_status="ok",
        scan_error=None,
        job_id=None,
        plugin_metadata=None,
    )
    file_id = insert_file(conn, record)
    conn.commit()
    return file_id


class TestHandlePathChange:
    """Tests for _handle_path_change function."""

    def test_updates_state_after_successful_db_update(
        self, tmp_path, db_conn, test_phase
    ):
        """State should only update after DB update succeeds."""
        old_path = tmp_path / "movie.avi"
        new_path = tmp_path / "movie.mkv"
        old_path.touch()
        new_path.touch()

        # Insert file record with old path
        create_file_record(db_conn, str(old_path), extension="avi")

        state = PhaseExecutionState(file_path=old_path, phase=test_phase)

        _handle_path_change(state, new_path, db_conn)

        # State should be updated
        assert state.file_path == new_path

        # DB should also be updated
        db_conn.commit()  # Commit since _handle_path_change doesn't
        record = get_file_by_path(db_conn, str(new_path))
        assert record is not None
        assert record.path == str(new_path)
        assert record.filename == "movie.mkv"
        assert record.extension == "mkv"

    def test_raises_when_file_not_in_database(self, tmp_path, db_conn, test_phase):
        """Should raise ValueError when old path not in database."""
        old_path = tmp_path / "unknown.avi"
        new_path = tmp_path / "unknown.mkv"

        state = PhaseExecutionState(file_path=old_path, phase=test_phase)

        with pytest.raises(ValueError, match="not in database"):
            _handle_path_change(state, new_path, db_conn)

        # State should NOT be updated on failure
        assert state.file_path == old_path

    def test_raises_on_duplicate_path(self, tmp_path, db_conn, test_phase):
        """Should raise ValueError when new path already exists in database."""
        old_path = tmp_path / "movie.avi"
        existing_path = tmp_path / "movie.mkv"
        old_path.touch()
        existing_path.touch()

        # Insert both files in database
        create_file_record(db_conn, str(old_path), extension="avi")
        create_file_record(db_conn, str(existing_path), extension="mkv")

        state = PhaseExecutionState(file_path=old_path, phase=test_phase)

        with pytest.raises(ValueError, match="already exists"):
            _handle_path_change(state, existing_path, db_conn)

        # State should NOT be updated on failure
        assert state.file_path == old_path

    def test_does_not_commit(self, tmp_path, db_conn, test_phase):
        """Function should not commit - caller manages transactions."""
        old_path = tmp_path / "movie.avi"
        new_path = tmp_path / "movie.mkv"
        old_path.touch()
        new_path.touch()

        # Insert file record
        create_file_record(db_conn, str(old_path), extension="avi")

        state = PhaseExecutionState(file_path=old_path, phase=test_phase)

        _handle_path_change(state, new_path, db_conn)

        # Rollback and verify change was not persisted
        db_conn.rollback()

        # Original path should still exist after rollback
        original = get_file_by_path(db_conn, str(old_path))
        assert original is not None
        assert original.path == str(old_path)

        # New path should NOT exist after rollback
        updated = get_file_by_path(db_conn, str(new_path))
        assert updated is None

    def test_state_unchanged_on_db_error(self, tmp_path, db_conn, test_phase):
        """State should remain unchanged when database update fails."""
        old_path = tmp_path / "movie.avi"
        new_path = tmp_path / "movie.mkv"
        old_path.touch()

        # Insert file record
        create_file_record(db_conn, str(old_path), extension="avi")

        state = PhaseExecutionState(file_path=old_path, phase=test_phase)

        # Mock update_file_path to raise an error
        with patch(
            "vpo.workflow.phases.executor.plan_operations.update_file_path"
        ) as mock_update:
            mock_update.side_effect = sqlite3.OperationalError("Database locked")

            with pytest.raises(RuntimeError, match="Database update failed"):
                _handle_path_change(state, new_path, db_conn)

        # State should NOT be updated on failure
        assert state.file_path == old_path

    def test_updates_extension_field(self, tmp_path, db_conn, test_phase):
        """Extension field should be updated after container conversion."""
        old_path = tmp_path / "movie.avi"
        new_path = tmp_path / "movie.mkv"
        old_path.touch()
        new_path.touch()

        # Insert file record with avi extension
        create_file_record(db_conn, str(old_path), extension="avi")

        state = PhaseExecutionState(file_path=old_path, phase=test_phase)

        _handle_path_change(state, new_path, db_conn)
        db_conn.commit()

        # Verify extension was updated
        record = get_file_by_path(db_conn, str(new_path))
        assert record is not None
        assert record.extension == "mkv"
