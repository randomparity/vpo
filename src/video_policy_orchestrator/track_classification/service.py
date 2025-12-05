"""Track classification service.

Main entry point for classifying audio tracks. Orchestrates metadata lookup,
acoustic analysis, and result persistence.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone

from video_policy_orchestrator.db.queries import (
    get_classifications_for_file,
    get_tracks_for_file,
    upsert_track_classification,
)
from video_policy_orchestrator.db.types import (
    CommentaryStatus,
    DetectionMethod,
    FileRecord,
    OriginalDubbedStatus,
    TrackClassificationRecord,
    TrackRecord,
)

from .metadata import determine_original_track, get_original_language_from_metadata
from .models import (
    AcousticProfile,
    ClassificationError,
    TrackClassificationResult,
)

logger = logging.getLogger(__name__)


def classify_track(
    conn: sqlite3.Connection,
    track: TrackRecord,
    file_record: FileRecord,
    original_language: str | None = None,
    language_analysis: dict[int, str] | None = None,
    acoustic_profile: AcousticProfile | None = None,
    all_audio_tracks: list[TrackRecord] | None = None,
) -> TrackClassificationResult:
    """Classify a single audio track.

    Applies classification logic in priority order:
    1. Metadata-based classification (original language from external sources)
    2. Position-based heuristic (first track often original)
    3. Acoustic analysis (commentary detection)

    Args:
        conn: Database connection.
        track: Track record to classify.
        file_record: Parent file record.
        original_language: Original language from external metadata.
        language_analysis: Map of track_id to detected language.
        acoustic_profile: Acoustic analysis results (for commentary detection).
        all_audio_tracks: All audio tracks in file (for relative comparison).

    Returns:
        TrackClassificationResult with classification determination.

    Raises:
        ClassificationError: If classification fails.
    """
    if track.track_type != "audio":
        raise ClassificationError(
            f"Cannot classify non-audio track: type={track.track_type}"
        )

    # Determine original/dubbed status
    original_dubbed_status = OriginalDubbedStatus.UNKNOWN
    commentary_status = CommentaryStatus.UNKNOWN
    detection_method = DetectionMethod.METADATA
    confidence = 0.0

    # Get all audio tracks if not provided
    if all_audio_tracks is None:
        all_audio_tracks = [
            t
            for t in get_tracks_for_file(conn, file_record.id)
            if t.track_type == "audio"
        ]

    # Determine which track is original
    original_track_id, method, orig_confidence = determine_original_track(
        all_audio_tracks,
        original_language=original_language,
        language_analysis=language_analysis,
    )

    if track.id == original_track_id:
        original_dubbed_status = OriginalDubbedStatus.ORIGINAL
        detection_method = method
        confidence = orig_confidence
        logger.debug(
            "Track %d classified as ORIGINAL (method=%s, confidence=%.2f)",
            track.id,
            method.value,
            orig_confidence,
        )
    elif original_track_id is not None:
        # If we know which track is original, others are dubbed
        original_dubbed_status = OriginalDubbedStatus.DUBBED
        detection_method = method
        confidence = orig_confidence * 0.9  # Slightly lower for inferred
        logger.debug(
            "Track %d classified as DUBBED (method=%s, confidence=%.2f)",
            track.id,
            method.value,
            confidence,
        )

    # Check for commentary based on metadata keywords in title
    if _is_commentary_by_metadata(track):
        commentary_status = CommentaryStatus.COMMENTARY
        if detection_method == DetectionMethod.METADATA:
            detection_method = DetectionMethod.COMBINED
        else:
            detection_method = DetectionMethod.METADATA
        confidence = max(confidence, 0.85)
        logger.debug(
            "Track %d detected as COMMENTARY via metadata (title=%r)",
            track.id,
            track.title,
        )
    elif acoustic_profile is not None:
        # Use acoustic analysis for commentary detection
        if _is_commentary_by_acoustic(acoustic_profile):
            commentary_status = CommentaryStatus.COMMENTARY
            detection_method = DetectionMethod.ACOUSTIC
            confidence = max(confidence, 0.7)
            logger.debug(
                "Track %d detected as COMMENTARY via acoustic analysis "
                "(speech_density=%.2f, dynamic_range=%.1f)",
                track.id,
                acoustic_profile.speech_density,
                acoustic_profile.dynamic_range_db,
            )
        else:
            commentary_status = CommentaryStatus.MAIN

    # Get track language for result
    track_language = None
    if language_analysis and track.id in language_analysis:
        track_language = language_analysis[track.id]
    elif track.language:
        track_language = track.language

    now = datetime.now(timezone.utc)
    return TrackClassificationResult(
        track_id=track.id,
        file_hash=file_record.content_hash or "",
        original_dubbed_status=original_dubbed_status,
        commentary_status=commentary_status,
        confidence=confidence,
        detection_method=detection_method,
        acoustic_profile=acoustic_profile,
        language=track_language,
        created_at=now,
        updated_at=now,
    )


def classify_file_tracks(
    conn: sqlite3.Connection,
    file_record: FileRecord,
    plugin_metadata: dict | None = None,
    language_analysis: dict[int, str] | None = None,
    force_reclassify: bool = False,
) -> list[TrackClassificationResult]:
    """Classify all audio tracks in a file.

    Args:
        conn: Database connection.
        file_record: File record to classify tracks for.
        plugin_metadata: Optional plugin metadata for original language lookup.
        language_analysis: Map of track_id to detected language.
        force_reclassify: If True, ignore cached classifications.

    Returns:
        List of TrackClassificationResult for all audio tracks.
    """
    # Check cache first (unless forced)
    if not force_reclassify:
        cached = _get_cached_classifications(conn, file_record)
        if cached:
            logger.debug(
                "Using cached classifications for file %d (%d tracks)",
                file_record.id,
                len(cached),
            )
            return cached

    # Get all audio tracks
    all_tracks = get_tracks_for_file(conn, file_record.id)
    audio_tracks = [t for t in all_tracks if t.track_type == "audio"]

    if not audio_tracks:
        logger.debug("No audio tracks found in file %d", file_record.id)
        return []

    # Get original language from metadata
    original_language = get_original_language_from_metadata(
        file_record=file_record,
        plugin_metadata=plugin_metadata,
    )

    # Classify each track
    results = []
    for track in audio_tracks:
        try:
            result = classify_track(
                conn=conn,
                track=track,
                file_record=file_record,
                original_language=original_language,
                language_analysis=language_analysis,
                all_audio_tracks=audio_tracks,
            )
            results.append(result)

            # Persist to database
            _persist_classification(conn, result)

        except ClassificationError as e:
            logger.warning(
                "Failed to classify track %d in file %d: %s",
                track.id,
                file_record.id,
                e,
            )

    logger.info("Classified %d audio tracks in file %d", len(results), file_record.id)
    return results


def _get_cached_classifications(
    conn: sqlite3.Connection,
    file_record: FileRecord,
) -> list[TrackClassificationResult] | None:
    """Check for valid cached classifications.

    Returns cached results only if:
    1. Classifications exist for this file
    2. File hash matches (content hasn't changed)

    Args:
        conn: Database connection.
        file_record: File record to check cache for.

    Returns:
        List of TrackClassificationResult if cache valid, None otherwise.
    """
    cached_records = get_classifications_for_file(conn, file_record.id)
    if not cached_records:
        return None

    # Validate cache by checking file hash
    current_hash = file_record.content_hash or ""
    for record in cached_records:
        if record.file_hash != current_hash:
            logger.debug(
                "Cache invalidated for file %d - hash mismatch", file_record.id
            )
            return None

    # Convert records to results
    results = []
    for record in cached_records:
        acoustic_profile = None
        if record.acoustic_profile_json:
            try:
                profile_data = json.loads(record.acoustic_profile_json)
                acoustic_profile = AcousticProfile.from_dict(profile_data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(
                    "Failed to parse acoustic profile for track %d: %s",
                    record.track_id,
                    e,
                )

        results.append(
            TrackClassificationResult(
                track_id=record.track_id,
                file_hash=record.file_hash,
                original_dubbed_status=OriginalDubbedStatus(
                    record.original_dubbed_status
                ),
                commentary_status=CommentaryStatus(record.commentary_status),
                confidence=record.confidence,
                detection_method=DetectionMethod(record.detection_method),
                acoustic_profile=acoustic_profile,
                created_at=datetime.fromisoformat(record.created_at),
                updated_at=datetime.fromisoformat(record.updated_at),
            )
        )

    return results


def _persist_classification(
    conn: sqlite3.Connection,
    result: TrackClassificationResult,
) -> None:
    """Persist classification result to database.

    Args:
        conn: Database connection.
        result: Classification result to persist.
    """
    acoustic_json = None
    if result.acoustic_profile:
        acoustic_json = json.dumps(result.acoustic_profile.to_dict())

    record = TrackClassificationRecord(
        id=None,
        track_id=result.track_id,
        file_hash=result.file_hash,
        original_dubbed_status=result.original_dubbed_status.value,
        commentary_status=result.commentary_status.value,
        confidence=result.confidence,
        detection_method=result.detection_method.value,
        acoustic_profile_json=acoustic_json,
        created_at=result.created_at.isoformat(),
        updated_at=result.updated_at.isoformat(),
    )

    upsert_track_classification(conn, record)


def _is_commentary_by_metadata(track: TrackRecord) -> bool:
    """Check if track title indicates commentary.

    Args:
        track: Track record to check.

    Returns:
        True if title contains commentary keywords.
    """
    if not track.title:
        return False

    title_lower = track.title.lower()
    commentary_keywords = [
        "commentary",
        "director's commentary",
        "cast commentary",
        "audio commentary",
        "behind the scenes",
        "making of",
    ]

    return any(keyword in title_lower for keyword in commentary_keywords)


def _is_commentary_by_acoustic(profile: AcousticProfile) -> bool:
    """Determine if acoustic profile indicates commentary track.

    Commentary tracks typically have:
    - High speech density (>0.7) - continuous talking
    - Low dynamic range (<15 dB) - consistent speech levels
    - 1-3 distinct voices - consistent speakers
    - Often have background audio (film playing underneath)

    Args:
        profile: Acoustic analysis profile.

    Returns:
        True if profile indicates commentary.
    """
    # Weighted scoring for commentary indicators
    score = 0.0

    # High speech density is strong indicator
    if profile.speech_density > 0.7:
        score += 0.4
    elif profile.speech_density > 0.5:
        score += 0.2

    # Low dynamic range typical for commentary
    if profile.dynamic_range_db < 15:
        score += 0.3
    elif profile.dynamic_range_db < 20:
        score += 0.15

    # 1-3 consistent voices typical for commentary
    if 1 <= profile.voice_count_estimate <= 3:
        score += 0.2

    # Background audio (film playing) is indicator
    if profile.has_background_audio:
        score += 0.1

    # Threshold for commentary determination
    return score >= 0.5
