"""Source track selection for audio synthesis.

This module implements the algorithm for selecting the best source track
for synthesis based on user-defined preferences.

Key Functions:
    select_source_track: Select best source track from available audio tracks
    score_track: Calculate preference score for a single track
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from video_policy_orchestrator.language import languages_match
from video_policy_orchestrator.policy.synthesis.models import (
    ChannelPreference,
    PreferenceCriterion,
    SourcePreferences,
    SourceTrackSelection,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.db.models import TrackInfo

logger = logging.getLogger(__name__)


# Scoring weights for preference criteria
LANGUAGE_MATCH_SCORE = 100
NOT_COMMENTARY_SCORE = 80
CODEC_MATCH_SCORE = 20
CHANNEL_SCORE_PER_CHANNEL = 10


def score_track(
    track: TrackInfo,
    criterion: PreferenceCriterion,
    commentary_patterns: tuple[str, ...] | None = None,
) -> tuple[int, list[str]]:
    """Calculate the preference score for a track against a criterion.

    Args:
        track: The audio track to score.
        criterion: The preference criterion to apply.
        commentary_patterns: Patterns to identify commentary tracks.

    Returns:
        Tuple of (score, reasons) where reasons are human-readable strings.
    """
    score = 0
    reasons: list[str] = []

    # Language matching
    if criterion.language is not None:
        languages = (
            criterion.language
            if isinstance(criterion.language, tuple)
            else (criterion.language,)
        )
        if track.language and any(
            languages_match(track.language, lang) for lang in languages
        ):
            score += LANGUAGE_MATCH_SCORE
            reasons.append(f"language={track.language}")

    # Not commentary matching
    if criterion.not_commentary is True:
        is_commentary = _is_commentary_track(track, commentary_patterns)
        if not is_commentary:
            score += NOT_COMMENTARY_SCORE
            reasons.append("not_commentary")

    # Channel count preference
    if criterion.channels is not None:
        if track.channels is not None:
            if isinstance(criterion.channels, ChannelPreference):
                if criterion.channels == ChannelPreference.MAX:
                    # Higher channel count is better
                    score += track.channels * CHANNEL_SCORE_PER_CHANNEL
                    reasons.append(f"channels={track.channels}")
                elif criterion.channels == ChannelPreference.MIN:
                    # Lower channel count is better (penalize high counts)
                    score -= track.channels * CHANNEL_SCORE_PER_CHANNEL
                    reasons.append(f"channels={track.channels} (min preferred)")
            elif isinstance(criterion.channels, int):
                # Exact channel count preference
                if track.channels == criterion.channels:
                    score += NOT_COMMENTARY_SCORE  # Same as not_commentary weight
                    reasons.append(f"channels={track.channels} (exact match)")

    # Codec matching
    if criterion.codec is not None:
        codecs = (
            criterion.codec
            if isinstance(criterion.codec, tuple)
            else (criterion.codec,)
        )
        if track.codec and any(
            track.codec.lower() == codec.lower() for codec in codecs
        ):
            score += CODEC_MATCH_SCORE
            reasons.append(f"codec={track.codec}")

    return score, reasons


def _is_commentary_track(
    track: TrackInfo,
    commentary_patterns: tuple[str, ...] | None = None,
) -> bool:
    """Check if a track is likely a commentary track.

    Args:
        track: The track to check.
        commentary_patterns: Regex patterns that indicate commentary.

    Returns:
        True if the track appears to be commentary.
    """
    if not track.title:
        return False

    patterns = commentary_patterns or ("commentary", "director", "cast")
    title_lower = track.title.lower()

    for pattern in patterns:
        try:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return True
        except re.error:
            # Invalid regex, try simple substring match
            if pattern.lower() in title_lower:
                return True

    return False


def select_source_track(
    audio_tracks: list[TrackInfo],
    preferences: SourcePreferences,
    commentary_patterns: tuple[str, ...] | None = None,
) -> SourceTrackSelection | None:
    """Select the best source track for synthesis.

    Evaluates each audio track against all preference criteria and returns
    the highest-scoring track. If no tracks score above 0, the first audio
    track is returned as a fallback.

    Args:
        audio_tracks: List of audio tracks to consider.
        preferences: Source selection preferences from policy.
        commentary_patterns: Patterns to identify commentary tracks.

    Returns:
        SourceTrackSelection with the chosen track, or None if no audio tracks.
    """
    if not audio_tracks:
        logger.warning("No audio tracks available for source selection")
        return None

    # Score each track
    track_scores: list[tuple[TrackInfo, int, list[str]]] = []

    for track in audio_tracks:
        total_score = 0
        all_reasons: list[str] = []

        for criterion in preferences.prefer:
            score, reasons = score_track(track, criterion, commentary_patterns)
            total_score += score
            all_reasons.extend(reasons)

        track_scores.append((track, total_score, all_reasons))

    # Sort by score (descending)
    track_scores.sort(key=lambda x: x[1], reverse=True)

    # Get best track
    best_track, best_score, best_reasons = track_scores[0]

    # Determine if this is a fallback (no criteria matched)
    is_fallback = best_score <= 0 and not best_reasons

    if is_fallback:
        # Use first track as fallback
        best_track = audio_tracks[0]
        best_reasons = ["fallback: first audio track"]
        logger.info(
            "No preference criteria matched, using first audio track (index %d)",
            best_track.index,
        )

    return SourceTrackSelection(
        track_index=best_track.index,
        track_info=best_track,
        score=best_score,
        is_fallback=is_fallback,
        match_reasons=tuple(best_reasons),
    )


def filter_audio_tracks(tracks: list[TrackInfo]) -> list[TrackInfo]:
    """Filter to only audio tracks from a list of all tracks.

    Args:
        tracks: List of all tracks.

    Returns:
        List containing only audio tracks.
    """
    return [t for t in tracks if t.track_type.lower() == "audio"]
