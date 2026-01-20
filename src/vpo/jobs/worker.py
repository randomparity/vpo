"""Job worker for processing queued jobs.

This module provides the worker that processes jobs from the queue:
- Configurable limits (max files, max duration, end time)
- Graceful shutdown on SIGTERM/SIGINT
- Heartbeat updates to prevent stale job recovery
- Progress reporting during transcoding
"""

import json
import logging
import os
import signal
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from vpo.db import (
    Job,
    JobStatus,
    JobType,
    update_job_progress,
)
from vpo.db.connection import get_connection
from vpo.jobs.logs import JobLogWriter
from vpo.jobs.maintenance import purge_old_jobs
from vpo.jobs.queue import (
    claim_next_job,
    recover_stale_jobs,
    release_job,
    update_heartbeat,
)
from vpo.jobs.services import (
    ProcessJobService,
    TranscodeJobService,
)
from vpo.tools.ffmpeg_progress import FFmpegProgress

logger = logging.getLogger(__name__)

# Heartbeat interval (seconds)
HEARTBEAT_INTERVAL = 30
MAX_HEARTBEAT_FAILURES = 3  # Abort job after this many consecutive heartbeat failures


class WorkerShutdownRequested(Exception):
    """Exception raised when worker shutdown is requested."""

    pass


class JobWorker:
    """Worker for processing jobs from the queue."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        max_files: int | None = None,
        max_duration: int | None = None,
        end_by: str | None = None,
        cpu_cores: int | None = None,
        auto_purge: bool = True,
        retention_days: int = 30,
    ) -> None:
        """Initialize the job worker.

        Args:
            conn: Database connection.
            max_files: Maximum files to process (None = unlimited).
            max_duration: Maximum duration in seconds (None = unlimited).
            end_by: End time in HH:MM format (None = run until complete).
            cpu_cores: CPU cores to use for transcoding.
            auto_purge: Whether to purge old jobs on start.
            retention_days: Days to keep completed jobs.
        """
        self.conn = conn
        self.max_files = max_files
        self.max_duration = max_duration
        self.end_by = self._parse_end_by(end_by)
        self.cpu_cores = cpu_cores
        self.auto_purge = auto_purge
        self.retention_days = retention_days

        # Extract db_path from connection for heartbeat thread
        # PRAGMA database_list returns (seq, name, file) tuples
        cursor = conn.execute("PRAGMA database_list")
        row = cursor.fetchone()
        self._db_path = Path(row[2]) if row and row[2] else None

        # Cache services for reuse across jobs
        self._transcode_service = TranscodeJobService(cpu_cores=cpu_cores)
        self._process_service: ProcessJobService | None = None

        # State
        self._shutdown_requested = False
        self._current_job: Job | None = None
        self._files_processed = 0
        self._start_time: float | None = None

        # Heartbeat thread
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()
        self._consecutive_heartbeat_failures = 0

        # Setup signal handlers
        self._setup_signal_handlers()

    def _parse_end_by(self, end_by: str | None) -> datetime | None:
        """Parse end_by time string to datetime."""
        if end_by is None:
            return None

        try:
            hour, minute = map(int, end_by.split(":"))
            now = datetime.now(timezone.utc)
            end_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If end time is in the past, assume it's tomorrow
            if end_time <= now:
                from datetime import timedelta

                end_time += timedelta(days=1)

            return end_time
        except (ValueError, AttributeError):
            logger.warning("Invalid end_by format: %s (expected HH:MM)", end_by)
            return None

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown signal handlers."""
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, requesting shutdown...", sig_name)
        self._shutdown_requested = True

    def _should_continue(self) -> bool:
        """Check if worker should continue processing."""
        if self._shutdown_requested:
            return False

        # Check max files
        if self.max_files is not None and self._files_processed >= self.max_files:
            logger.info("Reached max files limit (%d)", self.max_files)
            return False

        # Check max duration
        if self.max_duration is not None and self._start_time is not None:
            elapsed = time.time() - self._start_time
            if elapsed >= self.max_duration:
                logger.info(
                    "Reached max duration limit (%d seconds)", self.max_duration
                )
                return False

        # Check end time
        if self.end_by is not None:
            if datetime.now(timezone.utc) >= self.end_by:
                logger.info("Reached end time (%s)", self.end_by.strftime("%H:%M"))
                return False

        return True

    def _start_heartbeat(self, job_id: str) -> None:
        """Start heartbeat thread for a job.

        Uses a separate database connection to avoid interfering with
        transactions on the main connection. This prevents the heartbeat
        commit() from accidentally committing a partial transaction.

        Tracks consecutive heartbeat failures and requests shutdown if
        MAX_HEARTBEAT_FAILURES is reached, preventing duplicate job execution.
        """
        self._heartbeat_stop.clear()
        self._consecutive_heartbeat_failures = 0

        def heartbeat_loop() -> None:
            # Use separate connection for heartbeat to avoid transaction interference
            if self._db_path is None:
                logger.warning("Cannot start heartbeat: db_path not available")
                return

            with get_connection(self._db_path) as heartbeat_conn:
                while not self._heartbeat_stop.wait(HEARTBEAT_INTERVAL):
                    try:
                        update_heartbeat(heartbeat_conn, job_id, os.getpid())
                        self._consecutive_heartbeat_failures = 0  # Reset on success
                    except Exception as e:
                        self._consecutive_heartbeat_failures += 1
                        logger.error(
                            "Heartbeat failed (%d/%d): %s",
                            self._consecutive_heartbeat_failures,
                            MAX_HEARTBEAT_FAILURES,
                            e,
                        )
                        max_failures = MAX_HEARTBEAT_FAILURES
                        if self._consecutive_heartbeat_failures >= max_failures:
                            logger.critical(
                                "Max heartbeat failures reached, requesting shutdown"
                            )
                            self._shutdown_requested = True
                            break

        self._heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            daemon=True,
            name=f"heartbeat-{job_id[:8]}",
        )
        self._heartbeat_thread.start()
        logger.debug(
            "Heartbeat thread started for job %s (interval=%ds)",
            job_id[:8],
            HEARTBEAT_INTERVAL,
        )

    def _stop_heartbeat(self) -> None:
        """Stop heartbeat thread."""
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            thread_name = self._heartbeat_thread.name
            self._heartbeat_thread.join(timeout=1.0)
            if self._heartbeat_thread.is_alive():
                logger.warning(
                    "Heartbeat thread %s did not stop within timeout",
                    thread_name,
                )
            else:
                logger.debug("Heartbeat thread %s stopped", thread_name)
            self._heartbeat_thread = None

    def _purge_old_jobs(self) -> None:
        """Purge old completed/failed/cancelled jobs."""
        count = purge_old_jobs(
            self.conn,
            self.retention_days,
            auto_purge=self.auto_purge,
        )
        if count > 0:
            logger.info("Purged %d old job(s)", count)

    def _create_progress_callback(self, job: Job):
        """Create a progress callback for a job."""

        def callback(progress: FFmpegProgress) -> None:
            # Get duration from job policy
            percent = progress.get_percent(None)  # TODO: Get actual duration
            if progress.out_time_seconds:
                percent = min(99.9, progress.get_percent(3600))  # Estimate

            try:
                update_job_progress(
                    self.conn,
                    job.id,
                    percent,
                    json.dumps(
                        {
                            "frame": progress.frame,
                            "fps": progress.fps,
                            "bitrate": progress.bitrate,
                            "speed": progress.speed,
                            "out_time_seconds": progress.out_time_seconds,
                        }
                    ),
                )
            except Exception as e:
                logger.warning("Failed to update job progress: %s", e)

        return callback

    def _process_transcode_job(
        self, job: Job, job_log: JobLogWriter | None = None
    ) -> tuple[bool, str | None, str | None]:
        """Process a transcode job.

        Args:
            job: The job to process.
            job_log: Optional log writer for this job.

        Returns:
            Tuple of (success, error_message, output_path).
        """
        result = self._transcode_service.process(
            job,
            progress_callback=self._create_progress_callback(job),
            job_log=job_log,
        )
        return result.success, result.error_message, result.output_path

    def _process_workflow_job(
        self, job: Job, job_log: JobLogWriter | None = None
    ) -> tuple[bool, str | None, str | None]:
        """Process a workflow (PROCESS) job.

        Args:
            job: The job to process.
            job_log: Optional log writer for this job.

        Returns:
            Tuple of (success, error_message, output_path).
        """
        # Lazy init process service (needs conn)
        if self._process_service is None:
            self._process_service = ProcessJobService(self.conn)

        result = self._process_service.process(job, job_log)
        return result.success, result.error_message, None

    def process_job(self, job: Job) -> None:
        """Process a single job.

        Args:
            job: The job to process.
        """
        self._current_job = job
        self._start_heartbeat(job.id)
        job_start_time = time.time()

        # Create job log file
        job_log: JobLogWriter | None = None
        try:
            job_log = JobLogWriter(job.id)
            job_log.__enter__()

            # Update job with log path
            self._update_job_log_path(job.id, job_log.relative_path)
        except Exception as e:
            logger.warning("Failed to create job log: %s", e)
            job_log = None

        try:
            logger.info("Processing job %s: %s", job.id[:8], job.file_path)

            # Write log header
            if job_log:
                job_log.write_header(
                    job.job_type.value,
                    job.file_path,
                    policy=job.policy_name or "default",
                )

            if job.job_type == JobType.TRANSCODE:
                success, error_msg, output_path = self._process_transcode_job(
                    job, job_log
                )
            elif job.job_type == JobType.PROCESS:
                success, error_msg, output_path = self._process_workflow_job(
                    job, job_log
                )
            elif job.job_type == JobType.MOVE:
                # TODO: Implement move job processing
                success = False
                error_msg = "Move jobs not yet implemented"
                output_path = None
                if job_log:
                    job_log.write_error(error_msg)
            else:
                success = False
                error_msg = f"Unknown job type: {job.job_type}"
                output_path = None
                if job_log:
                    job_log.write_error(error_msg)

            # Write log footer
            if job_log:
                duration = time.time() - job_start_time
                job_log.write_footer(success, duration)

            # Release job with result
            status = JobStatus.COMPLETED if success else JobStatus.FAILED
            release_job(
                self.conn,
                job.id,
                status,
                error_message=error_msg,
                output_path=output_path,
            )

            if success:
                logger.info("Job %s completed successfully", job.id[:8])
            else:
                logger.error("Job %s failed: %s", job.id[:8], error_msg)

        except Exception as e:
            logger.exception("Job %s failed with exception", job.id[:8])
            if job_log:
                job_log.write_error("Unexpected exception", e)
                job_log.write_footer(False, time.time() - job_start_time)
            release_job(
                self.conn,
                job.id,
                JobStatus.FAILED,
                error_message=str(e),
            )

        finally:
            if job_log:
                job_log.close()
            self._stop_heartbeat()
            self._current_job = None
            self._files_processed += 1

    def _update_job_log_path(self, job_id: str, log_path: str | None) -> None:
        """Update the job's log_path in the database.

        Args:
            job_id: The job UUID.
            log_path: Relative path to the log file.
        """
        if log_path is None:
            return
        try:
            self.conn.execute(
                "UPDATE jobs SET log_path = ? WHERE id = ?",
                (log_path, job_id),
            )
            self.conn.commit()
        except Exception as e:
            logger.warning("Failed to update job log path: %s", e)

    def run(self) -> int:
        """Run the worker, processing jobs until limits reached or queue empty.

        Returns:
            Number of jobs processed.
        """
        self._start_time = time.time()
        self._files_processed = 0

        # Build config summary for logging
        config_parts = [f"PID={os.getpid()}"]
        if self.max_files is not None:
            config_parts.append(f"max_files={self.max_files}")
        if self.max_duration is not None:
            config_parts.append(f"max_duration={self.max_duration}s")
        if self.end_by is not None:
            config_parts.append(f"end_by={self.end_by.strftime('%H:%M')}")
        if self.cpu_cores is not None:
            config_parts.append(f"cpu_cores={self.cpu_cores}")
        config_parts.append(f"auto_purge={self.auto_purge}")

        logger.info("Starting job worker: %s", ", ".join(config_parts))

        # Purge old jobs
        self._purge_old_jobs()

        # Recover stale jobs
        recover_stale_jobs(self.conn)

        # Process jobs
        while self._should_continue():
            job = claim_next_job(self.conn)
            if job is None:
                logger.info("Queue is empty")
                break

            self.process_job(job)

        # Log summary
        elapsed = time.time() - self._start_time
        logger.info(
            "Worker finished: %d job(s) in %.1f seconds",
            self._files_processed,
            elapsed,
        )

        return self._files_processed
