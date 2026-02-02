"""Tests for job tracking functions."""

import json
import sqlite3

import pytest

from vpo.db import JobStatus, JobType
from vpo.jobs.exceptions import JobNotFoundError
from vpo.jobs.tracking import (
    cancel_process_job,
    cancel_scan_job,
    complete_process_job,
    complete_scan_job,
    create_process_job,
    create_scan_job,
    fail_job_with_retry,
    fail_process_job,
    fail_scan_job,
)


@pytest.fixture
def file_id(insert_test_file) -> int:
    """Insert a dummy file record and return its ID for FK-dependent tests."""
    return insert_test_file(path="/videos/movie.mkv", extension="mkv", size_bytes=100)


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
        """complete_scan_job raises JobNotFoundError for non-existent job."""
        summary = {
            "total_discovered": 0,
            "scanned": 0,
            "skipped": 0,
            "added": 0,
            "removed": 0,
            "errors": 0,
        }

        with pytest.raises(JobNotFoundError) as exc_info:
            complete_scan_job(db_conn, "nonexistent-job-id", summary)
        assert exc_info.value.job_id == "nonexistent-job-id"
        assert exc_info.value.operation == "complete"


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
        """cancel_scan_job raises JobNotFoundError for non-existent job."""
        with pytest.raises(JobNotFoundError) as exc_info:
            cancel_scan_job(db_conn, "nonexistent-job-id")
        assert exc_info.value.job_id == "nonexistent-job-id"
        assert exc_info.value.operation == "cancel"


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
        """fail_scan_job raises JobNotFoundError for non-existent job."""
        with pytest.raises(JobNotFoundError) as exc_info:
            fail_scan_job(db_conn, "nonexistent-job-id", "Error")
        assert exc_info.value.job_id == "nonexistent-job-id"
        assert exc_info.value.operation == "fail"


class TestCreateProcessJob:
    """Tests for create_process_job function."""

    def test_creates_job_with_defaults(self, db_conn: sqlite3.Connection, file_id: int):
        """create_process_job creates a job with default values."""
        job = create_process_job(
            db_conn,
            file_id=file_id,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        assert job.id is not None
        assert job.file_id == file_id
        assert job.file_path == "/videos/movie.mkv"
        assert job.job_type == JobType.PROCESS
        assert job.status == JobStatus.RUNNING
        assert job.policy_name == "default.yaml"
        assert job.origin == "cli"
        assert job.batch_id is None

    def test_creates_job_with_origin(self, db_conn: sqlite3.Connection):
        """create_process_job stores origin correctly."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
            origin="daemon",
        )

        assert job.origin == "daemon"

    def test_creates_job_with_batch_id(self, db_conn: sqlite3.Connection):
        """create_process_job stores batch_id correctly."""
        batch_uuid = "12345678-1234-1234-1234-123456789abc"
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
            batch_id=batch_uuid,
        )

        assert job.batch_id == batch_uuid

    def test_job_persisted_to_database(self, db_conn: sqlite3.Connection, file_id: int):
        """create_process_job persists job to database."""
        batch_uuid = "12345678-1234-1234-1234-123456789abc"
        job = create_process_job(
            db_conn,
            file_id=file_id,
            file_path="/videos/movie.mkv",
            policy_name="transcode.yaml",
            origin="cli",
            batch_id=batch_uuid,
        )

        # Query directly from database
        cursor = db_conn.execute("SELECT * FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()

        assert row is not None
        assert row["file_id"] == file_id
        assert row["file_path"] == "/videos/movie.mkv"
        assert row["job_type"] == JobType.PROCESS.value
        assert row["status"] == JobStatus.RUNNING.value
        assert row["policy_name"] == "transcode.yaml"
        assert row["origin"] == "cli"
        assert row["batch_id"] == batch_uuid

    def test_creates_job_with_timestamps(self, db_conn: sqlite3.Connection):
        """create_process_job sets created_at and started_at timestamps."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        assert job.created_at is not None
        assert job.started_at is not None

    def test_creates_job_with_null_file_id(self, db_conn: sqlite3.Connection):
        """create_process_job accepts None for file_id (unscanned files)."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        assert job.file_id is None


class TestCompleteProcessJob:
    """Tests for complete_process_job function."""

    def test_marks_job_completed(self, db_conn: sqlite3.Connection):
        """complete_process_job marks job as COMPLETED on success."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        complete_process_job(
            db_conn,
            job.id,
            success=True,
            phases_completed=3,
            total_changes=5,
        )

        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.COMPLETED.value

    def test_marks_job_failed_on_failure(self, db_conn: sqlite3.Connection):
        """complete_process_job marks job as FAILED when success=False."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        complete_process_job(
            db_conn,
            job.id,
            success=False,
            phases_completed=1,
            total_changes=0,
            error_message="Phase 'transcode' failed",
        )

        cursor = db_conn.execute(
            "SELECT status, error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value
        assert row["error_message"] == "Phase 'transcode' failed"

    def test_stores_summary_json(self, db_conn: sqlite3.Connection):
        """complete_process_job stores summary as JSON."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        complete_process_job(
            db_conn,
            job.id,
            success=True,
            phases_completed=3,
            total_changes=5,
            stats_id="abc-123",
        )

        cursor = db_conn.execute(
            "SELECT summary_json FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        summary = json.loads(row["summary_json"])
        assert summary["phases_completed"] == 3
        assert summary["total_changes"] == 5
        assert summary["stats_id"] == "abc-123"

    def test_sets_completed_at_timestamp(self, db_conn: sqlite3.Connection):
        """complete_process_job sets completed_at timestamp."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        complete_process_job(db_conn, job.id, success=True)

        cursor = db_conn.execute(
            "SELECT completed_at FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["completed_at"] is not None

    def test_sets_progress_to_100(self, db_conn: sqlite3.Connection):
        """complete_process_job sets progress to 100%."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        complete_process_job(db_conn, job.id, success=True)

        cursor = db_conn.execute(
            "SELECT progress_percent FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["progress_percent"] == 100.0

    def test_raises_for_nonexistent_job(self, db_conn: sqlite3.Connection):
        """complete_process_job raises JobNotFoundError for non-existent job."""
        with pytest.raises(JobNotFoundError) as exc_info:
            complete_process_job(db_conn, "nonexistent-job-id", success=True)
        assert exc_info.value.job_id == "nonexistent-job-id"
        assert exc_info.value.operation == "complete"


class TestFailProcessJob:
    """Tests for fail_process_job function."""

    def test_marks_job_failed(self, db_conn: sqlite3.Connection):
        """fail_process_job marks job as FAILED."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        fail_process_job(db_conn, job.id, "Exception during processing")

        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value

    def test_stores_error_message(self, db_conn: sqlite3.Connection):
        """fail_process_job stores error message."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        fail_process_job(db_conn, job.id, "Disk space exhausted")

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["error_message"] == "Disk space exhausted"

    def test_sets_completed_at_timestamp(self, db_conn: sqlite3.Connection):
        """fail_process_job sets completed_at timestamp."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        fail_process_job(db_conn, job.id, "Error")

        cursor = db_conn.execute(
            "SELECT completed_at FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["completed_at"] is not None

    def test_raises_for_nonexistent_job(self, db_conn: sqlite3.Connection):
        """fail_process_job raises JobNotFoundError for non-existent job."""
        with pytest.raises(JobNotFoundError) as exc_info:
            fail_process_job(db_conn, "nonexistent-job-id", "Error")
        assert exc_info.value.job_id == "nonexistent-job-id"
        assert exc_info.value.operation == "fail"


class TestCancelProcessJob:
    """Tests for cancel_process_job function."""

    def test_marks_job_cancelled(self, db_conn: sqlite3.Connection):
        """cancel_process_job marks job as CANCELLED."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        cancel_process_job(db_conn, job.id)

        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.CANCELLED.value

    def test_uses_default_reason(self, db_conn: sqlite3.Connection):
        """cancel_process_job uses default cancellation reason."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        cancel_process_job(db_conn, job.id)

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["error_message"] == "Cancelled by user"

    def test_uses_custom_reason(self, db_conn: sqlite3.Connection):
        """cancel_process_job uses custom cancellation reason."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        cancel_process_job(db_conn, job.id, reason="User pressed Ctrl+C")

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["error_message"] == "User pressed Ctrl+C"

    def test_sets_completed_at_timestamp(self, db_conn: sqlite3.Connection):
        """cancel_process_job sets completed_at timestamp."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        cancel_process_job(db_conn, job.id)

        cursor = db_conn.execute(
            "SELECT completed_at FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["completed_at"] is not None

    def test_raises_for_nonexistent_job(self, db_conn: sqlite3.Connection):
        """cancel_process_job raises JobNotFoundError for non-existent job."""
        with pytest.raises(JobNotFoundError) as exc_info:
            cancel_process_job(db_conn, "nonexistent-job-id")
        assert exc_info.value.job_id == "nonexistent-job-id"
        assert exc_info.value.operation == "cancel"


class TestInputValidation:
    """Tests for input validation in tracking functions."""

    def test_create_scan_job_rejects_empty_directory(self, db_conn: sqlite3.Connection):
        """create_scan_job raises ValueError for empty directory."""
        with pytest.raises(ValueError, match="directory cannot be empty"):
            create_scan_job(db_conn, "")

    def test_create_scan_job_rejects_whitespace_directory(
        self, db_conn: sqlite3.Connection
    ):
        """create_scan_job raises ValueError for whitespace-only directory."""
        with pytest.raises(ValueError, match="directory cannot be empty"):
            create_scan_job(db_conn, "   ")

    def test_create_process_job_rejects_empty_file_path(
        self, db_conn: sqlite3.Connection
    ):
        """create_process_job raises ValueError for empty file_path."""
        with pytest.raises(ValueError, match="file_path cannot be empty"):
            create_process_job(db_conn, None, "", "policy.yaml")

    def test_create_process_job_rejects_empty_policy_name(
        self, db_conn: sqlite3.Connection
    ):
        """create_process_job raises ValueError for empty policy_name."""
        with pytest.raises(ValueError, match="policy_name cannot be empty"):
            create_process_job(db_conn, None, "/videos/movie.mkv", "")

    def test_complete_scan_job_rejects_empty_job_id(self, db_conn: sqlite3.Connection):
        """complete_scan_job raises ValueError for empty job_id."""
        with pytest.raises(ValueError, match="job_id cannot be empty"):
            complete_scan_job(db_conn, "", {"total_discovered": 0})

    def test_fail_scan_job_rejects_empty_error_message(
        self, db_conn: sqlite3.Connection
    ):
        """fail_scan_job raises ValueError for empty error_message."""
        job = create_scan_job(db_conn, "/videos")
        with pytest.raises(ValueError, match="error_message cannot be empty"):
            fail_scan_job(db_conn, job.id, "")

    def test_fail_process_job_rejects_empty_error_message(
        self, db_conn: sqlite3.Connection
    ):
        """fail_process_job raises ValueError for empty error_message."""
        job = create_process_job(db_conn, None, "/videos/movie.mkv", "policy.yaml")
        with pytest.raises(ValueError, match="error_message cannot be empty"):
            fail_process_job(db_conn, job.id, "")


class TestFailJobWithRetry:
    """Tests for fail_job_with_retry function."""

    def test_successfully_fails_job(self, db_conn: sqlite3.Connection):
        """fail_job_with_retry marks job as failed and returns True."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        result = fail_job_with_retry(db_conn, job.id, "Something went wrong")

        assert result is True
        cursor = db_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row["status"] == JobStatus.FAILED.value

    def test_returns_false_for_nonexistent_job(self, db_conn: sqlite3.Connection):
        """fail_job_with_retry returns False for non-existent job."""
        result = fail_job_with_retry(db_conn, "nonexistent-job-id", "Error")

        assert result is False

    def test_stores_error_message(self, db_conn: sqlite3.Connection):
        """fail_job_with_retry stores the error message."""
        job = create_process_job(
            db_conn,
            file_id=None,
            file_path="/videos/movie.mkv",
            policy_name="default.yaml",
        )

        fail_job_with_retry(db_conn, job.id, "Database connection lost")

        cursor = db_conn.execute(
            "SELECT error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["error_message"] == "Database connection lost"
