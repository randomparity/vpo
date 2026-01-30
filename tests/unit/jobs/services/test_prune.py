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


class TestPruneJobServiceErrorPaths:
    """Tests for error handling in PruneJobService.process()."""

    def test_rolls_back_on_delete_failure(self, db_conn):
        """All deletions roll back if any single delete fails."""
        _insert_file(db_conn, 1, "/media/missing1.mkv", scan_status="missing")
        _insert_file(db_conn, 2, "/media/missing2.mkv", scan_status="missing")
        _insert_file(db_conn, 3, "/media/missing3.mkv", scan_status="missing")

        # Commit so files are persisted before we start
        db_conn.commit()

        # Monkey-patch delete_file to fail on the second call
        import vpo.jobs.services.prune as prune_module

        original_delete = prune_module.delete_file
        call_count = 0

        def failing_delete(conn, file_id):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise sqlite3.OperationalError("simulated delete failure")
            return original_delete(conn, file_id)

        prune_module.delete_file = failing_delete
        try:
            service = PruneJobService(db_conn)
            result = service.process()
        finally:
            prune_module.delete_file = original_delete

        # Should report failure
        assert result.success is False
        assert "simulated delete failure" in result.error_message

        # All 3 missing files should still exist (transaction rolled back)
        cursor = db_conn.execute(
            "SELECT COUNT(*) FROM files WHERE scan_status = 'missing'"
        )
        assert cursor.fetchone()[0] == 3

    def test_returns_failure_on_query_error(self, db_conn):
        """Returns failure result if the initial SELECT fails."""
        # Drop the files table to cause a query error
        db_conn.execute("DROP TABLE files")

        service = PruneJobService(db_conn)
        result = service.process()

        assert result.success is False
        assert result.error_message is not None

    def test_writes_to_job_log(self, db_conn):
        """Verifies job_log.write_line is called for progress messages."""
        _insert_file(db_conn, 1, "/media/missing1.mkv", scan_status="missing")
        _insert_file(db_conn, 2, "/media/missing2.mkv", scan_status="missing")

        class MockJobLog:
            def __init__(self):
                self.lines = []

            def write_line(self, msg):
                self.lines.append(msg)

        mock_log = MockJobLog()
        service = PruneJobService(db_conn)
        result = service.process(job_log=mock_log)

        assert result.success is True

        # Should have: header, per-file lines, summary
        assert any("Found 2" in line for line in mock_log.lines)
        assert any("Pruned:" in line for line in mock_log.lines)
        assert any("Pruned 2" in line for line in mock_log.lines)

    def test_no_missing_files_logs_message(self, db_conn):
        """When no files to prune, job log gets a message."""
        _insert_file(db_conn, 1, "/media/ok.mkv", scan_status="ok")

        class MockJobLog:
            def __init__(self):
                self.lines = []

            def write_line(self, msg):
                self.lines.append(msg)

        mock_log = MockJobLog()
        service = PruneJobService(db_conn)
        service.process(job_log=mock_log)

        assert any("No missing files" in line for line in mock_log.lines)
