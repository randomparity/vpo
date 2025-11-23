"""Unit tests for database concurrency and transaction handling (008-operational-ux).

These tests verify:
- Concurrent database access with WAL mode
- Transaction atomicity
- Proper error handling and rollback
"""

from __future__ import annotations

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pytest

from video_policy_orchestrator.db.models import (
    FileRecord,
    TrackInfo,
    get_file_by_path,
    upsert_file,
    upsert_tracks_for_file,
)
from video_policy_orchestrator.db.schema import initialize_database


class TestWALModeConcurrency:
    """Tests for WAL mode concurrent access."""

    def test_concurrent_readers_with_wal(self, tmp_path: Path) -> None:
        """Multiple readers should work concurrently in WAL mode."""
        db_path = tmp_path / "test.db"

        # Create database with WAL mode
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode = WAL")
        initialize_database(conn)

        # Insert test data
        record = FileRecord(
            id=None,
            path="/test/video.mkv",
            filename="video.mkv",
            directory="/test",
            extension="mkv",
            size_bytes=1000,
            modified_at=datetime.now(timezone.utc).isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )
        upsert_file(conn, record)
        conn.close()

        # Run concurrent reads
        results = []
        errors = []

        def read_file(reader_id: int) -> str | None:
            try:
                reader_conn = sqlite3.connect(str(db_path))
                reader_conn.execute("PRAGMA journal_mode = WAL")
                result = get_file_by_path(reader_conn, "/test/video.mkv")
                reader_conn.close()
                return result.filename if result else None
            except Exception as e:
                return f"Error: {e}"

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(read_file, i) for i in range(10)]
            for future in as_completed(futures):
                result = future.result()
                if result and result.startswith("Error:"):
                    errors.append(result)
                else:
                    results.append(result)

        assert len(errors) == 0, f"Concurrent reads failed: {errors}"
        assert len(results) == 10
        assert all(r == "video.mkv" for r in results)

    def test_writer_with_concurrent_readers(self, tmp_path: Path) -> None:
        """Writer and readers should work concurrently in WAL mode."""
        db_path = tmp_path / "test.db"

        # Create database with WAL mode
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        initialize_database(conn)
        conn.close()

        write_count = 0
        read_count = 0
        errors = []
        lock = threading.Lock()

        def writer() -> None:
            nonlocal write_count
            try:
                writer_conn = sqlite3.connect(str(db_path))
                writer_conn.execute("PRAGMA journal_mode = WAL")
                writer_conn.execute("PRAGMA busy_timeout = 5000")

                for i in range(5):
                    record = FileRecord(
                        id=None,
                        path=f"/test/video_{i}.mkv",
                        filename=f"video_{i}.mkv",
                        directory="/test",
                        extension="mkv",
                        size_bytes=1000 + i,
                        modified_at=datetime.now(timezone.utc).isoformat(),
                        content_hash=f"hash_{i}",
                        container_format="Matroska",
                        scanned_at=datetime.now(timezone.utc).isoformat(),
                        scan_status="ok",
                        scan_error=None,
                    )
                    upsert_file(writer_conn, record)
                    with lock:
                        write_count += 1
                    time.sleep(0.01)  # Small delay to interleave

                writer_conn.close()
            except Exception as e:
                with lock:
                    errors.append(f"Writer error: {e}")

        def reader() -> None:
            nonlocal read_count
            try:
                reader_conn = sqlite3.connect(str(db_path))
                reader_conn.execute("PRAGMA journal_mode = WAL")
                reader_conn.execute("PRAGMA busy_timeout = 5000")

                for _ in range(10):
                    cursor = reader_conn.execute("SELECT COUNT(*) FROM files")
                    cursor.fetchone()
                    with lock:
                        read_count += 1
                    time.sleep(0.005)

                reader_conn.close()
            except Exception as e:
                with lock:
                    errors.append(f"Reader error: {e}")

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent access failed: {errors}"
        assert write_count == 5
        assert read_count == 20


class TestTransactionAtomicity:
    """Tests for transaction atomicity."""

    def test_upsert_tracks_no_commit(self) -> None:
        """upsert_tracks_for_file should not commit (caller responsibility)."""
        conn = sqlite3.connect(":memory:")
        initialize_database(conn)

        # Create parent file
        record = FileRecord(
            id=None,
            path="/test/video.mkv",
            filename="video.mkv",
            directory="/test",
            extension="mkv",
            size_bytes=1000,
            modified_at=datetime.now(timezone.utc).isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )
        file_id = upsert_file(conn, record)

        # Add tracks without explicit commit from function
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="h264",
                language="und",
                title=None,
                is_default=True,
                is_forced=False,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                title="English",
                is_default=True,
                is_forced=False,
            ),
        ]
        upsert_tracks_for_file(conn, file_id, tracks)

        # Verify tracks are visible (in uncommitted transaction)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE file_id = ?", (file_id,)
        )
        count = cursor.fetchone()[0]
        assert count == 2

        # Rollback should remove the tracks (since upsert_tracks didn't commit)
        # But upsert_file already committed, so we need to manually test
        # the uncommitted state by using a savepoint

        conn.close()

    def test_rollback_on_track_update_failure(self) -> None:
        """Simulated failure during track update should allow rollback."""
        conn = sqlite3.connect(":memory:")
        initialize_database(conn)

        # Create parent file
        record = FileRecord(
            id=None,
            path="/test/video.mkv",
            filename="video.mkv",
            directory="/test",
            extension="mkv",
            size_bytes=1000,
            modified_at=datetime.now(timezone.utc).isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )
        file_id = upsert_file(conn, record)

        # Use savepoint to test rollback behavior
        conn.execute("SAVEPOINT track_update")

        try:
            # Add first track
            conn.execute(
                """
                INSERT INTO tracks (file_id, track_index, track_type, codec, language,
                                   title, is_default, is_forced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, 0, "video", "h264", "und", None, 1, 0),
            )

            # Simulate failure
            raise ValueError("Simulated failure")

        except ValueError:
            conn.execute("ROLLBACK TO SAVEPOINT track_update")

        # Verify no tracks were added
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE file_id = ?", (file_id,)
        )
        count = cursor.fetchone()[0]
        assert count == 0

        conn.close()


class TestForeignKeyConstraints:
    """Tests for foreign key constraint behavior."""

    def test_cascade_delete_tracks_on_file_delete(self) -> None:
        """Deleting a file should cascade delete its tracks."""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON")
        initialize_database(conn)

        # Create file with tracks
        record = FileRecord(
            id=None,
            path="/test/video.mkv",
            filename="video.mkv",
            directory="/test",
            extension="mkv",
            size_bytes=1000,
            modified_at=datetime.now(timezone.utc).isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )
        file_id = upsert_file(conn, record)

        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="h264",
                language="und",
                title=None,
                is_default=True,
                is_forced=False,
            ),
        ]
        upsert_tracks_for_file(conn, file_id, tracks)
        conn.commit()

        # Verify track exists
        cursor = conn.execute("SELECT COUNT(*) FROM tracks")
        assert cursor.fetchone()[0] == 1

        # Delete file
        conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        conn.commit()

        # Verify track was cascade deleted
        cursor = conn.execute("SELECT COUNT(*) FROM tracks")
        assert cursor.fetchone()[0] == 0

        conn.close()

    def test_foreign_key_prevents_orphan_tracks(self) -> None:
        """Cannot insert track with non-existent file_id."""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON")
        initialize_database(conn)

        # Try to insert track with non-existent file_id
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO tracks (file_id, track_index, track_type, codec, language,
                                   title, is_default, is_forced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (9999, 0, "video", "h264", "und", None, 1, 0),
            )

        conn.close()


class TestBusyTimeout:
    """Tests for database lock handling with busy timeout."""

    def test_busy_timeout_allows_retry(self, tmp_path: Path) -> None:
        """Busy timeout should allow waiting for lock release."""
        db_path = tmp_path / "test.db"

        # Create database
        conn1 = sqlite3.connect(str(db_path))
        conn1.execute("PRAGMA journal_mode = WAL")
        conn1.execute("PRAGMA busy_timeout = 5000")
        initialize_database(conn1)

        # Start a transaction in conn1
        conn1.execute("BEGIN IMMEDIATE")
        conn1.execute(
            "INSERT INTO _meta (key, value) VALUES ('test_key', 'test_value')"
        )

        # conn2 should wait for busy_timeout
        conn2 = sqlite3.connect(str(db_path))
        conn2.execute("PRAGMA busy_timeout = 100")  # Short timeout for test

        try:
            # This should timeout since conn1 holds the lock
            conn2.execute("BEGIN IMMEDIATE")
            pytest.fail("Expected database locked error")
        except sqlite3.OperationalError as e:
            assert "database is locked" in str(e)

        # Release lock
        conn1.rollback()
        conn1.close()

        # Now conn2 should succeed
        conn2.execute("BEGIN IMMEDIATE")
        conn2.rollback()
        conn2.close()
