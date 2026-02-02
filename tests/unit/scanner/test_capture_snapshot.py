"""Tests for library snapshot capture during scan."""

from vpo.scanner.orchestrator import ScannerOrchestrator


class TestCaptureLibrarySnapshot:
    """Tests for _capture_library_snapshot."""

    def test_captures_snapshot_with_correct_counts(self, db_conn, insert_test_file):
        """Snapshot captures total files, size, and missing/error counts."""
        insert_test_file(id=1, path="/media/a.mkv", scan_status="ok", size_bytes=1000)
        insert_test_file(id=2, path="/media/b.mkv", scan_status="ok", size_bytes=2000)
        insert_test_file(
            id=3, path="/media/c.mkv", scan_status="missing", size_bytes=500
        )
        insert_test_file(id=4, path="/media/d.mkv", scan_status="error", size_bytes=300)
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
