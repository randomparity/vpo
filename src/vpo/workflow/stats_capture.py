"""Statistics capture utilities for workflow processing.

This module provides helper functions and a StatsCollector class for capturing
processing statistics during workflow execution (040-processing-stats).
"""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection

from vpo.db.queries import (
    insert_action_result,
    insert_performance_metric,
    insert_processing_stats,
)
from vpo.db.types import (
    ActionResultRecord,
    FileInfo,
    PerformanceMetricsRecord,
    ProcessingStatsRecord,
    TrackInfo,
)
from vpo.policy.types import FileProcessingResult

logger = logging.getLogger(__name__)

# Size of chunks to read for partial hash (16 KB)
HASH_CHUNK_SIZE = 16 * 1024


def compute_partial_hash(file_path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """Compute a quick partial hash of a file.

    Reads the first chunk_size bytes of the file to create a fast
    fingerprint for detecting file modifications.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Number of bytes to read (default 16KB).

    Returns:
        Hex-encoded SHA-256 hash of the first chunk_size bytes.

    Raises:
        OSError: If file cannot be read.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        data = f.read(chunk_size)
        hasher.update(data)
    return hasher.hexdigest()


def count_tracks_by_type(
    tracks: list[TrackInfo],
) -> tuple[int, int, int]:
    """Count tracks by type.

    Args:
        tracks: List of TrackInfo objects.

    Returns:
        Tuple of (audio_count, subtitle_count, attachment_count).
    """
    audio_count = 0
    subtitle_count = 0
    attachment_count = 0

    for track in tracks:
        if track.track_type == "audio":
            audio_count += 1
        elif track.track_type == "subtitle":
            subtitle_count += 1
        elif track.track_type == "attachment":
            attachment_count += 1

    return audio_count, subtitle_count, attachment_count


def get_video_codec(tracks: list[TrackInfo]) -> str | None:
    """Get the video codec from tracks.

    Args:
        tracks: List of TrackInfo objects.

    Returns:
        Video codec string, or None if no video track.
    """
    for track in tracks:
        if track.track_type == "video":
            return track.codec
    return None


@dataclass
class ActionCapture:
    """Captured information about a single action."""

    action_type: str
    track_type: str | None = None
    track_index: int | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    success: bool = True
    duration_ms: int | None = None
    rule_reference: str | None = None
    message: str | None = None


@dataclass
class PhaseMetrics:
    """Performance metrics for a single phase."""

    phase_name: str
    wall_time_seconds: float
    bytes_read: int | None = None
    bytes_written: int | None = None
    encoding_fps: float | None = None
    encoding_bitrate: int | None = None


@dataclass
class StatsCollector:
    """Collector for processing statistics.

    This class accumulates statistics during workflow processing and
    persists them to the database when complete.

    Usage:
        collector = StatsCollector(conn, file_id, policy_name)
        collector.capture_before_state(file_info, size_before)
        # ... run workflow ...
        collector.capture_after_state(file_info, size_after, result)
        collector.persist()
    """

    conn: Connection
    file_id: int
    policy_name: str

    # Generated ID
    stats_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Job linkage (unified CLI/daemon tracking)
    job_id: str | None = None  # FK to jobs.id

    # Pre-processing state
    size_before: int = 0
    hash_before: str | None = None
    audio_before: int = 0
    subtitle_before: int = 0
    attachments_before: int = 0
    video_source_codec: str | None = None

    # Post-processing state
    size_after: int = 0
    hash_after: str | None = None
    audio_after: int = 0
    subtitle_after: int = 0
    attachments_after: int = 0

    # Transcode tracking
    video_target_codec: str | None = None
    video_transcode_skipped: bool = False
    video_skip_reason: str | None = None
    audio_tracks_transcoded: int = 0
    audio_tracks_preserved: int = 0
    encoder_type: str | None = None  # 'hardware', 'software', or None

    # Processing metrics
    duration_seconds: float = 0.0
    phases_completed: int = 0
    phases_total: int = 0
    total_changes: int = 0
    success: bool = True
    error_message: str | None = None

    # Captured actions and metrics
    actions: list[ActionCapture] = field(default_factory=list)
    phase_metrics: list[PhaseMetrics] = field(default_factory=list)

    def capture_before_state(
        self,
        file_info: FileInfo | None,
        file_path: Path,
    ) -> None:
        """Capture the file state before processing.

        Args:
            file_info: FileInfo from database (may be None for unscanned files).
            file_path: Path to the file.
        """
        try:
            stat = file_path.stat()
            self.size_before = stat.st_size
        except OSError as e:
            logger.debug("Failed to stat file before processing: %s - %s", file_path, e)
            self.size_before = 0

        try:
            self.hash_before = compute_partial_hash(file_path)
        except OSError as e:
            logger.debug("Failed to hash file before processing: %s - %s", file_path, e)
            self.hash_before = None

        if file_info and file_info.tracks:
            counts = count_tracks_by_type(file_info.tracks)
            self.audio_before = counts[0]
            self.subtitle_before = counts[1]
            self.attachments_before = counts[2]
            self.video_source_codec = get_video_codec(file_info.tracks)

    def capture_after_state(
        self,
        file_info: FileInfo | None,
        file_path: Path,
        result: FileProcessingResult,
    ) -> None:
        """Capture the file state after processing.

        Args:
            file_info: Updated FileInfo after processing (may be None).
            file_path: Path to the file.
            result: FileProcessingResult from workflow.
        """
        try:
            stat = file_path.stat()
            self.size_after = stat.st_size
        except OSError as e:
            logger.debug("Failed to stat file after processing: %s - %s", file_path, e)
            self.size_after = self.size_before

        try:
            self.hash_after = compute_partial_hash(file_path)
        except OSError as e:
            logger.debug("Failed to hash file after processing: %s - %s", file_path, e)
            self.hash_after = None

        if file_info and file_info.tracks:
            counts = count_tracks_by_type(file_info.tracks)
            self.audio_after = counts[0]
            self.subtitle_after = counts[1]
            self.attachments_after = counts[2]
        else:
            # No re-introspection available, assume counts unchanged
            self.audio_after = self.audio_before
            self.subtitle_after = self.subtitle_before
            self.attachments_after = self.attachments_before

        # Copy results
        self.duration_seconds = result.total_duration_seconds
        self.phases_completed = result.phases_completed
        self.total_changes = result.total_changes
        self.success = result.success
        self.error_message = result.error_message

    def add_action(self, action: ActionCapture) -> None:
        """Add an action capture.

        Args:
            action: ActionCapture to record.
        """
        self.actions.append(action)

    def add_phase_metrics(self, metrics: PhaseMetrics) -> None:
        """Add phase metrics.

        Args:
            metrics: PhaseMetrics to record.
        """
        self.phase_metrics.append(metrics)

    def set_video_transcode_info(
        self,
        target_codec: str | None = None,
        skipped: bool = False,
        skip_reason: str | None = None,
        encoder_type: str | None = None,
    ) -> None:
        """Set video transcode information.

        Args:
            target_codec: Target video codec (None if not transcoded).
            skipped: Whether transcode was skipped due to skip_if.
            skip_reason: Reason for skip (codec_matches, etc.).
            encoder_type: 'hardware', 'software', or None if unknown.
        """
        self.video_target_codec = target_codec
        self.video_transcode_skipped = skipped
        self.video_skip_reason = skip_reason
        self.encoder_type = encoder_type

    def set_audio_transcode_counts(
        self,
        transcoded: int = 0,
        preserved: int = 0,
    ) -> None:
        """Set audio transcode counts.

        Args:
            transcoded: Number of audio tracks transcoded.
            preserved: Number of audio tracks preserved (not transcoded).
        """
        self.audio_tracks_transcoded = transcoded
        self.audio_tracks_preserved = preserved

    def persist(self) -> str:
        """Persist collected statistics to database.

        All inserts are performed atomically within a single transaction.
        If any insert fails, all changes are rolled back.

        Returns:
            The stats_id (UUID) of the persisted record.
        """
        try:
            # Calculate derived values
            size_change = self.size_before - self.size_after
            audio_removed = self.audio_before - self.audio_after
            subtitle_removed = self.subtitle_before - self.subtitle_after
            attachments_removed = self.attachments_before - self.attachments_after

            # Create main stats record
            stats_record = ProcessingStatsRecord(
                id=self.stats_id,
                file_id=self.file_id,
                processed_at=datetime.now(timezone.utc).isoformat(),
                policy_name=self.policy_name,
                size_before=self.size_before,
                size_after=self.size_after,
                size_change=size_change,
                audio_tracks_before=self.audio_before,
                subtitle_tracks_before=self.subtitle_before,
                attachments_before=self.attachments_before,
                audio_tracks_after=self.audio_after,
                subtitle_tracks_after=self.subtitle_after,
                attachments_after=self.attachments_after,
                audio_tracks_removed=max(0, audio_removed),
                subtitle_tracks_removed=max(0, subtitle_removed),
                attachments_removed=max(0, attachments_removed),
                duration_seconds=self.duration_seconds,
                phases_completed=self.phases_completed,
                phases_total=self.phases_total,
                total_changes=self.total_changes,
                video_source_codec=self.video_source_codec,
                video_target_codec=self.video_target_codec,
                video_transcode_skipped=self.video_transcode_skipped,
                video_skip_reason=self.video_skip_reason,
                audio_tracks_transcoded=self.audio_tracks_transcoded,
                audio_tracks_preserved=self.audio_tracks_preserved,
                hash_before=self.hash_before,
                hash_after=self.hash_after,
                success=self.success,
                error_message=self.error_message,
                encoder_type=self.encoder_type,
                job_id=self.job_id,
            )

            insert_processing_stats(self.conn, stats_record)
            logger.debug(
                "Persisted processing stats %s for file_id %d",
                self.stats_id,
                self.file_id,
            )

            # Persist action results
            for action in self.actions:
                action_record = ActionResultRecord(
                    id=None,
                    stats_id=self.stats_id,
                    action_type=action.action_type,
                    track_type=action.track_type,
                    track_index=action.track_index,
                    before_state=json.dumps(action.before_state)
                    if action.before_state
                    else None,
                    after_state=json.dumps(action.after_state)
                    if action.after_state
                    else None,
                    success=action.success,
                    duration_ms=action.duration_ms,
                    rule_reference=action.rule_reference,
                    message=action.message,
                )
                insert_action_result(self.conn, action_record)

            # Persist phase metrics
            for metrics in self.phase_metrics:
                metric_record = PerformanceMetricsRecord(
                    id=None,
                    stats_id=self.stats_id,
                    phase_name=metrics.phase_name,
                    wall_time_seconds=metrics.wall_time_seconds,
                    bytes_read=metrics.bytes_read,
                    bytes_written=metrics.bytes_written,
                    encoding_fps=metrics.encoding_fps,
                    encoding_bitrate=metrics.encoding_bitrate,
                )
                insert_performance_metric(self.conn, metric_record)

            # Commit all inserts atomically
            self.conn.commit()

            logger.debug(
                "Persisted %d actions and %d phase metrics for stats %s",
                len(self.actions),
                len(self.phase_metrics),
                self.stats_id,
            )

            return self.stats_id
        except Exception:
            self.conn.rollback()
            raise
