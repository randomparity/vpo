"""V11 workflow processor for user-defined phases.

This module provides the V11WorkflowProcessor class that orchestrates
processing through user-defined phases in V11 policies.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sqlite3 import Connection

from video_policy_orchestrator.db.queries import (
    get_file_by_path,
    get_tracks_for_file,
    upsert_tracks_for_file,
)
from video_policy_orchestrator.db.types import FileInfo, tracks_to_track_info
from video_policy_orchestrator.introspector.ffprobe import (
    FFprobeIntrospector,
    MediaIntrospectionError,
)
from video_policy_orchestrator.policy.models import (
    FileProcessingResult,
    OnErrorMode,
    PhaseExecutionError,
    PhaseResult,
    V11PolicySchema,
)
from video_policy_orchestrator.workflow.phases.executor import V11PhaseExecutor

logger = logging.getLogger(__name__)


@dataclass
class V11WorkflowProgress:
    """Progress information for V11 workflow processing."""

    file_path: Path
    current_phase: str
    phase_index: int
    total_phases: int
    phase_progress: float = 0.0  # 0.0 - 1.0

    @property
    def overall_progress(self) -> float:
        """Calculate overall progress as a percentage."""
        if self.total_phases == 0:
            return 0.0
        base = (self.phase_index / self.total_phases) * 100
        phase_contrib = (self.phase_progress / self.total_phases) * 100
        return base + phase_contrib


# Type alias for progress callback
V11ProgressCallback = Callable[[V11WorkflowProgress], None]


class V11WorkflowProcessor:
    """Orchestrates workflow phases for V11 policies.

    The processor runs user-defined phases in order, re-introspecting
    the file between phases if modifications were made.
    """

    def __init__(
        self,
        conn: Connection,
        policy: V11PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
        progress_callback: V11ProgressCallback | None = None,
        policy_name: str = "workflow",
        selected_phases: list[str] | None = None,
    ) -> None:
        """Initialize the V11 workflow processor.

        Args:
            conn: Database connection for file lookups and updates.
            policy: V11PolicySchema with user-defined phases.
            dry_run: If True, preview changes without modifying files.
            verbose: If True, emit detailed logging.
            progress_callback: Optional callback for progress updates.
            policy_name: Name of the policy for audit records.
            selected_phases: Optional list of phase names to execute.
                If None, all phases are executed.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self.progress_callback = progress_callback
        self.policy_name = policy_name

        # Determine which phases to execute
        if selected_phases:
            # Validate selected phases exist
            valid_names = set(policy.phase_names)
            for name in selected_phases:
                if name not in valid_names:
                    raise ValueError(
                        f"Unknown phase '{name}'. "
                        f"Valid phases: {', '.join(sorted(valid_names))}"
                    )
            self.phases_to_execute = [
                p for p in policy.phases if p.name in selected_phases
            ]
        else:
            self.phases_to_execute = list(policy.phases)

        # Initialize phase executor
        self._executor = V11PhaseExecutor(
            conn=conn,
            policy=policy,
            dry_run=dry_run,
            verbose=verbose,
            policy_name=policy_name,
        )

    def process_file(self, file_path: Path) -> FileProcessingResult:
        """Process a single file through all enabled phases.

        Args:
            file_path: Path to the video file to process.

        Returns:
            FileProcessingResult with status of each phase.
        """
        file_path = file_path.expanduser().resolve()
        start_time = time.time()

        logger.info(
            "Processing %s with %d phase(s)",
            file_path,
            len(self.phases_to_execute),
        )

        phase_results: list[PhaseResult] = []
        phases_completed: list[str] = []
        phases_failed: list[str] = []
        phases_skipped: list[str] = []
        total_changes = 0
        failed_phase: str | None = None
        error_message: str | None = None

        # Get initial file info from database
        file_info = self._get_file_info(file_path)

        for idx, phase in enumerate(self.phases_to_execute):
            # Report progress
            if self.progress_callback:
                progress = V11WorkflowProgress(
                    file_path=file_path,
                    current_phase=phase.name,
                    phase_index=idx,
                    total_phases=len(self.phases_to_execute),
                    phase_progress=0.0,
                )
                self.progress_callback(progress)

            # Log phase start
            logger.info(
                "Phase %d/%d [%s]: Starting...",
                idx + 1,
                len(self.phases_to_execute),
                phase.name,
            )

            try:
                # Execute the phase
                phase_result = self._executor.execute_phase(
                    phase=phase,
                    file_path=file_path,
                    file_info=file_info,
                )
                phase_results.append(phase_result)

                if phase_result.success:
                    phases_completed.append(phase.name)
                    total_changes += phase_result.changes_made
                    logger.info(
                        "Phase %d/%d [%s]: Completed (%d changes)",
                        idx + 1,
                        len(self.phases_to_execute),
                        phase.name,
                        phase_result.changes_made,
                    )

                    # Re-introspect if file was modified
                    if phase_result.changes_made > 0 and not self.dry_run:
                        file_info = self._re_introspect(file_path)
                else:
                    # Phase returned success=False (should not happen normally)
                    phases_failed.append(phase.name)
                    failed_phase = phase.name
                    error_message = phase_result.error
                    break

            except PhaseExecutionError as e:
                # Phase raised an error
                phases_failed.append(phase.name)
                failed_phase = phase.name
                error_message = e.message

                logger.error(
                    "Phase %d/%d [%s]: Failed - %s",
                    idx + 1,
                    len(self.phases_to_execute),
                    phase.name,
                    e.message,
                )

                # Create a failure result
                phase_results.append(
                    PhaseResult(
                        phase_name=phase.name,
                        success=False,
                        duration_seconds=0.0,
                        operations_executed=(),
                        changes_made=0,
                        error=e.message,
                    )
                )

                # Handle error according to on_error policy
                on_error = self.policy.config.on_error
                if on_error == OnErrorMode.FAIL:
                    # Stop batch processing
                    remaining = self.phases_to_execute[idx + 1 :]
                    phases_skipped.extend(p.name for p in remaining)
                    break
                elif on_error == OnErrorMode.SKIP:
                    # Skip remaining phases for this file
                    remaining = self.phases_to_execute[idx + 1 :]
                    phases_skipped.extend(p.name for p in remaining)
                    break
                # OnErrorMode.CONTINUE - proceed to next phase

        duration = time.time() - start_time

        return FileProcessingResult(
            file_path=file_path,
            success=len(phases_failed) == 0,
            phase_results=tuple(phase_results),
            total_duration_seconds=duration,
            total_changes=total_changes,
            phases_completed=len(phases_completed),
            phases_failed=len(phases_failed),
            phases_skipped=len(phases_skipped),
            failed_phase=failed_phase,
            error_message=error_message,
        )

    def process_files(self, file_paths: list[Path]) -> list[FileProcessingResult]:
        """Process multiple files through the workflow.

        Args:
            file_paths: List of file paths to process.

        Returns:
            List of FileProcessingResult for each file.
        """
        results: list[FileProcessingResult] = []
        for file_path in file_paths:
            result = self.process_file(file_path)
            results.append(result)

            # Check if batch should stop
            if not result.success and self.policy.config.on_error == OnErrorMode.FAIL:
                logger.warning(
                    "Stopping batch due to error (on_error='fail'): %s",
                    result.error_message,
                )
                break

        return results

    def _get_file_info(self, file_path: Path) -> FileInfo | None:
        """Get file info from database.

        Args:
            file_path: Path to the file.

        Returns:
            FileInfo if found in database, None otherwise.
        """
        file_record = get_file_by_path(self.conn, str(file_path))
        if file_record is None:
            logger.debug("File not in database: %s", file_path)
            return None

        track_records = get_tracks_for_file(self.conn, file_record.id)
        tracks = tracks_to_track_info(track_records)

        # Parse ISO 8601 timestamp from database
        modified_at = datetime.fromisoformat(file_record.modified_at)

        return FileInfo(
            path=file_path,
            filename=file_record.filename,
            directory=Path(file_record.directory),
            extension=file_record.extension,
            size_bytes=file_record.size_bytes,
            modified_at=modified_at,
            content_hash=file_record.content_hash,
            container_format=file_record.container_format,
            tracks=tracks,
        )

    def _re_introspect(self, file_path: Path) -> FileInfo | None:
        """Re-introspect a file after modifications.

        Args:
            file_path: Path to the file.

        Returns:
            Updated FileInfo, or None if introspection failed.
        """
        logger.debug("Re-introspecting file after modification: %s", file_path)

        # Get file record from database (we need the file_id)
        file_record = get_file_by_path(self.conn, str(file_path))
        if file_record is None:
            logger.warning("File not in database, cannot re-introspect: %s", file_path)
            return None

        try:
            # Run ffprobe to get fresh track data
            introspector = FFprobeIntrospector()
            result = introspector.get_file_info(file_path)

            # Update tracks in database
            upsert_tracks_for_file(self.conn, file_record.id, result.tracks)
            logger.debug(
                "Updated %d tracks in database for file %s",
                len(result.tracks),
                file_path,
            )

            # Parse ISO 8601 timestamp from database
            modified_at = datetime.fromisoformat(file_record.modified_at)

            # Return fresh FileInfo with updated tracks
            return FileInfo(
                path=file_path,
                filename=file_record.filename,
                directory=Path(file_record.directory),
                extension=file_record.extension,
                size_bytes=file_record.size_bytes,
                modified_at=modified_at,
                content_hash=file_record.content_hash,
                container_format=result.container_format,
                tracks=result.tracks,
            )

        except MediaIntrospectionError as e:
            logger.error("Re-introspection failed for %s: %s", file_path, e)
            # Fall back to existing database info
            return self._get_file_info(file_path)
