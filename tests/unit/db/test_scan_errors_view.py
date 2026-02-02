"""Tests for scan errors view query."""

import sqlite3
from datetime import datetime, timezone

from vpo.db.queries import insert_file, insert_job
from vpo.db.types import FileRecord, Job, JobStatus, JobType
from vpo.db.views import ScanErrorView, get_scan_errors_for_job


def create_scan_job(conn: sqlite3.Connection, job_id: str = "test-scan-job") -> Job:
    """Create a test scan job."""
    job = Job(
        id=job_id,
        file_id=None,
        file_path="/test/path",
        job_type=JobType.SCAN,
        status=JobStatus.COMPLETED,
        priority=100,
        policy_name=None,
        policy_json="{}",
        progress_percent=100.0,
        progress_json=None,
        created_at=datetime.now(timezone.utc).isoformat(),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    insert_job(conn, job)
    return job


def create_transcode_job(
    conn: sqlite3.Connection, job_id: str = "test-transcode-job"
) -> Job:
    """Create a test transcode job."""
    job = Job(
        id=job_id,
        file_id=None,
        file_path="/test/path.mkv",
        job_type=JobType.TRANSCODE,
        status=JobStatus.COMPLETED,
        priority=100,
        policy_name=None,
        policy_json="{}",
        progress_percent=100.0,
        progress_json=None,
        created_at=datetime.now(timezone.utc).isoformat(),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    insert_job(conn, job)
    return job


def create_file_with_error(
    conn: sqlite3.Connection,
    file_id: int,
    job_id: str,
    filename: str,
    error: str,
) -> FileRecord:
    """Create a file record with scan error."""
    file = FileRecord(
        id=file_id,
        path=f"/test/path/{filename}",
        filename=filename,
        directory="/test/path",
        extension=".mkv",
        size_bytes=1000,
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_hash="abc123",
        container_format="matroska",
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scan_status="error",
        scan_error=error,
        job_id=job_id,
    )
    insert_file(conn, file)
    return file


def create_file_ok(
    conn: sqlite3.Connection,
    file_id: int,
    job_id: str,
    filename: str,
) -> FileRecord:
    """Create a file record with successful scan."""
    file = FileRecord(
        id=file_id,
        path=f"/test/path/{filename}",
        filename=filename,
        directory="/test/path",
        extension=".mkv",
        size_bytes=1000,
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_hash="abc123",
        container_format="matroska",
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scan_status="ok",
        scan_error=None,
        job_id=job_id,
    )
    insert_file(conn, file)
    return file


class TestGetScanErrorsForJob:
    """Tests for get_scan_errors_for_job function."""

    def test_returns_none_for_nonexistent_job(self, db_conn):
        """Returns None when job doesn't exist."""
        result = get_scan_errors_for_job(db_conn, "nonexistent-job-id")
        assert result is None

    def test_returns_none_for_non_scan_job(self, db_conn):
        """Returns None when job is not a scan job."""
        create_transcode_job(db_conn, "transcode-job")
        result = get_scan_errors_for_job(db_conn, "transcode-job")
        assert result is None

    def test_returns_empty_list_for_scan_job_without_errors(self, db_conn):
        """Returns empty list when scan job has no error files."""
        create_scan_job(db_conn, "scan-no-errors")
        create_file_ok(db_conn, 1, "scan-no-errors", "good-file.mkv")

        result = get_scan_errors_for_job(db_conn, "scan-no-errors")
        assert result == []

    def test_returns_error_files_for_scan_job(self, db_conn):
        """Returns list of error files for scan job."""
        create_scan_job(db_conn, "scan-with-errors")
        create_file_with_error(
            db_conn, 1, "scan-with-errors", "bad-file.mkv", "Permission denied"
        )

        result = get_scan_errors_for_job(db_conn, "scan-with-errors")

        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], ScanErrorView)
        assert result[0].filename == "bad-file.mkv"
        assert result[0].error == "Permission denied"
        assert result[0].path == "/test/path/bad-file.mkv"

    def test_returns_multiple_error_files(self, db_conn):
        """Returns all error files for scan job."""
        create_scan_job(db_conn, "scan-multi-error")
        create_file_with_error(db_conn, 1, "scan-multi-error", "file-a.mkv", "Error A")
        create_file_with_error(db_conn, 2, "scan-multi-error", "file-b.mkv", "Error B")
        create_file_ok(db_conn, 3, "scan-multi-error", "good-file.mkv")

        result = get_scan_errors_for_job(db_conn, "scan-multi-error")

        assert result is not None
        assert len(result) == 2
        # Should be ordered by filename
        assert result[0].filename == "file-a.mkv"
        assert result[1].filename == "file-b.mkv"

    def test_excludes_files_from_other_jobs(self, db_conn):
        """Only returns errors from the specified job."""
        create_scan_job(db_conn, "scan-job-1")
        create_scan_job(db_conn, "scan-job-2")
        create_file_with_error(db_conn, 1, "scan-job-1", "job1-error.mkv", "Error 1")
        create_file_with_error(db_conn, 2, "scan-job-2", "job2-error.mkv", "Error 2")

        result = get_scan_errors_for_job(db_conn, "scan-job-1")

        assert result is not None
        assert len(result) == 1
        assert result[0].filename == "job1-error.mkv"

    def test_results_ordered_by_filename(self, db_conn):
        """Results are ordered alphabetically by filename."""
        create_scan_job(db_conn, "scan-ordered")
        create_file_with_error(db_conn, 1, "scan-ordered", "zebra.mkv", "Error")
        create_file_with_error(db_conn, 2, "scan-ordered", "apple.mkv", "Error")
        create_file_with_error(db_conn, 3, "scan-ordered", "mango.mkv", "Error")

        result = get_scan_errors_for_job(db_conn, "scan-ordered")

        assert result is not None
        assert len(result) == 3
        assert result[0].filename == "apple.mkv"
        assert result[1].filename == "mango.mkv"
        assert result[2].filename == "zebra.mkv"


class TestScanErrorView:
    """Tests for ScanErrorView dataclass."""

    def test_has_required_fields(self):
        """ScanErrorView has path, filename, and error fields."""
        view = ScanErrorView(
            path="/test/path/file.mkv",
            filename="file.mkv",
            error="Test error message",
        )
        assert view.path == "/test/path/file.mkv"
        assert view.filename == "file.mkv"
        assert view.error == "Test error message"
