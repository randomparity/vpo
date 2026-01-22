"""Workflow processor for user-defined phases.

This module provides the WorkflowProcessor class that orchestrates
processing through user-defined phases in phased policies.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from vpo.core import parse_iso_timestamp

if TYPE_CHECKING:
    from vpo.plugin import PluginRegistry

from vpo.db.queries import (
    get_file_by_path,
    get_tracks_for_file,
    upsert_tracks_for_file,
)
from vpo.db.types import FileInfo, tracks_to_track_info
from vpo.introspector.ffprobe import (
    FFprobeIntrospector,
    MediaIntrospectionError,
)
from vpo.policy.types import (
    FileProcessingResult,
    OnErrorMode,
    PhaseDefinition,
    PhaseExecutionError,
    PhaseOutcome,
    PhaseResult,
    PolicySchema,
    SkipReason,
    SkipReasonType,
)
from vpo.workflow.phases.executor import PhaseExecutor
from vpo.workflow.skip_conditions import evaluate_skip_when
from vpo.workflow.stats_capture import (
    PhaseMetrics,
    StatsCollector,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkflowProgress:
    """Progress information for workflow processing."""

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
ProgressCallback = Callable[[WorkflowProgress], None]


class WorkflowProcessor:
    """Orchestrates workflow phases for phased policies.

    The processor runs user-defined phases in order, re-introspecting
    the file between phases if modifications were made.
    """

    def __init__(
        self,
        conn: Connection,
        policy: PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
        progress_callback: ProgressCallback | None = None,
        policy_name: str = "workflow",
        selected_phases: list[str] | None = None,
        plugin_registry: "PluginRegistry | None" = None,
    ) -> None:
        """Initialize the workflow processor.

        Args:
            conn: Database connection for file lookups and updates.
            policy: PolicySchema with user-defined phases.
            dry_run: If True, preview changes without modifying files.
            verbose: If True, emit detailed logging.
            progress_callback: Optional callback for progress updates.
            policy_name: Name of the policy for audit records.
            selected_phases: Optional list of phase names to execute.
                If None, all phases are executed.
            plugin_registry: Optional plugin registry for transcription.
                If provided, uses TranscriptionCoordinator for transcription
                operations. If None, transcription operations will be skipped.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self.progress_callback = progress_callback
        self.policy_name = policy_name
        self._plugin_registry = plugin_registry

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
        self._executor = PhaseExecutor(
            conn=conn,
            policy=policy,
            dry_run=dry_run,
            verbose=verbose,
            policy_name=policy_name,
            plugin_registry=plugin_registry,
        )

        # Track phase outcomes for dependency resolution
        self._phase_outcomes: dict[str, PhaseOutcome] = {}
        self._phase_modified: dict[str, bool] = {}

    def _check_skip_condition(
        self,
        phase: PhaseDefinition,
        file_info: "FileInfo | None",
        file_path: Path,
    ) -> SkipReason | None:
        """Check if phase should be skipped based on skip_when condition.

        Returns SkipReason if phase should be skipped, None otherwise.
        """
        if phase.skip_when is None:
            return None

        if file_info is None:
            logger.warning(
                "Cannot evaluate skip_when for phase '%s': file info unavailable",
                phase.name,
            )
            return None

        skip_reason = evaluate_skip_when(phase.skip_when, file_info, file_path)
        if skip_reason:
            logger.info(
                "Phase '%s' skipped: %s",
                phase.name,
                skip_reason.message,
            )
        return skip_reason

    def _check_dependency_condition(
        self,
        phase: PhaseDefinition,
    ) -> SkipReason | None:
        """Check if phase should be skipped due to dependency not completing.

        Returns SkipReason if phase should be skipped, None otherwise.
        """
        if phase.depends_on is None:
            return None

        for dep_name in phase.depends_on:
            outcome = self._phase_outcomes.get(dep_name, PhaseOutcome.PENDING)
            if outcome != PhaseOutcome.COMPLETED:
                reason = SkipReason(
                    reason_type=SkipReasonType.DEPENDENCY,
                    message=(
                        f"dependency '{dep_name}' did not complete "
                        f"(outcome: {outcome.value})"
                    ),
                    dependency_name=dep_name,
                    dependency_outcome=outcome.value,
                )
                logger.info(
                    "Phase '%s' skipped: %s",
                    phase.name,
                    reason.message,
                )
                return reason

        return None

    def _check_run_if_condition(
        self,
        phase: PhaseDefinition,
    ) -> SkipReason | None:
        """Check if phase should be skipped based on run_if condition.

        Returns SkipReason if phase should be skipped, None otherwise.
        """
        if phase.run_if is None:
            return None

        # Check phase_modified condition
        if phase.run_if.phase_modified:
            ref_name = phase.run_if.phase_modified
            modified = self._phase_modified.get(ref_name, False)
            if not modified:
                reason = SkipReason(
                    reason_type=SkipReasonType.RUN_IF,
                    message=f"'{ref_name}' made no modifications",
                    dependency_name=ref_name,
                )
                logger.info(
                    "Phase '%s' skipped: %s",
                    phase.name,
                    reason.message,
                )
                return reason

        # Future: Check phase_completed condition
        if phase.run_if.phase_completed:
            ref_name = phase.run_if.phase_completed
            outcome = self._phase_outcomes.get(ref_name, PhaseOutcome.PENDING)
            if outcome != PhaseOutcome.COMPLETED:
                reason = SkipReason(
                    reason_type=SkipReasonType.RUN_IF,
                    message=f"'{ref_name}' did not complete (outcome: {outcome.value})",
                    dependency_name=ref_name,
                )
                logger.info(
                    "Phase '%s' skipped: %s",
                    phase.name,
                    reason.message,
                )
                return reason

        return None

    def _get_effective_on_error(self, phase: PhaseDefinition) -> OnErrorMode:
        """Get effective on_error mode for a phase.

        Uses per-phase override if set, otherwise falls back to global config.
        """
        if phase.on_error is not None:
            return phase.on_error
        return self.policy.config.on_error

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
            file_path.name,
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

        # Initialize stats collector for non-dry-run processing
        stats_collector: StatsCollector | None = None
        if not self.dry_run and file_info:
            # Get file_id from database
            file_record = get_file_by_path(self.conn, str(file_path))
            if file_record and file_record.id:
                stats_collector = StatsCollector(
                    conn=self.conn,
                    file_id=file_record.id,
                    policy_name=self.policy_name,
                )
                stats_collector.phases_total = len(self.phases_to_execute)
                stats_collector.capture_before_state(file_info, file_path)

        # Reset phase outcome tracking for this file
        self._phase_outcomes = {}
        self._phase_modified = {}

        for idx, phase in enumerate(self.phases_to_execute):
            # Report progress
            if self.progress_callback:
                progress = WorkflowProgress(
                    file_path=file_path,
                    current_phase=phase.name,
                    phase_index=idx,
                    total_phases=len(self.phases_to_execute),
                    phase_progress=0.0,
                )
                self.progress_callback(progress)

            # Check all skip conditions before executing
            skip_reason: SkipReason | None = None

            # 1. Check dependency conditions first (highest priority)
            skip_reason = self._check_dependency_condition(phase)

            # 2. Check skip_when conditions
            if skip_reason is None:
                skip_reason = self._check_skip_condition(phase, file_info, file_path)

            # 3. Check run_if conditions
            if skip_reason is None:
                skip_reason = self._check_run_if_condition(phase)

            # If any skip condition matched, create skipped result
            if skip_reason is not None:
                phase_result = PhaseResult(
                    phase_name=phase.name,
                    success=True,  # Skipped phases are considered successful
                    duration_seconds=0.0,
                    operations_executed=(),
                    changes_made=0,
                    message=f"Skipped: {skip_reason.message}",
                    outcome=PhaseOutcome.SKIPPED,
                    skip_reason=skip_reason,
                    file_modified=False,
                )
                phase_results.append(phase_result)
                phases_skipped.append(phase.name)

                # Track outcome for dependency resolution
                self._phase_outcomes[phase.name] = PhaseOutcome.SKIPPED
                self._phase_modified[phase.name] = False

                logger.info(
                    "Phase %d/%d [%s]: Skipped - %s",
                    idx + 1,
                    len(self.phases_to_execute),
                    phase.name,
                    skip_reason.message,
                )
                continue  # Move to next phase

            # Log phase start
            logger.info(
                "Phase %d/%d [%s]: Starting...",
                idx + 1,
                len(self.phases_to_execute),
                phase.name,
            )

            phase_start_time = time.time()
            try:
                # Execute the phase
                phase_result = self._executor.execute_phase(
                    phase=phase,
                    file_path=file_path,
                    file_info=file_info,
                )

                # Determine if file was modified
                file_was_modified = phase_result.changes_made > 0

                # Create updated result with outcome tracking
                phase_result = PhaseResult(
                    phase_name=phase_result.phase_name,
                    success=phase_result.success,
                    duration_seconds=phase_result.duration_seconds,
                    operations_executed=phase_result.operations_executed,
                    changes_made=phase_result.changes_made,
                    message=phase_result.message,
                    error=phase_result.error,
                    planned_actions=phase_result.planned_actions,
                    transcode_skip_reason=phase_result.transcode_skip_reason,
                    outcome=PhaseOutcome.COMPLETED
                    if phase_result.success
                    else PhaseOutcome.FAILED,
                    skip_reason=None,
                    file_modified=file_was_modified,
                )
                phase_results.append(phase_result)

                # Track outcome for dependency resolution
                self._phase_outcomes[phase.name] = phase_result.outcome
                self._phase_modified[phase.name] = file_was_modified

                # Capture phase metrics for stats
                if stats_collector:
                    phase_duration = time.time() - phase_start_time
                    stats_collector.add_phase_metrics(
                        PhaseMetrics(
                            phase_name=phase.name,
                            wall_time_seconds=phase_duration,
                            encoding_fps=phase_result.encoding_fps,
                            encoding_bitrate=phase_result.encoding_bitrate_kbps,
                        )
                    )
                    # Capture transcode info if present
                    if phase_result.transcode_skip_reason:
                        stats_collector.set_video_transcode_info(
                            target_codec=None,
                            skipped=True,
                            skip_reason=phase_result.transcode_skip_reason,
                        )
                    elif phase_result.encoder_type:
                        # Successful transcode - capture encoder type
                        stats_collector.set_video_transcode_info(
                            encoder_type=phase_result.encoder_type,
                        )

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
                    if file_was_modified and not self.dry_run:
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
                phase_result = PhaseResult(
                    phase_name=phase.name,
                    success=False,
                    duration_seconds=0.0,
                    operations_executed=(),
                    changes_made=0,
                    error=e.message,
                    outcome=PhaseOutcome.FAILED,
                    file_modified=False,
                )
                phase_results.append(phase_result)

                # Track outcome for dependency resolution
                self._phase_outcomes[phase.name] = PhaseOutcome.FAILED
                self._phase_modified[phase.name] = False

                # Handle error according to effective on_error policy
                on_error = self._get_effective_on_error(phase)
                if on_error == OnErrorMode.FAIL:
                    # Stop batch processing
                    remaining = self.phases_to_execute[idx + 1 :]
                    phases_skipped.extend(p.name for p in remaining)
                    # Mark remaining phases as PENDING in outcome tracking
                    for remaining_phase in remaining:
                        self._phase_outcomes[remaining_phase.name] = (
                            PhaseOutcome.PENDING
                        )
                    break
                elif on_error == OnErrorMode.SKIP:
                    # Skip remaining phases for this file
                    remaining = self.phases_to_execute[idx + 1 :]
                    phases_skipped.extend(p.name for p in remaining)
                    # Mark remaining phases as PENDING in outcome tracking
                    for remaining_phase in remaining:
                        self._phase_outcomes[remaining_phase.name] = (
                            PhaseOutcome.PENDING
                        )
                    break
                # OnErrorMode.CONTINUE - proceed to next phase

        duration = time.time() - start_time

        result = FileProcessingResult(
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

        # Capture after state and persist statistics
        if stats_collector:
            stats_collector.capture_after_state(file_info, file_path, result)
            try:
                stats_id = stats_collector.persist()
                result = replace(result, stats_id=stats_id)
            except Exception as e:
                # Stats persistence failure should not affect workflow result
                logger.warning("Failed to persist processing stats: %s", e)

        return result

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
        modified_at = parse_iso_timestamp(file_record.modified_at)

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
            modified_at = parse_iso_timestamp(file_record.modified_at)

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
            raise PhaseExecutionError(
                phase_name="re-introspection",
                operation=None,
                message=f"Cannot re-introspect file after modification: {e}. "
                "File may be corrupted.",
            ) from e
