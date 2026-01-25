"""Process job service for workflow execution.

This module provides the service for processing PROCESS jobs, which
execute the workflow on files through user-defined phases.
"""

import json
import logging
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from vpo.config.loader import get_data_dir
from vpo.db.types import Job
from vpo.jobs.logs import JobLogWriter
from vpo.jobs.runner import WorkflowRunner, WorkflowRunnerConfig
from vpo.logging import worker_context
from vpo.policy.loader import load_policy
from vpo.policy.types import PolicySchema
from vpo.tools.ffmpeg_progress import FFmpegProgress

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessJobResult:
    """Result of processing a workflow job."""

    success: bool
    phases_completed: tuple[str, ...] = ()
    phases_failed: tuple[str, ...] = ()
    error_message: str | None = None


class ProcessJobService:
    """Service for processing workflow jobs.

    Executes the workflow on files through user-defined phases.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the process job service.

        Args:
            conn: Database connection.
        """
        self.conn = conn

    def process(
        self,
        job: Job,
        job_log: JobLogWriter | None = None,
        ffmpeg_progress_callback: Callable[[FFmpegProgress], None] | None = None,
    ) -> ProcessJobResult:
        """Process a workflow job using WorkflowRunner.

        Args:
            job: The job to process.
            job_log: Optional log writer for this job.
            ffmpeg_progress_callback: Optional callback for FFmpeg progress updates.
                Used during container conversion with audio transcoding.

        Returns:
            ProcessJobResult with success/failure status.
        """
        # Parse policy from job
        policy, error = self._parse_policy(job, job_log)
        if error:
            return ProcessJobResult(success=False, error_message=error)

        input_path = Path(job.file_path)

        # Execute workflow with worker context for log correlation
        # Use "D" for daemon worker, job ID prefix for file identification
        job_id_short = f"J{job.id[:8]}"
        with worker_context("D", job_id_short, input_path):
            # Create runner configuration
            config = WorkflowRunnerConfig(
                dry_run=False,
                verbose=True,
                policy_name=job.policy_name or "embedded",
            )

            # Create runner for daemon mode (worker manages job lifecycle)
            runner = WorkflowRunner.for_daemon(
                self.conn,
                policy,
                config,
                job_id=job.id,
                job_log=job_log,
                ffmpeg_progress_callback=ffmpeg_progress_callback,
            )

            run_result = runner.run_single(input_path)

            # Collect phase names from results
            phases_completed = tuple(
                pr.phase_name for pr in run_result.result.phase_results if pr.success
            )
            phases_failed = tuple(
                pr.phase_name
                for pr in run_result.result.phase_results
                if not pr.success
            )

            # Convert to ProcessJobResult for backward compatibility
            return ProcessJobResult(
                success=run_result.success,
                phases_completed=phases_completed,
                phases_failed=phases_failed,
                error_message=run_result.result.error_message,
            )

    def _parse_policy(
        self, job: Job, job_log: JobLogWriter | None
    ) -> tuple[PolicySchema | None, str | None]:
        """Parse policy from job.

        Args:
            job: The job with policy_json or policy_name.
            job_log: Optional log writer.

        Returns:
            Tuple of (policy, error_message).
        """
        try:
            # Try policy_json first (embedded in job)
            if job.policy_json:
                data = json.loads(job.policy_json)
                # Re-load through loader for full validation
                temp_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".yaml", delete=False
                    ) as f:
                        yaml.dump(data, f)
                        temp_path = Path(f.name)
                    policy = load_policy(temp_path)
                finally:
                    if temp_path and temp_path.exists():
                        temp_path.unlink(missing_ok=True)

                if job_log:
                    job_log.write_line(f"Policy: embedded (v{policy.schema_version})")
                return policy, None

            # Fall back to policy_name (file path)
            if job.policy_name:
                policy_path = Path(job.policy_name)
                if not policy_path.exists():
                    # Try in ~/.vpo/policies/
                    policy_path = get_data_dir() / "policies" / job.policy_name
                    if not policy_path.suffix:
                        policy_path = policy_path.with_suffix(".yaml")

                if not policy_path.exists():
                    return None, f"Policy file not found: {job.policy_name}"

                policy = load_policy(policy_path)
                if job_log:
                    ver = policy.schema_version
                    job_log.write_line(f"Policy: {policy_path} (v{ver})")
                return policy, None

            return None, "No policy specified in job"

        except Exception as e:
            error = f"Failed to parse policy: {e}"
            if job_log:
                job_log.write_error(error)
            return None, error
