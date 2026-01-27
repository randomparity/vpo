"""Type definitions for phase execution.

This module contains dataclasses used during phase execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from vpo.policy.types import OperationType, PhaseDefinition

if TYPE_CHECKING:
    from vpo.policy.types import ContainerChange, TrackDisposition


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

    # Enhanced workflow logging - accumulated details during execution
    track_dispositions: list[TrackDisposition] = field(default_factory=list)
    """Tracks removed/kept during filter operations (accumulated)."""

    container_change: ContainerChange | None = None
    """Container conversion details captured during container operation."""

    track_order_before: tuple[int, ...] | None = None
    """Track indices before reordering."""

    track_order_after: tuple[int, ...] | None = None
    """Track indices after reordering."""

    audio_synthesis_created: list[str] = field(default_factory=list)
    """Descriptions of audio tracks created by synthesis."""

    size_before: int | None = None
    """File size in bytes before transcode."""

    size_after: int | None = None
    """File size in bytes after transcode."""

    video_source_codec: str | None = None
    """Source video codec before transcode (e.g., 'h264')."""

    video_target_codec: str | None = None
    """Target video codec after transcode (e.g., 'hevc')."""
