"""Data type definitions for Video Policy Orchestrator database.

This module contains all enums and dataclasses for the database layer:
- Database records (FileRecord, TrackRecord, Job, etc.)
- View models for typed query results (FileListViewItem, etc.)

Domain models (TrackInfo, FileInfo, IntrospectionResult) and domain enums
(OriginalDubbedStatus, CommentaryStatus, etc.) are defined in vpo.domain
and re-exported here for backward compatibility.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple

# Import domain types for use in this module and re-export for backward compatibility
from vpo.domain import (
    CommentaryStatus,
    DetectionMethod,
    FileInfo,
    IntrospectionResult,
    OriginalDubbedStatus,
    PluginMetadataDict,
    TrackClassification,
    TrackInfo,
)

# Re-export domain types for backward compatibility
__all__ = [
    # Domain types (re-exported from vpo.domain)
    "TrackInfo",
    "FileInfo",
    "IntrospectionResult",
    "PluginMetadataDict",
    "OriginalDubbedStatus",
    "CommentaryStatus",
    "TrackClassification",
    "DetectionMethod",
]


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
    PRUNE = "prune"  # Prune missing files from library


class JobStatus(Enum):
    """Status of a job in the queue."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    # Container-level metadata tags (JSON-serialized dict, keys lowercase)
    container_tags: str | None = None

    @classmethod
    def from_file_info(cls, info: FileInfo, job_id: str | None = None) -> "FileRecord":
        """Create a FileRecord from a FileInfo domain object."""
        import json

        plugin_metadata_json: str | None = None
        if info.plugin_metadata:
            plugin_metadata_json = json.dumps(info.plugin_metadata)

        from vpo.db.queries.helpers import serialize_container_tags

        container_tags_json = serialize_container_tags(info.container_tags)

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
            container_tags=container_tags_json,
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

    # Origin and batch tracking (unified CLI/daemon jobs)
    origin: str | None = None  # 'cli' or 'daemon' (None = legacy)
    batch_id: str | None = None  # UUID grouping CLI batch operations


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


@dataclass
class TrackClassificationRecord:
    """Database record for track_classification_results table.

    Stores classification results for audio tracks, including original/dubbed
    status, commentary detection, and acoustic analysis profile.

    Attributes:
        id: Primary key (None for new records).
        track_id: Foreign key to tracks.id (unique constraint).
        file_hash: Content hash for cache validation.
        original_dubbed_status: Classification as original, dubbed, or unknown.
        commentary_status: Classification as commentary, main, or unknown.
        confidence: Classification confidence (0.0-1.0).
        detection_method: How classification was determined.
        acoustic_profile_json: JSON-serialized AcousticProfile (optional).
        created_at: ISO-8601 UTC creation timestamp.
        updated_at: ISO-8601 UTC last update timestamp.
    """

    id: int | None
    track_id: int
    file_hash: str
    original_dubbed_status: str  # OriginalDubbedStatus value
    commentary_status: str  # CommentaryStatus value
    confidence: float  # 0.0 - 1.0
    detection_method: str  # DetectionMethod value
    acoustic_profile_json: str | None  # JSON serialized AcousticProfile
    created_at: str  # ISO-8601 UTC
    updated_at: str  # ISO-8601 UTC


@dataclass
class ProcessingStatsRecord:
    """Database record for processing_stats table.

    Stores core statistics for each processing operation including
    file sizes, track counts, transcode info, and status.

    Attributes:
        id: Unique identifier (UUIDv4).
        file_id: Foreign key to files.id.
        processed_at: ISO-8601 UTC timestamp.
        policy_name: Name of policy used.
        size_before: File size in bytes before processing.
        size_after: File size in bytes after processing.
        size_change: Bytes saved (positive) or added (negative).
        audio_tracks_before: Audio track count before processing.
        subtitle_tracks_before: Subtitle track count before processing.
        attachments_before: Attachment count before processing.
        audio_tracks_after: Audio track count after processing.
        subtitle_tracks_after: Subtitle track count after processing.
        attachments_after: Attachment count after processing.
        audio_tracks_removed: Number of audio tracks removed.
        subtitle_tracks_removed: Number of subtitle tracks removed.
        attachments_removed: Number of attachments removed.
        duration_seconds: Total wall-clock processing time.
        phases_completed: Number of phases completed.
        phases_total: Total number of phases in policy.
        total_changes: Total number of changes applied.
        video_source_codec: Original video codec.
        video_target_codec: Target video codec (None if not transcoded).
        video_transcode_skipped: Whether video transcode was skipped.
        video_skip_reason: Reason for skip (codec_matches, etc.).
        audio_tracks_transcoded: Number of audio tracks transcoded.
        audio_tracks_preserved: Number of audio tracks preserved.
        hash_before: File hash before processing.
        hash_after: File hash after processing.
        success: Whether processing succeeded.
        error_message: Error details if failed.
    """

    id: str  # UUIDv4
    file_id: int
    processed_at: str  # ISO-8601 UTC
    policy_name: str

    # Size metrics
    size_before: int
    size_after: int
    size_change: int

    # Track counts (before)
    audio_tracks_before: int
    subtitle_tracks_before: int
    attachments_before: int

    # Track counts (after)
    audio_tracks_after: int
    subtitle_tracks_after: int
    attachments_after: int

    # Track counts (removed)
    audio_tracks_removed: int
    subtitle_tracks_removed: int
    attachments_removed: int

    # Processing metrics
    duration_seconds: float
    phases_completed: int
    phases_total: int
    total_changes: int

    # Transcode info
    video_source_codec: str | None
    video_target_codec: str | None
    video_transcode_skipped: bool
    video_skip_reason: str | None
    audio_tracks_transcoded: int
    audio_tracks_preserved: int

    # File integrity
    hash_before: str | None
    hash_after: str | None

    # Status
    success: bool
    error_message: str | None

    # Hardware encoder tracking (Issue #264)
    encoder_type: str | None = None

    # Job linkage (unified CLI/daemon tracking)
    job_id: str | None = None  # FK to jobs.id (None = legacy)


@dataclass
class ActionResultRecord:
    """Database record for action_results table.

    Stores per-action details within a processing operation.

    Attributes:
        id: Primary key (None for new records).
        stats_id: Foreign key to processing_stats.id.
        action_type: Action type (set_default, set_language, remove, etc.).
        track_type: Track type (audio, video, subtitle, attachment).
        track_index: Index of track affected.
        before_state: JSON-serialized state before action.
        after_state: JSON-serialized state after action.
        success: Whether action succeeded.
        duration_ms: Time taken for this action in milliseconds.
        rule_reference: Policy rule that triggered this action.
        message: Human-readable result message.
    """

    id: int | None
    stats_id: str  # FK to processing_stats.id
    action_type: str
    track_type: str | None
    track_index: int | None

    # State (JSON serialized)
    before_state: str | None
    after_state: str | None

    # Result
    success: bool
    duration_ms: int | None
    rule_reference: str | None
    message: str | None


@dataclass
class PerformanceMetricsRecord:
    """Database record for performance_metrics table.

    Stores per-phase performance data for a processing operation.

    Attributes:
        id: Primary key (None for new records).
        stats_id: Foreign key to processing_stats.id.
        phase_name: Phase name (analyze, remux, transcode, etc.).
        wall_time_seconds: Wall-clock duration in seconds.
        bytes_read: Bytes read from disk.
        bytes_written: Bytes written to disk.
        encoding_fps: Average encoding FPS (transcode phases).
        encoding_bitrate: Average output bitrate in bits/sec.
    """

    id: int | None
    stats_id: str  # FK to processing_stats.id
    phase_name: str

    # Timing
    wall_time_seconds: float

    # I/O metrics
    bytes_read: int | None
    bytes_written: int | None

    # FFmpeg metrics
    encoding_fps: float | None
    encoding_bitrate: int | None


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


@dataclass
class StatsSummary:
    """Aggregate statistics summary for dashboard display.

    Attributes:
        total_files_processed: Total number of files processed.
        total_successful: Number of successful processing runs.
        total_failed: Number of failed processing runs.
        success_rate: Success rate (0.0 to 1.0).
        total_size_before: Total bytes before processing.
        total_size_after: Total bytes after processing.
        total_size_saved: Total bytes saved (positive = saved).
        avg_savings_percent: Average savings as percentage.
        total_audio_removed: Total audio tracks removed.
        total_subtitles_removed: Total subtitle tracks removed.
        total_attachments_removed: Total attachments removed.
        total_videos_transcoded: Total videos transcoded.
        total_videos_skipped: Total videos where transcode was skipped.
        total_audio_transcoded: Total audio tracks transcoded.
        avg_processing_time: Average processing time in seconds.
        earliest_processing: ISO-8601 timestamp of earliest processing.
        latest_processing: ISO-8601 timestamp of latest processing.
    """

    total_files_processed: int
    total_successful: int
    total_failed: int
    success_rate: float  # 0.0 - 1.0

    total_size_before: int  # bytes
    total_size_after: int  # bytes
    total_size_saved: int  # bytes (positive = saved)
    avg_savings_percent: float

    total_audio_removed: int
    total_subtitles_removed: int
    total_attachments_removed: int

    total_videos_transcoded: int
    total_videos_skipped: int
    total_audio_transcoded: int

    avg_processing_time: float  # seconds

    # Time range
    earliest_processing: str | None = None  # ISO-8601
    latest_processing: str | None = None  # ISO-8601

    # Hardware encoder tracking (Issue #264)
    hardware_encodes: int = 0
    software_encodes: int = 0


@dataclass
class PolicyStats:
    """Statistics for a single policy.

    Attributes:
        policy_name: Name of the policy.
        files_processed: Number of files processed with this policy.
        success_rate: Success rate (0.0 to 1.0).
        total_size_saved: Total bytes saved by this policy.
        avg_savings_percent: Average savings as percentage.
        audio_tracks_removed: Total audio tracks removed.
        subtitle_tracks_removed: Total subtitle tracks removed.
        attachments_removed: Total attachments removed.
        videos_transcoded: Total videos transcoded.
        audio_transcoded: Total audio tracks transcoded.
        avg_processing_time: Average processing time in seconds.
        last_used: ISO-8601 timestamp of last use.
    """

    policy_name: str
    files_processed: int
    success_rate: float

    total_size_saved: int
    avg_savings_percent: float

    audio_tracks_removed: int
    subtitle_tracks_removed: int
    attachments_removed: int

    videos_transcoded: int
    audio_transcoded: int

    avg_processing_time: float

    last_used: str  # ISO-8601


@dataclass
class MissingFileViewItem:
    """Typed result for missing files view query.

    Replaces dict return from get_missing_files().

    Attributes:
        id: File primary key.
        path: Full file path.
        filename: File name only.
        size_bytes: File size in bytes (may be None).
        scanned_at: ISO-8601 timestamp of last scan (may be None).
    """

    id: int
    path: str
    filename: str
    size_bytes: int | None
    scanned_at: str | None


@dataclass
class DistributionItem:
    """A single category in a distribution count."""

    label: str
    count: int


@dataclass
class LibraryDistribution:
    """Distribution data for library composition pie charts."""

    containers: list[DistributionItem]
    video_codecs: list[DistributionItem]
    audio_codecs: list[DistributionItem]


@dataclass
class FileProcessingHistory:
    """Processing history entry for a file.

    Attributes:
        stats_id: Processing stats ID (UUID).
        processed_at: ISO-8601 timestamp of processing.
        policy_name: Policy used for processing.
        size_before: File size before processing.
        size_after: File size after processing.
        size_change: Size change (positive = saved).
        audio_removed: Number of audio tracks removed.
        subtitle_removed: Number of subtitle tracks removed.
        attachments_removed: Number of attachments removed.
        duration_seconds: Processing duration in seconds.
        success: Whether processing succeeded.
        error_message: Error message if failed.
        encoder_type: 'hardware', 'software', or None if unknown.
    """

    stats_id: str
    processed_at: str
    policy_name: str

    size_before: int
    size_after: int
    size_change: int

    audio_removed: int
    subtitle_removed: int
    attachments_removed: int

    duration_seconds: float
    success: bool
    error_message: str | None
    encoder_type: str | None = None


@dataclass
class ActionSummary:
    """Summary of an action performed during processing.

    Simplified view of action_results for display in stats detail.

    Attributes:
        action_type: Type of action (set_default, remove, etc.).
        track_type: Track type affected (audio, video, subtitle, attachment).
        track_index: Index of track affected.
        success: Whether action succeeded.
        message: Human-readable result message.
    """

    action_type: str
    track_type: str | None
    track_index: int | None
    success: bool
    message: str | None


@dataclass
class StatsDetailView:
    """Detailed view of a processing stats record with actions.

    Combines processing_stats with action_results for detailed display.

    Attributes:
        stats_id: Processing stats ID (UUID).
        file_id: ID of file processed.
        file_path: Path to file (if available).
        filename: Filename (if available).
        processed_at: ISO-8601 timestamp of processing.
        policy_name: Policy used for processing.
        size_before: File size before processing.
        size_after: File size after processing.
        size_change: Size change (positive = saved).
        audio_tracks_before: Audio track count before.
        audio_tracks_after: Audio track count after.
        audio_tracks_removed: Number of audio tracks removed.
        subtitle_tracks_before: Subtitle track count before.
        subtitle_tracks_after: Subtitle track count after.
        subtitle_tracks_removed: Number of subtitle tracks removed.
        attachments_before: Attachment count before.
        attachments_after: Attachment count after.
        attachments_removed: Number of attachments removed.
        video_source_codec: Original video codec.
        video_target_codec: Target codec (if transcoded).
        video_transcode_skipped: Whether video transcode was skipped.
        video_skip_reason: Reason transcode was skipped.
        audio_tracks_transcoded: Number of audio tracks transcoded.
        audio_tracks_preserved: Number of audio tracks preserved.
        duration_seconds: Processing duration in seconds.
        phases_completed: Number of phases completed.
        phases_total: Total phases in policy.
        total_changes: Total changes applied.
        hash_before: File hash before processing.
        hash_after: File hash after processing.
        success: Whether processing succeeded.
        error_message: Error message if failed.
        encoder_type: 'hardware', 'software', or None if unknown.
        actions: List of action summaries.
    """

    stats_id: str
    file_id: int
    file_path: str | None
    filename: str | None
    processed_at: str
    policy_name: str

    size_before: int
    size_after: int
    size_change: int

    audio_tracks_before: int
    audio_tracks_after: int
    audio_tracks_removed: int

    subtitle_tracks_before: int
    subtitle_tracks_after: int
    subtitle_tracks_removed: int

    attachments_before: int
    attachments_after: int
    attachments_removed: int

    video_source_codec: str | None
    video_target_codec: str | None
    video_transcode_skipped: bool
    video_skip_reason: str | None

    audio_tracks_transcoded: int
    audio_tracks_preserved: int

    duration_seconds: float
    phases_completed: int
    phases_total: int
    total_changes: int

    hash_before: str | None
    hash_after: str | None

    success: bool
    error_message: str | None

    # Hardware encoder tracking (Issue #264)
    encoder_type: str | None = None

    actions: list[ActionSummary] = field(default_factory=list)


# ==========================================================================
# Language Analysis View Types
# ==========================================================================


@dataclass
class AnalysisStatusSummary:
    """Summary of language analysis status across the library.

    Attributes:
        total_files: Total files with audio tracks.
        total_tracks: Total audio tracks in library.
        analyzed_tracks: Number of tracks with analysis results.
        pending_tracks: Number of tracks awaiting analysis.
        multi_language_count: Number of tracks classified as multi-language.
        single_language_count: Number of tracks classified as single-language.
    """

    total_files: int
    total_tracks: int
    analyzed_tracks: int
    pending_tracks: int
    multi_language_count: int
    single_language_count: int


@dataclass
class FileAnalysisStatus:
    """Analysis status for a single file.

    Attributes:
        file_id: File primary key.
        file_path: Full file path.
        track_count: Number of audio tracks.
        analyzed_count: Number of tracks with analysis.
    """

    file_id: int
    file_path: str
    track_count: int
    analyzed_count: int


@dataclass
class TrackAnalysisDetail:
    """Detailed analysis result for a single track.

    Attributes:
        track_id: Track primary key.
        track_index: Track index within file.
        language: Original language tag from file metadata.
        classification: Classification (single_language, multi_language).
        primary_language: Primary detected language.
        primary_percentage: Percentage of primary language (0.0-1.0).
        secondary_languages: Comma-separated secondary languages.
        analyzed_at: ISO-8601 timestamp of analysis.
    """

    track_id: int
    track_index: int
    language: str | None
    classification: str
    primary_language: str
    primary_percentage: float
    secondary_languages: str | None
    analyzed_at: str


# ==========================================================================
# Statistics Trend Types (Issue #264)
# ==========================================================================


@dataclass
class TrendDataPoint:
    """Data point for processing trend charts.

    Represents aggregated statistics for a time period (day, week, etc.).

    Attributes:
        date: ISO-8601 date string for the period.
        files_processed: Number of files processed in this period.
        size_saved: Total bytes saved in this period.
        success_count: Number of successful processing runs.
        fail_count: Number of failed processing runs.
    """

    date: str
    files_processed: int
    size_saved: int
    success_count: int
    fail_count: int


# ==========================================================================
# Library Maintenance View Types
# ==========================================================================


@dataclass
class LibraryInfoView:
    """Aggregate library statistics for the info command.

    Attributes:
        total_files: Total number of files in the library.
        files_ok: Files with scan_status='ok'.
        files_missing: Files with scan_status='missing'.
        files_error: Files with scan_status='error'.
        files_pending: Files with scan_status='pending'.
        total_size_bytes: Sum of size_bytes for all files.
        video_tracks: Number of video tracks.
        audio_tracks: Number of audio tracks.
        subtitle_tracks: Number of subtitle tracks.
        attachment_tracks: Number of attachment tracks.
        db_size_bytes: Database file size in bytes.
        db_page_size: Database page size in bytes.
        db_page_count: Total number of database pages.
        db_freelist_count: Number of free pages in the database.
        schema_version: Current database schema version.
    """

    total_files: int
    files_ok: int
    files_missing: int
    files_error: int
    files_pending: int
    total_size_bytes: int
    video_tracks: int
    audio_tracks: int
    subtitle_tracks: int
    attachment_tracks: int
    db_size_bytes: int
    db_page_size: int
    db_page_count: int
    db_freelist_count: int
    schema_version: int


@dataclass
class DuplicateGroup:
    """A group of files sharing the same content_hash.

    Attributes:
        content_hash: The shared content hash.
        file_count: Number of files with this hash.
        total_size_bytes: Total size of all files in the group.
        paths: List of file paths in the group.
    """

    content_hash: str
    file_count: int
    total_size_bytes: int
    paths: list[str]


class ForeignKeyViolation(NamedTuple):
    """A single foreign key constraint violation from PRAGMA foreign_key_check.

    Attributes:
        table: Table containing the violation.
        rowid: Row ID of the violating row.
        parent: Referenced parent table.
        fkid: Foreign key constraint index.
    """

    table: str
    rowid: int
    parent: str
    fkid: int


@dataclass
class IntegrityResult:
    """Result of SQLite integrity and foreign key checks.

    Attributes:
        integrity_ok: True if PRAGMA integrity_check passed.
        integrity_errors: List of error messages from integrity_check.
        foreign_key_ok: True if PRAGMA foreign_key_check passed.
        foreign_key_errors: List of foreign key violations.
    """

    integrity_ok: bool
    integrity_errors: list[str]
    foreign_key_ok: bool
    foreign_key_errors: list[ForeignKeyViolation]


@dataclass
class OptimizeResult:
    """Result of a VACUUM + ANALYZE operation.

    Attributes:
        size_before: Database size in bytes before optimization.
        size_after: Database size in bytes after optimization.
        space_saved: Bytes reclaimed by VACUUM.
        freelist_pages: Number of free pages (before optimization).
        dry_run: Whether this was a dry-run (no changes made).
    """

    size_before: int
    size_after: int
    space_saved: int
    freelist_pages: int
    dry_run: bool
