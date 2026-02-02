"""Tests for library snapshot view functions."""

from vpo.db.views.snapshots import (
    LibrarySnapshotPoint,
    get_library_snapshots,
    insert_library_snapshot,
)


class TestInsertLibrarySnapshot:
    """Tests for insert_library_snapshot."""

    def test_insert_snapshot(self, db_conn):
        insert_library_snapshot(
            db_conn,
            snapshot_at="2025-01-15T10:00:00Z",
            total_files=100,
            total_size_bytes=50_000_000_000,
            missing_files=5,
            error_files=2,
        )

        cursor = db_conn.execute("SELECT COUNT(*) FROM library_snapshots")
        assert cursor.fetchone()[0] == 1

    def test_insert_multiple_snapshots(self, db_conn):
        for i in range(3):
            insert_library_snapshot(
                db_conn,
                snapshot_at=f"2025-01-{15 + i}T10:00:00Z",
                total_files=100 + i,
                total_size_bytes=50_000_000_000,
                missing_files=i,
            )

        cursor = db_conn.execute("SELECT COUNT(*) FROM library_snapshots")
        assert cursor.fetchone()[0] == 3

    def test_default_error_files(self, db_conn):
        insert_library_snapshot(
            db_conn,
            snapshot_at="2025-01-15T10:00:00Z",
            total_files=100,
            total_size_bytes=50_000_000_000,
            missing_files=0,
        )

        cursor = db_conn.execute("SELECT error_files FROM library_snapshots")
        assert cursor.fetchone()[0] == 0


class TestGetLibrarySnapshots:
    """Tests for get_library_snapshots."""

    def test_returns_empty_list(self, db_conn):
        result = get_library_snapshots(db_conn)
        assert result == []

    def test_returns_snapshots_ascending(self, db_conn):
        insert_library_snapshot(
            db_conn,
            snapshot_at="2025-01-17T10:00:00Z",
            total_files=102,
            total_size_bytes=52_000_000_000,
            missing_files=2,
        )
        insert_library_snapshot(
            db_conn,
            snapshot_at="2025-01-15T10:00:00Z",
            total_files=100,
            total_size_bytes=50_000_000_000,
            missing_files=0,
        )

        result = get_library_snapshots(db_conn)
        assert len(result) == 2
        # Ascending order
        assert result[0].snapshot_at < result[1].snapshot_at
        assert result[0].total_files == 100
        assert result[1].total_files == 102

    def test_returns_typed_dataclass(self, db_conn):
        insert_library_snapshot(
            db_conn,
            snapshot_at="2025-01-15T10:00:00Z",
            total_files=100,
            total_size_bytes=50_000_000_000,
            missing_files=5,
            error_files=2,
        )

        result = get_library_snapshots(db_conn)
        assert len(result) == 1
        assert isinstance(result[0], LibrarySnapshotPoint)
        assert result[0].total_files == 100
        assert result[0].missing_files == 5
        assert result[0].error_files == 2

    def test_since_filter(self, db_conn):
        insert_library_snapshot(
            db_conn,
            snapshot_at="2025-01-10T10:00:00Z",
            total_files=90,
            total_size_bytes=45_000_000_000,
            missing_files=0,
        )
        insert_library_snapshot(
            db_conn,
            snapshot_at="2025-01-20T10:00:00Z",
            total_files=100,
            total_size_bytes=50_000_000_000,
            missing_files=3,
        )

        result = get_library_snapshots(db_conn, since="2025-01-15T00:00:00Z")
        assert len(result) == 1
        assert result[0].total_files == 100

    def test_limit(self, db_conn):
        for i in range(10):
            insert_library_snapshot(
                db_conn,
                snapshot_at=f"2025-01-{10 + i:02d}T10:00:00Z",
                total_files=100 + i,
                total_size_bytes=50_000_000_000,
                missing_files=0,
            )

        result = get_library_snapshots(db_conn, limit=5)
        assert len(result) == 5
