"""Unified workflow runner for CLI and daemon modes.

This module provides a unified interface for running workflows across
different execution contexts, with pluggable job lifecycle management.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from vpo.core.phase_formatting import format_phase_details
from vpo.policy.types import FileProcessingResult, PhaseOutcome, PolicySchema
from vpo.workflow import WorkflowProcessor

if TYPE_CHECKING:
    from collections.abc import Callable

    from vpo.jobs.logs import JobLogWriter
    from vpo.tools.ffmpeg_progress import FFmpegProgress

logger = logging.getLogger(__name__)


class ErrorClassification(Enum):
    """Classification of workflow errors for retry decisions.

    Used by callers to determine whether retrying a failed operation
    might succeed or if the error is permanent.

    Values:
        TRANSIENT: Retry likely to succeed (locks, temp disk full).
        PERMANENT: Retry won't help (corrupt file, unsupported format).
        FATAL: System-level issue (missing tool, config error).
    """

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    FATAL = "fatal"


def classify_workflow_error(exception: Exception) -> ErrorClassification:
    """Classify an exception for retry decision making.

    Args:
        exception: The exception to classify.

    Returns:
        ErrorClassification indicating whether retry might succeed.

    Examples:
        >>> classify_workflow_error(FileNotFoundError("file.mkv"))
        ErrorClassification.PERMANENT

        >>> classify_workflow_error(sqlite3.OperationalError("database is locked"))
        ErrorClassification.TRANSIENT
    """
    # Permanent errors (file-specific issues that won't change on retry)
    if isinstance(exception, (FileNotFoundError, IsADirectoryError)):
        return ErrorClassification.PERMANENT

    # Transient errors (may succeed on retry)
    if isinstance(exception, (sqlite3.OperationalError, OSError, PermissionError)):
        error_msg = str(exception).casefold()
        if "locked" in error_msg or "busy" in error_msg:
            return ErrorClassification.TRANSIENT
        if "no space" in error_msg or "disk full" in error_msg:
            return ErrorClassification.TRANSIENT
        # Permission errors might be transient (file in use) or permanent
        if isinstance(exception, PermissionError):
            return ErrorClassification.TRANSIENT

    # Fatal errors (configuration/environment issues)
    if isinstance(exception, (ValueError, TypeError, AttributeError)):
        return ErrorClassification.FATAL

    # Default to permanent (conservative - don't retry unknown errors)
    return ErrorClassification.PERMANENT


@dataclass
class WorkflowRunnerConfig:
    """Configuration for workflow execution.

    Attributes:
        dry_run: Whether to preview changes without modifying files.
        verbose: Whether to emit verbose logging.
        selected_phases: Optional list of phases to execute (None = all).
        policy_name: Name of the policy for audit logging.
    """

    dry_run: bool = False
    verbose: bool = False
    selected_phases: list[str] | None = None
    policy_name: str = ""


@runtime_checkable
class JobLifecycle(Protocol):
    """Protocol for job lifecycle management.

    Implementations provide context-specific job creation and completion:
    - CLI: Creates job records and updates them on completion
    - Daemon: No-op (worker manages job lifecycle)
    - Tests: Mock or null implementation
    """

    def on_job_start(
        self, file_path: Path, policy_name: str, file_id: int | None = None
    ) -> str | None:
        """Called when processing starts for a file.

        Args:
            file_path: Path to the file being processed.
            policy_name: Name of the policy being applied.
            file_id: Database ID of the file (if known).

        Returns:
            Job ID if a job record was created, None otherwise.
        """
        ...

    def on_job_complete(
        self,
        job_id: str | None,
        result: FileProcessingResult,
    ) -> None:
        """Called when processing completes for a file.

        Args:
            job_id: Job ID from on_job_start, or None.
            result: The processing result.
        """
        ...

    def on_job_fail(self, job_id: str | None, error: str) -> None:
        """Called when processing fails with an exception.

        Args:
            job_id: Job ID from on_job_start, or None.
            error: Error message describing the failure.
        """
        ...


class NullJobLifecycle:
    """No-op job lifecycle for dry-run mode or tests."""

    def on_job_start(
        self, file_path: Path, policy_name: str, file_id: int | None = None
    ) -> str | None:
        """No-op: returns None (no job created)."""
        return None

    def on_job_complete(
        self,
        job_id: str | None,
        result: FileProcessingResult,
    ) -> None:
        """No-op."""
        pass

    def on_job_fail(self, job_id: str | None, error: str) -> None:
        """No-op."""
        pass


@dataclass
class WorkflowRunResult:
    """Result of a workflow run.

    Attributes:
        result: The file processing result from the workflow.
        job_id: Job ID if one was created, None otherwise.
        success: Whether the workflow completed successfully.
        error_classification: Classification of error for retry decisions (if failed).
    """

    result: FileProcessingResult
    job_id: str | None = None
    error_classification: ErrorClassification | None = None
    success: bool = field(init=False)

    def __post_init__(self) -> None:
        """Set success based on result."""
        self.success = self.result.success


class WorkflowRunner:
    """Unified workflow runner for single file processing.

    Encapsulates the common workflow execution pattern used by both
    CLI and daemon, with pluggable job lifecycle management.

    Prefer using the factory methods for clarity:

    CLI mode (lifecycle manages job records):
        lifecycle = CLIJobLifecycle(conn, batch_id=batch_id, policy_name="policy.yaml")
        runner = WorkflowRunner.for_cli(conn, policy, config, lifecycle)
        result = runner.run_single(file_path, file_id=file_id)

    Daemon mode (worker manages job records):
        runner = WorkflowRunner.for_daemon(
            conn, policy, config, job_id=job.id,
            job_log=job_log, ffmpeg_progress_callback=callback
        )
        result = runner.run_single(file_path)
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        policy: PolicySchema,
        config: WorkflowRunnerConfig,
        lifecycle: JobLifecycle | None = None,
        job_log: JobLogWriter | None = None,
        ffmpeg_progress_callback: Callable[[FFmpegProgress], None] | None = None,
        job_id: str | None = None,
    ) -> None:
        """Initialize the workflow runner.

        Note: Prefer using for_cli() or for_daemon() factory methods for clarity.

        Args:
            conn: Database connection for workflow operations.
            policy: The policy to apply.
            config: Workflow runner configuration.
            lifecycle: Job lifecycle manager (None = use NullJobLifecycle).
            job_log: Optional log writer for daemon mode.
            ffmpeg_progress_callback: Optional callback for FFmpeg progress.
            job_id: Pre-existing job ID (for daemon mode where worker creates job).
        """
        self.conn = conn
        self.policy = policy
        self.config = config
        self.lifecycle = lifecycle or NullJobLifecycle()
        self.job_log = job_log
        self.ffmpeg_progress_callback = ffmpeg_progress_callback
        self.pre_existing_job_id = job_id

    @classmethod
    def for_cli(
        cls,
        conn: sqlite3.Connection,
        policy: PolicySchema,
        config: WorkflowRunnerConfig,
        lifecycle: JobLifecycle,
        job_log: JobLogWriter | None = None,
    ) -> WorkflowRunner:
        """Create runner for CLI mode where lifecycle manages job records.

        In CLI mode, the lifecycle creates job records on start and updates
        them on completion/failure. This is appropriate for batch processing
        where each file needs its own job record.

        Args:
            conn: Database connection for workflow operations.
            policy: The policy to apply.
            config: Workflow runner configuration.
            lifecycle: Job lifecycle manager (e.g., CLIJobLifecycle).
            job_log: Optional log writer for CLI logging (from lifecycle.job_log).

        Returns:
            Configured WorkflowRunner for CLI use.

        Example:
            lifecycle = CLIJobLifecycle(
                conn, batch_id=batch_id, policy_name="policy.yaml"
            )
            runner = WorkflowRunner.for_cli(conn, policy, config, lifecycle)
            result = runner.run_single(file_path, file_id=file_id)

        Example with logging:
            lifecycle = CLIJobLifecycle(
                conn, batch_id=batch_id, policy_name="policy.yaml", save_logs=True
            )
            # Note: Don't pass job_log here - it's created in on_job_start()
            # and retrieved dynamically by run_single() via lifecycle.job_log
            runner = WorkflowRunner.for_cli(conn, policy, config, lifecycle)
            try:
                result = runner.run_single(file_path, file_id=file_id)
            finally:
                lifecycle.close_job_log()
        """
        return cls(
            conn, policy, config, lifecycle=lifecycle, job_log=job_log, job_id=None
        )

    @classmethod
    def for_daemon(
        cls,
        conn: sqlite3.Connection,
        policy: PolicySchema,
        config: WorkflowRunnerConfig,
        job_id: str,
        job_log: JobLogWriter | None = None,
        ffmpeg_progress_callback: Callable[[FFmpegProgress], None] | None = None,
    ) -> WorkflowRunner:
        """Create runner for daemon mode where worker manages job records.

        In daemon mode, the job record already exists (created by queue system).
        The runner uses NullJobLifecycle since the worker handles completion
        and failure updates.

        Args:
            conn: Database connection for workflow operations.
            policy: The policy to apply.
            config: Workflow runner configuration.
            job_id: Pre-existing job ID from the queue system.
            job_log: Optional log writer for job-specific logs.
            ffmpeg_progress_callback: Optional callback for FFmpeg progress.

        Returns:
            Configured WorkflowRunner for daemon use.

        Example:
            runner = WorkflowRunner.for_daemon(
                conn, policy, config, job_id=job.id,
                job_log=job_log, ffmpeg_progress_callback=callback
            )
            result = runner.run_single(Path(job.file_path))
        """
        return cls(
            conn,
            policy,
            config,
            lifecycle=NullJobLifecycle(),
            job_log=job_log,
            ffmpeg_progress_callback=ffmpeg_progress_callback,
            job_id=job_id,
        )

    def run_single(
        self,
        file_path: Path,
        file_id: int | None = None,
    ) -> WorkflowRunResult:
        """Run the workflow on a single file.

        Args:
            file_path: Path to the file to process.
            file_id: Database ID of the file (if known).

        Returns:
            WorkflowRunResult with processing result, job info, and error
            classification (if failed).
        """
        job_id = self.pre_existing_job_id

        # Create job record if lifecycle manages jobs
        if job_id is None:
            job_id = self.lifecycle.on_job_start(
                file_path, self.config.policy_name, file_id
            )

        # Get job_log from lifecycle if not provided at construction.
        # This supports CLIJobLifecycle.save_logs where the log is created
        # in on_job_start().
        # IMPORTANT: WorkflowRunner NEVER closes the job_log - ownership
        # remains with the lifecycle (CLI mode) or caller (daemon mode).
        job_log = self.job_log
        if job_log is None:
            job_log = getattr(self.lifecycle, "job_log", None)

        try:
            # Validate input file exists
            if not file_path.exists():
                job_id_short = job_id[:8] if job_id else "no-job"
                error = (
                    f"Input file not found: {file_path} "
                    f"(policy: {self.config.policy_name or 'unnamed'})"
                )
                logger.error("Job %s: %s", job_id_short, error)
                if job_log:
                    job_log.write_error(error)
                result = _create_error_result(file_path, error)
                self.lifecycle.on_job_fail(job_id, error)
                return WorkflowRunResult(
                    result=result,
                    job_id=job_id,
                    error_classification=ErrorClassification.PERMANENT,
                )

            # Create and run workflow processor
            processor = WorkflowProcessor(
                conn=self.conn,
                policy=self.policy,
                dry_run=self.config.dry_run,
                verbose=self.config.verbose,
                policy_name=self.config.policy_name,
                selected_phases=self.config.selected_phases,
                job_id=job_id,
                ffmpeg_progress_callback=self.ffmpeg_progress_callback,
            )

            # Log workflow phases
            phases_str = ", ".join(self.policy.phase_names)
            job_id_short = job_id[:8] if job_id else "no-job"
            logger.debug("Job %s: Workflow phases: %s", job_id_short, phases_str)
            if job_log:
                job_log.write_line(f"Workflow phases: {phases_str}")

            result = processor.process_file(file_path)

            # Log phase results with enhanced detail
            for pr in result.phase_results:
                # Determine status string
                if pr.outcome == PhaseOutcome.SKIPPED:
                    status = "SKIP"
                elif pr.success:
                    status = "OK"
                else:
                    status = "FAILED"

                logger.info(
                    "Job %s: Phase %s: %s (%d changes, %.1fs)",
                    job_id_short,
                    pr.phase_name,
                    status,
                    pr.changes_made,
                    pr.duration_seconds,
                )
                if job_log:
                    job_log.write_line(
                        f"Phase {pr.phase_name}: {status} "
                        f"({pr.changes_made} changes, {pr.duration_seconds:.1f}s)"
                    )
                    # Write operations executed
                    if pr.operations_executed:
                        ops_str = ", ".join(pr.operations_executed)
                        job_log.write_line(f"  Operations: {ops_str}")

                    # Write enhanced detail lines
                    detail_lines = format_phase_details(pr)
                    for detail in detail_lines:
                        job_log.write_line(f"  {detail}")

                    # Write skip reason if phase was skipped
                    if pr.skip_reason:
                        job_log.write_line(f"  Skip reason: {pr.skip_reason.message}")

                    # Write message or error
                    if pr.message:
                        job_log.write_line(f"  {pr.message}")
                    if pr.error:
                        job_log.write_line(f"  Error: {pr.error}")

            # Notify lifecycle of completion
            self.lifecycle.on_job_complete(job_id, result)

            return WorkflowRunResult(result=result, job_id=job_id)

        except Exception as e:
            job_id_short = job_id[:8] if job_id else "no-job"
            logger.exception(
                "Job %s: Workflow execution failed for %s: %s",
                job_id_short,
                file_path,
                e,
            )
            error = str(e)
            error_class = classify_workflow_error(e)
            logger.info(
                "Job %s: Error classified as %s (retry %s)",
                job_id_short,
                error_class.value,
                "recommended"
                if error_class == ErrorClassification.TRANSIENT
                else "not recommended",
            )

            if job_log:
                job_log.write_error(f"Workflow execution failed: {e}", e)

            # Notify lifecycle of failure
            self.lifecycle.on_job_fail(job_id, error)

            result = _create_error_result(file_path, error)
            return WorkflowRunResult(
                result=result, job_id=job_id, error_classification=error_class
            )


def _create_error_result(file_path: Path, error_message: str) -> FileProcessingResult:
    """Create a minimal error result for failed processing.

    Args:
        file_path: Path to the file that failed.
        error_message: Description of the error.

    Returns:
        FileProcessingResult representing the failure.
    """
    return FileProcessingResult(
        file_path=file_path,
        success=False,
        phase_results=(),
        total_duration_seconds=0.0,
        total_changes=0,
        phases_completed=0,
        phases_failed=0,
        phases_skipped=0,
        error_message=error_message,
    )
