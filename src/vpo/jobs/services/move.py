"""Move job processing service.

This module extracts the move job business logic from the worker,
providing better testability and separation of concerns.
"""

import json
import logging
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from vpo.db.queries import update_file_path
from vpo.db.types import Job
from vpo.executor.move import MoveExecutor
from vpo.jobs.logs import JobLogWriter

logger = logging.getLogger(__name__)


class MoveRollbackError(Exception):
    """Raised when file rollback after DB failure fails."""


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

        # Update database if file_id and destination_path are available
        if job.file_id is not None and result.destination_path is not None:
            try:
                self._update_file_path(job.file_id, result.destination_path, job_log)
            except Exception as e:
                # Attempt to rollback the file move
                error_msg = f"Database update failed: {e}"
                if job_log:
                    job_log.write_error(error_msg)
                    job_log.write_line("Attempting to rollback file move...")

                try:
                    self._rollback_file_move(
                        result.destination_path, source_path, job_log
                    )
                    return MoveJobResult(
                        success=False,
                        source_path=str(source_path),
                        error_message=f"{error_msg} (file rolled back to source)",
                    )
                except MoveRollbackError as rollback_err:
                    # Critical: file moved but DB not updated and rollback failed
                    critical_msg = (
                        f"{error_msg}. "
                        f"CRITICAL: Rollback also failed: {rollback_err}. "
                        f"File is now at: {result.destination_path}"
                    )
                    logger.critical(
                        "Move job rollback failed: file_id=%s, "
                        "original_path=%s, current_path=%s, db_error=%s, "
                        "rollback_error=%s",
                        job.file_id,
                        source_path,
                        result.destination_path,
                        e,
                        rollback_err,
                    )
                    if job_log:
                        job_log.write_error(critical_msg)
                    return MoveJobResult(
                        success=False,
                        source_path=str(source_path),
                        destination_path=str(result.destination_path),
                        error_message=critical_msg,
                    )

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
            job_log.write_line(
                f"Config: destination={config.destination_path}, "
                f"create_directories={config.create_directories}, "
                f"overwrite={config.overwrite}"
            )

        return config, None

    def _update_file_path(
        self, file_id: int, new_path: Path, job_log: JobLogWriter | None
    ) -> None:
        """Update the file's path in the database.

        Args:
            file_id: Database ID of the file.
            new_path: New path after move.
            job_log: Optional log writer.

        Raises:
            sqlite3.Error: If database update fails.

        Note:
            Does NOT commit the transaction. Caller manages transactions.
        """
        updated = update_file_path(self.conn, file_id, str(new_path))
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
                "File not found in database during path update: "
                "file_id=%s, new_path=%s",
                file_id,
                new_path,
            )

    def _rollback_file_move(
        self, current_path: Path, original_path: Path, job_log: JobLogWriter | None
    ) -> None:
        """Attempt to rollback a file move by moving back to original location.

        Args:
            current_path: Current location of the file.
            original_path: Original location to restore.
            job_log: Optional log writer.

        Raises:
            MoveRollbackError: If rollback fails.
        """
        try:
            logger.warning(
                "Rolling back file move: %s -> %s", current_path, original_path
            )
            shutil.move(str(current_path), str(original_path))
            if job_log:
                job_log.write_line(
                    f"Rollback successful: file restored to {original_path}"
                )
            logger.info("File rollback successful: %s", original_path)
        except OSError as e:
            error_msg = (
                f"Failed to rollback file from {current_path} to {original_path}: {e}"
            )
            logger.error(error_msg)
            raise MoveRollbackError(error_msg) from e
