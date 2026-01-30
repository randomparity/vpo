"""Tests for worker prune job processing."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.schema import create_schema
from vpo.db.types import Job, JobStatus, JobType
from vpo.jobs.services.prune import PruneJobResult


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


def _make_prune_job() -> Job:
    """Create a minimal prune Job for testing."""
    return Job(
        id="test-prune-id",
        file_id=None,
        file_path="library",
        job_type=JobType.PRUNE,
        status=JobStatus.RUNNING,
        priority=50,
        policy_name=None,
        policy_json=None,
        progress_percent=0.0,
        progress_json=None,
        created_at="2025-01-01T00:00:00Z",
        started_at="2025-01-01T00:00:01Z",
        completed_at=None,
        worker_pid=None,
        worker_heartbeat=None,
        output_path=None,
        backup_path=None,
        error_message=None,
        files_affected_json=None,
        summary_json=None,
        log_path=None,
        origin=None,
        batch_id=None,
    )


class TestProcessPruneJob:
    """Tests for prune job processing in the worker."""

    @patch("vpo.jobs.worker.PruneJobService")
    def test_process_prune_job_calls_service(self, mock_cls, db_conn):
        """Worker creates PruneJobService and calls process()."""
        from vpo.jobs.worker import JobWorker

        mock_service = MagicMock()
        mock_service.process.return_value = PruneJobResult(success=True, files_pruned=2)
        mock_cls.return_value = mock_service

        worker = JobWorker(conn=db_conn)
        job = _make_prune_job()
        job_log = MagicMock()

        result = worker._process_prune_job(job, job_log)
        mock_cls.assert_called_once_with(db_conn)
        mock_service.process.assert_called_once_with(job_log=job_log)
        assert result.files_pruned == 2

    @patch("vpo.jobs.worker.PruneJobService")
    def test_process_prune_builds_summary(self, mock_cls, db_conn):
        """Summary JSON includes files_pruned count."""
        from vpo.jobs.worker import JobWorker

        mock_service = MagicMock()
        mock_service.process.return_value = PruneJobResult(success=True, files_pruned=7)
        mock_cls.return_value = mock_service

        worker = JobWorker(conn=db_conn)
        job = _make_prune_job()
        job_log = MagicMock()

        result = worker._process_prune_job(job, job_log)
        assert result.files_pruned == 7
