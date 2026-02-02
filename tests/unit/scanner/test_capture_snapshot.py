"""Tests for library snapshot capture during scan."""

from vpo.db.queries import insert_file
from vpo.db.types import FileRecord
from vpo.scanner.orchestrator import ScannerOrchestrator


def _insert_test_file(conn, file_id, path, scan_status="ok", size_bytes=1000):
    """Insert a test file record."""
    record = FileRecord(
        id=file_id,
        path=path,
        filename=path.split("/")[-1],
        directory="/media",
        extension=".mkv",
        size_bytes=size_bytes,
        modified_at="2025-01-01T00:00:00Z",
        content_hash=None,
        container_format="mkv",
        scanned_at="2025-01-01T00:00:00Z",
        scan_status=scan_status,
        scan_error=None,
    )
    return insert_file(conn, record)


class TestCaptureLibrarySnapshot:
    """Tests for _capture_library_snapshot."""

    def test_captures_snapshot_with_correct_counts(self, db_conn):
        """Snapshot captures total files, size, and missing/error counts."""
        _insert_test_file(db_conn, 1, "/media/a.mkv", "ok", 1000)
        _insert_test_file(db_conn, 2, "/media/b.mkv", "ok", 2000)
        _insert_test_file(db_conn, 3, "/media/c.mkv", "missing", 500)
        _insert_test_file(db_conn, 4, "/media/d.mkv", "error", 300)
        db_conn.commit()

        scanner = ScannerOrchestrator()
        scanner._capture_library_snapshot(db_conn)

        cursor = db_conn.execute(
            "SELECT total_files, total_size_bytes, missing_files, error_files "
            "FROM library_snapshots"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["total_files"] == 4
        assert row["total_size_bytes"] == 3800
        assert row["missing_files"] == 1
        assert row["error_files"] == 1

    def test_snapshot_failure_does_not_raise(self, db_conn):
        """If snapshot insert fails, it logs but doesn't raise."""
        # Drop the table to force an error
        db_conn.execute("DROP TABLE IF EXISTS library_snapshots")
        db_conn.commit()

        scanner = ScannerOrchestrator()
        # Should not raise
        scanner._capture_library_snapshot(db_conn)
