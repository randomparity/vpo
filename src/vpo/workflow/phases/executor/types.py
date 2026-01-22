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

    # FFmpeg encoding metrics (Issue #264)
    encoding_fps: float | None = None
    """Average encoding FPS from FFmpeg (for stats tracking)."""

    encoding_bitrate_kbps: int | None = None
    """Average encoding bitrate in kbps from FFmpeg (for stats tracking)."""

    total_frames: int | None = None
    """Total frames encoded by FFmpeg (for stats tracking)."""

    encoder_type: str | None = None
    """Encoder type used: 'hardware', 'software', or None if unknown."""

    original_mtime: float | None = None
    """Original file modification time (Unix timestamp) captured at phase start.
    Used by file_timestamp operation to restore original mtime after processing."""
