"""Integration tests for concurrent database writes.

Tests that the retry logic and transaction guards work correctly under
real concurrent write contention scenarios.
"""

import concurrent.futures
import sqlite3
import threading
from pathlib import Path

from vpo.db.queries import (
    insert_file,
    insert_track,
    upsert_transcription_result,
)
from vpo.db.schema import create_schema
from vpo.db.types import (
    FileRecord,
    TrackRecord,
    TranscriptionResultRecord,
)


class TestConcurrentTranscriptionWrites:
    """Test concurrent upsert_transcription_result calls."""

    def _setup_db_with_tracks(self, db_path: Path, num_tracks: int) -> None:
        """Create database with a file and specified number of tracks."""
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.row_factory = sqlite3.Row
        create_schema(conn)

        # Insert a file
        file_record = FileRecord(
            id=None,
            path=str(db_path.parent / "test.mkv"),
            filename="test.mkv",
            directory=str(db_path.parent),
            extension="mkv",
            size_bytes=1000000,
            content_hash="abc123",
            modified_at="2024-01-01T00:00:00Z",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="ok",
            scan_error=None,
            container_format="Matroska",
        )
        file_id = insert_file(conn, file_record)

        # Insert tracks
        for i in range(num_tracks):
            track_record = TrackRecord(
                id=None,
                file_id=file_id,
                track_index=i,
                track_type="audio",
                codec="aac",
                language="und",
                title=f"Track {i}",
                is_default=i == 0,
                is_forced=False,
                channels=2,
                channel_layout="stereo",
                duration_seconds=120.0,
            )
            insert_track(conn, track_record)

        conn.commit()
        conn.close()

    def _get_connection(self, db_path: Path) -> sqlite3.Connection:
        """Get a properly configured connection for a worker thread."""
        conn = sqlite3.connect(str(db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 1000")  # Short timeout, rely on retry
        conn.row_factory = sqlite3.Row
        return conn

    def test_concurrent_writes_to_different_tracks(self, tmp_path: Path) -> None:
        """Multiple threads writing to different tracks all succeed."""
        db_path = tmp_path / "test.db"
        num_tracks = 10

        self._setup_db_with_tracks(db_path, num_tracks)

        errors: list[str] = []
        success_count = [0]
        lock = threading.Lock()

        def upsert_for_track(track_id: int) -> None:
            conn = self._get_connection(db_path)
            try:
                record = TranscriptionResultRecord(
                    id=None,
                    track_id=track_id,
                    detected_language="eng",
                    confidence_score=0.95,
                    track_type="main",
                    transcript_sample=f"Sample for track {track_id}",
                    plugin_name="test-plugin",
                    created_at="2024-01-01T00:00:00Z",
                    updated_at="2024-01-01T00:00:00Z",
                )
                upsert_transcription_result(conn, record)
                with lock:
                    success_count[0] += 1
            except Exception as e:
                with lock:
                    errors.append(f"Track {track_id}: {e}")
            finally:
                conn.close()

        # Run concurrent upserts to different tracks
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Track IDs are 1-based from insert_track
            futures = [
                executor.submit(upsert_for_track, i) for i in range(1, num_tracks + 1)
            ]
            concurrent.futures.wait(futures)

        assert len(errors) == 0, f"Errors: {errors}"
        assert success_count[0] == num_tracks

        # Verify all records were written
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM transcription_results")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == num_tracks

    def test_concurrent_writes_to_same_track(self, tmp_path: Path) -> None:
        """Multiple threads writing to same track eventually all succeed."""
        db_path = tmp_path / "test.db"

        self._setup_db_with_tracks(db_path, 1)

        errors: list[str] = []
        success_count = [0]
        lock = threading.Lock()

        def upsert_same_track(iteration: int) -> None:
            conn = self._get_connection(db_path)
            try:
                record = TranscriptionResultRecord(
                    id=None,
                    track_id=1,  # All threads write to track 1
                    detected_language="eng",
                    confidence_score=0.90 + (iteration * 0.01),
                    track_type="main",
                    transcript_sample=f"Sample iteration {iteration}",
                    plugin_name="test-plugin",
                    created_at="2024-01-01T00:00:00Z",
                    updated_at="2024-01-01T00:00:00Z",
                )
                upsert_transcription_result(conn, record)
                with lock:
                    success_count[0] += 1
            except Exception as e:
                with lock:
                    errors.append(f"Iteration {iteration}: {e}")
            finally:
                conn.close()

        # Run concurrent upserts to the SAME track
        num_iterations = 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(upsert_same_track, i) for i in range(num_iterations)
            ]
            concurrent.futures.wait(futures)

        assert len(errors) == 0, f"Errors: {errors}"
        assert success_count[0] == num_iterations

        # Verify exactly one record exists (last-write-wins via ON CONFLICT)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM transcription_results")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

    def test_upsert_works_within_existing_transaction(self, tmp_path: Path) -> None:
        """Test that upsert works when called within an existing transaction."""
        db_path = tmp_path / "test.db"

        self._setup_db_with_tracks(db_path, 1)

        conn = self._get_connection(db_path)

        # Start a transaction manually
        conn.execute("BEGIN IMMEDIATE")

        record = TranscriptionResultRecord(
            id=None,
            track_id=1,
            detected_language="eng",
            confidence_score=0.95,
            track_type="main",
            transcript_sample="Test",
            plugin_name="test-plugin",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        # Should succeed - upsert participates in existing transaction
        result_id = upsert_transcription_result(conn, record)
        assert result_id is not None

        # Commit the outer transaction
        conn.execute("COMMIT")

        # Verify record was persisted
        cursor = conn.execute(
            "SELECT detected_language FROM transcription_results WHERE id = ?",
            (result_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "eng"

        conn.close()
