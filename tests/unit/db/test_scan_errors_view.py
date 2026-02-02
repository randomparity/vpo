"""Tests for scan errors view query."""

from vpo.db.queries import insert_job
from vpo.db.types import JobStatus, JobType
from vpo.db.views import ScanErrorView, get_scan_errors_for_job


class TestGetScanErrorsForJob:
    """Tests for get_scan_errors_for_job function."""

    def test_returns_none_for_nonexistent_job(self, db_conn):
        """Returns None when job doesn't exist."""
        result = get_scan_errors_for_job(db_conn, "nonexistent-job-id")
        assert result is None

    def test_returns_none_for_non_scan_job(self, db_conn, make_job):
        """Returns None when job is not a scan job."""
        job = make_job(
            id="transcode-job", job_type=JobType.TRANSCODE, status=JobStatus.COMPLETED
        )
        insert_job(db_conn, job)
        result = get_scan_errors_for_job(db_conn, "transcode-job")
        assert result is None

    def test_returns_empty_list_for_scan_job_without_errors(
        self, db_conn, make_job, insert_test_file
    ):
        """Returns empty list when scan job has no error files."""
        job = make_job(
            id="scan-no-errors", job_type=JobType.SCAN, status=JobStatus.COMPLETED
        )
        insert_job(db_conn, job)
        insert_test_file(id=1, path="/test/path/good-file.mkv", job_id="scan-no-errors")

        result = get_scan_errors_for_job(db_conn, "scan-no-errors")
        assert result == []

    def test_returns_error_files_for_scan_job(
        self, db_conn, make_job, insert_test_file
    ):
        """Returns list of error files for scan job."""
        job = make_job(
            id="scan-with-errors", job_type=JobType.SCAN, status=JobStatus.COMPLETED
        )
        insert_job(db_conn, job)
        insert_test_file(
            id=1,
            path="/test/path/bad-file.mkv",
            scan_status="error",
            scan_error="Permission denied",
            job_id="scan-with-errors",
        )

        result = get_scan_errors_for_job(db_conn, "scan-with-errors")

        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], ScanErrorView)
        assert result[0].filename == "bad-file.mkv"
        assert result[0].error == "Permission denied"
        assert result[0].path == "/test/path/bad-file.mkv"

    def test_returns_multiple_error_files(self, db_conn, make_job, insert_test_file):
        """Returns all error files for scan job."""
        job = make_job(
            id="scan-multi-error", job_type=JobType.SCAN, status=JobStatus.COMPLETED
        )
        insert_job(db_conn, job)
        insert_test_file(
            id=1,
            path="/test/path/file-a.mkv",
            scan_status="error",
            scan_error="Error A",
            job_id="scan-multi-error",
        )
        insert_test_file(
            id=2,
            path="/test/path/file-b.mkv",
            scan_status="error",
            scan_error="Error B",
            job_id="scan-multi-error",
        )
        insert_test_file(
            id=3, path="/test/path/good-file.mkv", job_id="scan-multi-error"
        )

        result = get_scan_errors_for_job(db_conn, "scan-multi-error")

        assert result is not None
        assert len(result) == 2
        # Should be ordered by filename
        assert result[0].filename == "file-a.mkv"
        assert result[1].filename == "file-b.mkv"

    def test_excludes_files_from_other_jobs(self, db_conn, make_job, insert_test_file):
        """Only returns errors from the specified job."""
        job1 = make_job(
            id="scan-job-1", job_type=JobType.SCAN, status=JobStatus.COMPLETED
        )
        job2 = make_job(
            id="scan-job-2", job_type=JobType.SCAN, status=JobStatus.COMPLETED
        )
        insert_job(db_conn, job1)
        insert_job(db_conn, job2)
        insert_test_file(
            id=1,
            path="/test/path/job1-error.mkv",
            scan_status="error",
            scan_error="Error 1",
            job_id="scan-job-1",
        )
        insert_test_file(
            id=2,
            path="/test/path/job2-error.mkv",
            scan_status="error",
            scan_error="Error 2",
            job_id="scan-job-2",
        )

        result = get_scan_errors_for_job(db_conn, "scan-job-1")

        assert result is not None
        assert len(result) == 1
        assert result[0].filename == "job1-error.mkv"

    def test_results_ordered_by_filename(self, db_conn, make_job, insert_test_file):
        """Results are ordered alphabetically by filename."""
        job = make_job(
            id="scan-ordered", job_type=JobType.SCAN, status=JobStatus.COMPLETED
        )
        insert_job(db_conn, job)
        insert_test_file(
            id=1,
            path="/test/path/zebra.mkv",
            scan_status="error",
            scan_error="Error",
            job_id="scan-ordered",
        )
        insert_test_file(
            id=2,
            path="/test/path/apple.mkv",
            scan_status="error",
            scan_error="Error",
            job_id="scan-ordered",
        )
        insert_test_file(
            id=3,
            path="/test/path/mango.mkv",
            scan_status="error",
            scan_error="Error",
            job_id="scan-ordered",
        )

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
