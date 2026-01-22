"""Track classification and ordering.

This module provides functions for classifying tracks by type and
computing desired track order based on policy preferences.
"""

from __future__ import annotations

from vpo.db import (
    TrackInfo,
    TranscriptionResultRecord,
)
from vpo.language import languages_match
from vpo.policy.matchers import CommentaryMatcher
from vpo.policy.types import (
    EvaluationPolicy,
    TrackType,
)
from vpo.transcription.models import (
    is_music_by_metadata,
    is_sfx_by_metadata,
)


def _find_language_preference_index(
    lang: str,
    preferences: tuple[str, ...],
) -> int:
    """Find the index of a language in the preference list.

    Uses languages_match() to compare, so "de", "ger", and "deu" all match.

    Args:
        lang: Language code to find (any ISO 639 format).
        preferences: Ordered tuple of preferred language codes.

    Returns:
        Index in preferences if found, len(preferences) otherwise.
    """
    for i, pref_lang in enumerate(preferences):
        if languages_match(lang, pref_lang):
            return i
    return len(preferences)


def classify_track(
    track: TrackInfo,
    policy: EvaluationPolicy,
    matcher: CommentaryMatcher,
    transcription_results: dict[int, TranscriptionResultRecord] | None = None,
) -> TrackType:
    """Classify a track according to policy rules.

    Classification priority for audio tracks:
    1. SFX (metadata-based) - most specific
    2. Music (metadata-based)
    3. Commentary (metadata-based)
    4. Transcription-based classification (sfx, music, non_speech, commentary)
    5. Language-based: AUDIO_MAIN if in preference, else AUDIO_ALTERNATE

    Args:
        track: Track metadata to classify.
        policy: Policy configuration.
        matcher: Commentary pattern matcher.
        transcription_results: Optional map of track_id to transcription result.
            Used for transcription-based classification (commentary, music,
            sfx, non_speech) when policy has transcription enabled.

    Returns:
        TrackType enum value for sorting.
    """
    track_type = track.track_type.casefold()

    if track_type == "video":
        return TrackType.VIDEO

    if track_type == "audio":
        # Stage 1: Metadata-based detection (most reliable)
        # Check SFX first - most specific
        if is_sfx_by_metadata(track.title):
            return TrackType.AUDIO_SFX

        # Check music keywords
        if is_music_by_metadata(track.title):
            return TrackType.AUDIO_MUSIC

        # Check for commentary (metadata-based)
        if matcher.is_commentary(track.title):
            return TrackType.AUDIO_COMMENTARY

        # Stage 2: Transcription-based classification
        if transcription_results is not None:
            track_id = getattr(track, "id", None)
            if track_id is None:
                track_id = getattr(track, "track_index", track.index)

            tr_result = transcription_results.get(track_id)
            if tr_result is not None:
                # Map transcription track_type to TrackType
                if tr_result.track_type == "sfx":
                    return TrackType.AUDIO_SFX
                if tr_result.track_type == "music":
                    return TrackType.AUDIO_MUSIC
                if tr_result.track_type == "non_speech":
                    return TrackType.AUDIO_NON_SPEECH
                if tr_result.track_type == "commentary":
                    # Only use transcription-based commentary if enabled
                    if (
                        policy.has_transcription_settings
                        and policy.transcription.detect_commentary
                    ):
                        return TrackType.AUDIO_COMMENTARY

        # Stage 3: Language-based classification for dialog tracks
        # Use languages_match() to handle different ISO standards
        lang = track.language or "und"
        for pref_lang in policy.audio_language_preference:
            if languages_match(lang, pref_lang):
                return TrackType.AUDIO_MAIN
        return TrackType.AUDIO_ALTERNATE

    if track_type == "subtitle":
        # Check for commentary first
        if matcher.is_commentary(track.title):
            return TrackType.SUBTITLE_COMMENTARY
        # Check if forced
        if track.is_forced:
            return TrackType.SUBTITLE_FORCED
        return TrackType.SUBTITLE_MAIN

    if track_type == "attachment":
        return TrackType.ATTACHMENT

    # Default to attachment for unknown types
    return TrackType.ATTACHMENT


def compute_desired_order(
    tracks: list[TrackInfo],
    policy: EvaluationPolicy,
    matcher: CommentaryMatcher,
    transcription_results: dict[int, TranscriptionResultRecord] | None = None,
) -> list[int]:
    """Compute desired track order according to policy.

    Args:
        tracks: List of track metadata.
        policy: Policy configuration.
        matcher: Commentary pattern matcher.
        transcription_results: Optional map of track_id to transcription result.
            Used for transcription-based commentary detection when policy
            has detect_commentary enabled.

    Returns:
        List of track indices in desired order.
    """
    if not tracks:
        return []

    # Create a list of (track_index, sort_key) tuples
    track_order_map = {t: i for i, t in enumerate(policy.track_order)}

    def sort_key(track: TrackInfo) -> tuple[int, int, int]:
        """Generate sort key for a track.

        Returns tuple of:
        1. Position in track_order (primary sort)
        2. Language preference position (secondary for audio/subtitle main)
        3. Original index (tertiary for stable sort)
        """
        classification = classify_track(track, policy, matcher, transcription_results)
        primary = track_order_map.get(classification, len(policy.track_order))

        # Secondary sort by language preference for main tracks
        secondary = 999  # Default for non-language-sorted tracks
        lang = track.language or "und"

        if classification == TrackType.AUDIO_MAIN:
            # Use languages_match() to find preference index
            secondary = _find_language_preference_index(
                lang, policy.audio_language_preference
            )
        elif classification == TrackType.SUBTITLE_MAIN:
            # Use languages_match() to find preference index
            secondary = _find_language_preference_index(
                lang, policy.subtitle_language_preference
            )

        return (primary, secondary, track.index)

    # Sort tracks and return indices
    sorted_tracks = sorted(tracks, key=sort_key)
    return [t.index for t in sorted_tracks]


def _find_preferred_track(
    tracks: list[TrackInfo],
    language_preference: tuple[str, ...],
    matcher: CommentaryMatcher,
) -> TrackInfo | None:
    """Find the preferred track based on language and non-commentary status.

    Args:
        tracks: List of tracks to search.
        language_preference: Ordered list of preferred languages.
        matcher: Commentary pattern matcher.

    Returns:
        The preferred track, or None if no suitable track found.
    """
    # Filter out commentary tracks
    non_commentary = [t for t in tracks if not matcher.is_commentary(t.title)]

    if not non_commentary:
        # Fall back to first track if all are commentary
        return tracks[0] if tracks else None

    # Find first track matching language preference
    # Use languages_match() to handle different ISO standards
    for lang in language_preference:
        for track in non_commentary:
            track_lang = track.language or "und"
            if languages_match(track_lang, lang):
                return track

    # Fall back to first non-commentary track
    return non_commentary[0]


def _audio_matches_language_preference(
    audio_tracks: list[TrackInfo],
    language_preference: tuple[str, ...],
    matcher: CommentaryMatcher,
) -> bool:
    """Check if any non-commentary audio track matches language preference.

    Returns False if:
    - No audio tracks exist
    - All audio tracks are commentary
    - No audio track language matches any preferred language
    - Audio language is undefined ('und') and 'und' not in preference

    Args:
        audio_tracks: List of audio tracks to check.
        language_preference: Ordered list of preferred languages.
        matcher: Commentary pattern matcher.

    Returns:
        True if at least one non-commentary audio matches preference.
    """
    non_commentary = [t for t in audio_tracks if not matcher.is_commentary(t.title)]

    if not non_commentary:
        return False  # No main audio = mismatch

    for track in non_commentary:
        track_lang = track.language or "und"
        for pref_lang in language_preference:
            if languages_match(track_lang, pref_lang):
                return True

    return False


def compute_default_flags(
    tracks: list[TrackInfo],
    policy: EvaluationPolicy,
    matcher: CommentaryMatcher,
) -> dict[int, bool]:
    """Compute desired default flag state for each track.

    Args:
        tracks: List of track metadata.
        policy: Policy configuration.
        matcher: Commentary pattern matcher.

    Returns:
        Dict mapping track_index to desired is_default value.
    """
    flags = policy.default_flags
    result: dict[int, bool] = {}

    # Group tracks by type
    video_tracks = [t for t in tracks if t.track_type.casefold() == "video"]
    audio_tracks = [t for t in tracks if t.track_type.casefold() == "audio"]
    subtitle_tracks = [t for t in tracks if t.track_type.casefold() == "subtitle"]

    # Process video tracks
    if flags.set_first_video_default and video_tracks:
        # First video track gets default
        result[video_tracks[0].index] = True
        if flags.clear_other_defaults:
            for track in video_tracks[1:]:
                result[track.index] = False

    # Process audio tracks
    if flags.set_preferred_audio_default and audio_tracks:
        # Find first non-commentary audio matching language preference
        default_audio = _find_preferred_track(
            audio_tracks, policy.audio_language_preference, matcher
        )
        if default_audio is not None:
            result[default_audio.index] = True
        if flags.clear_other_defaults:
            for track in audio_tracks:
                if track.index not in result:
                    result[track.index] = False

    # Process subtitle tracks
    if flags.set_preferred_subtitle_default and subtitle_tracks:
        # Find first non-commentary subtitle matching language preference
        default_subtitle = _find_preferred_track(
            subtitle_tracks, policy.subtitle_language_preference, matcher
        )
        if default_subtitle is not None:
            result[default_subtitle.index] = True
        if flags.clear_other_defaults:
            for track in subtitle_tracks:
                if track.index not in result:
                    result[track.index] = False
    elif flags.clear_other_defaults:
        # Clear defaults on all subtitles if not setting preferred
        for track in subtitle_tracks:
            result[track.index] = False

    # Set subtitle default when audio language differs from preference
    if (
        flags.set_subtitle_default_when_audio_differs
        and subtitle_tracks
        and not _audio_matches_language_preference(
            audio_tracks, policy.audio_language_preference, matcher
        )
    ):
        # Only set if we haven't already set a subtitle default above
        if not any(result.get(t.index) for t in subtitle_tracks):
            default_subtitle = _find_preferred_track(
                subtitle_tracks, policy.subtitle_language_preference, matcher
            )
            if default_subtitle is not None:
                result[default_subtitle.index] = True
            if flags.clear_other_defaults:
                for track in subtitle_tracks:
                    if track.index not in result:
                        result[track.index] = False

    return result
