"""Service layer for multi-language audio detection.

This module provides the high-level API for analyzing audio tracks to detect
multiple languages, with caching and database persistence.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

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


def analyze_track_languages(
    file_path: Path,
    track_index: int,
    track_id: int,
    track_duration: float,
    file_hash: str,
    transcriber: TranscriptionPlugin,
    config: MultiLanguageDetectionConfig | None = None,
) -> LanguageAnalysisResult:
    """Analyze an audio track for multiple languages.

    Samples the track at multiple positions, detects the language at each
    position, and aggregates results into a LanguageAnalysisResult.

    Args:
        file_path: Path to the video/audio file.
        track_index: Index of the audio track to analyze.
        track_id: Database ID of the track.
        track_duration: Total track duration in seconds.
        file_hash: Content hash of the file for caching.
        transcriber: Transcription plugin supporting multi_language_detection.
        config: Optional configuration for detection parameters.

    Returns:
        LanguageAnalysisResult with classification and language segments.

    Raises:
        LanguageAnalysisError: If analysis fails completely.
        ValueError: If plugin doesn't support multi_language_detection.
    """
    if config is None:
        config = MultiLanguageDetectionConfig()

    # Verify plugin supports the feature
    if not transcriber.supports_feature("multi_language_detection"):
        raise ValueError(
            f"Plugin '{transcriber.name}' does not support multi_language_detection"
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
