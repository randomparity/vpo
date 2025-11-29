"""Workflow processor for orchestrating video file processing.

This module provides the WorkflowProcessor class that orchestrates multiple
processing phases (analyze, apply, transcode) in the correct order.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection

from video_policy_orchestrator.policy.models import (
    PolicySchema,
    ProcessingPhase,
    WorkflowConfig,
)

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


@dataclass
class FileProcessingResult:
    """Result of processing one file through the workflow."""

    file_path: Path
    success: bool
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
    ) -> None:
        """Initialize the workflow processor.

        Args:
            conn: Database connection for file lookups and updates.
            policy: PolicySchema with workflow configuration.
            dry_run: If True, preview changes without modifying files.
            verbose: If True, emit detailed logging.
            progress_callback: Optional callback for progress updates.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self.progress_callback = progress_callback

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
            ),
            ProcessingPhase.APPLY: ApplyPhase(
                conn=self.conn,
                policy=self.policy,
                dry_run=self.dry_run,
                verbose=self.verbose,
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

        logger.info("Processing %s with %d phases", file_path, len(self.config.phases))

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
                    result.success = False
                    # Mark remaining phases as skipped
                    remaining = list(self.config.phases)[idx + 1 :]
                    result.phases_skipped.extend(remaining)
                    break
                elif self.config.on_error == "skip":
                    result.success = False
                    # Mark remaining phases as skipped
                    remaining = list(self.config.phases)[idx + 1 :]
                    result.phases_skipped.extend(remaining)
                    break
                # "continue": proceed to next phase

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
            return PhaseResult(
                phase=phase,
                success=True,
                changes_made=changes,
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
