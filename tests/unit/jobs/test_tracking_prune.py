"""Tests for prune job tracking functions."""

import sqlite3

import pytest

from vpo.db.schema import create_schema
from vpo.db.types import JobStatus, JobType
from vpo.jobs.tracking import complete_prune_job, create_prune_job


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class TestCreatePruneJob:
    """Tests for create_prune_job."""

    def test_creates_job_with_prune_type(self, db_conn):
        job = create_prune_job(db_conn)
        assert job.job_type == JobType.PRUNE

    def test_sets_priority_50(self, db_conn):
        job = create_prune_job(db_conn)
        assert job.priority == 50

    def test_sets_file_path_to_library(self, db_conn):
        job = create_prune_job(db_conn)
        assert job.file_path == "library"

    def test_sets_running_status(self, db_conn):
        job = create_prune_job(db_conn)
        assert job.status == JobStatus.RUNNING


class TestCompletePruneJob:
    """Tests for complete_prune_job."""

    def test_success_marks_completed(self, db_conn):
        job = create_prune_job(db_conn)
        complete_prune_job(db_conn, job.id, {"files_pruned": 5})

        cursor = db_conn.execute(
            "SELECT status, progress_percent FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["status"] == "completed"
        assert row["progress_percent"] == 100.0

    def test_success_stores_summary_json(self, db_conn):
        job = create_prune_job(db_conn)
        complete_prune_job(db_conn, job.id, {"files_pruned": 3})

        cursor = db_conn.execute(
            "SELECT summary_json FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert '"files_pruned": 3' in row["summary_json"]

    def test_with_error_marks_failed(self, db_conn):
        job = create_prune_job(db_conn)
        complete_prune_job(
            db_conn, job.id, {"files_pruned": 0}, error_message="DB locked"
        )

        cursor = db_conn.execute(
            "SELECT status, error_message FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row["status"] == "failed"
        assert row["error_message"] == "DB locked"
