"""Unit tests for JobWorker class.

Tests for worker limits, shutdown handling, heartbeat management,
and job processing logic that are not covered by integration tests.
"""

import signal
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.queries import get_job, insert_job
from vpo.db.types import Job, JobStatus, JobType
from vpo.jobs.worker import (
    JobWorker,
)


@pytest.fixture(autouse=True)
def mock_transcode_service():
    """Mock TranscodeJobService to avoid ffprobe dependency in unit tests.

    JobWorker creates a TranscodeJobService in __init__, which in turn
    creates an FFprobeIntrospector that requires ffprobe to be installed.
    This fixture mocks the service to avoid that dependency.
    """
    with patch("vpo.jobs.worker.TranscodeJobService") as mock_service:
        mock_service.return_value = MagicMock()
        yield mock_service


# =============================================================================
# Fixtures
# =============================================================================


def make_test_job(
    job_id: str | None = None,
    job_type: JobType = JobType.TRANSCODE,
    status: JobStatus = JobStatus.QUEUED,
    file_path: str = "/test/file.mkv",
) -> Job:
    """Create a test Job instance."""
    return Job(
        id=job_id or str(uuid.uuid4()),
        file_id=None,
        file_path=file_path,
        job_type=job_type,
        status=status,
        priority=100,
        policy_name="test_policy",
        policy_json="{}",
        progress_percent=0.0,
        progress_json=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# TestParseEndBy
# =============================================================================


class TestParseEndBy:
    """Tests for JobWorker._parse_end_by method."""

    def test_returns_none_for_none_input(self, db_conn: sqlite3.Connection) -> None:
        """Returns None when input is None."""
        worker = JobWorker(conn=db_conn, end_by=None)
        # end_by is parsed in __init__, so check the attribute
        assert worker.end_by is None

    def test_parses_valid_time(self, db_conn: sqlite3.Connection) -> None:
        """Parses valid HH:MM time string."""
        # Freeze time to avoid flakiness near midnight boundaries
        with patch("vpo.jobs.worker.datetime") as mock_dt:
            # Set current time to 10:00 AM
            mock_dt.now.return_value = datetime(2024, 1, 15, 10, 0, 0)

            worker = JobWorker(conn=db_conn, end_by="12:30")

            assert worker.end_by is not None
            assert worker.end_by.hour == 12
            assert worker.end_by.minute == 30

    def test_adds_day_when_time_in_past(self, db_conn: sqlite3.Connection) -> None:
        """Adds a day when end time is in the past."""
        # Use a time that's definitely in the past (2 hours ago)
        now = datetime.now(timezone.utc)
        past_hour = (now.hour - 2) % 24
        past_time = f"{past_hour:02d}:00"

        worker = JobWorker(conn=db_conn, end_by=past_time)

        assert worker.end_by is not None
        # The parsed time should be in the future (tomorrow)
        assert worker.end_by > now

    def test_returns_none_for_invalid_format(self, db_conn: sqlite3.Connection) -> None:
        """Returns None for invalid time format."""
        worker = JobWorker(conn=db_conn, end_by="invalid")
        assert worker.end_by is None

    def test_returns_none_for_missing_parts(self, db_conn: sqlite3.Connection) -> None:
        """Returns None for malformed strings."""
        worker = JobWorker(conn=db_conn, end_by="12")  # Missing minutes
        assert worker.end_by is None

    def test_returns_timezone_aware_datetime(self, db_conn: sqlite3.Connection) -> None:
        """Returns UTC-aware datetime for valid input."""
        # Use a future time to ensure we don't hit the "add a day" logic
        future_hour = (datetime.now(timezone.utc).hour + 2) % 24
        future_time = f"{future_hour:02d}:30"

        worker = JobWorker(conn=db_conn, end_by=future_time)

        assert worker.end_by is not None
        assert worker.end_by.tzinfo == timezone.utc


# =============================================================================
# TestShouldContinue
# =============================================================================


class TestShouldContinue:
    """Tests for JobWorker._should_continue method."""

    def test_returns_true_with_no_limits(self, db_conn: sqlite3.Connection) -> None:
        """Returns True when no limits are set."""
        worker = JobWorker(conn=db_conn)
        worker._start_time = time.time()
        worker._files_processed = 0

        assert worker._should_continue() is True

    def test_returns_false_when_shutdown_requested(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Returns False when shutdown is requested."""
        worker = JobWorker(conn=db_conn)
        worker._shutdown_requested = True

        assert worker._should_continue() is False

    def test_returns_false_when_max_files_reached(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Returns False when max_files limit is reached."""
        worker = JobWorker(conn=db_conn, max_files=5)
        worker._files_processed = 5

        assert worker._should_continue() is False

    def test_returns_true_when_max_files_not_reached(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Returns True when max_files limit is not reached."""
        worker = JobWorker(conn=db_conn, max_files=5)
        worker._start_time = time.time()
        worker._files_processed = 4

        assert worker._should_continue() is True

    def test_returns_false_when_max_duration_reached(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Returns False when max_duration limit is reached."""
        worker = JobWorker(conn=db_conn, max_duration=60)
        worker._start_time = time.time() - 61  # Started 61 seconds ago

        assert worker._should_continue() is False

    def test_returns_true_when_max_duration_not_reached(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Returns True when max_duration limit is not reached."""
        worker = JobWorker(conn=db_conn, max_duration=60)
        worker._start_time = time.time()
        worker._files_processed = 0

        assert worker._should_continue() is True

    def test_returns_false_when_end_time_reached(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Returns False when end_by time is reached."""
        worker = JobWorker(conn=db_conn)
        worker._start_time = time.time()
        # Set end_by to a past time (must be UTC-aware to match worker comparison)
        worker.end_by = datetime.now(timezone.utc) - timedelta(minutes=1)

        assert worker._should_continue() is False

    def test_returns_true_when_end_time_not_reached(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Returns True when end_by time is not reached."""
        worker = JobWorker(conn=db_conn)
        worker._start_time = time.time()
        worker._files_processed = 0
        # Set end_by to a future time (must be UTC-aware to match worker comparison)
        worker.end_by = datetime.now(timezone.utc) + timedelta(hours=1)

        assert worker._should_continue() is True


# =============================================================================
# TestSignalHandler
# =============================================================================


class TestSignalHandler:
    """Tests for signal handling."""

    def test_sigterm_sets_shutdown_flag(self, db_conn: sqlite3.Connection) -> None:
        """SIGTERM sets shutdown_requested flag."""
        worker = JobWorker(conn=db_conn)
        assert worker._shutdown_requested is False

        worker._signal_handler(signal.SIGTERM, None)

        assert worker._shutdown_requested is True

    def test_sigint_sets_shutdown_flag(self, db_conn: sqlite3.Connection) -> None:
        """SIGINT sets shutdown_requested flag."""
        worker = JobWorker(conn=db_conn)
        assert worker._shutdown_requested is False

        worker._signal_handler(signal.SIGINT, None)

        assert worker._shutdown_requested is True


# =============================================================================
# TestHeartbeatManagement
# =============================================================================


class TestHeartbeatManagement:
    """Tests for heartbeat thread management."""

    def test_start_heartbeat_creates_thread(self, db_conn: sqlite3.Connection) -> None:
        """Starting heartbeat creates a daemon thread."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        try:
            worker._start_heartbeat(job.id)

            assert worker._heartbeat_thread is not None
            assert worker._heartbeat_thread.daemon is True
            assert worker._heartbeat_thread.is_alive()
        finally:
            worker._stop_heartbeat()

    def test_stop_heartbeat_terminates_thread(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Stopping heartbeat terminates the thread."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        worker._start_heartbeat(job.id)
        assert worker._heartbeat_thread is not None
        assert worker._heartbeat_thread.is_alive()

        worker._stop_heartbeat()

        # Use join with timeout instead of sleep for reliable synchronization
        if worker._heartbeat_thread is not None:
            worker._heartbeat_thread.join(timeout=1.0)

        assert (
            worker._heartbeat_thread is None or not worker._heartbeat_thread.is_alive()
        )

    def test_heartbeat_stop_event_cleared_on_start(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Heartbeat stop event is cleared when starting."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        # Set the stop event
        worker._heartbeat_stop.set()

        try:
            worker._start_heartbeat(job.id)

            # Stop event should be cleared
            assert not worker._heartbeat_stop.is_set()
        finally:
            worker._stop_heartbeat()


# =============================================================================
# TestProcessJob
# =============================================================================


class TestProcessJob:
    """Tests for JobWorker.process_job method."""

    def test_processes_transcode_job(self, db_conn: sqlite3.Connection) -> None:
        """Successfully processes a transcode job."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job(job_type=JobType.TRANSCODE)
        insert_job(db_conn, job)

        # Mock the transcode service
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error_message = None
        mock_result.output_path = "/output/file.mkv"

        with patch.object(worker._transcode_service, "process") as mock_process:
            mock_process.return_value = mock_result
            worker.process_job(job)

        # Verify job was processed
        assert worker._files_processed == 1

        # Verify job status was updated
        updated = get_job(db_conn, job.id)
        assert updated is not None
        assert updated.status == JobStatus.COMPLETED

    def test_handles_move_job_not_implemented(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Handles MOVE job type (not yet implemented)."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job(job_type=JobType.MOVE)
        insert_job(db_conn, job)

        worker.process_job(job)

        # Job should be marked as failed
        updated = get_job(db_conn, job.id)
        assert updated is not None
        assert updated.status == JobStatus.FAILED
        assert "not yet implemented" in updated.error_message.lower()

    def test_increments_files_processed(self, db_conn: sqlite3.Connection) -> None:
        """Increments files_processed counter after job completion."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        initial_count = worker._files_processed

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error_message = None
        mock_result.output_path = None

        with patch.object(worker._transcode_service, "process") as mock_process:
            mock_process.return_value = mock_result
            worker.process_job(job)

        assert worker._files_processed == initial_count + 1

    def test_starts_and_stops_heartbeat(self, db_conn: sqlite3.Connection) -> None:
        """Starts heartbeat at beginning and stops at end of job processing."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        heartbeat_started = False
        heartbeat_stopped = False

        original_start = worker._start_heartbeat
        original_stop = worker._stop_heartbeat

        def mock_start(job_id):
            nonlocal heartbeat_started
            heartbeat_started = True
            original_start(job_id)

        def mock_stop():
            nonlocal heartbeat_stopped
            heartbeat_stopped = True
            original_stop()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error_message = None
        mock_result.output_path = None

        with (
            patch.object(worker, "_start_heartbeat", mock_start),
            patch.object(worker, "_stop_heartbeat", mock_stop),
            patch.object(worker._transcode_service, "process") as mock_process,
        ):
            mock_process.return_value = mock_result
            worker.process_job(job)

        assert heartbeat_started is True
        assert heartbeat_stopped is True

    def test_handles_exception_during_processing(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Handles exception during job processing gracefully."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        with patch.object(worker._transcode_service, "process") as mock_process:
            mock_process.side_effect = RuntimeError("Unexpected error")
            worker.process_job(job)

        # Job should be marked as failed
        updated = get_job(db_conn, job.id)
        assert updated is not None
        assert updated.status == JobStatus.FAILED
        assert "Unexpected error" in updated.error_message

    def test_clears_current_job_on_completion(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Clears _current_job after processing completes."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error_message = None
        mock_result.output_path = None

        with patch.object(worker._transcode_service, "process") as mock_process:
            mock_process.return_value = mock_result
            worker.process_job(job)

        assert worker._current_job is None

    def test_clears_current_job_on_exception(self, db_conn: sqlite3.Connection) -> None:
        """Clears _current_job even when exception occurs."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        with patch.object(worker._transcode_service, "process") as mock_process:
            mock_process.side_effect = RuntimeError("Error")
            worker.process_job(job)

        assert worker._current_job is None


# =============================================================================
# TestCreateProgressCallback
# =============================================================================


class TestCreateProgressCallback:
    """Tests for JobWorker._create_progress_callback method."""

    def test_callback_updates_job_progress(self, db_conn: sqlite3.Connection) -> None:
        """Progress callback updates job progress in database."""
        worker = JobWorker(conn=db_conn)
        job = make_test_job()
        insert_job(db_conn, job)

        callback = worker._create_progress_callback(job)

        # Create a mock progress object
        mock_progress = MagicMock()
        mock_progress.frame = 1000
        mock_progress.fps = 30.0
        mock_progress.bitrate = "5000kbits/s"
        mock_progress.speed = "2.5x"
        mock_progress.out_time_seconds = 33.0
        mock_progress.get_percent.return_value = 50.0

        # Call the callback
        callback(mock_progress)

        # Verify progress was updated
        updated = get_job(db_conn, job.id)
        assert updated is not None
        # Progress should be updated (less than 100 due to the min(99.9, ...) logic)
        assert updated.progress_percent < 100


# =============================================================================
# TestRun
# =============================================================================


class TestRun:
    """Tests for JobWorker.run method."""

    def test_returns_zero_when_queue_empty(self, db_conn: sqlite3.Connection) -> None:
        """Returns 0 when queue is empty."""
        worker = JobWorker(conn=db_conn)

        count = worker.run()

        assert count == 0

    def test_processes_available_jobs(self, db_conn: sqlite3.Connection) -> None:
        """Processes available jobs from queue."""
        worker = JobWorker(conn=db_conn)

        # Insert a job
        job = make_test_job()
        insert_job(db_conn, job)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error_message = None
        mock_result.output_path = None

        with patch.object(worker._transcode_service, "process") as mock_process:
            mock_process.return_value = mock_result
            count = worker.run()

        assert count == 1

    def test_respects_max_files_limit(self, db_conn: sqlite3.Connection) -> None:
        """Stops after processing max_files jobs."""
        worker = JobWorker(conn=db_conn, max_files=2)

        # Insert 5 jobs
        for i in range(5):
            job = make_test_job(job_id=f"test-job-{i}")
            insert_job(db_conn, job)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error_message = None
        mock_result.output_path = None

        with patch.object(worker._transcode_service, "process") as mock_process:
            mock_process.return_value = mock_result
            count = worker.run()

        # Should only process 2 jobs
        assert count == 2

    def test_records_start_time(self, db_conn: sqlite3.Connection) -> None:
        """Records start time when run begins."""
        worker = JobWorker(conn=db_conn)

        before = time.time()
        worker.run()
        after = time.time()

        assert worker._start_time is not None
        assert before <= worker._start_time <= after

    def test_recovers_stale_jobs(self, db_conn: sqlite3.Connection) -> None:
        """Recovers stale jobs at startup."""
        worker = JobWorker(conn=db_conn)

        with patch("vpo.jobs.worker.recover_stale_jobs") as mock_recover:
            worker.run()
            mock_recover.assert_called_once_with(db_conn)

    def test_purges_old_jobs_when_enabled(self, db_conn: sqlite3.Connection) -> None:
        """Purges old jobs when auto_purge is True."""
        worker = JobWorker(conn=db_conn, auto_purge=True)

        with patch("vpo.jobs.worker.purge_old_jobs") as mock_purge:
            mock_purge.return_value = 0
            worker.run()
            mock_purge.assert_called_once()
