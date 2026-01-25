"""Tests for job maintenance operations."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from vpo.db.queries import get_all_jobs, insert_job
from vpo.db.schema import create_schema
from vpo.db.types import Job, JobStatus, JobType
from vpo.jobs.maintenance import cleanup_orphaned_cli_jobs, purge_old_jobs


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


def create_test_job(
    conn: sqlite3.Connection,
    status: JobStatus,
    days_ago: int,
) -> Job:
    """Create a test job with a specific status and age."""
    created_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

    job = Job(
        id=f"test-job-{days_ago}-{status.value}",
        file_id=None,
        file_path="/test/path.mkv",
        job_type=JobType.TRANSCODE,
        status=status,
        priority=100,
        policy_name=None,
        policy_json="{}",
        progress_percent=0.0,
        progress_json=None,
        created_at=created_at,
        started_at=created_at,
    )
    insert_job(conn, job)
    return job


class TestPurgeOldJobs:
    """Tests for purge_old_jobs function."""

    def test_purge_deletes_old_completed_jobs(self, db_conn):
        """Old completed jobs are deleted."""
        # Create an old completed job (40 days old)
        create_test_job(db_conn, JobStatus.COMPLETED, days_ago=40)

        # Purge with 30 day retention
        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 1
        assert len(get_all_jobs(db_conn)) == 0

    def test_purge_deletes_old_failed_jobs(self, db_conn):
        """Old failed jobs are deleted."""
        create_test_job(db_conn, JobStatus.FAILED, days_ago=40)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 1
        assert len(get_all_jobs(db_conn)) == 0

    def test_purge_deletes_old_cancelled_jobs(self, db_conn):
        """Old cancelled jobs are deleted."""
        create_test_job(db_conn, JobStatus.CANCELLED, days_ago=40)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 1
        assert len(get_all_jobs(db_conn)) == 0

    def test_purge_preserves_recent_jobs(self, db_conn):
        """Recent jobs within retention period are preserved."""
        # Create a recent completed job (10 days old)
        create_test_job(db_conn, JobStatus.COMPLETED, days_ago=10)

        # Purge with 30 day retention
        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 0
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_preserves_running_jobs(self, db_conn):
        """Running jobs are never deleted regardless of age."""
        create_test_job(db_conn, JobStatus.RUNNING, days_ago=100)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 0
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_preserves_queued_jobs(self, db_conn):
        """Queued jobs are never deleted regardless of age."""
        create_test_job(db_conn, JobStatus.QUEUED, days_ago=100)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 0
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_auto_purge_disabled(self, db_conn):
        """Returns 0 when auto_purge is False."""
        create_test_job(db_conn, JobStatus.COMPLETED, days_ago=100)

        count = purge_old_jobs(db_conn, retention_days=30, auto_purge=False)

        assert count == 0
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_multiple_jobs(self, db_conn):
        """Multiple old jobs are deleted in one call."""
        # Create 3 old jobs
        create_test_job(db_conn, JobStatus.COMPLETED, days_ago=40)
        create_test_job(db_conn, JobStatus.FAILED, days_ago=50)
        create_test_job(db_conn, JobStatus.CANCELLED, days_ago=60)
        # And 1 recent job
        create_test_job(db_conn, JobStatus.COMPLETED, days_ago=5)

        count = purge_old_jobs(db_conn, retention_days=30)

        assert count == 3
        assert len(get_all_jobs(db_conn)) == 1

    def test_purge_respects_retention_days(self, db_conn):
        """Different retention_days values are respected."""
        # Create jobs at different ages
        create_test_job(db_conn, JobStatus.COMPLETED, days_ago=5)
        create_test_job(db_conn, JobStatus.COMPLETED, days_ago=15)
        create_test_job(db_conn, JobStatus.COMPLETED, days_ago=25)

        # Purge with 20 day retention
        count = purge_old_jobs(db_conn, retention_days=20)

        assert count == 1  # Only the 25-day-old job
        assert len(get_all_jobs(db_conn)) == 2


def create_cli_job(
    conn: sqlite3.Connection,
    status: JobStatus,
    hours_ago: int,
) -> Job:
    """Create a CLI test job with a specific status and age in hours."""
    created_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()

    job = Job(
        id=f"cli-job-{hours_ago}h-{status.value}",
        file_id=None,
        file_path="/test/path.mkv",
        job_type=JobType.PROCESS,
        status=status,
        priority=100,
        policy_name="test.yaml",
        policy_json=None,
        progress_percent=0.0,
        progress_json=None,
        created_at=created_at,
        started_at=created_at,
        origin="cli",
        batch_id="test-batch-123",
    )
    insert_job(conn, job)
    return job


def create_daemon_job(
    conn: sqlite3.Connection,
    status: JobStatus,
    hours_ago: int,
) -> Job:
    """Create a daemon test job with a specific status and age in hours."""
    created_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()

    job = Job(
        id=f"daemon-job-{hours_ago}h-{status.value}",
        file_id=None,
        file_path="/test/path.mkv",
        job_type=JobType.PROCESS,
        status=status,
        priority=100,
        policy_name="test.yaml",
        policy_json=None,
        progress_percent=0.0,
        progress_json=None,
        created_at=created_at,
        started_at=created_at,
        origin="daemon",
        batch_id=None,
    )
    insert_job(conn, job)
    return job


class TestCleanupOrphanedCliJobs:
    """Tests for cleanup_orphaned_cli_jobs function."""

    def test_cleans_up_old_running_cli_jobs(self, db_conn):
        """Old running CLI jobs are marked as failed."""
        # Create a CLI job that's been running for 48 hours
        job = create_cli_job(db_conn, JobStatus.RUNNING, hours_ago=48)

        # Cleanup with 24 hour threshold
        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 1
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value

    def test_preserves_recent_running_cli_jobs(self, db_conn):
        """Recent running CLI jobs are preserved."""
        # Create a CLI job that's been running for 12 hours
        job = create_cli_job(db_conn, JobStatus.RUNNING, hours_ago=12)

        # Cleanup with 24 hour threshold
        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 0
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.RUNNING.value

    def test_ignores_daemon_jobs(self, db_conn):
        """Daemon jobs are not affected even if old and running."""
        # Create an old running daemon job
        job = create_daemon_job(db_conn, JobStatus.RUNNING, hours_ago=100)

        # Cleanup should not affect daemon jobs
        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 0
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.RUNNING.value

    def test_ignores_completed_cli_jobs(self, db_conn):
        """Completed CLI jobs are not affected."""
        job = create_cli_job(db_conn, JobStatus.COMPLETED, hours_ago=100)

        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 0
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.COMPLETED.value

    def test_ignores_failed_cli_jobs(self, db_conn):
        """Already failed CLI jobs are not affected."""
        job = create_cli_job(db_conn, JobStatus.FAILED, hours_ago=100)

        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 0
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value

    def test_sets_error_message(self, db_conn):
        """Orphaned jobs get an error message explaining the situation."""
        job = create_cli_job(db_conn, JobStatus.RUNNING, hours_ago=48)

        cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert "orphaned" in row["error_message"].lower()

    def test_sets_completed_at(self, db_conn):
        """Orphaned jobs get a completed_at timestamp."""
        job = create_cli_job(db_conn, JobStatus.RUNNING, hours_ago=48)

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

    def test_cleans_up_multiple_orphaned_jobs(self, db_conn):
        """Multiple orphaned jobs are cleaned up in one call."""
        # Create 3 orphaned CLI jobs
        create_cli_job(db_conn, JobStatus.RUNNING, hours_ago=30)
        create_cli_job(db_conn, JobStatus.RUNNING, hours_ago=40)
        create_cli_job(db_conn, JobStatus.RUNNING, hours_ago=50)
        # And 1 recent one that should be preserved
        create_cli_job(db_conn, JobStatus.RUNNING, hours_ago=10)

        count = cleanup_orphaned_cli_jobs(db_conn, stale_threshold_hours=24)

        assert count == 3
        jobs = get_all_jobs(db_conn)
        running_jobs = [j for j in jobs if j.status == JobStatus.RUNNING]
        failed_jobs = [j for j in jobs if j.status == JobStatus.FAILED]
        assert len(running_jobs) == 1
        assert len(failed_jobs) == 3
