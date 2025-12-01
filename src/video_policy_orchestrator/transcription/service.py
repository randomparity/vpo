"""Transcription service layer.

This module provides service layers for transcription operations:
1. TranscriptionContext - Shared context for CLI transcription commands
2. TranscriptionService - High-level service for phase executor transcription

The TranscriptionService encapsulates the workflow:
1. Extract audio from track (via smart_detect)
2. Perform multi-sample language detection
3. Persist results to database

Design rationale:
- Single Responsibility: coordinate transcription workflow
- Dependency Injection: accepts transcriber plugin
- Testability: all dependencies explicit
- Type Safety: validates inputs, returns typed results
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from video_policy_orchestrator.db.models import (
    FileRecord,
    TrackRecord,
    TranscriptionResultRecord,
    get_file_by_path,
    get_tracks_for_file,
    get_transcription_result,
    upsert_transcription_result,
)
from video_policy_orchestrator.db.types import TrackClassification, TrackInfo
from video_policy_orchestrator.transcription.audio_extractor import is_ffmpeg_available
from video_policy_orchestrator.transcription.interface import TranscriptionPlugin
from video_policy_orchestrator.transcription.models import detect_track_classification
from video_policy_orchestrator.transcription.multi_sample import (
    AggregatedResult,
    MultiSampleConfig,
    smart_detect,
)
from video_policy_orchestrator.transcription.registry import (
    PluginNotFoundError,
    get_registry,
)

logger = logging.getLogger(__name__)


class TranscriptionSetupError(Exception):
    """Error during transcription setup/validation."""

    pass


@dataclass
class TranscriptionContext:
    """Shared context for transcription operations.

    Contains all validated prerequisites needed to perform transcription
    on audio tracks within a media file.

    Attributes:
        conn: Database connection for storing results. This connection is
            borrowed from the caller (not owned). The caller is responsible
            for connection lifecycle management (creation, closing).
        transcriber: Plugin to use for transcription.
        file_record: Database record for the target file.
        audio_tracks: List of audio tracks to process.
    """

    conn: sqlite3.Connection
    transcriber: TranscriptionPlugin
    file_record: FileRecord
    audio_tracks: list[TrackRecord]


def prepare_transcription_context(
    conn: sqlite3.Connection | None,
    path: Path,
    plugin_name: str | None = None,
) -> TranscriptionContext:
    """Validate prerequisites and prepare context for transcription.

    This function consolidates the common setup logic shared between
    the 'detect' and 'quick' CLI commands:
    - Database connection validation
    - ffmpeg availability check
    - Plugin acquisition
    - File lookup in database
    - Audio track filtering

    Args:
        conn: Database connection (may be None).
        path: Path to the video file to process.
        plugin_name: Optional specific plugin name to use.

    Returns:
        TranscriptionContext with all validated prerequisites.

    Raises:
        TranscriptionSetupError: If any prerequisite check fails.
    """
    # Check database connection
    if conn is None:
        raise TranscriptionSetupError("Database connection not available")

    # Check ffmpeg availability
    if not is_ffmpeg_available():
        raise TranscriptionSetupError(
            "ffmpeg not found. Please install ffmpeg and ensure it's in PATH."
        )

    # Get transcription plugin
    registry = get_registry()
    try:
        if plugin_name:
            transcriber = registry.get(plugin_name)
        else:
            transcriber = registry.get_default()
            if transcriber is None:
                raise TranscriptionSetupError(
                    "No transcription plugins available. "
                    "Install openai-whisper for local transcription."
                )
    except PluginNotFoundError as e:
        raise TranscriptionSetupError(str(e)) from e

    # Get file from database
    file_record = get_file_by_path(conn, str(path.resolve()))
    if file_record is None:
        raise TranscriptionSetupError(
            f"File not found in database. Run 'vpo scan' first: {path}"
        )

    # Get audio tracks
    tracks = get_tracks_for_file(conn, file_record.id)
    audio_tracks = [t for t in tracks if t.track_type == "audio"]

    if not audio_tracks:
        raise TranscriptionSetupError(f"No audio tracks found in: {path}")

    return TranscriptionContext(
        conn=conn,
        transcriber=transcriber,
        file_record=file_record,
        audio_tracks=audio_tracks,
    )


def should_skip_track(
    conn: sqlite3.Connection,
    track: TrackRecord,
    force: bool,
) -> tuple[bool, TranscriptionResultRecord | None]:
    """Check if transcription should be skipped for a track.

    Args:
        conn: Database connection.
        track: Track to check.
        force: Whether to force re-detection.

    Returns:
        Tuple of (should_skip, existing_result).
        If should_skip is True, existing_result contains the cached result.
    """
    existing = get_transcription_result(conn, track.id)
    if existing and not force:
        return True, existing
    return False, None


# ==========================================================================
# TranscriptionService - High-level service for phase executor
# ==========================================================================

# Default confidence threshold for language detection
DEFAULT_CONFIDENCE_THRESHOLD = 0.8


@dataclass
class TranscriptionOptions:
    """Options for transcription analysis."""

    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    max_samples: int = 3
    sample_duration: int = 30
    incumbent_bonus: float = 0.15


@dataclass
class TranscriptionServiceResult:
    """Result of transcribing a single audio track via TranscriptionService."""

    track_index: int
    detected_language: str | None
    confidence: float
    transcript_sample: str | None
    track_type: TrackClassification


class TranscriptionService:
    """Service for coordinating transcription operations in phase executor.

    This service encapsulates the workflow:
    1. Extract audio from track (via smart_detect)
    2. Perform multi-sample language detection
    3. Persist results to database

    Design rationale:
    - Single Responsibility: coordinate transcription workflow
    - Dependency Injection: accepts transcriber plugin
    - Testability: all dependencies explicit
    - Type Safety: validates inputs, returns typed results
    """

    def __init__(self, transcriber: TranscriptionPlugin) -> None:
        """Initialize transcription service.

        Args:
            transcriber: Transcription plugin to use for language detection.
        """
        self.transcriber = transcriber

    def analyze_track(
        self,
        file_path: Path,
        track: TrackInfo,
        track_duration: float,
        options: TranscriptionOptions | None = None,
    ) -> TranscriptionServiceResult:
        """Analyze a single audio track for language detection.

        Args:
            file_path: Path to the media file.
            track: TrackInfo for the audio track to analyze.
            track_duration: Duration of track in seconds.
            options: Transcription options (uses defaults if None).

        Returns:
            TranscriptionServiceResult with detected language and confidence.

        Raises:
            TranscriptionError: If analysis fails.
        """
        if options is None:
            options = TranscriptionOptions()

        logger.debug("Analyzing track %d for language detection", track.index)

        # Create multi-sample config from options
        config = MultiSampleConfig(
            max_samples=options.max_samples,
            sample_duration=options.sample_duration,
            confidence_threshold=options.confidence_threshold,
            incumbent_bonus=options.incumbent_bonus,
        )

        # Perform multi-sample detection
        # NOTE: smart_detect handles audio extraction internally
        aggregated = smart_detect(
            file_path=file_path,
            track_index=track.index,
            track_duration=track_duration,
            transcriber=self.transcriber,
            config=config,
            incumbent_language=track.language,
        )

        # Determine track type from metadata and transcript
        track_type = self._classify_track(track, aggregated)

        return TranscriptionServiceResult(
            track_index=track.index,
            detected_language=aggregated.language,
            confidence=aggregated.confidence,
            transcript_sample=aggregated.transcript_sample,
            track_type=track_type,
        )

    def analyze_and_persist(
        self,
        file_path: Path,
        track: TrackInfo,
        track_duration: float,
        conn: sqlite3.Connection,
        options: TranscriptionOptions | None = None,
    ) -> TranscriptionServiceResult:
        """Analyze track and persist results to database.

        Args:
            file_path: Path to the media file.
            track: TrackInfo for the audio track (must have database ID).
            track_duration: Duration of track in seconds.
            conn: Database connection.
            options: Transcription options.

        Returns:
            TranscriptionServiceResult with detected language.

        Raises:
            ValueError: If track has no database ID.
            TranscriptionError: If analysis fails.
            sqlite3.Error: If database operation fails.
        """
        # Validate track has database ID
        if track.id is None:
            raise ValueError(f"Track {track.index} has no database ID")

        # Analyze the track
        result = self.analyze_track(file_path, track, track_duration, options)

        # Build database record
        now = datetime.now(timezone.utc).isoformat()
        record = TranscriptionResultRecord(
            id=None,  # Will be assigned by database
            track_id=track.id,
            detected_language=result.detected_language,
            confidence_score=result.confidence,
            track_type=result.track_type.value,
            transcript_sample=result.transcript_sample,
            plugin_name=self.transcriber.name,
            created_at=now,
            updated_at=now,
        )

        # Persist to database
        upsert_transcription_result(conn, record)

        logger.info(
            "Track %d: detected language=%s (confidence=%.2f, type=%s)",
            track.index,
            result.detected_language,
            result.confidence,
            result.track_type.value,
        )

        return result

    def _classify_track(
        self,
        track: TrackInfo,
        aggregated: AggregatedResult,
    ) -> TrackClassification:
        """Classify track type using metadata and transcript analysis.

        Uses the detect_track_classification function which applies
        multi-stage detection:
        1. Metadata keywords (most reliable - SFX/MUSIC/COMMENTARY)
        2. Speech detection + confidence (for unlabeled tracks)
        3. Transcript analysis (for commentary detection)

        Args:
            track: TrackInfo with metadata.
            aggregated: AggregatedResult from multi-sample detection.

        Returns:
            TrackClassification enum value.
        """
        # Determine if we detected speech based on confidence
        # Low confidence + empty/hallucinated transcript = no speech
        has_speech = aggregated.confidence > 0.4 or bool(aggregated.transcript_sample)

        return detect_track_classification(
            title=track.title,
            transcript_sample=aggregated.transcript_sample,
            has_speech=has_speech,
            confidence=aggregated.confidence,
        )
