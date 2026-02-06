"""Integration tests for jobs CLI commands (008-operational-ux).

These tests verify the jobs CLI functionality using database-level tests
since the CLI creates its own database connection.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from vpo.cli import main
from vpo.core import parse_relative_time
from vpo.db import (
    Job,
    JobStatus,
    JobType,
    get_jobs_by_id_prefix,
    get_jobs_filtered,
    insert_job,
)
from vpo.db.schema import create_schema


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """Create a temporary database connection with full schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def sample_jobs(db_conn: sqlite3.Connection) -> list[Job]:
    """Insert sample jobs for testing."""
    now = datetime.now(timezone.utc).isoformat()
    jobs = []

    # Create scan job (completed)
    scan_job = Job(
        id=str(uuid.uuid4()),
        file_id=0,
        file_path="/media/videos",
        job_type=JobType.SCAN,
        status=JobStatus.COMPLETED,
        priority=100,
        policy_name=None,
        policy_json=json.dumps({"incremental": True}),
        progress_percent=100.0,
        progress_json=None,
        created_at=now,
        started_at=now,
        completed_at=now,
        summary_json=json.dumps({"files_scanned": 100}),
    )
    insert_job(db_conn, scan_job)
    jobs.append(scan_job)

    # Create apply job (running)
    apply_job = Job(
        id=str(uuid.uuid4()),
        file_id=1,
        file_path="/media/videos/movie.mkv",
        job_type=JobType.APPLY,
        status=JobStatus.RUNNING,
        priority=100,
        policy_name="normalize",
        policy_json=json.dumps({"policy": "normalize.yaml"}),
        progress_percent=50.0,
        progress_json=None,
        created_at=now,
        started_at=now,
    )
    insert_job(db_conn, apply_job)
    jobs.append(apply_job)

    # Create transcode job (failed)
    transcode_job = Job(
        id=str(uuid.uuid4()),
        file_id=2,
        file_path="/media/videos/video.mp4",
        job_type=JobType.TRANSCODE,
        status=JobStatus.FAILED,
        priority=100,
        policy_name="compress",
        policy_json=json.dumps({"codec": "hevc"}),
        progress_percent=25.0,
        progress_json=None,
        created_at=now,
        started_at=now,
        completed_at=now,
        error_message="Transcoding failed: disk full",
    )
    insert_job(db_conn, transcode_job)
    jobs.append(transcode_job)

    return jobs


class TestParseRelativeTime:
    """Tests for relative time parsing."""

    def test_parse_days(self) -> None:
        """Parse days relative time."""
        result = parse_relative_time("1d")
        now = datetime.now(timezone.utc)
        assert (now - result).days == 1

    def test_parse_weeks(self) -> None:
        """Parse weeks relative time."""
        result = parse_relative_time("1w")
        now = datetime.now(timezone.utc)
        assert (now - result).days == 7

    def test_parse_hours(self) -> None:
        """Parse hours relative time."""
        result = parse_relative_time("2h")
        now = datetime.now(timezone.utc)
        diff = now - result
        assert 7000 < diff.total_seconds() < 7300  # ~2 hours

    def test_parse_multiple_units(self) -> None:
        """Parse multi-digit values."""
        result = parse_relative_time("30d")
        now = datetime.now(timezone.utc)
        assert (now - result).days == 30

    def test_invalid_format(self) -> None:
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid relative time format"):
            parse_relative_time("invalid")

    def test_invalid_unit(self) -> None:
        """Invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid relative time format"):
            parse_relative_time("1x")


class TestGetJobsFiltered:
    """Tests for get_jobs_filtered() function."""

    def test_filter_all(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Get all jobs without filters."""
        jobs = get_jobs_filtered(db_conn)
        assert len(jobs) == len(sample_jobs)

    def test_filter_by_status(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Filter by job status."""
        jobs = get_jobs_filtered(db_conn, status=JobStatus.FAILED)
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.FAILED

    def test_filter_by_type(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Filter by job type."""
        jobs = get_jobs_filtered(db_conn, job_type=JobType.SCAN)
        assert len(jobs) == 1
        assert jobs[0].job_type == JobType.SCAN

    def test_filter_by_since(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Filter by since timestamp."""
        # All jobs should be recent
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        jobs = get_jobs_filtered(db_conn, since=yesterday)
        assert len(jobs) == len(sample_jobs)

        # Future date should return none
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        jobs = get_jobs_filtered(db_conn, since=future)
        assert len(jobs) == 0

    def test_filter_with_limit(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Limit number of results."""
        jobs = get_jobs_filtered(db_conn, limit=1)
        assert len(jobs) == 1

    def test_combined_filters(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Combine multiple filters."""
        jobs = get_jobs_filtered(
            db_conn,
            status=JobStatus.COMPLETED,
            job_type=JobType.SCAN,
        )
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.COMPLETED
        assert jobs[0].job_type == JobType.SCAN

    def test_search_filter(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Filter by search term in file_path."""
        # Search for a substring that matches one job
        jobs = get_jobs_filtered(db_conn, search="movie.mkv")
        assert len(jobs) >= 1
        assert all("movie.mkv" in j.file_path.lower() for j in jobs)

    def test_search_filter_case_insensitive(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Search is case-insensitive."""
        jobs_upper = get_jobs_filtered(db_conn, search="MOVIE")
        jobs_lower = get_jobs_filtered(db_conn, search="movie")
        # Both should return the same results
        assert len(jobs_upper) == len(jobs_lower)

    def test_search_filter_partial_match(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Search matches partial strings."""
        jobs = get_jobs_filtered(db_conn, search="video")
        # Should match paths containing 'video'
        for job in jobs:
            assert "video" in job.file_path.lower()

    def test_sort_by_created_at_desc(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Sort by created_at descending (default)."""
        jobs = get_jobs_filtered(db_conn, sort_by="created_at", sort_order="desc")
        assert len(jobs) > 1
        # Verify descending order
        for i in range(len(jobs) - 1):
            assert jobs[i].created_at >= jobs[i + 1].created_at

    def test_sort_by_created_at_asc(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Sort by created_at ascending."""
        jobs = get_jobs_filtered(db_conn, sort_by="created_at", sort_order="asc")
        assert len(jobs) > 1
        # Verify ascending order
        for i in range(len(jobs) - 1):
            assert jobs[i].created_at <= jobs[i + 1].created_at

    def test_sort_by_status(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Sort by status column."""
        jobs = get_jobs_filtered(db_conn, sort_by="status", sort_order="asc")
        assert len(jobs) > 1
        # Verify status values are in order
        statuses = [j.status.value for j in jobs]
        assert statuses == sorted(statuses)

    def test_sort_by_file_path(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Sort by file_path column."""
        jobs = get_jobs_filtered(db_conn, sort_by="file_path", sort_order="asc")
        assert len(jobs) > 1
        # Verify paths are in order
        paths = [j.file_path for j in jobs]
        assert paths == sorted(paths)

    def test_invalid_sort_column_uses_default(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Invalid sort column falls back to created_at."""
        # This should not raise, but use default sorting
        jobs = get_jobs_filtered(db_conn, sort_by="invalid_column", sort_order="desc")
        # Default is created_at DESC
        assert len(jobs) == len(sample_jobs)
        # Should be in created_at desc order
        for i in range(len(jobs) - 1):
            assert jobs[i].created_at >= jobs[i + 1].created_at

    def test_search_with_sort(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Combine search with sort."""
        jobs = get_jobs_filtered(
            db_conn,
            search="video",
            sort_by="file_path",
            sort_order="asc",
        )
        # All should match search
        for job in jobs:
            assert "video" in job.file_path.lower()
        # Should be sorted by file_path
        if len(jobs) > 1:
            paths = [j.file_path for j in jobs]
            assert paths == sorted(paths)

    def test_search_escapes_percent_wildcard(self, db_conn: sqlite3.Connection) -> None:
        """Search with % matches literally, not as wildcard."""
        now = datetime.now(timezone.utc).isoformat()
        # Insert job with literal % in path
        job = Job(
            id=str(uuid.uuid4()),
            file_id=99,
            file_path="/videos/100%_complete.mkv",
            job_type=JobType.APPLY,
            status=JobStatus.COMPLETED,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=100.0,
            progress_json=None,
            created_at=now,
        )
        insert_job(db_conn, job)
        db_conn.commit()

        jobs = get_jobs_filtered(db_conn, search="100%")
        assert len(jobs) == 1
        assert "100%" in jobs[0].file_path

    def test_search_escapes_underscore_wildcard(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Search with _ matches literally, not as single-char wildcard."""
        now = datetime.now(timezone.utc).isoformat()
        job1 = Job(
            id=str(uuid.uuid4()),
            file_id=100,
            file_path="/videos/file_v1.mkv",
            job_type=JobType.APPLY,
            status=JobStatus.COMPLETED,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=100.0,
            progress_json=None,
            created_at=now,
        )
        job2 = Job(
            id=str(uuid.uuid4()),
            file_id=101,
            file_path="/videos/fileXv1.mkv",
            job_type=JobType.APPLY,
            status=JobStatus.COMPLETED,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=100.0,
            progress_json=None,
            created_at=now,
        )
        insert_job(db_conn, job1)
        insert_job(db_conn, job2)
        db_conn.commit()

        # Search for underscore - should only match file_v1, not fileXv1
        jobs = get_jobs_filtered(db_conn, search="_v1")
        assert len(jobs) == 1
        assert "_v1" in jobs[0].file_path

    def test_search_escapes_bracket(self, db_conn: sqlite3.Connection) -> None:
        """Search with [ matches literally, not as character class."""
        now = datetime.now(timezone.utc).isoformat()
        job = Job(
            id=str(uuid.uuid4()),
            file_id=102,
            file_path="/videos/test[1].mkv",
            job_type=JobType.APPLY,
            status=JobStatus.COMPLETED,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=100.0,
            progress_json=None,
            created_at=now,
        )
        insert_job(db_conn, job)
        db_conn.commit()

        jobs = get_jobs_filtered(db_conn, search="[1]")
        assert len(jobs) == 1
        assert "[1]" in jobs[0].file_path

    def test_sort_by_duration_nulls_last(self, db_conn: sqlite3.Connection) -> None:
        """Duration sort places running jobs (NULL completed_at) at end."""
        now = datetime.now(timezone.utc)
        # Create completed job with short duration
        completed_job = Job(
            id=str(uuid.uuid4()),
            file_id=110,
            file_path="/videos/short.mkv",
            job_type=JobType.APPLY,
            status=JobStatus.COMPLETED,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=100.0,
            progress_json=None,
            created_at=now.isoformat(),
            started_at=now.isoformat(),
            completed_at=(now + timedelta(seconds=30)).isoformat(),
        )
        # Create running job (no completed_at)
        running_job = Job(
            id=str(uuid.uuid4()),
            file_id=111,
            file_path="/videos/running.mkv",
            job_type=JobType.APPLY,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=50.0,
            progress_json=None,
            created_at=now.isoformat(),
            started_at=now.isoformat(),
            completed_at=None,
        )
        insert_job(db_conn, completed_job)
        insert_job(db_conn, running_job)
        db_conn.commit()

        # Sort by duration ascending
        jobs = get_jobs_filtered(db_conn, sort_by="duration", sort_order="asc")

        # Find positions
        running = [j for j in jobs if j.completed_at is None]
        completed = [j for j in jobs if j.completed_at is not None]

        if running and completed:
            running_positions = [jobs.index(j) for j in running]
            completed_positions = [jobs.index(j) for j in completed]
            # Running jobs (NULL duration) should be after completed jobs
            assert min(running_positions) > max(completed_positions)


class TestGetJobsByIdPrefix:
    """Tests for get_jobs_by_id_prefix() function."""

    def test_full_id_match(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Find job by full ID."""
        job = sample_jobs[0]
        matches = get_jobs_by_id_prefix(db_conn, job.id)
        assert len(matches) == 1
        assert matches[0].id == job.id

    def test_prefix_match(
        self, db_conn: sqlite3.Connection, sample_jobs: list[Job]
    ) -> None:
        """Find job by ID prefix."""
        job = sample_jobs[0]
        matches = get_jobs_by_id_prefix(db_conn, job.id[:8])
        assert len(matches) >= 1
        assert any(m.id == job.id for m in matches)

    def test_no_match(self, db_conn: sqlite3.Connection) -> None:
        """No job matches nonexistent prefix."""
        matches = get_jobs_by_id_prefix(db_conn, "nonexistent")
        assert len(matches) == 0


class TestJobsCLIHelp:
    """Tests for CLI help commands (can run without database)."""

    def test_jobs_help(self) -> None:
        """Test that jobs --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["jobs", "--help"])
        assert result.exit_code == 0
        assert "Manage job queue" in result.output

    def test_jobs_list_help(self) -> None:
        """Test that jobs list --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["jobs", "list", "--help"])
        assert result.exit_code == 0
        assert "--status" in result.output
        assert "--type" in result.output
        assert "--since" in result.output
        assert "--format" in result.output

    def test_jobs_show_help(self) -> None:
        """Test that jobs show --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["jobs", "show", "--help"])
        assert result.exit_code == 0
        assert "JOB_ID" in result.output
        assert "--format" in result.output
