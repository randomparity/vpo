"""Transcription-based language updates.

This module provides functions for computing language updates
from transcription results.
"""

from __future__ import annotations

from vpo.db import (
    TrackInfo,
    TrackRecord,
    TranscriptionResultRecord,
)
from vpo.language import languages_match, normalize_language
from vpo.policy.types import EvaluationPolicy


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
