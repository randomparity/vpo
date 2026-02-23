"""Track filtering logic.

This module provides functions for evaluating track dispositions
based on policy filter configurations (audio, subtitle, attachment).
"""

from __future__ import annotations

from typing import Literal

from vpo.db import TrackInfo
from vpo.language import languages_match
from vpo.policy.evaluator.classification import classify_track
from vpo.policy.exceptions import InsufficientTracksError
from vpo.policy.matchers import CommentaryMatcher
from vpo.policy.types import (
    AttachmentFilterConfig,
    AudioFilterConfig,
    EvaluationPolicy,
    SubtitleFilterConfig,
    TrackDisposition,
    TrackType,
    TranscriptionInfo,
)
from vpo.transcription.models import (
    is_music_by_metadata,
    is_sfx_by_metadata,
)


def _evaluate_audio_track(
    track: TrackInfo,
    config: AudioFilterConfig,
    classification: TrackType | None = None,
) -> tuple[Literal["KEEP", "REMOVE"], str]:
    """Evaluate a single audio track against audio filter config.

    V10: Handles music, sfx, and non_speech track exemptions from language filter.

    Args:
        track: Audio track to evaluate.
        config: Audio filter configuration.
        classification: Optional track classification from classify_track().
            Used to determine music/sfx/non_speech exemptions.

    Returns:
        Tuple of (action, reason) for the track.
    """
    # V10: Check music track handling
    if classification == TrackType.AUDIO_MUSIC or is_music_by_metadata(track.title):
        if not config.keep_music_tracks:
            return ("REMOVE", "music track excluded by policy")
        if config.exclude_music_from_language_filter:
            return ("KEEP", "music track (exempt from language filter)")

    # V10: Check SFX track handling
    if classification == TrackType.AUDIO_SFX or is_sfx_by_metadata(track.title):
        if not config.keep_sfx_tracks:
            return ("REMOVE", "sfx track excluded by policy")
        if config.exclude_sfx_from_language_filter:
            return ("KEEP", "sfx track (exempt from language filter)")

    # V10: Check non-speech track handling (transcription-detected)
    if classification == TrackType.AUDIO_NON_SPEECH:
        if not config.keep_non_speech_tracks:
            return ("REMOVE", "non-speech track excluded by policy")
        if config.exclude_non_speech_from_language_filter:
            return ("KEEP", "non-speech track (exempt from language filter)")

    # Standard language filtering for dialog tracks
    lang = track.language or "und"

    # Check if track language matches any in the keep list
    for keep_lang in config.languages:
        if languages_match(lang, keep_lang):
            return ("KEEP", "language in keep list")

    return ("REMOVE", "language not in keep list")


def _evaluate_subtitle_track(
    track: TrackInfo,
    config: SubtitleFilterConfig,
    forced_will_be_cleared: bool = False,
) -> tuple[Literal["KEEP", "REMOVE"], str]:
    """Evaluate a single subtitle track against subtitle filter config.

    Args:
        track: Subtitle track to evaluate.
        config: Subtitle filter configuration.
        forced_will_be_cleared: If True, all forced flags will be cleared by
            subtitle_actions before filtering, so don't preserve based on
            current forced state.

    Returns:
        Tuple of (action, reason) for the track.
    """
    # remove_all overrides all other settings
    if config.remove_all:
        return ("REMOVE", "remove_all enabled")

    # Check forced flag first (if preserve_forced is enabled)
    # But if forced flags will be cleared by actions, don't preserve based on
    # the current forced state
    if config.preserve_forced and not forced_will_be_cleared and track.is_forced:
        return ("KEEP", "forced subtitle preserved")

    # If no language filter is specified, keep all (unless remove_all)
    if config.languages is None:
        return ("KEEP", "no language filter applied")

    # Check if track language matches any in the keep list
    lang = track.language or "und"
    for keep_lang in config.languages:
        if languages_match(lang, keep_lang):
            return ("KEEP", "language in keep list")

    return ("REMOVE", "language not in keep list")


def _detect_content_language(tracks: list[TrackInfo]) -> str | None:
    """Detect the content language from the first audio track.

    Args:
        tracks: List of all tracks.

    Returns:
        Language code of first audio track, or None if no audio tracks.
    """
    for track in tracks:
        if track.track_type.casefold() == "audio":
            return track.language or "und"
    return None


def _has_styled_subtitles(tracks: list[TrackInfo]) -> bool:
    """Check if any tracks are styled subtitles (ASS/SSA).

    Args:
        tracks: List of all tracks.

    Returns:
        True if any subtitle track uses ASS/SSA format.
    """
    styled_codecs = {"ass", "ssa", "ass_subtitle", "ssa_subtitle"}
    for track in tracks:
        if track.track_type.casefold() == "subtitle":
            codec = (track.codec or "").casefold()
            if codec in styled_codecs:
                return True
    return False


def _is_font_attachment(track: TrackInfo) -> bool:
    """Check if a track is a font attachment.

    Args:
        track: Track to check.

    Returns:
        True if track is a font attachment.
    """
    codec = (track.codec or "").casefold()
    font_extensions = {"ttf", "otf", "ttc", "woff", "woff2"}
    if codec in font_extensions:
        return True
    # Check mime types
    if codec.startswith("font/") or codec in {
        "application/x-truetype-font",
        "application/x-font-ttf",
        "application/font-sfnt",
    }:
        return True
    return False


def _evaluate_attachment_track(
    track: TrackInfo,
    config: AttachmentFilterConfig,
    has_styled_subs: bool,
) -> tuple[Literal["KEEP", "REMOVE"], str]:
    """Evaluate a single attachment track against attachment filter config.

    Args:
        track: Attachment track to evaluate.
        config: Attachment filter configuration.
        has_styled_subs: True if file has ASS/SSA subtitles.

    Returns:
        Tuple of (action, reason) for the track.
    """
    if not config.remove_all:
        return ("KEEP", "attachment kept")

    # Check if this is a font and we have styled subtitles
    if _is_font_attachment(track) and has_styled_subs:
        return (
            "REMOVE",
            "remove_all enabled (font removed, styled subtitles may be affected)",
        )

    return ("REMOVE", "remove_all enabled")


def _apply_fallback(
    audio_tracks: list[TrackInfo],
    initial_actions: dict[int, tuple[Literal["KEEP", "REMOVE"], str]],
    config: AudioFilterConfig,
    all_tracks: list[TrackInfo],
) -> dict[int, tuple[Literal["KEEP", "REMOVE"], str]]:
    """Apply fallback logic when insufficient tracks match the filter.

    Args:
        audio_tracks: List of audio tracks.
        initial_actions: Initial track actions before fallback.
        config: Audio filter configuration.
        all_tracks: All tracks (for content language detection).

    Returns:
        Updated actions dict after applying fallback.

    Raises:
        InsufficientTracksError: If fallback mode is 'error' or None.
    """
    kept_count = sum(1 for action, _ in initial_actions.values() if action == "KEEP")
    fallback = config.fallback

    # No fallback configured - raise error
    if fallback is None or fallback.mode == "error":
        policy_languages = config.languages
        file_languages = tuple(t.language or "und" for t in audio_tracks)
        raise InsufficientTracksError(
            track_type="audio",
            required=config.minimum,
            available=kept_count,
            policy_languages=policy_languages,
            file_languages=file_languages,
        )

    # Apply fallback based on mode
    result = dict(initial_actions)

    if fallback.mode == "keep_all":
        # Keep all audio tracks
        for track in audio_tracks:
            result[track.index] = ("KEEP", "fallback: keep_all applied")
        return result

    elif fallback.mode == "keep_first":
        # Keep first N tracks to meet minimum
        needed = config.minimum - kept_count
        for track in audio_tracks:
            if needed <= 0:
                break
            action, _ = result.get(track.index, ("REMOVE", ""))
            if action == "REMOVE":
                result[track.index] = ("KEEP", "fallback: keep_first applied")
                needed -= 1
        return result

    elif fallback.mode == "content_language":
        # Keep tracks matching content language (first audio track's language)
        content_lang = _detect_content_language(all_tracks)
        if content_lang:
            for track in audio_tracks:
                track_lang = track.language or "und"
                if languages_match(track_lang, content_lang):
                    result[track.index] = ("KEEP", "fallback: content language match")
        return result

    return result


def compute_track_dispositions(
    tracks: list[TrackInfo],
    policy: EvaluationPolicy,
    transcription_results: dict[int, TranscriptionInfo] | None = None,
    subtitle_forced_will_be_cleared: bool = False,
) -> tuple[TrackDisposition, ...]:
    """Compute disposition for each track based on policy filters.

    This function evaluates all tracks against the policy's filter
    configurations and returns a TrackDisposition for each track
    indicating whether it should be kept or removed and why.

    Args:
        tracks: List of track metadata from introspection.
        policy: Validated policy configuration.
        transcription_results: Optional map of track_id to transcription result.
            Used to populate transcription_status for audio tracks.
        subtitle_forced_will_be_cleared: If True, subtitle_actions will clear
            all forced flags before filtering, so preserve_forced should not
            preserve tracks based on current forced state.

    Returns:
        Tuple of TrackDisposition objects, one per track.

    Raises:
        InsufficientTracksError: If filtering would leave insufficient
            audio tracks and no fallback is configured.
    """
    dispositions: list[TrackDisposition] = []
    audio_tracks = [t for t in tracks if t.track_type.casefold() == "audio"]

    # Pre-compute whether we have styled subtitles (for font warning)
    has_styled_subs = _has_styled_subtitles(tracks)

    # Create commentary matcher for classification
    matcher = CommentaryMatcher(policy.commentary_patterns)

    # First pass: evaluate each track
    audio_actions: dict[int, tuple[Literal["KEEP", "REMOVE"], str]] = {}

    for track in tracks:
        track_type = track.track_type.casefold()
        action: Literal["KEEP", "REMOVE"] = "KEEP"
        reason = "no filter applied"

        if track_type == "audio" and policy.keep_audio:
            # Classify track for V10 music/sfx/non_speech handling
            classification = classify_track(
                track, policy, matcher, transcription_results
            )
            action, reason = _evaluate_audio_track(
                track, policy.keep_audio, classification
            )
            audio_actions[track.index] = (action, reason)
        elif track_type == "subtitle" and policy.keep_subtitles:
            action, reason = _evaluate_subtitle_track(
                track, policy.keep_subtitles, subtitle_forced_will_be_cleared
            )
        elif track_type == "attachment" and policy.filter_attachments:
            action, reason = _evaluate_attachment_track(
                track, policy.filter_attachments, has_styled_subs
            )

        # Build resolution string for video tracks
        resolution = None
        if track.width and track.height:
            resolution = f"{track.width}x{track.height}"

        # Compute transcription status for audio tracks
        transcription_status: str | None = None
        if track_type == "audio":
            # Get track ID for lookup (TrackInfo uses id attribute if available)
            track_id = getattr(track, "id", None)
            if transcription_results and track_id in transcription_results:
                tr = transcription_results[track_id]
                pct = int(tr.confidence_score * 100)
                transcription_status = f"{tr.track_type} {pct}%"
            else:
                transcription_status = "TBD"

        dispositions.append(
            TrackDisposition(
                track_index=track.index,
                track_type=track_type,
                codec=track.codec,
                language=track.language,
                title=track.title,
                channels=track.channels,
                resolution=resolution,
                action=action,
                reason=reason,
                transcription_status=transcription_status,
            )
        )

    # Check if audio filtering is active and needs fallback
    if policy.keep_audio and audio_tracks:
        kept_count = sum(1 for action, _ in audio_actions.values() if action == "KEEP")

        if kept_count < policy.keep_audio.minimum:
            # Apply fallback logic
            updated_actions = _apply_fallback(
                audio_tracks,
                audio_actions,
                policy.keep_audio,
                tracks,
            )

            # Update dispositions with fallback results
            for i, disp in enumerate(dispositions):
                if disp.track_index in updated_actions:
                    new_action, new_reason = updated_actions[disp.track_index]
                    if new_action != disp.action or new_reason != disp.reason:
                        # Create new disposition with updated values
                        dispositions[i] = TrackDisposition(
                            track_index=disp.track_index,
                            track_type=disp.track_type,
                            codec=disp.codec,
                            language=disp.language,
                            title=disp.title,
                            channels=disp.channels,
                            resolution=disp.resolution,
                            action=new_action,
                            reason=new_reason,
                            transcription_status=disp.transcription_status,
                        )

    return tuple(dispositions)
