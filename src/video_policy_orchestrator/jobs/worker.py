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

from video_policy_orchestrator.db.models import (
    Job,
    JobStatus,
    JobType,
    delete_old_jobs,
    update_job_progress,
)
from video_policy_orchestrator.executor.move import MoveExecutor
from video_policy_orchestrator.executor.transcode import (
    TranscodeExecutor,
)
from video_policy_orchestrator.introspector import FFprobeIntrospector
from video_policy_orchestrator.jobs.logs import JobLogWriter
from video_policy_orchestrator.jobs.progress import FFmpegProgress
from video_policy_orchestrator.jobs.queue import (
    claim_next_job,
    recover_stale_jobs,
    release_job,
    update_heartbeat,
)
from video_policy_orchestrator.metadata.parser import parse_filename
from video_policy_orchestrator.metadata.templates import parse_template
from video_policy_orchestrator.policy.models import TranscodePolicyConfig

logger = logging.getLogger(__name__)

# Heartbeat interval (seconds)
HEARTBEAT_INTERVAL = 30


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

        # State
        self._shutdown_requested = False
        self._current_job: Job | None = None
        self._files_processed = 0
        self._start_time: float | None = None

        # Heartbeat thread
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()

        # Setup signal handlers
        self._setup_signal_handlers()

    def _parse_end_by(self, end_by: str | None) -> datetime | None:
        """Parse end_by time string to datetime."""
        if end_by is None:
            return None

        try:
            hour, minute = map(int, end_by.split(":"))
            now = datetime.now()
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
            if datetime.now() >= self.end_by:
                logger.info("Reached end time (%s)", self.end_by.strftime("%H:%M"))
                return False

        return True

    def _start_heartbeat(self, job_id: str) -> None:
        """Start heartbeat thread for a job."""
        self._heartbeat_stop.clear()

        def heartbeat_loop():
            while not self._heartbeat_stop.wait(HEARTBEAT_INTERVAL):
                try:
                    update_heartbeat(self.conn, job_id, os.getpid())
                except Exception as e:
                    logger.error("Heartbeat failed: %s", e)

        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        """Stop heartbeat thread."""
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=1.0)
            self._heartbeat_thread = None

    def _purge_old_jobs(self) -> None:
        """Purge old completed/failed/cancelled jobs."""
        if not self.auto_purge:
            return

        from datetime import timedelta

        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        ).isoformat()

        count = delete_old_jobs(self.conn, cutoff)
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
        # Parse policy from job
        try:
            policy_data = json.loads(job.policy_json)
            policy = TranscodePolicyConfig(
                target_video_codec=policy_data.get("target_video_codec"),
                target_crf=policy_data.get("target_crf"),
                target_bitrate=policy_data.get("target_bitrate"),
                max_resolution=policy_data.get("max_resolution"),
                max_width=policy_data.get("max_width"),
                max_height=policy_data.get("max_height"),
                audio_preserve_codecs=tuple(
                    policy_data.get("audio_preserve_codecs", [])
                ),
                audio_transcode_to=policy_data.get("audio_transcode_to", "aac"),
                audio_transcode_bitrate=policy_data.get("audio_bitrate", "192k"),
                audio_downmix=policy_data.get("audio_downmix"),
            )
            if job_log:
                job_log.write_line(f"Parsed policy: {job.policy_name or 'default'}")
        except Exception as e:
            if job_log:
                job_log.write_error(f"Invalid policy JSON: {e}")
            return False, f"Invalid policy JSON: {e}", None

        # Get input file info
        input_path = Path(job.file_path)
        if not input_path.exists():
            error = f"Input file not found: {input_path}"
            if job_log:
                job_log.write_error(error)
            return False, error, None

        # Introspect file
        if job_log:
            job_log.write_section("Introspecting file")
        introspector = FFprobeIntrospector()
        result = introspector.introspect(input_path)
        if not result.success:
            error = f"Introspection failed: {result.error}"
            if job_log:
                job_log.write_error(error)
            return False, error, None

        if job_log:
            job_log.write_line(f"Container: {result.container_format}")
            job_log.write_line(f"Duration: {result.duration}s")
            job_log.write_line(f"Tracks: {len(result.tracks)}")

        # Get video track info
        video_track = next((t for t in result.tracks if t.track_type == "video"), None)
        if not video_track:
            error = "No video track found"
            if job_log:
                job_log.write_error(error)
            return False, error, None

        if job_log:
            job_log.write_line(
                f"Video: {video_track.codec} {video_track.width}x{video_track.height}"
            )

        # Determine output path
        output_dir = policy_data.get("output_dir")
        if output_dir:
            output_path = Path(output_dir) / input_path.name
        else:
            # Same directory with .transcoded suffix before extension
            stem = input_path.stem
            output_path = input_path.with_name(f"{stem}.transcoded{input_path.suffix}")

        if job_log:
            job_log.write_line(f"Output path: {output_path}")

        # Create executor and plan
        executor = TranscodeExecutor(
            policy=policy,
            cpu_cores=self.cpu_cores,
            progress_callback=self._create_progress_callback(job),
        )

        plan = executor.create_plan(
            input_path=input_path,
            output_path=output_path,
            video_codec=video_track.codec,
            video_width=video_track.width,
            video_height=video_track.height,
            duration_seconds=result.duration,
        )

        # Execute transcode
        if job_log:
            job_log.write_section("Executing transcode")
            job_log.write_line(f"Target codec: {policy.target_video_codec}")
            if policy.target_crf:
                job_log.write_line(f"Target CRF: {policy.target_crf}")
            if self.cpu_cores:
                job_log.write_line(f"CPU cores: {self.cpu_cores}")

        transcode_result = executor.execute(plan)

        if not transcode_result.success:
            if job_log:
                job_log.write_error(
                    f"Transcode failed: {transcode_result.error_message}"
                )
            return False, transcode_result.error_message, None

        if job_log:
            job_log.write_line("Transcode completed successfully")

        final_output_path = output_path

        # Handle destination template if specified
        destination_template = policy_data.get("destination")
        destination_base = policy_data.get("destination_base")

        if destination_template and transcode_result.output_path:
            if job_log:
                job_log.write_section("Moving to destination")
                job_log.write_line(f"Template: {destination_template}")

            try:
                # Parse metadata from filename
                metadata = parse_filename(input_path)
                metadata_dict = metadata.as_dict()

                # Parse and render template
                template = parse_template(destination_template)
                fallback = policy_data.get("destination_fallback", "Unknown")

                # Use base directory or input file's directory
                if destination_base:
                    base_dir = Path(destination_base)
                else:
                    base_dir = input_path.parent

                # Compute final destination
                dest_path = template.render_path(base_dir, metadata_dict, fallback)

                # Add filename to destination
                final_dest = dest_path / transcode_result.output_path.name

                if job_log:
                    job_log.write_line(f"Destination: {final_dest}")

                # Move file to destination
                move_executor = MoveExecutor(create_directories=True)
                move_plan = move_executor.create_plan(
                    source_path=transcode_result.output_path,
                    destination_path=final_dest,
                )

                move_result = move_executor.execute(move_plan)
                if move_result.success:
                    final_output_path = move_result.destination_path
                    logger.info("Moved output to: %s", final_output_path)
                    if job_log:
                        job_log.write_line(f"Moved to: {final_output_path}")
                else:
                    logger.warning(
                        "File movement failed: %s (transcoded file kept at: %s)",
                        move_result.error_message,
                        output_path,
                    )
                    if job_log:
                        job_log.write_error(f"Move failed: {move_result.error_message}")
            except Exception as e:
                logger.warning(
                    "Destination template processing failed: %s "
                    "(transcoded file kept at: %s)",
                    e,
                    output_path,
                )
                if job_log:
                    job_log.write_error(f"Template processing failed: {e}")

        return True, None, str(final_output_path)

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

        logger.info("Starting job worker (PID: %d)", os.getpid())

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
