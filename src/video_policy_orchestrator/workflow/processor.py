"""Workflow processor for orchestrating video file processing.

This module provides the WorkflowProcessor class that orchestrates multiple
processing phases (analyze, apply, transcode) in the correct order.
"""

import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from video_policy_orchestrator.policy.models import (
    PolicySchema,
    ProcessingPhase,
    WorkflowConfig,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.plugin import PluginRegistry
    from video_policy_orchestrator.policy.models import Plan

logger = logging.getLogger(__name__)


class PhaseError(Exception):
    """Error during phase execution."""

    def __init__(
        self,
        phase: ProcessingPhase,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        self.phase = phase
        self.message = message
        self.cause = cause
        super().__init__(f"{phase.value}: {message}")


@dataclass
class PhaseResult:
    """Result of a single phase execution."""

    phase: ProcessingPhase
    success: bool
    message: str | None = None
    duration_seconds: float = 0.0
    changes_made: int = 0
    plan: "Plan | None" = None  # Populated in dry-run mode for rich output


@dataclass
class FileProcessingResult:
    """Result of processing one file through the workflow.

    Attributes:
        file_path: Path to the processed file.
        success: Whether processing succeeded.
        batch_should_stop: If True, batch processing should halt (on_error='fail').
            When False, batch processing can continue to next file (on_error='skip').
        phases_completed: List of successfully completed phases.
        phases_failed: List of phases that failed.
        phases_skipped: List of phases that were skipped due to earlier failure.
        phase_results: Detailed results for each phase.
        error_message: Error message if processing failed.
        duration_seconds: Total processing duration.
    """

    file_path: Path
    success: bool
    batch_should_stop: bool = False  # True if on_error='fail', batch should halt
    phases_completed: list[ProcessingPhase] = field(default_factory=list)
    phases_failed: list[ProcessingPhase] = field(default_factory=list)
    phases_skipped: list[ProcessingPhase] = field(default_factory=list)
    phase_results: list[PhaseResult] = field(default_factory=list)
    error_message: str | None = None
    duration_seconds: float = 0.0

    @property
    def summary(self) -> str:
        """Human-readable summary of the processing result."""
        if self.success:
            completed = [p.value for p in self.phases_completed]
            return f"Completed phases: {', '.join(completed)}"
        else:
            failed = [p.value for p in self.phases_failed]
            return f"Failed phases: {', '.join(failed)} - {self.error_message}"


@dataclass
class WorkflowProgress:
    """Progress information for workflow processing."""

    file_path: Path
    current_phase: ProcessingPhase
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
    """Orchestrates workflow phases for video files.

    The processor runs phases in order: ANALYZE → APPLY → TRANSCODE.
    Each phase is optional and controlled by the policy's workflow config.
    """

    def __init__(
        self,
        conn: Connection,
        policy: PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
        progress_callback: ProgressCallback | None = None,
        policy_name: str = "workflow",
        plugin_registry: "PluginRegistry | None" = None,
    ) -> None:
        """Initialize the workflow processor.

        Args:
            conn: Database connection for file lookups and updates.
            policy: PolicySchema with workflow configuration.
            dry_run: If True, preview changes without modifying files.
            verbose: If True, emit detailed logging.
            progress_callback: Optional callback for progress updates.
            policy_name: Name of the policy for audit records.
            plugin_registry: Optional plugin registry for coordinator-based
                transcription in the ANALYZE phase. If provided, uses
                TranscriptionCoordinator. If None, falls back to legacy
                TranscriberFactory.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self.progress_callback = progress_callback
        self.policy_name = policy_name
        self._plugin_registry = plugin_registry

        # Get workflow config, defaulting to just APPLY if not specified
        self.config: WorkflowConfig = policy.workflow or WorkflowConfig(
            phases=(ProcessingPhase.APPLY,),
        )

        # Initialize phase implementations
        self._phases = self._init_phases()

    def _init_phases(self) -> dict:
        """Initialize phase implementations lazily."""
        from video_policy_orchestrator.workflow.phases.analyze import AnalyzePhase
        from video_policy_orchestrator.workflow.phases.apply import ApplyPhase
        from video_policy_orchestrator.workflow.phases.transcode import TranscodePhase

        return {
            ProcessingPhase.ANALYZE: AnalyzePhase(
                conn=self.conn,
                policy=self.policy,
                dry_run=self.dry_run,
                verbose=self.verbose,
                plugin_registry=self._plugin_registry,
            ),
            ProcessingPhase.APPLY: ApplyPhase(
                conn=self.conn,
                policy=self.policy,
                dry_run=self.dry_run,
                verbose=self.verbose,
                policy_name=self.policy_name,
            ),
            ProcessingPhase.TRANSCODE: TranscodePhase(
                conn=self.conn,
                policy=self.policy,
                dry_run=self.dry_run,
                verbose=self.verbose,
            ),
        }

    def process_file(self, file_path: Path) -> FileProcessingResult:
        """Process a single file through all enabled phases.

        Args:
            file_path: Path to the video file to process.

        Returns:
            FileProcessingResult with status of each phase.
        """
        file_path = file_path.expanduser().resolve()
        start_time = time.time()

        result = FileProcessingResult(
            file_path=file_path,
            success=True,
            phases_completed=[],
            phases_failed=[],
            phases_skipped=[],
            phase_results=[],
        )

        logger.info(
            "Processing %s with %d phases", file_path.name, len(self.config.phases)
        )

        for idx, phase in enumerate(self.config.phases):
            # Report progress
            if self.progress_callback:
                progress = WorkflowProgress(
                    file_path=file_path,
                    current_phase=phase,
                    phase_index=idx,
                    total_phases=len(self.config.phases),
                    phase_progress=0.0,
                )
                self.progress_callback(progress)

            # Run the phase
            phase_result = self._run_phase(phase, file_path)
            result.phase_results.append(phase_result)

            if phase_result.success:
                result.phases_completed.append(phase)
                logger.info(
                    "Phase %s completed for %s (%d changes)",
                    phase.value,
                    file_path.name,
                    phase_result.changes_made,
                )
            else:
                result.phases_failed.append(phase)
                result.error_message = phase_result.message
                logger.error(
                    "Phase %s failed for %s: %s",
                    phase.value,
                    file_path.name,
                    phase_result.message,
                )

                # Handle error according to on_error policy
                if self.config.on_error == "fail":
                    # Abort workflow AND signal batch should stop
                    result.success = False
                    result.batch_should_stop = True
                    remaining = list(self.config.phases)[idx + 1 :]
                    result.phases_skipped.extend(remaining)
                    break
                elif self.config.on_error == "skip":
                    # Abort workflow for this file, but batch can continue
                    result.success = False
                    result.batch_should_stop = False
                    remaining = list(self.config.phases)[idx + 1 :]
                    result.phases_skipped.extend(remaining)
                    break
                # "continue": proceed to next phase despite error

        result.duration_seconds = time.time() - start_time
        return result

    def _run_phase(self, phase: ProcessingPhase, file_path: Path) -> PhaseResult:
        """Run a single phase.

        Args:
            phase: The phase to run.
            file_path: Path to the file to process.

        Returns:
            PhaseResult with success status and details.
        """
        phase_impl = self._phases.get(phase)
        if phase_impl is None:
            return PhaseResult(
                phase=phase,
                success=False,
                message=f"Unknown phase: {phase.value}",
            )

        start_time = time.time()
        try:
            changes = phase_impl.run(file_path)

            # Commit any database changes made by the phase
            # (centralized commit to ensure transaction boundaries are managed here)
            if not self.dry_run:
                self.conn.commit()

            # Extract plan from ApplyPhase for dry-run output
            plan = None
            if self.dry_run and phase == ProcessingPhase.APPLY:
                plan = getattr(phase_impl, "_last_plan", None)

            return PhaseResult(
                phase=phase,
                success=True,
                changes_made=changes,
                duration_seconds=time.time() - start_time,
                plan=plan,
            )
        except sqlite3.Error as e:
            # Database error - rollback any uncommitted changes
            self.conn.rollback()
            logger.exception("Database error in phase %s", phase.value)
            return PhaseResult(
                phase=phase,
                success=False,
                message=f"Database error: {e}",
                duration_seconds=time.time() - start_time,
            )
        except PhaseError as e:
            return PhaseResult(
                phase=phase,
                success=False,
                message=str(e),
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.exception("Unexpected error in phase %s", phase.value)
            return PhaseResult(
                phase=phase,
                success=False,
                message=f"Unexpected error: {e}",
                duration_seconds=time.time() - start_time,
            )

    def process_files(self, file_paths: list[Path]) -> list[FileProcessingResult]:
        """Process multiple files through the workflow.

        Args:
            file_paths: List of file paths to process.

        Returns:
            List of FileProcessingResult for each file.
        """
        results = []
        for file_path in file_paths:
            result = self.process_file(file_path)
            results.append(result)
        return results
