"""External metadata integration for track classification.

This module handles original language detection using external metadata
from sources like Radarr, Sonarr, and file plugin metadata.
"""

import json
import logging

from vpo.db.types import (
    DetectionMethod,
    FileRecord,
    TrackRecord,
)

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Confidence Score Constants for Original/Dubbed Detection
# -----------------------------------------------------------------------------
# These values represent the confidence level assigned to different detection
# scenarios. Higher values indicate more reliable classification.

# Single track matches original language from external metadata (Radarr/Sonarr/TMDB)
CONFIDENCE_METADATA_SINGLE = 0.9

# Multiple tracks match original language (ambiguous - could be theatrical vs extended)
CONFIDENCE_METADATA_MULTIPLE = 0.75

# Position heuristic with multiple tracks (first audio track assumed original)
CONFIDENCE_POSITION_MULTI = 0.6

# Single audio track defaults to original (no other signal available)
CONFIDENCE_POSITION_SINGLE = 0.5


def get_original_language_from_metadata(
    file_record: FileRecord | None = None,
    plugin_metadata: dict | None = None,
) -> str | None:
    """Extract original language from external metadata sources.

    Checks multiple metadata sources in priority order:
    1. Plugin metadata (e.g., from Radarr/Sonarr integration)
    2. File-level plugin_metadata JSON field

    Args:
        file_record: Database file record (may contain plugin_metadata).
        plugin_metadata: Direct plugin metadata dict (higher priority).

    Returns:
        ISO 639-2/B language code of original language, or None if not found.
    """
    # Priority 1: Direct plugin metadata argument
    if plugin_metadata:
        original_lang = _extract_original_language(plugin_metadata)
        if original_lang:
            logger.debug(
                "Found original language from plugin metadata: %s", original_lang
            )
            return original_lang

    # Priority 2: File record plugin_metadata field
    if file_record and file_record.plugin_metadata:
        try:
            metadata = json.loads(file_record.plugin_metadata)
            original_lang = _extract_original_language(metadata)
            if original_lang:
                logger.debug(
                    "Found original language from file plugin metadata: %s",
                    original_lang,
                )
                return original_lang
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failed to parse plugin_metadata JSON for file %s: %s",
                file_record.path if file_record else "unknown",
                e,
            )

    return None


def _extract_original_language(metadata: dict) -> str | None:
    """Extract original language from plugin metadata dict.

    Supports multiple plugin formats:
    - radarr/sonarr: metadata["<plugin>"]["original_language"]
    - tmdb: metadata["tmdb"]["original_language"]
    - generic: metadata["original_language"]

    Args:
        metadata: Plugin metadata dictionary.

    Returns:
        Normalized ISO 639-2/B language code, or None if not found.
    """
    from vpo.language import normalize_language

    # Check for Radarr plugin metadata
    if "radarr" in metadata:
        radarr_data = metadata["radarr"]
        if isinstance(radarr_data, dict) and "original_language" in radarr_data:
            return normalize_language(radarr_data["original_language"])

    # Check for Sonarr plugin metadata
    if "sonarr" in metadata:
        sonarr_data = metadata["sonarr"]
        if isinstance(sonarr_data, dict) and "original_language" in sonarr_data:
            return normalize_language(sonarr_data["original_language"])

    # Check for TMDB plugin metadata
    if "tmdb" in metadata:
        tmdb_data = metadata["tmdb"]
        if isinstance(tmdb_data, dict) and "original_language" in tmdb_data:
            return normalize_language(tmdb_data["original_language"])

    # Check for generic original_language at top level
    if "original_language" in metadata:
        return normalize_language(metadata["original_language"])

    return None


def determine_original_track(
    audio_tracks: list[TrackRecord],
    original_language: str | None = None,
    language_analysis: dict[int, str] | None = None,
) -> tuple[int | None, DetectionMethod, float]:
    """Determine which track is the original theatrical audio.

    Applies detection priority:
    1. Language match with external metadata (highest confidence)
    2. Position heuristic (first audio track often original)
    3. Future: Acoustic analysis for quality comparison

    Args:
        audio_tracks: List of audio track records from database.
        original_language: Expected original language from metadata (ISO 639-2/B).
        language_analysis: Map of track_id to detected language code.

    Returns:
        Tuple of (track_id, detection_method, confidence) or (None, _, 0.0) if
        no determination can be made.
    """
    if not audio_tracks:
        return None, DetectionMethod.METADATA, 0.0

    # Single track edge case: default to original with low confidence
    if len(audio_tracks) == 1:
        logger.debug(
            "Single audio track detected - defaulting to original with low confidence"
        )
        return audio_tracks[0].id, DetectionMethod.POSITION, CONFIDENCE_POSITION_SINGLE

    # Priority 1: Match track language against original language from metadata
    if original_language:
        matching_tracks = []
        for track in audio_tracks:
            track_lang = _get_track_language(track, language_analysis)
            if track_lang and track_lang == original_language:
                matching_tracks.append(track)

        if len(matching_tracks) == 1:
            logger.debug(
                "Found single track matching original language %s: track %d",
                original_language,
                matching_tracks[0].id,
            )
            return (
                matching_tracks[0].id,
                DetectionMethod.METADATA,
                CONFIDENCE_METADATA_SINGLE,
            )

        if len(matching_tracks) > 1:
            # Multiple tracks match - could be theatrical vs extended
            # Return first match (lowest index) with slightly lower confidence
            logger.debug(
                "Multiple tracks match original language %s - selecting first",
                original_language,
            )
            return (
                matching_tracks[0].id,
                DetectionMethod.METADATA,
                CONFIDENCE_METADATA_MULTIPLE,
            )

    # Priority 2: Position heuristic (first audio track)
    # Sort by track_index to ensure consistent ordering
    sorted_tracks = sorted(audio_tracks, key=lambda t: t.track_index)
    first_track = sorted_tracks[0]

    logger.debug(
        "Using position heuristic - first audio track %d assumed original",
        first_track.id,
    )
    return first_track.id, DetectionMethod.POSITION, CONFIDENCE_POSITION_MULTI


def _get_track_language(
    track: TrackRecord, language_analysis: dict[int, str] | None
) -> str | None:
    """Get language for a track, preferring analysis result over metadata.

    Args:
        track: Track record from database.
        language_analysis: Map of track_id to detected language.

    Returns:
        ISO 639-2/B language code, or None if unknown.
    """
    # Prefer analyzed language over track metadata
    if language_analysis and track.id in language_analysis:
        return language_analysis[track.id]

    return track.language
