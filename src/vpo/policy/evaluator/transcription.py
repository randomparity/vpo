"""Transcription-based language and title updates.

This module provides functions for computing language updates
and title updates from transcription results.
"""

from __future__ import annotations

from vpo.db import (
    TrackInfo,
    TrackRecord,
    TranscriptionResultRecord,
)
from vpo.language import languages_match, normalize_language
from vpo.policy.types import EvaluationPolicy

# Mapping from transcription track_type to display title
CLASSIFICATION_TITLES: dict[str, str] = {
    "main": "Main",
    "commentary": "Commentary",
    "alternate": "Alternate",
    "music": "Music",
    "sfx": "Sound Effects",
    "non_speech": "Non-Speech",
}

# Tokens that indicate a generic/auto-generated title (case-insensitive)
# These are codec names, channel layouts, and format descriptors
GENERIC_TITLE_PATTERNS: set[str] = {
    # Channel layouts
    "mono",
    "stereo",
    "surround",
    "2.0",
    "2.1",
    "5.1",
    "7.1",
    # Common audio codecs
    "aac",
    "ac3",
    "ac-3",
    "eac3",
    "e-ac-3",
    "dts",
    "dts-hd",
    "flac",
    "mp3",
    "opus",
    "pcm",
    "truehd",
    "vorbis",
    "pcm_s16le",
    "pcm_s24le",
    "pcm_s32le",
    # Bit depths / sample rates
    "16-bit",
    "24-bit",
    "32-bit",
    "16bit",
    "24bit",
    "32bit",
}


def compute_language_updates(
    tracks: list[TrackInfo | TrackRecord],
    transcription_results: dict[int, TranscriptionResultRecord],
    policy: EvaluationPolicy,
) -> dict[int, str]:
    """Compute desired language updates from transcription results.

    Args:
        tracks: List of track metadata (either TrackInfo or TrackRecord).
        transcription_results: Map of track_id (database ID) to transcription result.
            For TrackRecord tracks, uses track.id.
            For TrackInfo tracks, uses track.index as fallback key.
        policy: Policy configuration with transcription settings.

    Returns:
        Dict mapping track_index to desired language code.
        Only includes tracks that need language updates.
    """
    result: dict[int, str] = {}

    # Skip if transcription is not enabled or language updates disabled
    if not policy.has_transcription_settings:
        return result
    if not policy.transcription.update_language_from_transcription:
        return result

    threshold = policy.transcription.confidence_threshold

    for track in tracks:
        # Only process audio tracks
        if track.track_type.casefold() != "audio":
            continue

        # Get track ID for lookup - TrackRecord has 'id', TrackInfo doesn't
        # For TrackRecord, use database ID; for TrackInfo, use index as key
        track_id = getattr(track, "id", None)
        if track_id is None:
            # Fallback for TrackInfo: use track_index if it exists, else index
            track_id = getattr(track, "track_index", track.index)

        # Check if we have a transcription result for this track
        tr_result = transcription_results.get(track_id)
        if tr_result is None:
            continue

        # Skip if no language was detected
        if tr_result.detected_language is None:
            continue

        # Check confidence threshold
        if tr_result.confidence_score < threshold:
            continue

        # Check if update is needed (language differs or is undefined)
        current_lang = track.language or "und"
        detected_lang = tr_result.detected_language

        # Skip if language already matches (cross-standard comparison)
        # This handles cases where "ger" == "de" == "deu" (all German)
        if languages_match(current_lang, detected_lang):
            continue

        # Get track index for output (TrackRecord has track_index, TrackInfo has index)
        track_index = getattr(track, "track_index", getattr(track, "index", None))

        # Normalize detected language to project standard before storing
        detected_lang_normalized = normalize_language(detected_lang)

        # Only update if current language is undefined or explicitly differs
        # This prevents overwriting known-correct language tags
        if current_lang == "und" or not languages_match(current_lang, detected_lang):
            result[track_index] = detected_lang_normalized

    return result


def _is_generic_title(title: str | None) -> bool:
    """Check if a track title is generic (auto-generated or uninformative).

    A title is generic if it is None, empty, or composed entirely of
    codec names, channel layout descriptors, and similar format tokens.

    Args:
        title: The track title to check.

    Returns:
        True if the title is generic and safe to overwrite.
    """
    if not title or not title.strip():
        return True

    # Split on whitespace and slashes, check if all tokens are generic
    # Note: don't split on _ or - as codec names use them (e.g. pcm_s16le, dts-hd)
    tokens = title.replace("/", " ").split()
    return all(token.casefold() in GENERIC_TITLE_PATTERNS for token in tokens)


def compute_title_updates(
    tracks: list[TrackInfo | TrackRecord],
    transcription_results: dict[int, TranscriptionResultRecord],
    policy: EvaluationPolicy,
) -> dict[int, str]:
    """Compute desired title updates from transcription classification results.

    Args:
        tracks: List of track metadata (either TrackInfo or TrackRecord).
        transcription_results: Map of track_id (database ID) to transcription result.
            For TrackRecord tracks, uses track.id.
            For TrackInfo tracks, uses track.index as fallback key.
        policy: Policy configuration with transcription settings.

    Returns:
        Dict mapping track_index to desired title string.
        Only includes tracks that need title updates.
    """
    result: dict[int, str] = {}

    # Skip if transcription is not configured or title updates disabled
    if not policy.has_transcription_settings:
        return result
    if not policy.transcription.update_title_from_classification:
        return result

    threshold = policy.transcription.confidence_threshold

    for track in tracks:
        # Only process audio tracks
        if track.track_type.casefold() != "audio":
            continue

        # Get track ID for lookup - TrackRecord has 'id', TrackInfo doesn't
        track_id = getattr(track, "id", None)
        if track_id is None:
            track_id = getattr(track, "track_index", track.index)

        # Check if we have a transcription result for this track
        tr_result = transcription_results.get(track_id)
        if tr_result is None:
            continue

        # Check confidence threshold
        if tr_result.confidence_score < threshold:
            continue

        # Map classification to display title
        desired_title = CLASSIFICATION_TITLES.get(tr_result.track_type)
        if desired_title is None:
            continue

        # Get track index for output
        track_index = getattr(track, "track_index", getattr(track, "index", None))

        # Skip tracks with descriptive (non-generic) existing titles
        current_title = track.title
        if not _is_generic_title(current_title):
            continue

        # Idempotent: skip if title already matches desired value
        if current_title == desired_title:
            continue

        result[track_index] = desired_title

    return result
