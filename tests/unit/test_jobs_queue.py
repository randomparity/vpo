"""Unit tests for jobs queue operations."""

from datetime import datetime, timedelta, timezone

from vpo.db import (
    JobStatus,
    get_job,
)
from vpo.jobs.queue import (
    DEFAULT_HEARTBEAT_TIMEOUT,
    cancel_job,
    claim_next_job,
    get_queue_stats,
    recover_stale_jobs,
    release_job,
    requeue_job,
    update_heartbeat,
)


class TestClaimNextJob:
    """Tests for claim_next_job function."""

    def test_claims_queued_job(self, db_conn, insert_test_job):
        """Should claim a queued job."""
        job = insert_test_job()
        db_conn.commit()

        claimed = claim_next_job(db_conn)

        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.status == JobStatus.RUNNING
        assert claimed.worker_pid is not None

    def test_returns_none_when_empty(self, db_conn):
        """Should return None when queue is empty."""
        claimed = claim_next_job(db_conn)
        assert claimed is None

    def test_priority_ordering(self, db_conn, insert_test_job):
        """Lower priority number is claimed first."""
        high_priority = insert_test_job(priority=10)
        insert_test_job(priority=100)
        db_conn.commit()

        claimed = claim_next_job(db_conn)

        assert claimed.id == high_priority.id

    def test_fifo_for_same_priority(self, db_conn, insert_test_job):
        """Older jobs claimed first for same priority."""
        old_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        new_time = datetime.now(timezone.utc).isoformat()

        insert_test_job(created_at=new_time)
        old_job = insert_test_job(created_at=old_time)
        db_conn.commit()

        claimed = claim_next_job(db_conn)

        assert claimed.id == old_job.id

    def test_skips_running_jobs(self, db_conn, insert_test_job):
        """Doesn't claim already running jobs."""
        insert_test_job(status=JobStatus.RUNNING)
        queued = insert_test_job()
        db_conn.commit()

        claimed = claim_next_job(db_conn)

        assert claimed.id == queued.id

    def test_skips_completed_jobs(self, db_conn, insert_test_job):
        """Doesn't claim completed jobs."""
        insert_test_job(status=JobStatus.COMPLETED)
        db_conn.commit()

        claimed = claim_next_job(db_conn)

        assert claimed is None


class TestReleaseJob:
    """Tests for release_job function."""

    def test_releases_with_completed_status(self, db_conn, insert_test_job):
        """Successfully releases job as completed."""
        job = insert_test_job(status=JobStatus.RUNNING)

        result = release_job(db_conn, job.id, JobStatus.COMPLETED)

        assert result is True
        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.COMPLETED
        assert updated.completed_at is not None

    def test_releases_with_error(self, db_conn, insert_test_job):
        """Releases job with error message."""
        job = insert_test_job(status=JobStatus.RUNNING)

        release_job(db_conn, job.id, JobStatus.FAILED, error_message="Test error")

        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.FAILED
        assert updated.error_message == "Test error"

    def test_records_output_path(self, db_conn, insert_test_job):
        """Records output path on success."""
        job = insert_test_job(status=JobStatus.RUNNING)

        release_job(
            db_conn, job.id, JobStatus.COMPLETED, output_path="/output/file.mkv"
        )

        updated = get_job(db_conn, job.id)
        assert updated.output_path == "/output/file.mkv"

    def test_returns_false_for_missing_job(self, db_conn):
        """Returns False when job not found."""
        result = release_job(db_conn, "nonexistent-id", JobStatus.COMPLETED)
        assert result is False

    def test_records_summary_json(self, db_conn, insert_test_job):
        """Records summary_json on completion."""
        job = insert_test_job(status=JobStatus.RUNNING)

        summary = '{"phases_completed": 3, "total_changes": 5}'
        release_job(
            db_conn,
            job.id,
            JobStatus.COMPLETED,
            summary_json=summary,
        )

        updated = get_job(db_conn, job.id)
        assert updated.summary_json == summary

    def test_set_progress_100_updates_progress(self, db_conn, insert_test_job):
        """set_progress_100=True sets progress_percent to 100.0."""
        job = insert_test_job(status=JobStatus.RUNNING)

        # Set partial progress first
        db_conn.execute(
            "UPDATE jobs SET progress_percent = 50.0 WHERE id = ?",
            (job.id,),
        )
        db_conn.commit()

        release_job(db_conn, job.id, JobStatus.COMPLETED, set_progress_100=True)

        updated = get_job(db_conn, job.id)
        assert updated.progress_percent == 100.0

    def test_set_progress_100_false_preserves_progress(self, db_conn, insert_test_job):
        """set_progress_100=False preserves existing progress_percent."""
        job = insert_test_job(status=JobStatus.RUNNING)

        # Set partial progress
        db_conn.execute(
            "UPDATE jobs SET progress_percent = 75.0 WHERE id = ?",
            (job.id,),
        )
        db_conn.commit()

        release_job(db_conn, job.id, JobStatus.FAILED, set_progress_100=False)

        updated = get_job(db_conn, job.id)
        assert updated.progress_percent == 75.0


class TestUpdateHeartbeat:
    """Tests for update_heartbeat function."""

    def test_updates_heartbeat(self, db_conn, insert_test_job):
        """Updates heartbeat timestamp."""
        job = insert_test_job(status=JobStatus.RUNNING)

        result = update_heartbeat(db_conn, job.id, worker_pid=12345)

        assert result is True
        updated = get_job(db_conn, job.id)
        assert updated.worker_pid == 12345
        assert updated.worker_heartbeat is not None

    def test_only_updates_running_jobs(self, db_conn, insert_test_job):
        """Doesn't update heartbeat for non-running jobs."""
        job = insert_test_job(status=JobStatus.QUEUED)

        result = update_heartbeat(db_conn, job.id)

        assert result is False


class TestRecoverStaleJobs:
    """Tests for recover_stale_jobs function."""

    def test_recovers_stale_jobs(self, db_conn, insert_test_job):
        """Recovers jobs with old heartbeat."""
        # Create a job with old heartbeat
        job = insert_test_job(status=JobStatus.RUNNING)

        # Set old heartbeat directly
        old_heartbeat = (
            datetime.now(timezone.utc)
            - timedelta(seconds=DEFAULT_HEARTBEAT_TIMEOUT + 60)
        ).isoformat()
        db_conn.execute(
            "UPDATE jobs SET worker_heartbeat = ? WHERE id = ?",
            (old_heartbeat, job.id),
        )
        db_conn.commit()

        count = recover_stale_jobs(db_conn)

        assert count == 1
        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.QUEUED
        assert updated.worker_pid is None

    def test_does_not_recover_fresh_jobs(self, db_conn, insert_test_job):
        """Doesn't recover jobs with recent heartbeat."""
        job = insert_test_job(status=JobStatus.RUNNING)

        # Set recent heartbeat
        recent_heartbeat = datetime.now(timezone.utc).isoformat()
        db_conn.execute(
            "UPDATE jobs SET worker_heartbeat = ? WHERE id = ?",
            (recent_heartbeat, job.id),
        )
        db_conn.commit()

        count = recover_stale_jobs(db_conn)

        assert count == 0
        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.RUNNING

    def test_custom_timeout(self, db_conn, insert_test_job):
        """Respects custom timeout value."""
        job = insert_test_job(status=JobStatus.RUNNING)

        # Set heartbeat 10 seconds ago
        old_heartbeat = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        db_conn.execute(
            "UPDATE jobs SET worker_heartbeat = ? WHERE id = ?",
            (old_heartbeat, job.id),
        )
        db_conn.commit()

        # Default timeout (300s) should not recover
        count = recover_stale_jobs(db_conn, timeout_seconds=300)
        assert count == 0

        # Short timeout (5s) should recover
        count = recover_stale_jobs(db_conn, timeout_seconds=5)
        assert count == 1


class TestGetQueueStats:
    """Tests for get_queue_stats function."""

    def test_returns_all_statuses(self, db_conn):
        """Returns counts for all status types."""
        stats = get_queue_stats(db_conn)

        assert "queued" in stats
        assert "running" in stats
        assert "completed" in stats
        assert "failed" in stats
        assert "cancelled" in stats
        assert "total" in stats

    def test_counts_correctly(self, db_conn, insert_test_job):
        """Counts jobs correctly by status."""
        insert_test_job(status=JobStatus.QUEUED)
        insert_test_job(status=JobStatus.QUEUED)
        insert_test_job(status=JobStatus.RUNNING)
        insert_test_job(status=JobStatus.COMPLETED)

        stats = get_queue_stats(db_conn)

        assert stats["queued"] == 2
        assert stats["running"] == 1
        assert stats["completed"] == 1
        assert stats["failed"] == 0
        assert stats["total"] == 4


class TestCancelJob:
    """Tests for cancel_job function."""

    def test_cancels_queued_job(self, db_conn, insert_test_job):
        """Cancels a queued job."""
        job = insert_test_job(status=JobStatus.QUEUED)

        result = cancel_job(db_conn, job.id)

        assert result is True
        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.CANCELLED
        assert updated.completed_at is not None

    def test_cannot_cancel_running_job(self, db_conn, insert_test_job):
        """Cannot cancel a running job."""
        job = insert_test_job(status=JobStatus.RUNNING)

        result = cancel_job(db_conn, job.id)

        assert result is False
        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.RUNNING

    def test_returns_false_for_missing_job(self, db_conn):
        """Returns False when job not found."""
        result = cancel_job(db_conn, "nonexistent-id")
        assert result is False


class TestRequeueJob:
    """Tests for requeue_job function."""

    def test_requeues_failed_job(self, db_conn, insert_test_job):
        """Requeues a failed job."""
        job = insert_test_job(status=JobStatus.FAILED)

        result = requeue_job(db_conn, job.id)

        assert result is True
        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.QUEUED
        assert updated.error_message is None
        assert updated.progress_percent == 0.0

    def test_requeues_cancelled_job(self, db_conn, insert_test_job):
        """Requeues a cancelled job."""
        job = insert_test_job(status=JobStatus.CANCELLED)

        result = requeue_job(db_conn, job.id)

        assert result is True
        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.QUEUED

    def test_cannot_requeue_completed_job(self, db_conn, insert_test_job):
        """Cannot requeue a completed job."""
        job = insert_test_job(status=JobStatus.COMPLETED)

        result = requeue_job(db_conn, job.id)

        assert result is False
        updated = get_job(db_conn, job.id)
        assert updated.status == JobStatus.COMPLETED

    def test_cannot_requeue_running_job(self, db_conn, insert_test_job):
        """Cannot requeue a running job."""
        job = insert_test_job(status=JobStatus.RUNNING)

        result = requeue_job(db_conn, job.id)

        assert result is False


class TestConcurrency:
    """Tests for concurrent queue operations."""

    def test_multiple_claims_return_different_jobs(self, db_conn, insert_test_job):
        """Multiple claims should return different jobs."""
        insert_test_job()
        insert_test_job()
        db_conn.commit()

        claimed1 = claim_next_job(db_conn)
        claimed2 = claim_next_job(db_conn)

        assert claimed1 is not None
        assert claimed2 is not None
        assert claimed1.id != claimed2.id

    def test_claims_exhaust_queue(self, db_conn, insert_test_job):
        """Claims should exhaust the queue."""
        insert_test_job()
        db_conn.commit()

        claimed1 = claim_next_job(db_conn)
        claimed2 = claim_next_job(db_conn)

        assert claimed1 is not None
        assert claimed2 is None
