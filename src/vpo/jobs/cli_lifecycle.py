"""Job lifecycle implementation for CLI batch processing.

This module provides CLIJobLifecycle, which creates and manages job records
for CLI batch processing operations, bridging the CLI to the unified
workflow abstractions.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from vpo.jobs.logs import JobLogWriter
from vpo.jobs.runner import JobLifecycle
from vpo.jobs.tracking import (
    complete_process_job,
    create_process_job,
    fail_job_with_retry,
)

if TYPE_CHECKING:
    from vpo.policy.types import FileProcessingResult

logger = logging.getLogger(__name__)


class CLIJobLifecycle:
    """Job lifecycle for CLI batch processing.

    Creates job records on start and updates them on completion/failure.
    Used with WorkflowRunner.for_cli() factory method.

    Example:
        lifecycle = CLIJobLifecycle(
            conn, batch_id=batch_id, policy_name="my-policy.yaml"
        )
        runner = WorkflowRunner.for_cli(conn, policy, config, lifecycle)
        result = runner.run_single(file_path, file_id=file_id)

    With log saving:
        lifecycle = CLIJobLifecycle(
            conn, batch_id=batch_id, policy_name="my-policy.yaml", save_logs=True
        )
        runner = WorkflowRunner.for_cli(conn, policy, config, lifecycle,
                                        job_log=lifecycle.job_log)
        try:
            result = runner.run_single(file_path, file_id=file_id)
        finally:
            lifecycle.close_job_log()
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        batch_id: str | None = None,
        policy_name: str,
        save_logs: bool = False,
    ) -> None:
        """Initialize CLI job lifecycle.

        Args:
            conn: Database connection for job operations.
            batch_id: UUID grouping CLI batch operations (None if dry-run).
            policy_name: Name/path of the policy being used.
            save_logs: If True, create log files like daemon mode.
        """
        self.conn = conn
        self.batch_id = batch_id
        self.policy_name = policy_name
        self.save_logs = save_logs
        self._current_job_log: JobLogWriter | None = None

    def on_job_start(
        self,
        file_path: Path,
        policy_name: str,
        file_id: int | None = None,
    ) -> str | None:
        """Create a process job record and return its ID.

        Args:
            file_path: Path to the file being processed.
            policy_name: Name of the policy being applied
                (may override instance default).
            file_id: Database ID of the file (if known).

        Returns:
            Job ID of the created job record.
        """
        job = create_process_job(
            self.conn,
            file_id,
            str(file_path),
            policy_name or self.policy_name,
            origin="cli",
            batch_id=self.batch_id,
        )
        self.conn.commit()

        # Create log file if save_logs is enabled
        if self.save_logs:
            try:
                self._current_job_log = JobLogWriter(job.id)
                self._current_job_log.__enter__()
                self._update_job_log_path(job.id, self._current_job_log.relative_path)
            except Exception as e:
                logger.warning("Failed to create job log: %s", e)
                self._current_job_log = None

        return job.id

    @property
    def job_log(self) -> JobLogWriter | None:
        """Get the current job log writer.

        Returns:
            The JobLogWriter for the current job, or None if not saving logs.
        """
        return self._current_job_log

    def close_job_log(self) -> None:
        """Close the current job log writer.

        Should be called in a finally block after processing completes.
        """
        if self._current_job_log is not None:
            self._current_job_log.close()
            self._current_job_log = None

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

    def on_job_complete(
        self,
        job_id: str | None,
        result: FileProcessingResult,
    ) -> None:
        """Update job record with completion status.

        Args:
            job_id: Job ID from on_job_start, or None.
            result: The processing result.
        """
        if not job_id:
            return

        complete_process_job(
            self.conn,
            job_id,
            success=result.success,
            phases_completed=result.phases_completed,
            total_changes=result.total_changes,
            error_message=result.error_message,
            stats_id=result.stats_id,
        )
        self.conn.commit()

    def on_job_fail(self, job_id: str | None, error: str) -> None:
        """Update job record with failure status using retry logic.

        Uses fail_job_with_retry to handle transient database errors
        gracefully during error handling paths.

        Args:
            job_id: Job ID from on_job_start, or None.
            error: Error message describing the failure.
        """
        if not job_id:
            return

        success = fail_job_with_retry(self.conn, job_id, error)
        if not success:
            # Job failure recording itself failed - this is critical
            # The job will remain in RUNNING state (orphaned)
            logger.error(
                "CRITICAL: Job %s may be orphaned - failed to record failure",
                job_id,
            )


# Type assertion: CLIJobLifecycle implements JobLifecycle protocol
_: type[JobLifecycle] = CLIJobLifecycle  # type: ignore[assignment]
