"""Data type definitions for Video Policy Orchestrator database.

This module contains all enums and dataclasses for the database layer:
- Domain models (TrackInfo, FileInfo, IntrospectionResult)
- Database records (FileRecord, TrackRecord, Job, etc.)
- View models for typed query results (FileListViewItem, etc.)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class OperationStatus(Enum):
    """Status of a policy operation."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class JobType(Enum):
    """Type of job in the queue."""

    TRANSCODE = "transcode"
    MOVE = "move"
    SCAN = "scan"  # Directory scan operation
    APPLY = "apply"  # Policy application operation
    PROCESS = "process"  # Full workflow processing (analyze → apply → transcode)


class JobStatus(Enum):
    """Status of a job in the queue."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrackClassification(Enum):
    """Classification of audio track purpose.

    Detection priority:
    1. MUSIC/SFX: Identified by metadata keywords (title)
    2. NON_SPEECH: Detected via transcription analysis (no speech/low confidence)
    3. COMMENTARY: Identified by metadata keywords or transcript content
    4. ALTERNATE: Identified as non-main dialog track
    5. MAIN: Default for dialog tracks
    """

    MAIN = "main"  # Primary audio track with dialog
    COMMENTARY = "commentary"  # Director/cast commentary
    ALTERNATE = "alternate"  # Alternate mix with dialog
    MUSIC = "music"  # Score, soundtrack (metadata-identified)
    SFX = "sfx"  # Sound effects, ambient (metadata-identified)
    NON_SPEECH = "non_speech"  # Unlabeled track detected as no speech


class PlanStatus(Enum):
    """Status of a plan in the approval workflow.

    State transitions:
        pending → approved   (approve action)
        pending → rejected   (reject action)
        pending → canceled   (cancel action or timeout)
        approved → applied   (execution job completes)
        approved → canceled  (cancel action before execution)

    Terminal states: rejected, applied, canceled
    """

    PENDING = "pending"  # Awaiting operator review
    APPROVED = "approved"  # Approved for execution
    REJECTED = "rejected"  # Rejected by operator (terminal)
    APPLIED = "applied"  # Changes have been executed (terminal)
    CANCELED = "canceled"  # Withdrawn by operator or system (terminal)


@dataclass
class TrackInfo:
    """Represents a media track within a video file (domain model)."""

    index: int
    track_type: str  # "video", "audio", "subtitle", "attachment", "other"
    # Database ID (optional, set when loaded from database)
    # Used for linking to related data like language analysis results
    id: int | None = None
    codec: str | None = None
    language: str | None = None
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False
    # Audio-specific fields (003-media-introspection)
    channels: int | None = None
    channel_layout: str | None = None  # Human-readable: "stereo", "5.1", etc.
    # Video-specific fields (003-media-introspection)
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None  # Stored as string to preserve precision
    # HDR color metadata fields (034-conditional-video-transcode)
    color_transfer: str | None = None  # e.g., "smpte2084" (PQ), "arib-std-b67" (HLG)
    color_primaries: str | None = None  # e.g., "bt2020"
    color_space: str | None = None  # e.g., "bt2020nc"
    color_range: str | None = None  # e.g., "tv", "pc"
    # Track duration (035-multi-language-audio-detection)
    duration_seconds: float | None = None  # Duration in seconds


@dataclass
class FileInfo:
    """Represents a scanned video file with its tracks (domain model)."""

    path: Path
    filename: str
    directory: Path
    extension: str
    size_bytes: int
    modified_at: datetime
    content_hash: str | None = None
    container_format: str | None = None
    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scan_status: str = "ok"  # "ok", "error", "pending"
    scan_error: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)
    # Plugin-provided metadata (039-plugin-metadata-policy)
    # Dict keyed by plugin name, e.g., {"radarr": {"original_language": "jpn", ...}}
    plugin_metadata: dict[str, dict[str, str | int | float | bool | None]] | None = None


@dataclass
class IntrospectionResult:
    """Result of media file introspection."""

    file_path: Path
    container_format: str | None
    tracks: list[TrackInfo]
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        """Return True if introspection completed without fatal errors."""
        return self.error is None

    @property
    def primary_video_track(self) -> TrackInfo | None:
        """Return the first video track, or None if no video tracks exist."""
        return next((t for t in self.tracks if t.track_type == "video"), None)

    @property
    def duration_seconds(self) -> float | None:
        """Return duration from primary video track, or None if unavailable."""
        video = self.primary_video_track
        return video.duration_seconds if video else None


@dataclass
class FileRecord:
    """Database record for files table."""

    id: int | None
    path: str
    filename: str
    directory: str
    extension: str
    size_bytes: int
    modified_at: str  # ISO 8601
    content_hash: str | None
    container_format: str | None
    scanned_at: str  # ISO 8601
    scan_status: str
    scan_error: str | None
    job_id: str | None = None  # UUID of scan job that discovered/updated this file
    # Plugin-provided metadata (039-plugin-metadata-policy)
    # JSON-serialized dict keyed by plugin name
    plugin_metadata: str | None = None

    @classmethod
    def from_file_info(cls, info: FileInfo, job_id: str | None = None) -> "FileRecord":
        """Create a FileRecord from a FileInfo domain object."""
        import json

        plugin_metadata_json: str | None = None
        if info.plugin_metadata:
            plugin_metadata_json = json.dumps(info.plugin_metadata)

        return cls(
            id=None,
            path=str(info.path),
            filename=info.filename,
            directory=str(info.directory),
            extension=info.extension,
            size_bytes=info.size_bytes,
            modified_at=info.modified_at.isoformat(),
            content_hash=info.content_hash,
            container_format=info.container_format,
            scanned_at=info.scanned_at.isoformat(),
            scan_status=info.scan_status,
            scan_error=info.scan_error,
            job_id=job_id,
            plugin_metadata=plugin_metadata_json,
        )


@dataclass
class TrackRecord:
    """Database record for tracks table."""

    id: int | None
    file_id: int
    track_index: int
    track_type: str
    codec: str | None
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
    # New fields (003-media-introspection)
    channels: int | None = None
    channel_layout: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None
    # HDR color metadata fields (034-conditional-video-transcode)
    color_transfer: str | None = None
    color_primaries: str | None = None
    color_space: str | None = None
    color_range: str | None = None
    # Track duration (035-multi-language-audio-detection)
    duration_seconds: float | None = None

    @classmethod
    def from_track_info(cls, info: TrackInfo, file_id: int) -> "TrackRecord":
        """Create a TrackRecord from a TrackInfo domain object."""
        return cls(
            id=None,
            file_id=file_id,
            track_index=info.index,
            track_type=info.track_type,
            codec=info.codec,
            language=info.language,
            title=info.title,
            is_default=info.is_default,
            is_forced=info.is_forced,
            channels=info.channels,
            channel_layout=info.channel_layout,
            width=info.width,
            height=info.height,
            frame_rate=info.frame_rate,
            color_transfer=info.color_transfer,
            color_primaries=info.color_primaries,
            color_space=info.color_space,
            color_range=info.color_range,
            duration_seconds=info.duration_seconds,
        )

    def to_track_info(self) -> TrackInfo:
        """Convert TrackRecord to TrackInfo domain object.

        This is the inverse of from_track_info(), allowing bidirectional
        conversion between database records and domain objects.

        Returns:
            TrackInfo domain object suitable for policy evaluation.
        """
        return TrackInfo(
            index=self.track_index,
            track_type=self.track_type,
            codec=self.codec,
            language=self.language,
            title=self.title,
            is_default=self.is_default,
            is_forced=self.is_forced,
            channels=self.channels,
            channel_layout=self.channel_layout,
            width=self.width,
            height=self.height,
            frame_rate=self.frame_rate,
            color_transfer=self.color_transfer,
            color_primaries=self.color_primaries,
            color_space=self.color_space,
            color_range=self.color_range,
            duration_seconds=self.duration_seconds,
            id=self.id,
        )


def tracks_to_track_info(records: list[TrackRecord]) -> list[TrackInfo]:
    """Convert list of TrackRecord to list of TrackInfo.

    Convenience function for batch conversion.

    Args:
        records: List of database track records.

    Returns:
        List of TrackInfo domain objects.
    """
    return [r.to_track_info() for r in records]


@dataclass
class OperationRecord:
    """Database record for operations table (audit log).

    Tracks policy operations applied to media files for audit purposes.
    """

    id: str  # UUID
    file_id: int
    file_path: str  # Path at time of operation
    policy_name: str  # Name/path of policy used
    policy_version: int  # Schema version of policy
    actions_json: str  # Serialized list of applied actions
    status: OperationStatus
    started_at: str  # ISO 8601 UTC
    error_message: str | None = None
    backup_path: str | None = None
    completed_at: str | None = None  # ISO 8601 UTC


@dataclass
class PlanRecord:
    """Database record for plans table.

    Persisted representation of a planned change set awaiting approval.
    Tracks policy evaluation results through the approval workflow.

    Attributes:
        id: Unique identifier (UUIDv4).
        file_id: Reference to the target file (nullable if file deleted).
        file_path: Cached file path (for display when file deleted).
        policy_name: Name of the policy that generated the plan.
        policy_version: Version of the policy at evaluation time.
        job_id: Reference to originating job (if from batch evaluation).
        actions_json: JSON-serialized list of PlannedAction.
        action_count: Number of planned actions (cached for display).
        requires_remux: Whether plan requires container remux.
        status: Plan status enum value.
        created_at: ISO-8601 UTC creation timestamp.
        updated_at: ISO-8601 UTC last update timestamp.
    """

    id: str  # UUID
    file_id: int | None  # FK to files.id, nullable for deleted files
    file_path: str  # Cached at creation time
    policy_name: str
    policy_version: int
    job_id: str | None  # Reference to originating job
    actions_json: str  # JSON-serialized PlannedAction list
    action_count: int  # Cached for list display
    requires_remux: bool
    status: PlanStatus
    created_at: str  # ISO-8601 UTC
    updated_at: str  # ISO-8601 UTC


@dataclass
class PluginAcknowledgment:
    """Database record for plugin_acknowledgments table.

    Records user acknowledgments for directory-based plugins.
    Used to track which plugins the user has explicitly trusted.
    """

    id: int | None
    plugin_name: str
    plugin_hash: str  # SHA-256 hash of plugin file(s)
    acknowledged_at: str  # ISO 8601 UTC
    acknowledged_by: str | None = None  # Hostname or user identifier


@dataclass
class JobProgress:
    """Detailed progress information for a running job."""

    percent: float  # Overall percentage 0-100

    # For transcoding jobs
    frame_current: int | None = None
    frame_total: int | None = None
    time_current: float | None = None  # Seconds
    time_total: float | None = None  # Seconds
    fps: float | None = None  # Current encoding FPS
    bitrate: str | None = None  # Current bitrate
    size_current: int | None = None  # Output size so far (bytes)

    # Estimates
    eta_seconds: int | None = None  # Estimated time remaining


@dataclass
class Job:
    """Database record for jobs table."""

    id: str  # UUID v4
    file_id: int | None  # FK to files.id (None for scan jobs)
    file_path: str  # Path at time of job creation
    job_type: JobType  # TRANSCODE, MOVE, SCAN, or APPLY
    status: JobStatus  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    priority: int  # Lower = higher priority (default: 100)

    # Policy reference
    policy_name: str | None  # Name of policy used
    policy_json: str | None  # Serialized policy settings for this job

    # Progress tracking
    progress_percent: float  # 0.0 - 100.0
    progress_json: str | None  # Detailed progress (frames, time, etc.)

    # Timing (all ISO-8601 UTC)
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None

    # Worker tracking
    worker_pid: int | None = None  # PID of worker processing this job
    worker_heartbeat: str | None = None  # ISO-8601 UTC, updated periodically

    # Results
    output_path: str | None = None  # Path to output file
    backup_path: str | None = None  # Path to backup of original
    error_message: str | None = None  # Error details if FAILED

    # Extended fields (008-operational-ux)
    files_affected_json: str | None = None  # JSON array of affected file paths
    summary_json: str | None = None  # Job-specific summary (e.g., scan counts)

    # Log file reference (016-job-detail-view)
    log_path: str | None = None  # Relative path to log file from VPO data directory


@dataclass
class TranscriptionResultRecord:
    """Database record for transcription_results table."""

    id: int | None
    track_id: int
    detected_language: str | None
    confidence_score: float
    track_type: str  # 'main', 'commentary', 'alternate'
    transcript_sample: str | None
    plugin_name: str
    created_at: str  # ISO-8601 UTC
    updated_at: str  # ISO-8601 UTC


@dataclass
class LanguageAnalysisResultRecord:
    """Database record for language_analysis_results table.

    Stores aggregated language analysis for an audio track, including
    the primary language, classification, and analysis metadata.

    Attributes:
        id: Primary key (None for new records).
        track_id: Foreign key to tracks.id (unique constraint).
        file_hash: Content hash for cache validation.
        primary_language: ISO 639-2/B code of primary language.
        primary_percentage: Percentage of track in primary language (0.0-1.0).
        classification: 'SINGLE_LANGUAGE' or 'MULTI_LANGUAGE'.
        analysis_metadata: JSON string with analysis details.
        created_at: ISO-8601 UTC creation timestamp.
        updated_at: ISO-8601 UTC last update timestamp.
    """

    id: int | None
    track_id: int
    file_hash: str
    primary_language: str
    primary_percentage: float
    classification: str  # 'SINGLE_LANGUAGE' or 'MULTI_LANGUAGE'
    analysis_metadata: str | None  # JSON string
    created_at: str  # ISO-8601 UTC
    updated_at: str  # ISO-8601 UTC


@dataclass
class LanguageSegmentRecord:
    """Database record for language_segments table.

    Stores individual language detection segments within an analysis.

    Attributes:
        id: Primary key (None for new records).
        analysis_id: Foreign key to language_analysis_results.id.
        language_code: ISO 639-2/B language code.
        start_time: Start position in seconds.
        end_time: End position in seconds.
        confidence: Detection confidence (0.0-1.0).
    """

    id: int | None
    analysis_id: int
    language_code: str
    start_time: float
    end_time: float
    confidence: float


# ==========================================================================
# View Model Dataclasses
# ==========================================================================
# These dataclasses represent typed results from view/aggregation queries
# that previously returned raw dicts. They provide type safety and IDE support.


@dataclass
class FileListViewItem:
    """Typed result for library list view query.

    Replaces dict return from get_files_filtered(). Contains file metadata
    with aggregated track information for list display.

    Attributes:
        id: File primary key.
        path: Full file path.
        filename: File name only.
        scanned_at: ISO-8601 timestamp of last scan.
        scan_status: Status code (ok, error, pending).
        scan_error: Error message if scan failed.
        video_title: Title from video track metadata.
        width: Video width in pixels.
        height: Video height in pixels.
        audio_languages: Comma-separated language codes from GROUP_CONCAT.
    """

    id: int
    path: str
    filename: str
    scanned_at: str
    scan_status: str
    scan_error: str | None
    video_title: str | None
    width: int | None
    height: int | None
    audio_languages: str | None


@dataclass
class LanguageOption:
    """Language option for filter dropdowns.

    Replaces dict return from get_distinct_audio_languages().

    Attributes:
        code: ISO 639-2/B language code.
        label: Human-readable language label.
    """

    code: str
    label: str


@dataclass
class TranscriptionListViewItem:
    """Typed result for transcriptions overview query.

    Replaces dict return from get_files_with_transcriptions().

    Attributes:
        id: File primary key.
        filename: File name only.
        path: Full file path.
        scan_status: Status code (ok, error, pending).
        transcription_count: Number of transcriptions for this file.
        detected_languages: Comma-separated detected language codes.
        avg_confidence: Average confidence score across transcriptions.
    """

    id: int
    filename: str
    path: str
    scan_status: str
    transcription_count: int
    detected_languages: str | None
    avg_confidence: float | None


@dataclass
class TranscriptionDetailView:
    """Typed result for transcription detail query.

    Replaces dict return from get_transcription_detail(). Contains joined
    data from transcriptions, tracks, and files tables.

    Attributes:
        id: Transcription primary key.
        track_id: Foreign key to tracks table.
        detected_language: Detected language code.
        confidence_score: Detection confidence (0.0-1.0).
        track_type: Type of track (audio, subtitle).
        transcript_sample: Sample text from transcription.
        plugin_name: Name of plugin that created this transcription.
        created_at: ISO-8601 timestamp of creation.
        updated_at: ISO-8601 timestamp of last update.
        track_index: Track index within the file.
        codec: Track codec name.
        original_language: Original language tag from file.
        title: Track title from metadata.
        channels: Number of audio channels.
        channel_layout: Audio channel layout string.
        is_default: Whether track is marked as default (0 or 1).
        is_forced: Whether track is marked as forced (0 or 1).
        file_id: Foreign key to files table.
        filename: File name only.
        path: Full file path.
    """

    id: int
    track_id: int
    detected_language: str | None
    confidence_score: float
    track_type: str
    transcript_sample: str | None
    plugin_name: str
    created_at: str
    updated_at: str
    track_index: int
    codec: str | None
    original_language: str | None
    title: str | None
    channels: int | None
    channel_layout: str | None
    is_default: int
    is_forced: int
    file_id: int
    filename: str
    path: str


@dataclass
class ScanErrorView:
    """Typed result for scan job error listing.

    Contains file path and error information for files that failed
    during a scan job.

    Attributes:
        path: Full file path.
        filename: File name only.
        error: Error message from scan failure.
    """

    path: str
    filename: str
    error: str
