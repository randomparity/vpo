"""Tests for the prune job service."""

import sqlite3

import pytest

from vpo.db.queries import insert_file
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord
from vpo.jobs.services.prune import PruneJobResult, PruneJobService


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _insert_file(conn, file_id, path, scan_status="ok"):
    """Insert a test file record."""
    record = FileRecord(
        id=file_id,
        path=path,
        filename=path.split("/")[-1],
        directory="/media",
        extension=".mkv",
        size_bytes=1000,
        modified_at="2025-01-01T00:00:00Z",
        content_hash=None,
        container_format="mkv",
        scanned_at="2025-01-01T00:00:00Z",
        scan_status=scan_status,
        scan_error=None,
    )
    return insert_file(conn, record)


class TestPruneJobResult:
    """Tests for PruneJobResult dataclass."""

    def test_success_result(self):
        result = PruneJobResult(success=True, files_pruned=5)
        assert result.success is True
        assert result.files_pruned == 5
        assert result.error_message is None

    def test_failure_result(self):
        result = PruneJobResult(success=False, error_message="DB error")
        assert result.success is False
        assert result.files_pruned == 0
        assert result.error_message == "DB error"


class TestPruneJobServiceProcess:
    """Tests for PruneJobService.process()."""

    def test_prune_deletes_missing_files(self, db_conn):
        """Pruning removes files with scan_status='missing'."""
        _insert_file(db_conn, 1, "/media/ok.mkv", scan_status="ok")
        _insert_file(db_conn, 2, "/media/missing1.mkv", scan_status="missing")
        _insert_file(db_conn, 3, "/media/missing2.mkv", scan_status="missing")
        _insert_file(db_conn, 4, "/media/error.mkv", scan_status="error")

        service = PruneJobService(db_conn)
        result = service.process()

        assert result.success is True
        assert result.files_pruned == 2

        # Verify only missing files were deleted
        cursor = db_conn.execute("SELECT COUNT(*) FROM files")
        assert cursor.fetchone()[0] == 2  # ok + error remain

    def test_prune_no_missing_files(self, db_conn):
        """Pruning with no missing files returns zero count."""
        _insert_file(db_conn, 1, "/media/ok.mkv", scan_status="ok")

        service = PruneJobService(db_conn)
        result = service.process()

        assert result.success is True
        assert result.files_pruned == 0

    def test_prune_empty_database(self, db_conn):
        """Pruning an empty database returns zero count."""
        service = PruneJobService(db_conn)
        result = service.process()

        assert result.success is True
        assert result.files_pruned == 0

    def test_prune_preserves_ok_and_error_files(self, db_conn):
        """Pruning does not touch ok or error files."""
        _insert_file(db_conn, 1, "/media/ok.mkv", scan_status="ok")
        _insert_file(db_conn, 2, "/media/error.mkv", scan_status="error")
        _insert_file(db_conn, 3, "/media/missing.mkv", scan_status="missing")

        service = PruneJobService(db_conn)
        service.process()

        # ok and error files remain
        cursor = db_conn.execute("SELECT scan_status FROM files ORDER BY id")
        statuses = [row[0] for row in cursor.fetchall()]
        assert statuses == ["ok", "error"]
