"""Phase implementations for workflow processing.

Each phase wraps existing VPO functionality into a consistent interface.
All phases implement the Phase protocol.

V11 adds user-defined phases via V11PhaseExecutor.
"""

from pathlib import Path
from typing import Protocol

from vpo.workflow.phases.analyze import AnalyzePhase
from vpo.workflow.phases.apply import ApplyPhase
from vpo.workflow.phases.executor import V11PhaseExecutor
from vpo.workflow.phases.transcode import TranscodePhase


class Phase(Protocol):
    """Protocol defining the interface for workflow phases.

    All phase implementations must provide a `run` method that processes
    a single file and returns the number of changes made.

    Example:
        class MyPhase:
            def __init__(self, conn, policy, dry_run, verbose):
                ...

            def run(self, file_path: Path) -> int:
                # Process the file
                return changes_made
    """

    def run(self, file_path: Path) -> int:
        """Run the phase on a single file.

        Args:
            file_path: Path to the video file to process.

        Returns:
            Number of changes made by this phase.

        Raises:
            PhaseError: If the phase encounters an error.
        """
        ...


__all__ = [
    "Phase",
    "AnalyzePhase",
    "ApplyPhase",
    "TranscodePhase",
    "V11PhaseExecutor",
]
