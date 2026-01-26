"""Unit tests for server/api/jobs.py.

Tests the jobs API handlers, models, and helper functions:
- JobFilterParams query parameter parsing
- JobListItem/JobListResponse serialization
- JobDetailItem properties and serialization
- JobLogsResponse pagination model
- ScanErrorItem/ScanErrorsResponse serialization
- Helper functions for job conversion
"""

from __future__ import annotations

import pytest

from vpo.server.ui.models import (
    JobDetailContext,
    JobDetailItem,
    JobFilterParams,
    JobListContext,
    JobListItem,
    JobListResponse,
    JobLogsResponse,
    ScanErrorItem,
    ScanErrorsResponse,
)

# =============================================================================
# Tests for JobFilterParams
# =============================================================================


class TestJobFilterParams:
    """Tests for JobFilterParams.from_query() method."""

    def test_parses_default_values(self):
        """Returns default values for empty query."""
        params = JobFilterParams.from_query({})

        assert params.status is None
        assert params.job_type is None
        assert params.since is None
        assert params.limit == 50
        assert params.offset == 0

    def test_parses_status_filter(self):
        """Parses status filter from query."""
        params = JobFilterParams.from_query({"status": "running"})

        assert params.status == "running"

    def test_parses_type_filter(self):
        """Parses type filter from query (uses 'type' key)."""
        params = JobFilterParams.from_query({"type": "scan"})

        assert params.job_type == "scan"

    def test_parses_since_filter(self):
        """Parses since time filter."""
        params = JobFilterParams.from_query({"since": "24h"})

        assert params.since == "24h"

    def test_parses_limit_within_bounds(self):
        """Parses limit value within bounds (1-100)."""
        params = JobFilterParams.from_query({"limit": "25"})

        assert params.limit == 25

    def test_clamps_limit_minimum(self):
        """Clamps limit to minimum of 1."""
        params = JobFilterParams.from_query({"limit": "0"})

        assert params.limit == 1

    def test_clamps_limit_maximum(self):
        """Clamps limit to maximum of 100."""
        params = JobFilterParams.from_query({"limit": "500"})

        assert params.limit == 100

    def test_handles_invalid_limit(self):
        """Returns default limit for invalid values."""
        params = JobFilterParams.from_query({"limit": "invalid"})

        assert params.limit == 50

    def test_parses_offset(self):
        """Parses offset value."""
        params = JobFilterParams.from_query({"offset": "100"})

        assert params.offset == 100

    def test_clamps_negative_offset(self):
        """Clamps negative offset to 0."""
        params = JobFilterParams.from_query({"offset": "-10"})

        assert params.offset == 0

    def test_handles_invalid_offset(self):
        """Returns default offset for invalid values."""
        params = JobFilterParams.from_query({"offset": "abc"})

        assert params.offset == 0

    def test_parses_all_parameters(self):
        """Parses all parameters together."""
        params = JobFilterParams.from_query(
            {
                "status": "completed",
                "type": "apply",
                "since": "7d",
                "limit": "20",
                "offset": "40",
            }
        )

        assert params.status == "completed"
        assert params.job_type == "apply"
        assert params.since == "7d"
        assert params.limit == 20
        assert params.offset == 40

    # Search parameter tests

    def test_parses_search_filter(self):
        """Parses search filter from query."""
        params = JobFilterParams.from_query({"search": "movie"})

        assert params.search == "movie"

    def test_strips_search_whitespace(self):
        """Strips leading/trailing whitespace from search."""
        params = JobFilterParams.from_query({"search": "  movie  "})

        assert params.search == "movie"

    def test_truncates_long_search(self):
        """Truncates search to 200 characters max."""
        long_search = "a" * 250
        params = JobFilterParams.from_query({"search": long_search})

        assert len(params.search) == 200

    def test_empty_search_becomes_none(self):
        """Empty search string becomes None."""
        params = JobFilterParams.from_query({"search": ""})

        assert params.search is None

    def test_whitespace_only_search_becomes_none(self):
        """Whitespace-only search string becomes None."""
        params = JobFilterParams.from_query({"search": "   "})

        assert params.search is None

    # Sort parameter tests

    def test_parses_sort_by(self):
        """Parses valid sort_by column from query."""
        params = JobFilterParams.from_query({"sort": "created_at"})

        assert params.sort_by == "created_at"

    def test_parses_sort_by_file_path(self):
        """Parses file_path sort column."""
        params = JobFilterParams.from_query({"sort": "file_path"})

        assert params.sort_by == "file_path"

    def test_parses_sort_by_duration(self):
        """Parses duration sort column."""
        params = JobFilterParams.from_query({"sort": "duration"})

        assert params.sort_by == "duration"

    def test_invalid_sort_by_becomes_none(self):
        """Invalid sort column becomes None (uses default)."""
        params = JobFilterParams.from_query({"sort": "invalid_column"})

        assert params.sort_by is None

    def test_parses_sort_order_asc(self):
        """Parses ascending sort order."""
        params = JobFilterParams.from_query({"order": "asc"})

        assert params.sort_order == "asc"

    def test_parses_sort_order_desc(self):
        """Parses descending sort order."""
        params = JobFilterParams.from_query({"order": "desc"})

        assert params.sort_order == "desc"

    def test_parses_sort_order_uppercase(self):
        """Handles uppercase sort order (converts to lowercase)."""
        params = JobFilterParams.from_query({"order": "ASC"})

        assert params.sort_order == "asc"

    def test_invalid_sort_order_becomes_none(self):
        """Invalid sort order becomes None (uses default)."""
        params = JobFilterParams.from_query({"order": "random"})

        assert params.sort_order is None

    def test_parses_all_parameters_with_search_and_sort(self):
        """Parses all parameters including search and sort."""
        params = JobFilterParams.from_query(
            {
                "status": "completed",
                "type": "apply",
                "since": "7d",
                "search": "movie",
                "sort": "file_path",
                "order": "asc",
                "limit": "20",
                "offset": "40",
            }
        )

        assert params.status == "completed"
        assert params.job_type == "apply"
        assert params.since == "7d"
        assert params.search == "movie"
        assert params.sort_by == "file_path"
        assert params.sort_order == "asc"
        assert params.limit == 20
        assert params.offset == 40


# =============================================================================
# Tests for JobListItem
# =============================================================================


class TestJobListItem:
    """Tests for JobListItem.to_dict() method."""

    def test_to_dict_basic(self):
        """Serializes basic job list item."""
        item = JobListItem(
            id="abc123",
            job_type="scan",
            status="running",
            file_path="/videos",
            progress_percent=50.0,
            created_at="2024-01-15T10:00:00Z",
        )

        result = item.to_dict()

        assert result["id"] == "abc123"
        assert result["job_type"] == "scan"
        assert result["status"] == "running"
        assert result["file_path"] == "/videos"
        assert result["progress_percent"] == 50.0
        assert result["created_at"] == "2024-01-15T10:00:00Z"
        assert result["completed_at"] is None
        assert result["duration_seconds"] is None

    def test_to_dict_completed_job(self):
        """Serializes completed job with duration."""
        item = JobListItem(
            id="def456",
            job_type="apply",
            status="completed",
            file_path="/videos/movie.mkv",
            progress_percent=100.0,
            created_at="2024-01-15T10:00:00Z",
            completed_at="2024-01-15T10:05:00Z",
            duration_seconds=300,
        )

        result = item.to_dict()

        assert result["completed_at"] == "2024-01-15T10:05:00Z"
        assert result["duration_seconds"] == 300


# =============================================================================
# Tests for JobListResponse
# =============================================================================


class TestJobListResponse:
    """Tests for JobListResponse.to_dict() method."""

    def test_to_dict_empty_list(self):
        """Serializes response with no jobs."""
        response = JobListResponse(
            jobs=[],
            total=0,
            limit=50,
            offset=0,
            has_filters=False,
        )

        result = response.to_dict()

        assert result["jobs"] == []
        assert result["total"] == 0
        assert result["limit"] == 50
        assert result["offset"] == 0
        assert result["has_filters"] is False

    def test_to_dict_with_jobs(self):
        """Serializes response with job list."""
        job1 = JobListItem(
            id="job1",
            job_type="scan",
            status="completed",
            file_path="/videos",
            progress_percent=100.0,
            created_at="2024-01-15T10:00:00Z",
        )
        job2 = JobListItem(
            id="job2",
            job_type="apply",
            status="running",
            file_path="/videos/movie.mkv",
            progress_percent=50.0,
            created_at="2024-01-15T11:00:00Z",
        )
        response = JobListResponse(
            jobs=[job1, job2],
            total=100,
            limit=50,
            offset=0,
            has_filters=True,
        )

        result = response.to_dict()

        assert len(result["jobs"]) == 2
        assert result["jobs"][0]["id"] == "job1"
        assert result["jobs"][1]["id"] == "job2"
        assert result["total"] == 100
        assert result["has_filters"] is True


# =============================================================================
# Tests for JobDetailItem
# =============================================================================


class TestJobDetailItem:
    """Tests for JobDetailItem class."""

    @pytest.fixture
    def completed_scan_job(self):
        """Create a completed scan job detail item."""
        return JobDetailItem(
            id="abc12345-1234-1234-1234-123456789012",
            id_short="abc12345",
            job_type="scan",
            status="completed",
            priority=0,
            file_path="/videos",
            policy_name=None,
            created_at="2024-01-15T10:00:00Z",
            started_at="2024-01-15T10:00:01Z",
            completed_at="2024-01-15T10:05:00Z",
            duration_seconds=299,
            progress_percent=100.0,
            error_message=None,
            output_path=None,
            summary="Scanned 10 files",
            summary_raw={"scanned": 10, "errors": 0},
            has_logs=True,
        )

    def test_has_scan_errors_false_when_no_errors(self, completed_scan_job):
        """has_scan_errors returns False when errors count is 0."""
        assert completed_scan_job.has_scan_errors is False

    def test_has_scan_errors_true_when_errors_present(self, completed_scan_job):
        """has_scan_errors returns True when errors count > 0."""
        completed_scan_job.summary_raw = {"scanned": 10, "errors": 2}

        assert completed_scan_job.has_scan_errors is True

    def test_has_scan_errors_false_for_non_scan_jobs(self, completed_scan_job):
        """has_scan_errors returns False for non-scan job types."""
        completed_scan_job.job_type = "apply"
        completed_scan_job.summary_raw = {"errors": 5}  # Would match if scan

        assert completed_scan_job.has_scan_errors is False

    def test_has_scan_errors_false_when_no_summary(self, completed_scan_job):
        """has_scan_errors returns False when summary_raw is None."""
        completed_scan_job.summary_raw = None

        assert completed_scan_job.has_scan_errors is False

    def test_to_dict_includes_all_fields(self, completed_scan_job):
        """to_dict includes all fields including computed has_scan_errors."""
        result = completed_scan_job.to_dict()

        assert result["id"] == "abc12345-1234-1234-1234-123456789012"
        assert result["id_short"] == "abc12345"
        assert result["job_type"] == "scan"
        assert result["status"] == "completed"
        assert result["priority"] == 0
        assert result["file_path"] == "/videos"
        assert result["policy_name"] is None
        assert result["created_at"] == "2024-01-15T10:00:00Z"
        assert result["started_at"] == "2024-01-15T10:00:01Z"
        assert result["completed_at"] == "2024-01-15T10:05:00Z"
        assert result["duration_seconds"] == 299
        assert result["progress_percent"] == 100.0
        assert result["error_message"] is None
        assert result["output_path"] is None
        assert result["summary"] == "Scanned 10 files"
        assert result["summary_raw"] == {"scanned": 10, "errors": 0}
        assert result["has_logs"] is True
        assert result["has_scan_errors"] is False


# =============================================================================
# Tests for JobLogsResponse
# =============================================================================


class TestJobLogsResponse:
    """Tests for JobLogsResponse.to_dict() method."""

    def test_to_dict_empty_logs(self):
        """Serializes response with no log lines."""
        response = JobLogsResponse(
            job_id="job123",
            lines=[],
            total_lines=0,
            offset=0,
            has_more=False,
        )

        result = response.to_dict()

        assert result["job_id"] == "job123"
        assert result["lines"] == []
        assert result["total_lines"] == 0
        assert result["offset"] == 0
        assert result["has_more"] is False

    def test_to_dict_with_pagination(self):
        """Serializes response with pagination info."""
        response = JobLogsResponse(
            job_id="job456",
            lines=["Line 1", "Line 2", "Line 3"],
            total_lines=100,
            offset=50,
            has_more=True,
        )

        result = response.to_dict()

        assert result["lines"] == ["Line 1", "Line 2", "Line 3"]
        assert result["total_lines"] == 100
        assert result["offset"] == 50
        assert result["has_more"] is True


# =============================================================================
# Tests for ScanErrorItem and ScanErrorsResponse
# =============================================================================


class TestScanErrorItem:
    """Tests for ScanErrorItem.to_dict() method."""

    def test_to_dict(self):
        """Serializes scan error item."""
        item = ScanErrorItem(
            path="/videos/corrupt.mkv",
            filename="corrupt.mkv",
            error="ffprobe failed: Invalid data found",
        )

        result = item.to_dict()

        assert result["path"] == "/videos/corrupt.mkv"
        assert result["filename"] == "corrupt.mkv"
        assert result["error"] == "ffprobe failed: Invalid data found"


class TestScanErrorsResponse:
    """Tests for ScanErrorsResponse.to_dict() method."""

    def test_to_dict_empty(self):
        """Serializes response with no errors."""
        response = ScanErrorsResponse(
            job_id="job123",
            errors=[],
            total_errors=0,
        )

        result = response.to_dict()

        assert result["job_id"] == "job123"
        assert result["errors"] == []
        assert result["total_errors"] == 0

    def test_to_dict_with_errors(self):
        """Serializes response with error list."""
        error1 = ScanErrorItem(
            path="/videos/bad1.mkv",
            filename="bad1.mkv",
            error="Error 1",
        )
        error2 = ScanErrorItem(
            path="/videos/bad2.mkv",
            filename="bad2.mkv",
            error="Error 2",
        )
        response = ScanErrorsResponse(
            job_id="job456",
            errors=[error1, error2],
            total_errors=2,
        )

        result = response.to_dict()

        assert len(result["errors"]) == 2
        assert result["errors"][0]["filename"] == "bad1.mkv"
        assert result["errors"][1]["filename"] == "bad2.mkv"
        assert result["total_errors"] == 2


# =============================================================================
# Tests for JobListContext
# =============================================================================


class TestJobListContext:
    """Tests for JobListContext.default() method."""

    def test_default_has_status_options(self):
        """Default context includes status filter options."""
        context = JobListContext.default()

        assert len(context.status_options) > 0
        status_values = [opt["value"] for opt in context.status_options]
        assert "" in status_values  # All statuses
        assert "running" in status_values
        assert "completed" in status_values
        assert "failed" in status_values

    def test_default_has_type_options(self):
        """Default context includes type filter options."""
        context = JobListContext.default()

        assert len(context.type_options) > 0
        type_values = [opt["value"] for opt in context.type_options]
        assert "" in type_values  # All types
        assert "scan" in type_values
        assert "apply" in type_values

    def test_default_has_time_options(self):
        """Default context includes time range options."""
        context = JobListContext.default()

        assert len(context.time_options) > 0
        time_values = [opt["value"] for opt in context.time_options]
        assert "" in time_values  # All time
        assert "24h" in time_values
        assert "7d" in time_values


# =============================================================================
# Tests for JobDetailContext
# =============================================================================


class TestJobDetailContext:
    """Tests for JobDetailContext.from_job_and_request() method."""

    @pytest.fixture
    def job_detail(self):
        """Create a sample job detail item."""
        return JobDetailItem(
            id="abc12345",
            id_short="abc12345",
            job_type="scan",
            status="completed",
            priority=0,
            file_path="/videos",
            policy_name=None,
            created_at="2024-01-15T10:00:00Z",
            started_at="2024-01-15T10:00:01Z",
            completed_at="2024-01-15T10:05:00Z",
            duration_seconds=299,
            progress_percent=100.0,
            error_message=None,
            output_path=None,
            summary="Scanned 10 files",
            summary_raw=None,
            has_logs=True,
        )

    def test_default_back_url_when_no_referer(self, job_detail):
        """Returns default /jobs URL when no referer."""
        context = JobDetailContext.from_job_and_request(job_detail, referer=None)

        assert context.back_url == "/jobs"
        assert context.job == job_detail

    def test_preserves_filters_from_referer(self, job_detail):
        """Preserves query params from referer URL with filters."""
        referer = "/jobs?status=running&type=scan"

        context = JobDetailContext.from_job_and_request(job_detail, referer=referer)

        assert context.back_url == "/jobs?status=running&type=scan"

    def test_extracts_path_from_absolute_referer(self, job_detail):
        """Extracts path from absolute URL referer."""
        referer = "http://localhost:8080/jobs?status=completed"

        context = JobDetailContext.from_job_and_request(job_detail, referer=referer)

        assert context.back_url == "/jobs?status=completed"

    def test_default_when_referer_not_jobs_page(self, job_detail):
        """Returns default URL when referer is not jobs page."""
        referer = "/library"

        context = JobDetailContext.from_job_and_request(job_detail, referer=referer)

        assert context.back_url == "/jobs"
