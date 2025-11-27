"""Service layer for multi-language audio detection.

This module provides the high-level API for analyzing audio tracks to detect
multiple languages, with caching and database persistence.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from video_policy_orchestrator.db.models import TranscriptionResultRecord

from video_policy_orchestrator.db.models import (
    LanguageAnalysisResultRecord,
    LanguageSegmentRecord,
    delete_language_analysis_result,
    get_language_analysis_result,
    get_language_segments,
    upsert_language_analysis_result,
    upsert_language_segments,
)
from video_policy_orchestrator.language_analysis.models import (
    AnalysisMetadata,
    LanguageAnalysisResult,
    LanguageClassification,
    LanguagePercentage,
    LanguageSegment,
)
from video_policy_orchestrator.transcription.audio_extractor import (
    extract_audio_stream,
)
from video_policy_orchestrator.transcription.interface import (
    MultiLanguageDetectionConfig,
    MultiLanguageDetectionResult,
    TranscriptionError,
    TranscriptionPlugin,
)
from video_policy_orchestrator.transcription.multi_sample import (
    calculate_sample_positions,
)

logger = logging.getLogger(__name__)


class LanguageAnalysisError(Exception):
    """Exception raised when language analysis fails."""

    pass


class InsufficientSpeechError(LanguageAnalysisError):
    """Exception raised when audio track has insufficient speech for analysis.

    This occurs when the speech ratio is below the minimum threshold,
    indicating the track may be music, sound effects, or silence.
    """

    def __init__(self, track_index: int, speech_ratio: float, threshold: float = 0.1):
        self.track_index = track_index
        self.speech_ratio = speech_ratio
        self.threshold = threshold
        super().__init__(
            f"Track {track_index} has insufficient speech for analysis "
            f"(speech ratio: {speech_ratio:.1%}, threshold: {threshold:.1%})"
        )


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
        if sample.has_speech and sample.language:
            segment = LanguageSegment(
                language_code=sample.language,
                start_time=sample.position,
                end_time=sample.position + sample_duration,
                confidence=sample.confidence,
            )
            segments.append(segment)
    return segments


def get_cached_analysis(
    conn,
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
    conn,
    record: LanguageAnalysisResultRecord,
) -> LanguageAnalysisResult:
    """Convert database record to domain model.

    Args:
        conn: Database connection (for fetching segments).
        record: Database record.

    Returns:
        LanguageAnalysisResult domain model.
    """
    # Fetch segments
    segment_records = get_language_segments(conn, record.id)
    segments = tuple(
        LanguageSegment(
            language_code=seg.language_code,
            start_time=seg.start_time,
            end_time=seg.end_time,
            confidence=seg.confidence,
        )
        for seg in segment_records
    )

    # Parse metadata from JSON
    metadata_dict = (
        json.loads(record.analysis_metadata) if record.analysis_metadata else {}
    )
    metadata = AnalysisMetadata(
        plugin_name=metadata_dict.get("plugin_name", "unknown"),
        plugin_version=metadata_dict.get("plugin_version", "0.0.0"),
        model_name=metadata_dict.get("model_name", "unknown"),
        sample_positions=tuple(metadata_dict.get("sample_positions", [])),
        sample_duration=metadata_dict.get("sample_duration", 30.0),
        total_duration=metadata_dict.get("total_duration", 0.0),
        speech_ratio=metadata_dict.get("speech_ratio", 0.0),
    )

    # Calculate secondary languages from segments
    secondary_languages = _calculate_secondary_languages(
        segments, record.primary_language, record.primary_percentage
    )

    return LanguageAnalysisResult(
        track_id=record.track_id,
        file_hash=record.file_hash,
        primary_language=record.primary_language,
        primary_percentage=record.primary_percentage,
        secondary_languages=secondary_languages,
        classification=LanguageClassification(record.classification),
        segments=segments,
        metadata=metadata,
        created_at=datetime.fromisoformat(record.created_at),
        updated_at=datetime.fromisoformat(record.updated_at),
    )


def _calculate_secondary_languages(
    segments: tuple[LanguageSegment, ...],
    primary_language: str,
    primary_percentage: float,
) -> tuple[LanguagePercentage, ...]:
    """Calculate secondary language percentages from segments.

    Args:
        segments: All language segments.
        primary_language: The primary language code.
        primary_percentage: Primary language percentage.

    Returns:
        Tuple of LanguagePercentage for secondary languages.
    """
    if not segments:
        return ()

    # Count duration per language
    language_durations: dict[str, float] = {}
    for seg in segments:
        duration = seg.end_time - seg.start_time
        language_durations[seg.language_code] = (
            language_durations.get(seg.language_code, 0.0) + duration
        )

    total_duration = sum(language_durations.values())
    if total_duration <= 0:
        return ()

    # Build secondary languages (excluding primary)
    secondary = []
    for lang, duration in language_durations.items():
        if lang != primary_language:
            percentage = duration / total_duration
            if percentage > 0:
                secondary.append(LanguagePercentage(lang, percentage))

    # Sort by percentage descending
    secondary.sort(key=lambda lp: lp.percentage, reverse=True)
    return tuple(secondary)


def persist_analysis_result(
    conn,
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
    now = datetime.now(timezone.utc).isoformat()

    # Serialize metadata to JSON
    metadata_json = json.dumps(
        {
            "plugin_name": result.metadata.plugin_name,
            "plugin_version": result.metadata.plugin_version,
            "model_name": result.metadata.model_name,
            "sample_positions": list(result.metadata.sample_positions),
            "sample_duration": result.metadata.sample_duration,
            "total_duration": result.metadata.total_duration,
            "speech_ratio": result.metadata.speech_ratio,
        }
    )

    # Create main record
    record = LanguageAnalysisResultRecord(
        id=None,
        track_id=result.track_id,
        file_hash=result.file_hash,
        primary_language=result.primary_language,
        primary_percentage=result.primary_percentage,
        classification=result.classification.value,
        analysis_metadata=metadata_json,
        created_at=result.created_at.isoformat(),
        updated_at=now,
    )

    # Upsert main record
    analysis_id = upsert_language_analysis_result(conn, record)

    # Create segment records
    segment_records = [
        LanguageSegmentRecord(
            id=None,
            analysis_id=analysis_id,
            language_code=seg.language_code,
            start_time=seg.start_time,
            end_time=seg.end_time,
            confidence=seg.confidence,
        )
        for seg in result.segments
    ]

    # Upsert segments
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
    conn,
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
    from datetime import timedelta

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
