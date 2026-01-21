"""Tests for job tracking functions."""

import json
import sqlite3

import pytest

from vpo.db import JobStatus, JobType
from vpo.jobs.tracking import (
    cancel_scan_job,
    complete_scan_job,
    create_scan_job,
    fail_scan_job,
)


class TestCreateScanJob:
    """Tests for create_scan_job function."""

    def test_creates_job_with_defaults(self, db_conn: sqlite3.Connection):
        """create_scan_job creates a job with default configuration."""
        job = create_scan_job(db_conn, "/videos")

        assert job.id is not None
        assert job.file_path == "/videos"
        assert job.job_type == JobType.SCAN
        assert job.status == JobStatus.RUNNING
        assert job.file_id is None  # Scan jobs don't target specific files

    def test_creates_job_with_incremental_config(self, db_conn: sqlite3.Connection):
        """create_scan_job stores incremental flag in policy_json."""
        job = create_scan_job(db_conn, "/videos", incremental=True)

        config = json.loads(job.policy_json)
        assert config["incremental"] is True

    def test_creates_job_with_prune_config(self, db_conn: sqlite3.Connection):
        """create_scan_job stores prune flag in policy_json."""
        job = create_scan_job(db_conn, "/videos", prune=True)

        config = json.loads(job.policy_json)
        assert config["prune"] is True

    def test_creates_job_with_verify_hash_config(self, db_conn: sqlite3.Connection):
        """create_scan_job stores verify_hash flag in policy_json."""
        job = create_scan_job(db_conn, "/videos", verify_hash=True)

        config = json.loads(job.policy_json)
        assert config["verify_hash"] is True

    def test_creates_job_with_all_config_options(self, db_conn: sqlite3.Connection):
        """create_scan_job stores all config options."""
        job = create_scan_job(
            db_conn,
            "/videos",
            incremental=False,
            prune=True,
            verify_hash=True,
        )

        config = json.loads(job.policy_json)
        assert config["incremental"] is False
        assert config["prune"] is True
        assert config["verify_hash"] is True

    def test_job_persisted_to_database(self, db_conn: sqlite3.Connection):
        """create_scan_job persists job to database."""
        job = create_scan_job(db_conn, "/videos")

        # Query directly from database
        cursor = db_conn.execute("SELECT * FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()

        assert row is not None
        assert row["file_path"] == "/videos"
        assert row["job_type"] == JobType.SCAN.value
        assert row["status"] == JobStatus.RUNNING.value

    def test_creates_job_with_timestamps(self, db_conn: sqlite3.Connection):
        """create_scan_job sets created_at and started_at timestamps."""
        job = create_scan_job(db_conn, "/videos")

        assert job.created_at is not None
        assert job.started_at is not None

    def test_creates_job_with_zero_progress(self, db_conn: sqlite3.Connection):
        """create_scan_job initializes progress to 0."""
        job = create_scan_job(db_conn, "/videos")

        assert job.progress_percent == 0.0


class TestCompleteScanJob:
    """Tests for complete_scan_job function."""

    def test_marks_job_completed(self, db_conn: sqlite3.Connection):
        """complete_scan_job marks job as COMPLETED."""
        job = create_scan_job(db_conn, "/videos")
        summary = {
            "total_discovered": 10,
            "scanned": 10,
            "skipped": 0,
            "added": 5,
            "removed": 0,
            "errors": 0,
        }

        complete_scan_job(db_conn, job.id, summary)

        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.COMPLETED.value

    def test_stores_summary_json(self, db_conn: sqlite3.Connection):
        """complete_scan_job stores summary as JSON."""
        job = create_scan_job(db_conn, "/videos")
        summary = {
            "total_discovered": 100,
            "scanned": 80,
            "skipped": 15,
            "added": 50,
            "removed": 5,
            "errors": 5,
        }

        complete_scan_job(db_conn, job.id, summary)

        cursor = db_conn.execute(
            "SELECT summary_json FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        stored_summary = json.loads(row["summary_json"])
        assert stored_summary == summary

    def test_sets_completed_at_timestamp(self, db_conn: sqlite3.Connection):
        """complete_scan_job sets completed_at timestamp."""
        job = create_scan_job(db_conn, "/videos")
        summary = {
            "total_discovered": 10,
            "scanned": 10,
            "skipped": 0,
            "added": 5,
            "removed": 0,
            "errors": 0,
        }

        complete_scan_job(db_conn, job.id, summary)

        cursor = db_conn.execute(
            "SELECT completed_at FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["completed_at"] is not None

    def test_sets_progress_to_100(self, db_conn: sqlite3.Connection):
        """complete_scan_job sets progress to 100%."""
        job = create_scan_job(db_conn, "/videos")
        summary = {
            "total_discovered": 10,
            "scanned": 10,
            "skipped": 0,
            "added": 5,
            "removed": 0,
            "errors": 0,
        }

        complete_scan_job(db_conn, job.id, summary)

        cursor = db_conn.execute(
            "SELECT progress_percent FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["progress_percent"] == 100.0

    def test_with_error_message_marks_failed(self, db_conn: sqlite3.Connection):
        """complete_scan_job with error_message marks job as FAILED."""
        job = create_scan_job(db_conn, "/videos")
        summary = {
            "total_discovered": 10,
            "scanned": 5,
            "skipped": 0,
            "added": 0,
            "removed": 0,
            "errors": 5,
        }

        complete_scan_job(db_conn, job.id, summary, error_message="Scan failed")

        cursor = db_conn.execute(
            "SELECT status, error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value
        assert row["error_message"] == "Scan failed"

    def test_raises_for_nonexistent_job(self, db_conn: sqlite3.Connection):
        """complete_scan_job raises ValueError for non-existent job."""
        summary = {
            "total_discovered": 0,
            "scanned": 0,
            "skipped": 0,
            "added": 0,
            "removed": 0,
            "errors": 0,
        }

        with pytest.raises(ValueError, match="not found"):
            complete_scan_job(db_conn, "nonexistent-job-id", summary)


class TestCancelScanJob:
    """Tests for cancel_scan_job function."""

    def test_marks_job_cancelled(self, db_conn: sqlite3.Connection):
        """cancel_scan_job marks job as CANCELLED."""
        job = create_scan_job(db_conn, "/videos")

        cancel_scan_job(db_conn, job.id)

        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.CANCELLED.value

    def test_uses_default_reason(self, db_conn: sqlite3.Connection):
        """cancel_scan_job uses default cancellation reason."""
        job = create_scan_job(db_conn, "/videos")

        cancel_scan_job(db_conn, job.id)

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["error_message"] == "Cancelled by user"

    def test_uses_custom_reason(self, db_conn: sqlite3.Connection):
        """cancel_scan_job uses custom cancellation reason."""
        job = create_scan_job(db_conn, "/videos")

        cancel_scan_job(db_conn, job.id, reason="User pressed Ctrl+C")

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["error_message"] == "User pressed Ctrl+C"

    def test_sets_completed_at_timestamp(self, db_conn: sqlite3.Connection):
        """cancel_scan_job sets completed_at timestamp."""
        job = create_scan_job(db_conn, "/videos")

        cancel_scan_job(db_conn, job.id)

        cursor = db_conn.execute(
            "SELECT completed_at FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["completed_at"] is not None

    def test_raises_for_nonexistent_job(self, db_conn: sqlite3.Connection):
        """cancel_scan_job raises ValueError for non-existent job."""
        with pytest.raises(ValueError, match="not found"):
            cancel_scan_job(db_conn, "nonexistent-job-id")


class TestFailScanJob:
    """Tests for fail_scan_job function."""

    def test_marks_job_failed(self, db_conn: sqlite3.Connection):
        """fail_scan_job marks job as FAILED."""
        job = create_scan_job(db_conn, "/videos")

        fail_scan_job(db_conn, job.id, "Permission denied")

        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value

    def test_stores_error_message(self, db_conn: sqlite3.Connection):
        """fail_scan_job stores error message."""
        job = create_scan_job(db_conn, "/videos")

        fail_scan_job(db_conn, job.id, "Permission denied: /videos")

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["error_message"] == "Permission denied: /videos"

    def test_sets_completed_at_timestamp(self, db_conn: sqlite3.Connection):
        """fail_scan_job sets completed_at timestamp."""
        job = create_scan_job(db_conn, "/videos")

        fail_scan_job(db_conn, job.id, "Error")

        cursor = db_conn.execute(
            "SELECT completed_at FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["completed_at"] is not None

    def test_raises_for_nonexistent_job(self, db_conn: sqlite3.Connection):
        """fail_scan_job raises ValueError for non-existent job."""
        with pytest.raises(ValueError, match="not found"):
            fail_scan_job(db_conn, "nonexistent-job-id", "Error")
