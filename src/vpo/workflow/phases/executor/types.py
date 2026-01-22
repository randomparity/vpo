"""Type definitions for phase execution.

This module contains dataclasses used during phase execution.
"""

from dataclasses import dataclass, field
from pathlib import Path

from vpo.policy.types import OperationType, PhaseDefinition


@dataclass
class OperationResult:
    """Result of executing a single operation within a phase."""

    operation: OperationType
    success: bool
    constraint_skipped: bool = False
    """True if a policy constraint caused the operation to be skipped (not an error)."""
    changes_made: int = 0
    message: str | None = None
    duration_seconds: float = 0.0


@dataclass
class PhaseExecutionState:
    """Mutable state during phase execution."""

    file_path: Path
    """Path to the media file being processed."""

    phase: PhaseDefinition
    """The phase definition being executed."""

    backup_path: Path | None = None
    """Path to backup file created at phase start."""

    operations_completed: list[str] = field(default_factory=list)
    """List of operation names completed in this phase."""

    file_modified: bool = False
    """True if any operation in this phase modified the file."""

    total_changes: int = 0
    """Total changes made in this phase."""

    transcode_skip_reason: str | None = None
    """If transcode was skipped, the reason (for stats tracking)."""
