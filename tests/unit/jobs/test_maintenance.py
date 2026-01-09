"""Tests for job maintenance operations."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from vpo.db.queries import get_all_jobs, insert_job
from vpo.db.schema import create_schema
from vpo.db.types import Job, JobStatus, JobType
from vpo.jobs.maintenance import purge_old_jobs


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
