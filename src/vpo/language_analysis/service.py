"""Service layer for multi-language audio detection.

This module provides the high-level API for analyzing audio tracks to detect
multiple languages, with caching and database persistence.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.db import TranscriptionResultRecord

from vpo.db import (
    LanguageAnalysisResultRecord,
    delete_language_analysis_result,
    get_language_analysis_result,
    get_language_segments,
    upsert_language_analysis_result,
    upsert_language_segments,
)
from vpo.language_analysis.models import (
    AnalysisMetadata,
    LanguageAnalysisResult,
    LanguageClassification,
    LanguageSegment,
)
from vpo.transcription.audio_extractor import (
    extract_audio_stream,
)
from vpo.transcription.interface import (
    MultiLanguageDetectionConfig,
    MultiLanguageDetectionResult,
    TranscriptionError,
    TranscriptionPlugin,
)
from vpo.transcription.multi_sample import (
    calculate_sample_positions,
)

logger = logging.getLogger(__name__)


class LanguageAnalysisError(Exception):
    """Exception raised when language analysis fails."""

    pass


class ShortTrackError(LanguageAnalysisError):
    """Exception raised when audio track is too short for reliable analysis.

    Tracks shorter than 30 seconds may not have enough content for
    multi-language detection.
    """

    def __init__(self, track_index: int, duration: float, minimum: float = 30.0):
        self.track_index = track_index
        self.duration = duration
        self.minimum = minimum
        super().__init__(
            f"Track {track_index} is too short for analysis "
            f"({duration:.1f}s, minimum: {minimum:.1f}s)"
        )


class TranscriptionPluginError(LanguageAnalysisError):
    """Exception raised when transcription plugin is unavailable or misconfigured."""

    pass


def analyze_track_languages(
    file_path: Path,
    track_index: int,
    track_id: int,
    track_duration: float,
    file_hash: str,
    transcriber: TranscriptionPlugin,
    config: MultiLanguageDetectionConfig | None = None,
    transcription_result: TranscriptionResultRecord | None = None,
) -> LanguageAnalysisResult:
    """Analyze an audio track for multiple languages.

    Samples the track at multiple positions, detects the language at each
    position, and aggregates results into a LanguageAnalysisResult.

    When transcription_result is provided, the detected language is used
    as a starting point. If the confidence is high enough, a full analysis
    may be skipped for single-language content.

    Args:
        file_path: Path to the video/audio file.
        track_index: Index of the audio track to analyze.
        track_id: Database ID of the track.
        track_duration: Total track duration in seconds.
        file_hash: Content hash of the file for caching.
        transcriber: Transcription plugin supporting multi_language_detection.
        config: Optional configuration for detection parameters.
        transcription_result: Optional existing transcription result for
            the track. If provided and confidence is high, may use this
            as the language without full multi-sample analysis.

    Returns:
        LanguageAnalysisResult with classification and language segments.

    Raises:
        LanguageAnalysisError: If analysis fails completely.
        ShortTrackError: If track is too short for reliable analysis (<30s).
        InsufficientSpeechError: If track has insufficient speech content.
        TranscriptionPluginError: If transcription plugin is unavailable.
        ValueError: If plugin doesn't support multi_language_detection.
    """
    if config is None:
        config = MultiLanguageDetectionConfig()

    # T098: Check for very short audio tracks
    minimum_duration = getattr(config, "minimum_duration", 30.0)
    if track_duration < minimum_duration:
        logger.warning(
            "Track %d is too short for reliable analysis (%.1fs < %.1fs)",
            track_index,
            track_duration,
            minimum_duration,
        )
        raise ShortTrackError(track_index, track_duration, minimum_duration)

    # T076: Check for existing transcription result with high confidence
    # If we have a transcription result with high confidence and the caller
    # doesn't need detailed segment analysis, we can use that directly
    if (
        transcription_result is not None
        and transcription_result.detected_language is not None
        and transcription_result.confidence_score >= config.confidence_threshold
    ):
        # Use transcription result as primary language
        # This provides a fast path for single-language content
        logger.info(
            "Using existing transcription result for track %d: %s (%.2f confidence)",
            track_index,
            transcription_result.detected_language,
            transcription_result.confidence_score,
        )

        now = datetime.now(timezone.utc)
        return LanguageAnalysisResult(
            track_id=track_id,
            file_hash=file_hash,
            primary_language=transcription_result.detected_language,
            primary_percentage=1.0,
            secondary_languages=(),
            classification=LanguageClassification.SINGLE_LANGUAGE,
            segments=(),  # No segments from single-sample transcription
            metadata=AnalysisMetadata(
                plugin_name=transcription_result.plugin_name,
                plugin_version="1.0.0",  # Not stored in transcription result
                model_name="whisper",
                sample_positions=(),  # Single sample, no positions
                sample_duration=30.0,  # Default sample duration
                total_duration=track_duration,
                speech_ratio=1.0,  # Assume speech detected
            ),
            created_at=now,
            updated_at=now,
        )

    # T099: Verify plugin supports the feature
    if not transcriber.supports_feature("multi_language_detection"):
        raise TranscriptionPluginError(
            f"Plugin '{transcriber.name}' does not support multi_language_detection. "
            "Please install openai-whisper or another compatible transcription plugin."
        )

    # Calculate sample positions
    positions = calculate_sample_positions(
        track_duration,
        config.num_samples,
        int(config.sample_duration),
    )

    logger.info(
        "Analyzing track %d (%d samples, %.1fs each) for multi-language detection",
        track_index,
        len(positions),
        config.sample_duration,
    )

    # Collect detection results from each position
    sample_results: list[MultiLanguageDetectionResult] = []
    speech_samples = 0
    total_samples = 0

    for i, position in enumerate(positions):
        logger.debug(
            "Sampling position %.1fs (%d/%d) for track %d",
            position,
            i + 1,
            len(positions),
            track_index,
        )

        try:
            # Extract audio at this position
            audio_data = extract_audio_stream(
                file_path,
                track_index,
                sample_duration=int(config.sample_duration),
                start_offset=position,
            )

            # Detect language at this position
            result = transcriber.detect_multi_language(audio_data)
            # Set the position since plugin doesn't know it
            result.position = position
            sample_results.append(result)

            total_samples += 1
            if result.has_speech:
                speech_samples += 1

            logger.debug(
                "Sample at %.1fs: language=%s, confidence=%.2f, speech=%s",
                position,
                result.language,
                result.confidence,
                result.has_speech,
            )

        except TranscriptionError as e:
            logger.warning("Failed to process sample at %.1fs: %s", position, e)
            sample_results.append(
                MultiLanguageDetectionResult(
                    position=position,
                    language=None,
                    confidence=0.0,
                    has_speech=False,
                    errors=[str(e)],
                )
            )
            total_samples += 1

    if not sample_results:
        raise LanguageAnalysisError(
            f"No samples could be processed for track {track_index}"
        )

    # Calculate speech ratio
    speech_ratio = speech_samples / total_samples if total_samples > 0 else 0.0

    # Convert sample results to language segments
    segments = _create_segments_from_samples(sample_results, config.sample_duration)

    if not segments:
        # No speech detected - create a minimal result
        logger.warning("No speech detected in any samples for track %d", track_index)
        now = datetime.now(timezone.utc)
        return LanguageAnalysisResult(
            track_id=track_id,
            file_hash=file_hash,
            primary_language="und",  # Undetermined
            primary_percentage=1.0,
            secondary_languages=(),
            classification=LanguageClassification.SINGLE_LANGUAGE,
            segments=(),
            metadata=AnalysisMetadata(
                plugin_name=transcriber.name,
                plugin_version=transcriber.version,
                model_name="whisper",
                sample_positions=tuple(positions),
                sample_duration=config.sample_duration,
                total_duration=track_duration,
                speech_ratio=speech_ratio,
            ),
            created_at=now,
            updated_at=now,
        )

    # Create metadata
    metadata = AnalysisMetadata(
        plugin_name=transcriber.name,
        plugin_version=transcriber.version,
        model_name="whisper",
        sample_positions=tuple(positions),
        sample_duration=config.sample_duration,
        total_duration=track_duration,
        speech_ratio=speech_ratio,
    )

    # Create result using from_segments factory
    return LanguageAnalysisResult.from_segments(
        track_id=track_id,
        file_hash=file_hash,
        segments=segments,
        metadata=metadata,
    )


def _create_segments_from_samples(
    samples: list[MultiLanguageDetectionResult],
    sample_duration: float,
) -> list[LanguageSegment]:
    """Convert sample detection results to language segments.

    Each sample becomes a segment representing the detected language
    at that position in the track.

    Args:
        samples: Detection results from each sample position.
        sample_duration: Duration of each sample in seconds.

    Returns:
        List of LanguageSegment objects for samples with detected speech.
    """
    segments = []
    for sample in samples:
        segment = LanguageSegment.from_detection_result(sample, sample_duration)
        if segment is not None:
            segments.append(segment)
    return segments


def get_cached_analysis(
    conn: sqlite3.Connection,
    track_id: int,
    file_hash: str,
) -> LanguageAnalysisResult | None:
    """Get cached language analysis result if valid.

    Checks if a cached result exists and is still valid based on file hash.

    Args:
        conn: Database connection.
        track_id: Database ID of the track.
        file_hash: Current content hash of the file.

    Returns:
        LanguageAnalysisResult if cache is valid, None otherwise.
    """
    record = get_language_analysis_result(conn, track_id)
    if record is None:
        return None

    # Check if file hash matches (cache is still valid)
    if record.file_hash != file_hash:
        logger.debug(
            "Cache miss for track %d: file hash changed (%s != %s)",
            track_id,
            record.file_hash,
            file_hash,
        )
        return None

    # Reconstruct domain model from database records
    return _record_to_result(conn, record)


def _record_to_result(
    conn: sqlite3.Connection,
    record: LanguageAnalysisResultRecord,
) -> LanguageAnalysisResult:
    """Convert database record to domain model.

    Args:
        conn: Database connection (for fetching segments).
        record: Database record.

    Returns:
        LanguageAnalysisResult domain model.
    """
    segment_records = get_language_segments(conn, record.id)
    return LanguageAnalysisResult.from_record(record, segment_records)


def persist_analysis_result(
    conn: sqlite3.Connection,
    result: LanguageAnalysisResult,
) -> int:
    """Persist language analysis result to database.

    Stores the result in language_analysis_results and language_segments tables.

    Args:
        conn: Database connection.
        result: LanguageAnalysisResult to persist.

    Returns:
        ID of the persisted record.
    """
    # Convert domain model to database records
    record, segment_records = result.to_records()

    # Upsert main record
    analysis_id = upsert_language_analysis_result(conn, record)

    # Update segment records with the analysis_id and upsert
    for seg_record in segment_records:
        # Create new record with correct analysis_id (dataclass is not frozen)
        seg_record.analysis_id = analysis_id

    upsert_language_segments(conn, analysis_id, segment_records)

    logger.info(
        "Persisted language analysis for track %d: %s (%.1f%% %s, %d segments)",
        result.track_id,
        result.classification.value,
        result.primary_percentage * 100,
        result.primary_language,
        len(result.segments),
    )

    return analysis_id


def invalidate_analysis_cache(
    conn: sqlite3.Connection,
    track_id: int,
) -> bool:
    """Invalidate cached analysis for a track.

    Call when file content changes and cached results are no longer valid.

    Args:
        conn: Database connection.
        track_id: Database ID of the track.

    Returns:
        True if cache was invalidated, False if no cache existed.
    """
    deleted = delete_language_analysis_result(conn, track_id)
    if deleted:
        logger.debug("Invalidated language analysis cache for track %d", track_id)
    return deleted


def is_analysis_stale(
    result: LanguageAnalysisResult,
    file_hash: str,
    max_age_days: int = 30,
) -> bool:
    """Check if a cached analysis result is stale and needs re-analysis.

    A result is considered stale if:
    - The file hash has changed (content modified)
    - The result is older than max_age_days

    Args:
        result: The cached analysis result.
        file_hash: Current content hash of the file.
        max_age_days: Maximum age in days before result is considered stale.

    Returns:
        True if the result is stale, False otherwise.
    """
    # T079: Check if file hash changed
    if result.file_hash != file_hash:
        logger.debug(
            "Analysis for track %d is stale: file hash changed",
            result.track_id,
        )
        return True

    # Check age
    now = datetime.now(timezone.utc)
    age = now - result.updated_at
    if age > timedelta(days=max_age_days):
        logger.debug(
            "Analysis for track %d is stale: %.1f days old (max: %d)",
            result.track_id,
            age.total_seconds() / 86400,
            max_age_days,
        )
        return True

    return False


def needs_full_analysis(result: LanguageAnalysisResult) -> bool:
    """Check if a result needs upgrade from single-sample to full analysis.

    A result needs full analysis if:
    - It has no segment data (from single-sample transcription)
    - It's marked as single-language but has low confidence indicators

    This is used by T077 to determine if a single-sample transcription
    result should be upgraded to full multi-sample analysis.

    Args:
        result: The analysis result to check.

    Returns:
        True if full multi-sample analysis is needed.
    """
    # No segments means this came from single-sample transcription
    if not result.segments:
        # Check if speech ratio indicates uncertain result
        if result.metadata.speech_ratio < 0.5:
            logger.debug(
                "Analysis for track %d needs full analysis: low speech ratio (%.2f)",
                result.track_id,
                result.metadata.speech_ratio,
            )
            return True

        # If classified as multi-language but no segments, something is wrong
        if result.classification == LanguageClassification.MULTI_LANGUAGE:
            logger.debug(
                "Analysis for track %d needs full analysis: "
                "multi-language without segments",
                result.track_id,
            )
            return True

    return False
