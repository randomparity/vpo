"""Unit tests for processing_stats database queries."""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from video_policy_orchestrator.db.queries import (
    delete_all_processing_stats,
    delete_processing_stats_before,
    delete_processing_stats_by_policy,
)
from video_policy_orchestrator.db.schema import create_schema


@pytest.fixture
def conn() -> sqlite3.Connection:
    """Create an in-memory database with schema for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    yield conn
    conn.close()


def _insert_test_stats(
    conn: sqlite3.Connection,
    stats_id: str,
    policy_name: str,
    processed_at: str,
    file_id: int = 1,
) -> None:
    """Insert a minimal test processing_stats record directly."""
    conn.execute(
        """
        INSERT INTO processing_stats (
            id, file_id, processed_at, policy_name,
            size_before, size_after, size_change,
            audio_tracks_before, subtitle_tracks_before, attachments_before,
            audio_tracks_after, subtitle_tracks_after, attachments_after,
            audio_tracks_removed, subtitle_tracks_removed, attachments_removed,
            duration_seconds, phases_completed, phases_total, total_changes,
            video_source_codec, video_target_codec, video_transcode_skipped,
            video_skip_reason, audio_tracks_transcoded, audio_tracks_preserved,
            hash_before, hash_after, success, error_message
        ) VALUES (
            ?, ?, ?, ?,
            1000, 900, 100,
            2, 3, 1,
            2, 3, 1,
            0, 0, 0,
            10.5, 1, 1, 5,
            'h264', NULL, 0,
            NULL, 0, 2,
            NULL, NULL, 1, NULL
        )
        """,
        (stats_id, file_id, processed_at, policy_name),
    )
    conn.commit()


class TestDeleteProcessingStatsBefore:
    """Tests for delete_processing_stats_before."""

    def test_deletes_old_records(self, conn: sqlite3.Connection) -> None:
        """Should delete records older than specified date."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=60)).isoformat()
        recent_date = (now - timedelta(days=10)).isoformat()
        cutoff = (now - timedelta(days=30)).isoformat()

        # Insert records
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", old_date)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-b", old_date)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", recent_date)

        # Delete old records
        deleted = delete_processing_stats_before(conn, cutoff)

        assert deleted == 2

        # Verify only recent record remains
        cursor = conn.execute("SELECT COUNT(*) FROM processing_stats")
        assert cursor.fetchone()[0] == 1

    def test_dry_run_returns_count_without_deleting(
        self, conn: sqlite3.Connection
    ) -> None:
        """Dry run should return count but not delete."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=60)).isoformat()
        cutoff = (now - timedelta(days=30)).isoformat()

        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", old_date)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-b", old_date)

        # Dry run
        count = delete_processing_stats_before(conn, cutoff, dry_run=True)

        assert count == 2

        # Verify records still exist
        cursor = conn.execute("SELECT COUNT(*) FROM processing_stats")
        assert cursor.fetchone()[0] == 2

    def test_no_matches_returns_zero(self, conn: sqlite3.Connection) -> None:
        """Should return 0 when no records match."""
        now = datetime.now(timezone.utc)
        recent_date = now.isoformat()
        cutoff = (now - timedelta(days=30)).isoformat()

        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", recent_date)

        deleted = delete_processing_stats_before(conn, cutoff)

        assert deleted == 0


class TestDeleteProcessingStatsByPolicy:
    """Tests for delete_processing_stats_by_policy."""

    def test_deletes_records_for_policy(self, conn: sqlite3.Connection) -> None:
        """Should delete all records for specified policy."""
        now = datetime.now(timezone.utc).isoformat()

        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", now)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", now)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-b", now)

        deleted = delete_processing_stats_by_policy(conn, "policy-a")

        assert deleted == 2

        # Verify only policy-b record remains
        cursor = conn.execute("SELECT COUNT(*) FROM processing_stats")
        assert cursor.fetchone()[0] == 1

    def test_dry_run_returns_count_without_deleting(
        self, conn: sqlite3.Connection
    ) -> None:
        """Dry run should return count but not delete."""
        now = datetime.now(timezone.utc).isoformat()

        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", now)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", now)

        count = delete_processing_stats_by_policy(conn, "policy-a", dry_run=True)

        assert count == 2

        cursor = conn.execute("SELECT COUNT(*) FROM processing_stats")
        assert cursor.fetchone()[0] == 2

    def test_no_matches_returns_zero(self, conn: sqlite3.Connection) -> None:
        """Should return 0 when policy has no records."""
        now = datetime.now(timezone.utc).isoformat()

        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", now)

        deleted = delete_processing_stats_by_policy(conn, "nonexistent")

        assert deleted == 0


class TestDeleteAllProcessingStats:
    """Tests for delete_all_processing_stats."""

    def test_deletes_all_records(self, conn: sqlite3.Connection) -> None:
        """Should delete all processing stats records."""
        now = datetime.now(timezone.utc).isoformat()

        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", now)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-b", now)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-c", now)

        deleted = delete_all_processing_stats(conn)

        assert deleted == 3

        cursor = conn.execute("SELECT COUNT(*) FROM processing_stats")
        assert cursor.fetchone()[0] == 0

    def test_dry_run_returns_count_without_deleting(
        self, conn: sqlite3.Connection
    ) -> None:
        """Dry run should return count but not delete."""
        now = datetime.now(timezone.utc).isoformat()

        _insert_test_stats(conn, str(uuid.uuid4()), "policy-a", now)
        _insert_test_stats(conn, str(uuid.uuid4()), "policy-b", now)

        count = delete_all_processing_stats(conn, dry_run=True)

        assert count == 2

        cursor = conn.execute("SELECT COUNT(*) FROM processing_stats")
        assert cursor.fetchone()[0] == 2

    def test_empty_table_returns_zero(self, conn: sqlite3.Connection) -> None:
        """Should return 0 when table is empty."""
        deleted = delete_all_processing_stats(conn)
        assert deleted == 0
