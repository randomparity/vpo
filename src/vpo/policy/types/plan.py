"""Plan and execution types for policy processing.

This module contains types for execution plans, phase results,
and processing context used during policy application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from vpo.policy.types.enums import (
    ActionType,
    PhaseOutcome,
    SkipReasonType,
)

if TYPE_CHECKING:
    from vpo.domain.models import FileInfo, TrackInfo
    from vpo.executor.transcode.decisions import TranscodeReason
    from vpo.policy.types.actions import ConditionalResult, SkipFlags


@dataclass(frozen=True)
class SkipReason:
    """Captures why a phase was skipped for logging and JSON output.

    Provides detailed information about the skip reason including
    which condition or dependency triggered the skip.
    """

    reason_type: SkipReasonType
    """The type of skip reason."""

    message: str
    """Human-readable explanation of the skip."""

    condition_name: str | None = None
    """Which condition matched (for CONDITION type)."""

    condition_value: str | None = None
    """What value triggered the skip (for CONDITION type)."""

    dependency_name: str | None = None
    """Which dependency failed (for DEPENDENCY type)."""

    dependency_outcome: str | None = None
    """The outcome of the failed dependency (for DEPENDENCY type)."""


@dataclass(frozen=True)
class PhaseSkipCondition:
    """Conditions for skipping a phase based on file characteristics.

    All specified conditions use OR logic - if ANY condition matches,
    the phase is skipped. Unspecified conditions (None) are not evaluated.

    This is different from SkipCondition which is for transcode operations.
    """

    video_codec: tuple[str, ...] | None = None
    """Skip if video codec matches any in this list (case-insensitive)."""

    audio_codec_exists: str | None = None
    """Skip if an audio track with this codec exists."""

    subtitle_language_exists: str | None = None
    """Skip if a subtitle track with this language exists."""

    container: tuple[str, ...] | None = None
    """Skip if container format matches any in this list."""

    resolution: str | None = None
    """Skip if video resolution matches exactly (e.g., '1080p')."""

    resolution_under: str | None = None
    """Skip if video resolution is under this threshold."""

    file_size_under: str | None = None
    """Skip if file size is under this value (e.g., '5GB')."""

    file_size_over: str | None = None
    """Skip if file size is over this value."""

    duration_under: str | None = None
    """Skip if duration is under this value (e.g., '30m')."""

    duration_over: str | None = None
    """Skip if duration is over this value."""


@dataclass(frozen=True)
class RunIfCondition:
    """Conditions for running a phase based on previous phase outcomes.

    Exactly one field must be set. The referenced phase must exist
    and appear earlier in the policy.
    """

    phase_modified: str | None = None
    """Run only if the named phase modified the file."""

    phase_completed: str | None = None
    """Run only if the named phase completed successfully (future)."""


@dataclass(frozen=True)
class TrackDisposition:
    """Disposition of a track in the filtering plan.

    Represents the planned action for a single track, including whether it
    will be kept or removed and the reason for that decision.
    """

    track_index: int
    """0-based global track index in source file."""

    track_type: str
    """Track type: 'video', 'audio', 'subtitle', 'attachment'."""

    codec: str | None
    """Codec name (e.g., 'hevc', 'aac', 'subrip')."""

    language: str | None
    """ISO 639-2/B language code or None if untagged."""

    title: str | None
    """Track title if present."""

    channels: int | None
    """Audio channels (audio tracks only)."""

    resolution: str | None
    """Resolution string like '1920x1080' (video tracks only)."""

    action: Literal["KEEP", "REMOVE"]
    """Whether the track will be kept or removed."""

    reason: str
    """Human-readable reason for the action."""

    transcription_status: str | None = None
    """Transcription analysis status for audio tracks.

    Format: 'main 95%', 'commentary 88%', 'alternate 72%', or 'TBD'.
    None for non-audio tracks.
    """


@dataclass(frozen=True)
class IncompatibleTrackPlan:
    """Plan for handling an incompatible track during container conversion.

    Created when on_incompatible_codec is set to 'transcode' and a track
    has a codec that cannot be directly copied to the target container.

    Invariants:
    - If action is "transcode" or "convert", target_codec must be set
    - If action is "remove", target_codec must be None
    - target_bitrate is only valid when action is "transcode"
    """

    track_index: int
    """0-based global track index in source file."""

    track_type: str
    """Track type: 'audio' or 'subtitle'."""

    source_codec: str
    """Source codec that is incompatible (e.g., 'truehd', 'hdmv_pgs_subtitle')."""

    action: Literal["transcode", "remove", "convert"]
    """Action to take:
    - transcode: Re-encode to compatible codec (audio)
    - convert: Convert to compatible format (text subtitles)
    - remove: Remove track entirely (bitmap subtitles)
    """

    target_codec: str | None = None
    """Target codec after transcoding/conversion (None if removing)."""

    target_bitrate: str | None = None
    """Target bitrate for audio transcoding (e.g., '256k')."""

    reason: str = ""
    """Human-readable reason for this action."""

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if self.action in ("transcode", "convert"):
            if self.target_codec is None:
                raise ValueError(
                    f"IncompatibleTrackPlan with action='{self.action}' requires "
                    f"target_codec to be set (track {self.track_index})"
                )
        elif self.action == "remove":
            if self.target_codec is not None:
                raise ValueError(
                    f"IncompatibleTrackPlan with action='remove' must have "
                    f"target_codec=None, got '{self.target_codec}' "
                    f"(track {self.track_index})"
                )

        if self.target_bitrate is not None and self.action != "transcode":
            raise ValueError(
                f"IncompatibleTrackPlan with action='{self.action}' must have "
                f"target_bitrate=None, got '{self.target_bitrate}' "
                f"(track {self.track_index}). "
                f"target_bitrate is only valid for action='transcode'"
            )


@dataclass(frozen=True)
class ContainerTranscodePlan:
    """Plan for container conversion with track transcoding.

    Created when on_incompatible_codec is 'transcode' and incompatible
    tracks are found. Contains the detailed plan for each track.
    """

    track_plans: tuple[IncompatibleTrackPlan, ...]
    """Plans for each incompatible track."""

    warnings: tuple[str, ...] = ()
    """Warnings about the conversion (e.g., lost subtitle styling)."""


@dataclass(frozen=True)
class ContainerChange:
    """Planned container format conversion.

    Represents a container format change from the source format to the
    target format, including any warnings about the conversion.
    """

    source_format: str
    """Source container format (e.g., 'mkv', 'avi', 'mp4')."""

    target_format: str
    """Target container format (e.g., 'mkv', 'mp4')."""

    warnings: tuple[str, ...]
    """Warnings about the conversion (e.g., subtitle format limitations)."""

    incompatible_tracks: tuple[int, ...]
    """Track indices that are incompatible with target format."""

    transcode_plan: ContainerTranscodePlan | None = None
    """Plan for handling incompatible tracks via transcoding.

    Only present when on_incompatible_codec is 'transcode' and
    incompatible tracks were found.
    """

    preserve_metadata: bool = True
    """If True, preserve portable container-level metadata during conversion."""


@dataclass(frozen=True)
class PlannedAction:
    """A single planned change. Immutable.

    Note: For SET_CONTAINER_METADATA actions, ``current_value`` stores the
    metadata field name (not the actual current value) and ``desired_value``
    stores the new value to set. An empty ``desired_value`` means clear/delete.
    """

    action_type: ActionType
    track_index: int | None  # None for REORDER (file-level action)
    current_value: Any
    desired_value: Any
    track_id: str | None = None  # Track UID if available

    @property
    def description(self) -> str:
        """Human-readable description of this action."""
        if self.action_type == ActionType.REORDER:
            return f"Reorder: {self.current_value} → {self.desired_value}"
        elif self.action_type == ActionType.SET_DEFAULT:
            return f"Track {self.track_index}: Set as default"
        elif self.action_type == ActionType.CLEAR_DEFAULT:
            return f"Track {self.track_index}: Clear default flag"
        elif self.action_type == ActionType.SET_FORCED:
            return f"Track {self.track_index}: Set as forced"
        elif self.action_type == ActionType.CLEAR_FORCED:
            return f"Track {self.track_index}: Clear forced flag"
        elif self.action_type == ActionType.SET_TITLE:
            return f"Track {self.track_index}: Set title '{self.desired_value}'"
        elif self.action_type == ActionType.SET_LANGUAGE:
            return f"Track {self.track_index}: Set language '{self.desired_value}'"
        elif self.action_type == ActionType.SET_CONTAINER_METADATA:
            if self.desired_value == "":
                return f"Container: Clear metadata '{self.current_value}'"
            field = self.current_value
            val = self.desired_value
            return f"Container: Set metadata '{field}' = '{val}'"
        else:
            return f"Track {self.track_index}: {self.action_type.value}"


@dataclass(frozen=True)
class Plan:
    """Immutable execution plan produced by policy evaluation."""

    file_id: str
    file_path: Path
    policy_version: int
    actions: tuple[PlannedAction, ...]
    requires_remux: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # V3 fields for track filtering
    track_dispositions: tuple[TrackDisposition, ...] = ()
    """Detailed disposition for each track in the source file."""

    container_change: ContainerChange | None = None
    """Container conversion details if applicable."""

    tracks_removed: int = 0
    """Count of tracks being removed."""

    tracks_kept: int = 0
    """Count of tracks being kept."""

    # V4 fields for conditional rules
    conditional_result: ConditionalResult | None = None
    """Result of conditional rule evaluation, if any rules were defined."""

    skip_flags: SkipFlags = field(default_factory=lambda: _get_default_skip_flags())
    """Flags set by conditional rules to suppress operations."""

    @property
    def is_empty(self) -> bool:
        """True if no actions needed."""
        # Check both traditional actions and v3 track dispositions
        has_removals = self.tracks_removed > 0
        has_container_change = self.container_change is not None
        return len(self.actions) == 0 and not has_removals and not has_container_change

    @property
    def summary(self) -> str:
        """Human-readable summary of changes."""
        if self.is_empty:
            return "No changes required"

        parts = []

        # Traditional actions
        action_count = len(self.actions)
        if action_count > 0:
            parts.append(f"{action_count} change{'s' if action_count != 1 else ''}")

        # Track filtering summary
        if self.tracks_removed > 0:
            plural = "s" if self.tracks_removed != 1 else ""
            parts.append(f"{self.tracks_removed} track{plural} removed")

        # Container change
        if self.container_change:
            src = self.container_change.source_format
            tgt = self.container_change.target_format
            parts.append(f"convert {src} → {tgt}")

        summary = ", ".join(parts)
        remux_note = " (requires remux)" if self.requires_remux else ""
        return f"{summary}{remux_note}"


def _get_default_skip_flags() -> SkipFlags:
    """Get default SkipFlags instance (avoids circular import at module load)."""
    from vpo.policy.types.actions import SkipFlags

    return SkipFlags()


@dataclass
class PhaseExecutionContext:
    """Mutable context passed through phase execution.

    This context is created at the start of file processing and
    updated as each phase executes.
    """

    file_path: Path
    """Path to the media file being processed."""

    file_info: Any  # FileInfo from db module - avoiding circular import
    """Current introspection data for the file."""

    policy: Any  # PolicySchema - avoiding circular import
    """The policy being applied."""

    current_phase: str
    """Name of the currently executing phase."""

    phase_index: int
    """1-based index of the current phase."""

    total_phases: int
    """Total number of phases to execute."""

    global_config: Any  # GlobalConfig - avoiding circular import
    """Global configuration from policy."""

    # Execution state
    backup_path: Path | None = None
    """Path to backup file created at phase start."""

    file_modified: bool = False
    """True if any operation in this phase modified the file."""

    operations_completed: list[str] = field(default_factory=list)
    """List of operation names completed in this phase."""

    # Dry-run output
    dry_run: bool = False
    """True if running in dry-run mode (no file modifications)."""

    planned_actions: list[PlannedAction] = field(default_factory=list)
    """Actions planned during dry-run."""


@dataclass(frozen=True)
class PhaseResult:
    """Result from executing a single phase."""

    phase_name: str
    """Name of the phase that was executed."""

    success: bool
    """True if phase completed successfully."""

    duration_seconds: float
    """Time taken to execute the phase."""

    operations_executed: tuple[str, ...]
    """Names of operations that were executed."""

    changes_made: int
    """Number of changes made to the file."""

    message: str | None = None
    """Human-readable status message."""

    error: str | None = None
    """Error message if success is False."""

    # For dry-run output
    planned_actions: tuple[PlannedAction, ...] = ()
    """Actions that would be taken (dry-run mode)."""

    # Transcode tracking for stats
    transcode_skip_reason: str | None = None
    """If transcode was skipped, the reason (e.g., 'codec_matches')."""

    transcode_reasons: tuple[TranscodeReason, ...] = ()
    """Structured reasons why transcoding was performed."""

    # FFmpeg encoding metrics (Issue #264)
    encoding_fps: float | None = None
    """Average encoding FPS from FFmpeg (for stats tracking)."""

    encoding_bitrate_kbps: int | None = None
    """Average encoding bitrate in kbps from FFmpeg (for stats tracking)."""

    total_frames: int | None = None
    """Total frames encoded by FFmpeg (for stats tracking)."""

    encoder_type: str | None = None
    """Encoder type used: 'hardware', 'software', or None if unknown."""

    # Enhanced workflow logging - detailed transformation info
    track_dispositions: tuple[TrackDisposition, ...] = ()
    """Tracks that were removed or kept during filter operations."""

    container_change: ContainerChange | None = None
    """Container conversion details (source -> target format)."""

    track_order_change: tuple[tuple[int, ...], tuple[int, ...]] | None = None
    """Track order before and after (before_indices, after_indices)."""

    size_before: int | None = None
    """File size in bytes before transcode operation."""

    size_after: int | None = None
    """File size in bytes after transcode operation."""

    video_source_codec: str | None = None
    """Source video codec before transcode (e.g., 'h264')."""

    video_target_codec: str | None = None
    """Target video codec after transcode (e.g., 'hevc')."""

    audio_synthesis_created: tuple[str, ...] = ()
    """Descriptions of audio tracks created by synthesis (e.g., 'eng stereo AAC')."""

    transcription_results: tuple[tuple[int, str | None, float, str], ...] = ()
    """Transcription results: (track_index, language, confidence, track_type)."""

    operation_failures: tuple[tuple[str, str], ...] = ()
    """Operations that failed: (operation_name, error_message)."""

    # Phase outcome tracking (for conditional phases feature)
    outcome: PhaseOutcome = PhaseOutcome.PENDING
    """Explicit outcome enum for dependency resolution."""

    skip_reason: SkipReason | None = None
    """Why the phase was skipped (if outcome is SKIPPED)."""

    file_modified: bool = False
    """True if this phase modified the file (for run_if evaluation)."""

    output_path: Path | None = None
    """New file path if container conversion changed it, None otherwise."""


@dataclass(frozen=True)
class FileSnapshot:
    """Immutable snapshot of a file's track layout at a point in time."""

    container_format: str | None
    """Container format string (e.g., 'matroska,webm')."""

    size_bytes: int
    """File size in bytes."""

    tracks: tuple[TrackInfo, ...]
    """Ordered tuple of track info snapshots."""

    @staticmethod
    def from_file_info(file_info: FileInfo) -> FileSnapshot:
        """Create a snapshot from a FileInfo domain object."""
        return FileSnapshot(
            container_format=file_info.container_format,
            size_bytes=file_info.size_bytes,
            tracks=tuple(file_info.tracks),
        )


@dataclass(frozen=True)
class FileProcessingResult:
    """Result from processing a file through all phases."""

    file_path: Path
    """Path to the processed file."""

    success: bool
    """True if all phases completed successfully."""

    phase_results: tuple[PhaseResult, ...]
    """Results from each executed phase."""

    total_duration_seconds: float
    """Total time taken to process the file."""

    total_changes: int
    """Total number of changes made across all phases."""

    # Summary counts
    phases_completed: int
    """Number of phases that completed successfully."""

    phases_failed: int
    """Number of phases that failed."""

    phases_skipped: int
    """Number of phases that were skipped."""

    # Error info
    failed_phase: str | None = None
    """Name of the phase that failed, if any."""

    error_message: str | None = None
    """Error message from failed phase, if any."""

    # Statistics reference
    stats_id: str | None = None
    """UUID of the processing_stats record, for lookup via 'vpo stats detail'."""

    # Before/after snapshots for verbose output
    file_before: FileSnapshot | None = None
    """Track layout snapshot before processing (None if file not in DB)."""

    file_after: FileSnapshot | None = None
    """Track layout snapshot after processing (None if dry-run or failed)."""


class PhaseExecutionError(Exception):
    """Raised when phase execution fails.

    This exception wraps operation-level errors and provides context
    about which phase and operation failed.
    """

    def __init__(
        self,
        phase_name: str,
        operation: str | None,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        """Initialize PhaseExecutionError.

        Args:
            phase_name: Name of the phase that failed.
            operation: Name of the operation that failed, if known.
            message: Human-readable error message.
            cause: The underlying exception, if any.
        """
        self.phase_name = phase_name
        self.operation = operation
        self.message = message
        self.cause = cause
        super().__init__(f"Phase '{phase_name}' failed: {message}")
