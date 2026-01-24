"""Move job processing service.

This module extracts the move job business logic from the worker,
providing better testability and separation of concerns.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from vpo.db.queries import update_file_path
from vpo.db.types import Job
from vpo.executor.move import MoveExecutor
from vpo.jobs.logs import JobLogWriter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MoveConfig:
    """Configuration for a move operation."""

    destination_path: Path
    create_directories: bool = True
    overwrite: bool = False


@dataclass(frozen=True)
class MoveJobResult:
    """Result of processing a move job."""

    success: bool
    source_path: str | None = None
    destination_path: str | None = None
    error_message: str | None = None


class MoveJobService:
    """Service for processing move jobs.

    Separates business logic from worker orchestration for better testability.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the move job service.

        Args:
            conn: Database connection for updating file records.
        """
        self.conn = conn

    def process(
        self,
        job: Job,
        job_log: JobLogWriter | None = None,
    ) -> MoveJobResult:
        """Process a move job end-to-end.

        Args:
            job: The job to process.
            job_log: Optional log writer for this job.

        Returns:
            MoveJobResult with success/failure status and paths.
        """
        # Parse config
        config, error = self._parse_config(job, job_log)
        if error:
            return MoveJobResult(success=False, error_message=error)

        # Validate source file exists
        source_path = Path(job.file_path)
        if not source_path.exists():
            error = f"Source file not found: {source_path}"
            if job_log:
                job_log.write_error(error)
            return MoveJobResult(success=False, error_message=error)

        if job_log:
            job_log.write_section("Moving file")
            job_log.write_line(f"Source: {source_path}")
            job_log.write_line(f"Destination: {config.destination_path}")

        # Execute move
        executor = MoveExecutor(
            create_directories=config.create_directories,
            overwrite=config.overwrite,
        )
        plan = executor.create_plan(
            source_path=source_path,
            destination_path=config.destination_path,
        )
        result = executor.execute(plan)

        if not result.success:
            if job_log:
                job_log.write_error(f"Move failed: {result.error_message}")
            return MoveJobResult(
                success=False,
                source_path=str(source_path),
                error_message=result.error_message,
            )

        if job_log:
            job_log.write_line("Move completed successfully")

        # Update database if file_id is available
        if job.file_id is not None:
            self._update_file_path(job.file_id, result.destination_path, job_log)

        return MoveJobResult(
            success=True,
            source_path=str(source_path),
            destination_path=str(result.destination_path),
        )

    def _parse_config(
        self, job: Job, job_log: JobLogWriter | None
    ) -> tuple[MoveConfig | None, str | None]:
        """Parse move configuration from job JSON.

        Returns:
            Tuple of (config, error_message).
            On success, error_message is None.
            On failure, config is None.
        """
        if not job.policy_json:
            error = "Missing policy_json for move job"
            if job_log:
                job_log.write_error(error)
            return None, error

        try:
            policy_data = json.loads(job.policy_json)
        except json.JSONDecodeError as e:
            error = f"Invalid policy JSON: {e}"
            if job_log:
                job_log.write_error(error)
            return None, error

        # Extract destination_path (required)
        destination = policy_data.get("destination_path")
        if not destination:
            error = "Missing 'destination_path' in policy_json"
            if job_log:
                job_log.write_error(error)
            return None, error

        config = MoveConfig(
            destination_path=Path(destination),
            create_directories=policy_data.get("create_directories", True),
            overwrite=policy_data.get("overwrite", False),
        )

        if job_log:
            job_log.write_line(f"Parsed config: dest={config.destination_path}")

        return config, None

    def _update_file_path(
        self, file_id: int, new_path: Path, job_log: JobLogWriter | None
    ) -> None:
        """Update the file's path in the database.

        Args:
            file_id: Database ID of the file.
            new_path: New path after move.
            job_log: Optional log writer.
        """
        try:
            updated = update_file_path(self.conn, file_id, str(new_path))
            self.conn.commit()
            if updated:
                if job_log:
                    job_log.write_line(f"Updated database path for file_id={file_id}")
                logger.info(
                    "Updated file path in database: file_id=%s -> %s", file_id, new_path
                )
            else:
                if job_log:
                    job_log.write_line(f"File not found in database: file_id={file_id}")
                logger.warning(
                    "File not found in database during path update: file_id=%s", file_id
                )
        except sqlite3.Error as e:
            # Log warning but don't fail the job - the file was successfully moved
            if job_log:
                job_log.write_line(f"Warning: Failed to update database path: {e}")
            logger.warning("Failed to update file path in database: %s", e)
