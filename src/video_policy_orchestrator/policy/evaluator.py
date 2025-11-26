"""Pure-function policy evaluation.

This module provides the core evaluation logic for applying policies
to media file track metadata. All functions are pure (no side effects).
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from video_policy_orchestrator.db.models import (
    TrackInfo,
    TrackRecord,
    TranscriptionResultRecord,
)
from video_policy_orchestrator.language import languages_match, normalize_language
from video_policy_orchestrator.policy.exceptions import InsufficientTracksError
from video_policy_orchestrator.policy.matchers import CommentaryMatcher
from video_policy_orchestrator.policy.models import (
    ActionType,
    AudioFilterConfig,
    Plan,
    PlannedAction,
    PolicySchema,
    TrackDisposition,
    TrackType,
)


# Evaluation exceptions
class EvaluationError(Exception):
    """Base class for evaluation errors."""

    pass


class NoTracksError(EvaluationError):
    """File has no tracks to evaluate."""

    pass


class UnsupportedContainerError(EvaluationError):
    """Container format not supported for requested operations."""

    def __init__(self, container: str, operation: str) -> None:
        self.container = container
        self.operation = operation
        super().__init__(
            f"Container '{container}' does not support {operation}. "
            "Consider converting to MKV for full track manipulation support."
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
    policy: PolicySchema,
    matcher: CommentaryMatcher,
    transcription_results: dict[int, TranscriptionResultRecord] | None = None,
) -> TrackType:
    """Classify a track according to policy rules.

    Args:
        track: Track metadata to classify.
        policy: Policy configuration.
        matcher: Commentary pattern matcher.
        transcription_results: Optional map of track_id to transcription result.
            Used for transcription-based commentary detection when policy
            has detect_commentary enabled.

    Returns:
        TrackType enum value for sorting.
    """
    track_type = track.track_type.lower()

    if track_type == "video":
        return TrackType.VIDEO

    if track_type == "audio":
        # Check for commentary first (metadata-based)
        if matcher.is_commentary(track.title):
            return TrackType.AUDIO_COMMENTARY

        # Check for transcription-based commentary detection
        if (
            transcription_results is not None
            and policy.has_transcription_settings
            and policy.transcription.detect_commentary
        ):
            track_id = getattr(track, "id", None)
            if track_id is None:
                track_id = getattr(track, "track_index", track.index)

            tr_result = transcription_results.get(track_id)
            if tr_result is not None and tr_result.track_type == "commentary":
                return TrackType.AUDIO_COMMENTARY

        # Check if language is in preference list
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
    policy: PolicySchema,
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


def compute_default_flags(
    tracks: list[TrackInfo],
    policy: PolicySchema,
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
    video_tracks = [t for t in tracks if t.track_type.lower() == "video"]
    audio_tracks = [t for t in tracks if t.track_type.lower() == "audio"]
    subtitle_tracks = [t for t in tracks if t.track_type.lower() == "subtitle"]

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

    return result


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


def compute_language_updates(
    tracks: list[TrackInfo | TrackRecord],
    transcription_results: dict[int, TranscriptionResultRecord],
    policy: PolicySchema,
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
        if track.track_type.lower() != "audio":
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


# =============================================================================
# Track Filtering Functions (V3)
# =============================================================================


def _evaluate_audio_track(
    track: TrackInfo,
    config: AudioFilterConfig,
) -> tuple[Literal["KEEP", "REMOVE"], str]:
    """Evaluate a single audio track against audio filter config.

    Args:
        track: Audio track to evaluate.
        config: Audio filter configuration.

    Returns:
        Tuple of (action, reason) for the track.
    """
    lang = track.language or "und"

    # Check if track language matches any in the keep list
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
        if track.track_type.lower() == "audio":
            return track.language or "und"
    return None


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
    policy: PolicySchema,
) -> tuple[TrackDisposition, ...]:
    """Compute disposition for each track based on policy filters.

    This function evaluates all tracks against the policy's filter
    configurations and returns a TrackDisposition for each track
    indicating whether it should be kept or removed and why.

    Args:
        tracks: List of track metadata from introspection.
        policy: Validated policy configuration.

    Returns:
        Tuple of TrackDisposition objects, one per track.

    Raises:
        InsufficientTracksError: If filtering would leave insufficient
            audio tracks and no fallback is configured.
    """
    dispositions: list[TrackDisposition] = []
    audio_tracks = [t for t in tracks if t.track_type.lower() == "audio"]

    # First pass: evaluate each track
    audio_actions: dict[int, tuple[Literal["KEEP", "REMOVE"], str]] = {}

    for track in tracks:
        track_type = track.track_type.lower()
        action: Literal["KEEP", "REMOVE"] = "KEEP"
        reason = "no filter applied"

        if track_type == "audio" and policy.audio_filter:
            action, reason = _evaluate_audio_track(track, policy.audio_filter)
            audio_actions[track.index] = (action, reason)

        # Build resolution string for video tracks
        resolution = None
        if track.width and track.height:
            resolution = f"{track.width}x{track.height}"

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
            )
        )

    # Check if audio filtering is active and needs fallback
    if policy.audio_filter and audio_tracks:
        kept_count = sum(1 for action, _ in audio_actions.values() if action == "KEEP")

        if kept_count < policy.audio_filter.minimum:
            # Apply fallback logic
            updated_actions = _apply_fallback(
                audio_tracks,
                audio_actions,
                policy.audio_filter,
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
                        )

    return tuple(dispositions)


def evaluate_policy(
    file_id: str,
    file_path: Path,
    container: str,
    tracks: list[TrackInfo],
    policy: PolicySchema,
    transcription_results: dict[int, TranscriptionResultRecord] | None = None,
) -> Plan:
    """Evaluate a policy against file tracks to produce an execution plan.

    This is a pure function with no side effects. Given the same inputs,
    it always produces the same output.

    Args:
        file_id: UUID of the file being evaluated.
        file_path: Path to the media file.
        container: Container format (mkv, mp4, etc.).
        tracks: List of track metadata from introspection.
        policy: Validated policy configuration.
        transcription_results: Optional map of track_id to transcription result.
            Required for transcription-based language updates.

    Returns:
        Plan describing all changes needed to make tracks conform to policy.

    Raises:
        NoTracksError: If no tracks are provided.

    Edge cases handled:
        - No tracks: Raises NoTracksError
        - No audio tracks: Skips audio default flag processing
        - All commentary: Falls back to first track for defaults
        - Missing language: Uses "und" as fallback
        - Missing transcription results: Skips language updates for those tracks
        - Low confidence: Skips update if below threshold
    """
    # Edge case: no tracks
    if not tracks:
        raise NoTracksError("File has no tracks to evaluate")

    matcher = CommentaryMatcher(policy.commentary_patterns)
    actions: list[PlannedAction] = []
    requires_remux = False

    # Compute desired track order (handles empty tracks gracefully)
    # Pass transcription_results to enable transcription-based commentary detection
    current_order = [t.index for t in sorted(tracks, key=lambda t: t.index)]
    desired_order = compute_desired_order(
        tracks, policy, matcher, transcription_results
    )

    # Check if reordering is needed
    if current_order != desired_order:
        # Only MKV supports track reordering
        if container.lower() in ("mkv", "matroska"):
            actions.append(
                PlannedAction(
                    action_type=ActionType.REORDER,
                    track_index=None,
                    current_value=current_order,
                    desired_value=desired_order,
                )
            )
            requires_remux = True

    # Compute desired default flags (handles edge cases internally)
    # - All commentary tracks: uses first track as default
    # - Missing language: uses "und" as fallback
    # - No tracks of type: skips that type
    desired_defaults = compute_default_flags(tracks, policy, matcher)

    # Create actions for flag changes
    for track in tracks:
        desired = desired_defaults.get(track.index)
        if desired is not None and desired != track.is_default:
            if desired:
                action_type = ActionType.SET_DEFAULT
            else:
                action_type = ActionType.CLEAR_DEFAULT
            actions.append(
                PlannedAction(
                    action_type=action_type,
                    track_index=track.index,
                    current_value=track.is_default,
                    desired_value=desired,
                )
            )

    # Compute language updates from transcription results
    if transcription_results is not None:
        language_updates = compute_language_updates(
            tracks, transcription_results, policy
        )
        for track in tracks:
            new_lang = language_updates.get(track.index)
            if new_lang is not None:
                current_lang = track.language or "und"
                actions.append(
                    PlannedAction(
                        action_type=ActionType.SET_LANGUAGE,
                        track_index=track.index,
                        current_value=current_lang,
                        desired_value=new_lang,
                    )
                )

    return Plan(
        file_id=file_id,
        file_path=file_path,
        policy_version=policy.schema_version,
        actions=tuple(actions),
        requires_remux=requires_remux,
        created_at=datetime.now(timezone.utc),
    )
