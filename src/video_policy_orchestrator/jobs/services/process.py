"""Process job service for workflow execution.

This module provides the service for processing PROCESS jobs, which
execute the unified workflow (analyze → apply → transcode) on files.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from video_policy_orchestrator.db.types import Job
from video_policy_orchestrator.jobs.logs import JobLogWriter
from video_policy_orchestrator.policy.loader import load_policy
from video_policy_orchestrator.policy.models import PolicySchema

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessJobResult:
    """Result of processing a workflow job."""

    success: bool
    phases_completed: list[str] | None = None
    phases_failed: list[str] | None = None
    error_message: str | None = None


class ProcessJobService:
    """Service for processing workflow jobs.

    Executes the unified workflow (analyze → apply → transcode) on files.
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
    ) -> ProcessJobResult:
        """Process a workflow job end-to-end.

        Args:
            job: The job to process.
            job_log: Optional log writer for this job.

        Returns:
            ProcessJobResult with success/failure status.
        """
        # Parse policy from job
        policy, error = self._parse_policy(job, job_log)
        if error:
            return ProcessJobResult(success=False, error_message=error)

        # Validate input file
        input_path = Path(job.file_path)
        if not input_path.exists():
            error = f"Input file not found: {input_path}"
            if job_log:
                job_log.write_error(error)
            return ProcessJobResult(success=False, error_message=error)

        # Execute workflow
        try:
            from video_policy_orchestrator.workflow import WorkflowProcessor

            processor = WorkflowProcessor(
                conn=self.conn,
                policy=policy,
                dry_run=False,
                verbose=True,
            )

            if job_log:
                phases_str = ", ".join(
                    p.value for p in (policy.workflow.phases if policy.workflow else [])
                )
                job_log.write_line(f"Workflow phases: {phases_str}")

            result = processor.process_file(input_path)

            phases_completed = [p.value for p in result.phases_completed]
            phases_failed = [p.value for p in result.phases_failed]

            if job_log:
                for pr in result.phase_results:
                    status = "OK" if pr.success else "FAILED"
                    job_log.write_line(
                        f"Phase {pr.phase.value}: {status} "
                        f"({pr.changes_made} changes, {pr.duration_seconds:.1f}s)"
                    )
                    if pr.message:
                        job_log.write_line(f"  {pr.message}")

            if result.success:
                return ProcessJobResult(
                    success=True,
                    phases_completed=phases_completed,
                    phases_failed=phases_failed,
                )
            else:
                return ProcessJobResult(
                    success=False,
                    phases_completed=phases_completed,
                    phases_failed=phases_failed,
                    error_message=result.error_message,
                )

        except Exception as e:
            logger.exception("Workflow execution failed")
            error = f"Workflow execution failed: {e}"
            if job_log:
                job_log.write_error(error, e)
            return ProcessJobResult(success=False, error_message=error)

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
                import tempfile

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as f:
                    import yaml

                    yaml.dump(data, f)
                    temp_path = Path(f.name)
                try:
                    policy = load_policy(temp_path)
                finally:
                    temp_path.unlink()

                if job_log:
                    job_log.write_line(f"Policy: embedded (v{policy.schema_version})")
                return policy, None

            # Fall back to policy_name (file path)
            if job.policy_name:
                policy_path = Path(job.policy_name)
                if not policy_path.exists():
                    # Try in ~/.vpo/policies/
                    from video_policy_orchestrator.config import get_config_dir

                    policy_path = get_config_dir() / "policies" / job.policy_name
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
