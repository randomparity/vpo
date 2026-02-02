"""Tests for job maintenance operations."""

from datetime import datetime, timedelta, timezone

import pytest

from vpo.db.queries import get_all_jobs, insert_job
from vpo.db.types import JobStatus, JobType
from vpo.jobs.maintenance import cleanup_orphaned_cli_jobs, purge_old_jobs


@pytest.fixture
def create_test_job(db_conn, make_job):
    """Create and insert a test job with specific status and age in days."""

    def _create(status, days_ago):
        created_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        job = make_job(
            id=f"test-job-{days_ago}-{status.value}",
            status=status,
            created_at=created_at,
            started_at=created_at,
            policy_name=None,
        )
        insert_job(db_conn, job)
        return job

    return _create


class TestPurgeOldJobs:
    """Tests for purge_old_jobs function."""

    def test_purge_deletes_old_completed_jobs(self, db_conn, create_test_job):
        """Old completed jobs are deleted."""
        # Create an old completed job (40 days old)
        create_test_job(JobStatus.COMPLETED, days_ago=40)

        # Purge with 30 day retention
        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 1
        assert len(get_all_jobs(db_conn)) == 0

    def test_purge_deletes_old_failed_jobs(self, db_conn, create_test_job):
        """Old failed jobs are deleted."""
        create_test_job(JobStatus.FAILED, days_ago=40)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 1
        assert len(get_all_jobs(db_conn)) == 0

    def test_purge_deletes_old_cancelled_jobs(self, db_conn, create_test_job):
        """Old cancelled jobs are deleted."""
        create_test_job(JobStatus.CANCELLED, days_ago=40)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 1
        assert len(get_all_jobs(db_conn)) == 0

    def test_purge_preserves_recent_jobs(self, db_conn, create_test_job):
        """Recent jobs within retention period are preserved."""
        # Create a recent completed job (10 days old)
        create_test_job(JobStatus.COMPLETED, days_ago=10)

        # Purge with 30 day retention
        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 0
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_preserves_running_jobs(self, db_conn, create_test_job):
        """Running jobs are never deleted regardless of age."""
        create_test_job(JobStatus.RUNNING, days_ago=100)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 0
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_preserves_queued_jobs(self, db_conn, create_test_job):
        """Queued jobs are never deleted regardless of age."""
        create_test_job(JobStatus.QUEUED, days_ago=100)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 0
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_auto_purge_disabled(self, db_conn, create_test_job):
        """Returns 0 when auto_purge is False."""
        create_test_job(JobStatus.COMPLETED, days_ago=100)

        count = purge_old_jobs(db_conn, retention_days=30, auto_purge=False)

        assert count == 0
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_multiple_jobs(self, db_conn, create_test_job):
        """Multiple old jobs are deleted in one call."""
        # Create 3 old jobs
        create_test_job(JobStatus.COMPLETED, days_ago=40)
        create_test_job(JobStatus.FAILED, days_ago=50)
        create_test_job(JobStatus.CANCELLED, days_ago=60)
        # And 1 recent job
        create_test_job(JobStatus.COMPLETED, days_ago=5)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 3
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_respects_retention_days(self, db_conn, create_test_job):
        """Different retention_days values are respected."""
        # Create jobs at different ages
        create_test_job(JobStatus.COMPLETED, days_ago=5)
        create_test_job(JobStatus.COMPLETED, days_ago=15)
        create_test_job(JobStatus.COMPLETED, days_ago=25)

        # Purge with 20 day retention
        count = purge_old_jobs(db_conn, retention_days=20)

        assert count == 1  # Only the 25-day-old job
        assert len(get_all_jobs(db_conn)) == 2


@pytest.fixture
def create_cli_job(db_conn, make_job):
    """Create and insert a CLI job with specific status and age in hours."""

    def _create(status, hours_ago):
        created_at = (
            datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        ).isoformat()
        job = make_job(
            id=f"cli-job-{hours_ago}h-{status.value}",
            job_type=JobType.PROCESS,
            status=status,
            created_at=created_at,
            started_at=created_at,
            policy_name="test.yaml",
            policy_json=None,
            origin="cli",
            batch_id="test-batch-123",
        )
        insert_job(db_conn, job)
        return job

    return _create


@pytest.fixture
def create_daemon_job(db_conn, make_job):
    """Create and insert a daemon job with specific status and age in hours."""

    def _create(status, hours_ago):
        created_at = (
            datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        ).isoformat()
        job = make_job(
            id=f"daemon-job-{hours_ago}h-{status.value}",
            job_type=JobType.PROCESS,
            status=status,
            created_at=created_at,
            started_at=created_at,
            policy_name="test.yaml",
            policy_json=None,
            origin="daemon",
            batch_id=None,
        )
        insert_job(db_conn, job)
        return job

    return _create


class TestCleanupOrphanedCliJobs:
    """Tests for cleanup_orphaned_cli_jobs function."""

    def test_cleans_up_old_running_cli_jobs(self, db_conn, create_cli_job):
        """Old running CLI jobs are marked as failed."""
        # Create a CLI job that's been running for 48 hours
        job = create_cli_job(JobStatus.RUNNING, hours_ago=48)

        # Cleanup with 24 hour threshold
        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 1
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value

    def test_preserves_recent_running_cli_jobs(self, db_conn, create_cli_job):
        """Recent running CLI jobs are preserved."""
        # Create a CLI job that's been running for 12 hours
        job = create_cli_job(JobStatus.RUNNING, hours_ago=12)

        # Cleanup with 24 hour threshold
        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 0
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.RUNNING.value

    def test_ignores_daemon_jobs(self, db_conn, create_daemon_job):
        """Daemon jobs are not affected even if old and running."""
        # Create an old running daemon job
        job = create_daemon_job(JobStatus.RUNNING, hours_ago=100)

        # Cleanup should not affect daemon jobs
        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 0
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.RUNNING.value

    def test_ignores_completed_cli_jobs(self, db_conn, create_cli_job):
        """Completed CLI jobs are not affected."""
        job = create_cli_job(JobStatus.COMPLETED, hours_ago=100)

        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 0
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.COMPLETED.value

    def test_ignores_failed_cli_jobs(self, db_conn, create_cli_job):
        """Already failed CLI jobs are not affected."""
        job = create_cli_job(JobStatus.FAILED, hours_ago=100)

        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 0
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value

    def test_sets_error_message(self, db_conn, create_cli_job):
        """Orphaned jobs get an error message explaining the situation."""
        job = create_cli_job(JobStatus.RUNNING, hours_ago=48)

        cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert "orphaned" in row["error_message"].lower()

    def test_sets_completed_at(self, db_conn, create_cli_job):
        """Orphaned jobs get a completed_at timestamp."""
        job = create_cli_job(JobStatus.RUNNING, hours_ago=48)

        cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        cursor = db_conn.execute(
            "SELECT completed_at FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["completed_at"] is not None

    def test_rejects_invalid_threshold(self, db_conn):
        """Raises ValueError for threshold less than 1 hour."""
        with pytest.raises(
            ValueError, match="stale_threshold_hours must be at least 1"
        ):
            cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=0)

    def test_cleans_up_multiple_orphaned_jobs(self, db_conn, create_cli_job):
        """Multiple orphaned jobs are cleaned up in one call."""
        # Create 3 orphaned CLI jobs
        create_cli_job(JobStatus.RUNNING, hours_ago=30)
        create_cli_job(JobStatus.RUNNING, hours_ago=40)
        create_cli_job(JobStatus.RUNNING, hours_ago=50)
        # And 1 recent one that should be preserved
        create_cli_job(JobStatus.RUNNING, hours_ago=10)

        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 3
        jobs = get_all_jobs(db_conn)
        running_jobs = [j for j in jobs if j.status == JobStatus.RUNNING]
        failed_jobs = [j for j in jobs if j.status == JobStatus.FAILED]
        assert len(running_jobs) == 1
        assert len(failed_jobs) == 3
