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
from vpo.cli.jobs import _parse_relative_date
from vpo.db.models import (
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


class TestParseRelativeDate:
    """Tests for relative date parsing."""

    def test_parse_days(self) -> None:
        """Parse days relative date."""
        result = _parse_relative_date("1d")
        now = datetime.now(timezone.utc)
        assert (now - result).days == 1

    def test_parse_weeks(self) -> None:
        """Parse weeks relative date."""
        result = _parse_relative_date("1w")
        now = datetime.now(timezone.utc)
        assert (now - result).days == 7

    def test_parse_hours(self) -> None:
        """Parse hours relative date."""
        result = _parse_relative_date("2h")
        now = datetime.now(timezone.utc)
        diff = now - result
        assert 7000 < diff.total_seconds() < 7300  # ~2 hours

    def test_parse_multiple_units(self) -> None:
        """Parse multi-digit values."""
        result = _parse_relative_date("30d")
        now = datetime.now(timezone.utc)
        assert (now - result).days == 30

    def test_invalid_format(self) -> None:
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid relative date"):
            _parse_relative_date("invalid")

    def test_invalid_unit(self) -> None:
        """Invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid relative date"):
            _parse_relative_date("1x")


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
        assert "--json" in result.output

    def test_jobs_show_help(self) -> None:
        """Test that jobs show --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["jobs", "show", "--help"])
        assert result.exit_code == 0
        assert "JOB_ID" in result.output
        assert "--json" in result.output
