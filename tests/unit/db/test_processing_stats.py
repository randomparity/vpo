"""Unit tests for processing_stats database queries."""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from vpo.db.queries import (
    delete_all_processing_stats,
    delete_processing_stats_before,
    delete_processing_stats_by_policy,
    get_action_results_for_stats,
    get_performance_metrics_for_stats,
    get_processing_stats_by_id,
    get_processing_stats_for_file,
    insert_action_result,
    insert_performance_metric,
    insert_processing_stats,
)
from vpo.db.schema import create_schema
from vpo.db.types import (
    ActionResultRecord,
    PerformanceMetricsRecord,
    ProcessingStatsRecord,
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    """Create an in-memory database with schema for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    # Enable foreign keys for constraint testing
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


@pytest.fixture
def file_id(conn: sqlite3.Connection) -> int:
    """Create a test file record and return its ID."""
    conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            modified_at, scanned_at, scan_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/test/video.mkv",
            "video.mkv",
            "/test",
            ".mkv",
            1000000,
            "2024-01-01T00:00:00",
            "2024-01-01T00:00:00",
            "complete",
        ),
    )
    conn.commit()
    cursor = conn.execute("SELECT last_insert_rowid()")
    return cursor.fetchone()[0]


def _create_stats_record(
    file_id: int,
    stats_id: str | None = None,
    policy_name: str = "test-policy.yaml",
    processed_at: str | None = None,
) -> ProcessingStatsRecord:
    """Create a ProcessingStatsRecord for testing."""
    return ProcessingStatsRecord(
        id=stats_id or str(uuid.uuid4()),
        file_id=file_id,
        processed_at=processed_at or datetime.now(timezone.utc).isoformat(),
        policy_name=policy_name,
        size_before=1000000,
        size_after=900000,
        size_change=100000,
        audio_tracks_before=3,
        subtitle_tracks_before=5,
        attachments_before=2,
        audio_tracks_after=2,
        subtitle_tracks_after=3,
        attachments_after=1,
        audio_tracks_removed=1,
        subtitle_tracks_removed=2,
        attachments_removed=1,
        duration_seconds=15.5,
        phases_completed=2,
        phases_total=3,
        total_changes=5,
        video_source_codec="h264",
        video_target_codec="hevc",
        video_transcode_skipped=False,
        video_skip_reason=None,
        audio_tracks_transcoded=1,
        audio_tracks_preserved=2,
        hash_before="abc123",
        hash_after="def456",
        success=True,
        error_message=None,
    )


def _ensure_file_exists(conn: sqlite3.Connection, file_id: int) -> None:
    """Ensure a file record exists with the given ID."""
    cursor = conn.execute("SELECT id FROM files WHERE id = ?", (file_id,))
    if cursor.fetchone() is None:
        conn.execute(
            """
            INSERT INTO files (
                id, path, filename, directory, extension, size_bytes,
                modified_at, scanned_at, scan_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                f"/test/video_{file_id}.mkv",
                f"video_{file_id}.mkv",
                "/test",
                ".mkv",
                1000000,
                "2024-01-01T00:00:00",
                "2024-01-01T00:00:00",
                "complete",
            ),
        )


def _insert_test_stats(
    conn: sqlite3.Connection,
    stats_id: str,
    policy_name: str,
    processed_at: str,
    file_id: int = 1,
) -> None:
    """Insert a minimal test processing_stats record directly."""
    _ensure_file_exists(conn, file_id)
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


class TestInsertProcessingStats:
    """Tests for insert_processing_stats."""

    def test_insert_creates_record(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Should insert a new processing stats record with all fields."""
        record = _create_stats_record(file_id)

        result_id = insert_processing_stats(conn, record)
        conn.commit()

        assert result_id == record.id

        # Verify record was inserted
        cursor = conn.execute(
            "SELECT * FROM processing_stats WHERE id = ?", (record.id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["file_id"] == file_id
        assert row["policy_name"] == "test-policy.yaml"
        assert row["size_before"] == 1000000
        assert row["success"] == 1

    def test_insert_rejects_invalid_file_id(self, conn: sqlite3.Connection) -> None:
        """Should fail to insert stats with non-existent file_id (FK constraint)."""
        record = _create_stats_record(file_id=99999)  # Non-existent file

        with pytest.raises(sqlite3.IntegrityError):
            insert_processing_stats(conn, record)


class TestInsertActionResult:
    """Tests for insert_action_result."""

    def test_insert_links_to_stats(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Should insert action result linked to stats record."""
        stats_record = _create_stats_record(file_id)
        insert_processing_stats(conn, stats_record)

        action_record = ActionResultRecord(
            id=None,
            stats_id=stats_record.id,
            action_type="remove_track",
            track_type="audio",
            track_index=2,
            before_state='{"codec": "aac"}',
            after_state=None,
            success=True,
            duration_ms=150,
            rule_reference="audio_filter.languages",
            message="Removed Japanese audio track",
        )

        result_id = insert_action_result(conn, action_record)
        conn.commit()

        assert result_id is not None

        # Verify record
        cursor = conn.execute("SELECT * FROM action_results WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["stats_id"] == stats_record.id
        assert row["action_type"] == "remove_track"

    def test_insert_rejects_invalid_stats_id(self, conn: sqlite3.Connection) -> None:
        """Should fail to insert action with non-existent stats_id (FK constraint)."""
        action_record = ActionResultRecord(
            id=None,
            stats_id="nonexistent-uuid",
            action_type="remove_track",
            track_type="audio",
            track_index=1,
            before_state=None,
            after_state=None,
            success=True,
            duration_ms=100,
            rule_reference=None,
            message=None,
        )

        with pytest.raises(sqlite3.IntegrityError):
            insert_action_result(conn, action_record)


class TestInsertPerformanceMetric:
    """Tests for insert_performance_metric."""

    def test_insert_links_to_stats(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Should insert performance metric linked to stats record."""
        stats_record = _create_stats_record(file_id)
        insert_processing_stats(conn, stats_record)

        metric_record = PerformanceMetricsRecord(
            id=None,
            stats_id=stats_record.id,
            phase_name="transcode",
            wall_time_seconds=45.5,
            bytes_read=1000000,
            bytes_written=900000,
            encoding_fps=60.0,
            encoding_bitrate=5000000,
        )

        result_id = insert_performance_metric(conn, metric_record)
        conn.commit()

        assert result_id is not None

        cursor = conn.execute(
            "SELECT * FROM performance_metrics WHERE id = ?", (result_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["stats_id"] == stats_record.id
        assert row["phase_name"] == "transcode"


class TestGetProcessingStatsById:
    """Tests for get_processing_stats_by_id."""

    def test_returns_record_when_exists(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Should return the stats record when it exists."""
        record = _create_stats_record(file_id)
        insert_processing_stats(conn, record)
        conn.commit()

        result = get_processing_stats_by_id(conn, record.id)

        assert result is not None
        assert result.id == record.id
        assert result.file_id == file_id
        assert result.policy_name == "test-policy.yaml"

    def test_returns_none_for_missing(self, conn: sqlite3.Connection) -> None:
        """Should return None when stats_id doesn't exist."""
        result = get_processing_stats_by_id(conn, "nonexistent-uuid")
        assert result is None


class TestGetProcessingStatsForFile:
    """Tests for get_processing_stats_for_file."""

    def test_returns_ordered_list(self, conn: sqlite3.Connection, file_id: int) -> None:
        """Should return records ordered by processed_at DESC."""
        now = datetime.now(timezone.utc)
        old = (now - timedelta(hours=2)).isoformat()
        recent = (now - timedelta(hours=1)).isoformat()
        newest = now.isoformat()

        # Insert in random order
        record1 = _create_stats_record(file_id, processed_at=recent)
        record2 = _create_stats_record(file_id, processed_at=old)
        record3 = _create_stats_record(file_id, processed_at=newest)
        insert_processing_stats(conn, record1)
        insert_processing_stats(conn, record2)
        insert_processing_stats(conn, record3)
        conn.commit()

        results = get_processing_stats_for_file(conn, file_id)

        assert len(results) == 3
        # Should be newest first
        assert results[0].processed_at == newest
        assert results[1].processed_at == recent
        assert results[2].processed_at == old

    def test_respects_limit(self, conn: sqlite3.Connection, file_id: int) -> None:
        """Should respect the limit parameter."""
        for _ in range(5):
            insert_processing_stats(conn, _create_stats_record(file_id))
        conn.commit()

        results = get_processing_stats_for_file(conn, file_id, limit=2)

        assert len(results) == 2

    def test_rejects_invalid_limit(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Should raise ValueError for invalid limit values."""
        with pytest.raises(ValueError, match="Invalid limit value"):
            get_processing_stats_for_file(conn, file_id, limit=0)

        with pytest.raises(ValueError, match="Invalid limit value"):
            get_processing_stats_for_file(conn, file_id, limit=-1)

        with pytest.raises(ValueError, match="Invalid limit value"):
            get_processing_stats_for_file(conn, file_id, limit=10001)

    def test_accepts_valid_limit(self, conn: sqlite3.Connection, file_id: int) -> None:
        """Should accept valid limit boundary values."""
        insert_processing_stats(conn, _create_stats_record(file_id))
        conn.commit()

        # Boundary values should work
        results = get_processing_stats_for_file(conn, file_id, limit=1)
        assert len(results) == 1

        results = get_processing_stats_for_file(conn, file_id, limit=10000)
        assert len(results) == 1


class TestGetActionResultsForStats:
    """Tests for get_action_results_for_stats."""

    def test_returns_linked_actions(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Should return all actions linked to stats record."""
        stats_record = _create_stats_record(file_id)
        insert_processing_stats(conn, stats_record)

        # Insert multiple actions
        for i in range(3):
            action = ActionResultRecord(
                id=None,
                stats_id=stats_record.id,
                action_type=f"action_{i}",
                track_type="audio",
                track_index=i,
                before_state=None,
                after_state=None,
                success=True,
                duration_ms=100,
                rule_reference=None,
                message=None,
            )
            insert_action_result(conn, action)
        conn.commit()

        results = get_action_results_for_stats(conn, stats_record.id)

        assert len(results) == 3


class TestGetPerformanceMetricsForStats:
    """Tests for get_performance_metrics_for_stats."""

    def test_returns_linked_metrics(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Should return all metrics linked to stats record."""
        stats_record = _create_stats_record(file_id)
        insert_processing_stats(conn, stats_record)

        # Insert multiple metrics
        for phase in ["analyze", "transcode", "mux"]:
            metric = PerformanceMetricsRecord(
                id=None,
                stats_id=stats_record.id,
                phase_name=phase,
                wall_time_seconds=10.0,
                bytes_read=None,
                bytes_written=None,
                encoding_fps=None,
                encoding_bitrate=None,
            )
            insert_performance_metric(conn, metric)
        conn.commit()

        results = get_performance_metrics_for_stats(conn, stats_record.id)

        assert len(results) == 3


class TestCascadeDelete:
    """Tests for CASCADE delete behavior."""

    def test_delete_stats_cascades_to_actions(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Deleting stats should cascade delete to actions."""
        stats_record = _create_stats_record(file_id)
        insert_processing_stats(conn, stats_record)

        action = ActionResultRecord(
            id=None,
            stats_id=stats_record.id,
            action_type="remove_track",
            track_type="audio",
            track_index=1,
            before_state=None,
            after_state=None,
            success=True,
            duration_ms=100,
            rule_reference=None,
            message=None,
        )
        insert_action_result(conn, action)
        conn.commit()

        # Verify action exists
        cursor = conn.execute("SELECT COUNT(*) FROM action_results")
        assert cursor.fetchone()[0] == 1

        # Delete stats
        conn.execute("DELETE FROM processing_stats WHERE id = ?", (stats_record.id,))
        conn.commit()

        # Verify action was cascaded
        cursor = conn.execute("SELECT COUNT(*) FROM action_results")
        assert cursor.fetchone()[0] == 0

    def test_delete_stats_cascades_to_metrics(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Deleting stats should cascade delete to metrics."""
        stats_record = _create_stats_record(file_id)
        insert_processing_stats(conn, stats_record)

        metric = PerformanceMetricsRecord(
            id=None,
            stats_id=stats_record.id,
            phase_name="transcode",
            wall_time_seconds=10.0,
            bytes_read=None,
            bytes_written=None,
            encoding_fps=None,
            encoding_bitrate=None,
        )
        insert_performance_metric(conn, metric)
        conn.commit()

        # Verify metric exists
        cursor = conn.execute("SELECT COUNT(*) FROM performance_metrics")
        assert cursor.fetchone()[0] == 1

        # Delete stats
        conn.execute("DELETE FROM processing_stats WHERE id = ?", (stats_record.id,))
        conn.commit()

        # Verify metric was cascaded
        cursor = conn.execute("SELECT COUNT(*) FROM performance_metrics")
        assert cursor.fetchone()[0] == 0


# ==========================================================================
# Stats Trends Tests (Issue #264)
# ==========================================================================


class TestGetStatsTrends:
    """Tests for get_stats_trends function."""

    def test_empty_database_returns_empty_list(self, conn: sqlite3.Connection) -> None:
        """Empty database should return empty trends list."""
        from vpo.db.views import get_stats_trends

        trends = get_stats_trends(conn)
        assert trends == []

    def test_trends_grouped_by_day(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Trends should be grouped by day correctly."""
        from vpo.db.views import get_stats_trends

        # Insert stats for different days
        day1 = "2024-01-15T10:00:00Z"
        day2 = "2024-01-16T10:00:00Z"

        for i, date in enumerate([day1, day1, day2]):
            record = ProcessingStatsRecord(
                id=str(uuid.uuid4()),
                file_id=file_id,
                processed_at=date,
                policy_name="test-policy",
                size_before=1000000,
                size_after=500000,
                size_change=500000,
                audio_tracks_before=2,
                subtitle_tracks_before=1,
                attachments_before=0,
                audio_tracks_after=1,
                subtitle_tracks_after=1,
                attachments_after=0,
                audio_tracks_removed=1,
                subtitle_tracks_removed=0,
                attachments_removed=0,
                duration_seconds=10.0,
                phases_completed=1,
                phases_total=1,
                total_changes=1,
                video_source_codec=None,
                video_target_codec=None,
                video_transcode_skipped=False,
                video_skip_reason=None,
                audio_tracks_transcoded=0,
                audio_tracks_preserved=0,
                hash_before=None,
                hash_after=None,
                success=True,
                error_message=None,
            )
            insert_processing_stats(conn, record)
        conn.commit()

        trends = get_stats_trends(conn, group_by="day")

        assert len(trends) == 2
        # Day 1 should have 2 files
        assert trends[0].date == "2024-01-15"
        assert trends[0].files_processed == 2
        # Day 2 should have 1 file
        assert trends[1].date == "2024-01-16"
        assert trends[1].files_processed == 1

    def test_trends_with_since_filter(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Trends should respect since filter."""
        from vpo.db.views import get_stats_trends

        # Insert old and new stats
        old_date = "2024-01-01T10:00:00Z"
        new_date = "2024-01-15T10:00:00Z"

        for date in [old_date, new_date]:
            record = ProcessingStatsRecord(
                id=str(uuid.uuid4()),
                file_id=file_id,
                processed_at=date,
                policy_name="test-policy",
                size_before=1000000,
                size_after=500000,
                size_change=500000,
                audio_tracks_before=2,
                subtitle_tracks_before=1,
                attachments_before=0,
                audio_tracks_after=1,
                subtitle_tracks_after=1,
                attachments_after=0,
                audio_tracks_removed=1,
                subtitle_tracks_removed=0,
                attachments_removed=0,
                duration_seconds=10.0,
                phases_completed=1,
                phases_total=1,
                total_changes=1,
                video_source_codec=None,
                video_target_codec=None,
                video_transcode_skipped=False,
                video_skip_reason=None,
                audio_tracks_transcoded=0,
                audio_tracks_preserved=0,
                hash_before=None,
                hash_after=None,
                success=True,
                error_message=None,
            )
            insert_processing_stats(conn, record)
        conn.commit()

        # Filter since 2024-01-10
        trends = get_stats_trends(conn, since="2024-01-10T00:00:00Z")

        assert len(trends) == 1
        assert trends[0].date == "2024-01-15"

    def test_trends_success_fail_counts(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Trends should track success and fail counts."""
        from vpo.db.views import get_stats_trends

        date = "2024-01-15T10:00:00Z"

        # Insert 2 successful and 1 failed
        for success in [True, True, False]:
            record = ProcessingStatsRecord(
                id=str(uuid.uuid4()),
                file_id=file_id,
                processed_at=date,
                policy_name="test-policy",
                size_before=1000000,
                size_after=500000,
                size_change=500000,
                audio_tracks_before=2,
                subtitle_tracks_before=1,
                attachments_before=0,
                audio_tracks_after=1,
                subtitle_tracks_after=1,
                attachments_after=0,
                audio_tracks_removed=1,
                subtitle_tracks_removed=0,
                attachments_removed=0,
                duration_seconds=10.0,
                phases_completed=1,
                phases_total=1,
                total_changes=1,
                video_source_codec=None,
                video_target_codec=None,
                video_transcode_skipped=False,
                video_skip_reason=None,
                audio_tracks_transcoded=0,
                audio_tracks_preserved=0,
                hash_before=None,
                hash_after=None,
                success=success,
                error_message=None if success else "Test error",
            )
            insert_processing_stats(conn, record)
        conn.commit()

        trends = get_stats_trends(conn)

        assert len(trends) == 1
        assert trends[0].success_count == 2
        assert trends[0].fail_count == 1


class TestEncoderTypeTracking:
    """Tests for encoder type tracking (Issue #264)."""

    def test_encoder_type_stored_correctly(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Encoder type should be stored and retrieved correctly."""
        record = ProcessingStatsRecord(
            id=str(uuid.uuid4()),
            file_id=file_id,
            processed_at="2024-01-15T10:00:00Z",
            policy_name="test-policy",
            size_before=1000000,
            size_after=500000,
            size_change=500000,
            audio_tracks_before=0,
            subtitle_tracks_before=0,
            attachments_before=0,
            audio_tracks_after=0,
            subtitle_tracks_after=0,
            attachments_after=0,
            audio_tracks_removed=0,
            subtitle_tracks_removed=0,
            attachments_removed=0,
            duration_seconds=10.0,
            phases_completed=1,
            phases_total=1,
            total_changes=1,
            video_source_codec="h264",
            video_target_codec="hevc",
            video_transcode_skipped=False,
            video_skip_reason=None,
            audio_tracks_transcoded=0,
            audio_tracks_preserved=0,
            hash_before=None,
            hash_after=None,
            success=True,
            error_message=None,
            encoder_type="hardware",
        )

        insert_processing_stats(conn, record)
        conn.commit()

        retrieved = get_processing_stats_by_id(conn, record.id)
        assert retrieved is not None
        assert retrieved.encoder_type == "hardware"

    def test_encoder_type_counts_in_summary(
        self, conn: sqlite3.Connection, file_id: int
    ) -> None:
        """Summary should include hardware/software encoder counts."""
        from vpo.db.views import get_stats_summary

        # Insert stats with different encoder types
        encoder_types = ["hardware", "hardware", "software", None]

        for encoder in encoder_types:
            record = ProcessingStatsRecord(
                id=str(uuid.uuid4()),
                file_id=file_id,
                processed_at="2024-01-15T10:00:00Z",
                policy_name="test-policy",
                size_before=1000000,
                size_after=500000,
                size_change=500000,
                audio_tracks_before=0,
                subtitle_tracks_before=0,
                attachments_before=0,
                audio_tracks_after=0,
                subtitle_tracks_after=0,
                attachments_after=0,
                audio_tracks_removed=0,
                subtitle_tracks_removed=0,
                attachments_removed=0,
                duration_seconds=10.0,
                phases_completed=1,
                phases_total=1,
                total_changes=1,
                video_source_codec=None,
                video_target_codec=None,
                video_transcode_skipped=False,
                video_skip_reason=None,
                audio_tracks_transcoded=0,
                audio_tracks_preserved=0,
                hash_before=None,
                hash_after=None,
                success=True,
                error_message=None,
                encoder_type=encoder,
            )
            insert_processing_stats(conn, record)
        conn.commit()

        summary = get_stats_summary(conn)

        assert summary.hardware_encodes == 2
        assert summary.software_encodes == 1
