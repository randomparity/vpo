"""Transcription-based language and title updates.

This module provides functions for computing language updates
and title updates from transcription results.
"""

from __future__ import annotations

from vpo.db import TrackInfo
from vpo.language import languages_match, normalize_language
from vpo.policy.types import EvaluationPolicy, TranscriptionInfo

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
    "dts:x",
    "dts-x",
    "flac",
    "mp3",
    "opus",
    "pcm",
    "truehd",
    "vorbis",
    "alac",
    "atmos",
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
    "lossless",
    "lossy",
}


def compute_language_updates(
    tracks: list[TrackInfo],
    transcription_results: dict[int, TranscriptionInfo],
    policy: EvaluationPolicy,
) -> dict[int, str]:
    """Compute desired language updates from transcription results.

    Args:
        tracks: List of track metadata.
        transcription_results: Map of track ID to transcription info.
            Uses track.id if available, otherwise track.index.
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
        if track.track_type.casefold() != "audio":
            continue

        lookup_id = track.id if track.id is not None else track.index
        tr_result = transcription_results.get(lookup_id)
        if tr_result is None:
            continue

        if tr_result.detected_language is None:
            continue

        if tr_result.confidence_score < threshold:
            continue

        current_lang = track.language or "und"
        detected_lang = tr_result.detected_language

        # Skip if language already matches (cross-standard comparison,
        # e.g. "ger" == "de" == "deu")
        if languages_match(current_lang, detected_lang):
            continue

        detected_lang_normalized = normalize_language(detected_lang)

        if current_lang == "und" or not languages_match(current_lang, detected_lang):
            result[track.index] = detected_lang_normalized

    return result


def _is_generic_title(title: str | None) -> bool:
    """Return True if the title is None, empty, or composed entirely of format tokens.

    Format tokens include codec names (aac, dts-hd), channel layouts (5.1, stereo),
    and bit depths (24-bit). Such titles are safe to overwrite with classification.
    """
    if not title or not title.strip():
        return True

    # Split on whitespace and slashes, check if all tokens are generic
    # Note: don't split on _ or - as codec names use them (e.g. pcm_s16le, dts-hd)
    tokens = title.replace("/", " ").split()
    return all(token.casefold() in GENERIC_TITLE_PATTERNS for token in tokens)


def compute_title_updates(
    tracks: list[TrackInfo],
    transcription_results: dict[int, TranscriptionInfo],
    policy: EvaluationPolicy,
) -> dict[int, str]:
    """Compute desired title updates from transcription classification results.

    Args:
        tracks: List of track metadata.
        transcription_results: Map of track ID to transcription info.
            Uses track.id if available, otherwise track.index.
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
        if track.track_type.casefold() != "audio":
            continue

        lookup_id = track.id if track.id is not None else track.index
        tr_result = transcription_results.get(lookup_id)
        if tr_result is None or tr_result.confidence_score < threshold:
            continue

        desired_title = CLASSIFICATION_TITLES.get(tr_result.track_type)
        if desired_title is None:
            continue

        # Skip tracks with descriptive (non-generic) existing titles
        current_title = track.title
        if not _is_generic_title(current_title):
            continue

        # Idempotent: skip if title already matches
        if current_title == desired_title:
            continue

        result[track.index] = desired_title

    return result
