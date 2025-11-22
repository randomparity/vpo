"""Pure-function policy evaluation.

This module provides the core evaluation logic for applying policies
to media file track metadata. All functions are pure (no side effects).
"""

from datetime import datetime, timezone
from pathlib import Path

from video_policy_orchestrator.db.models import (
    TrackInfo,
    TrackRecord,
    TranscriptionResultRecord,
)
from video_policy_orchestrator.policy.matchers import CommentaryMatcher
from video_policy_orchestrator.policy.models import (
    ActionType,
    Plan,
    PlannedAction,
    PolicySchema,
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


def classify_track(
    track: TrackInfo,
    policy: PolicySchema,
    matcher: CommentaryMatcher,
) -> TrackType:
    """Classify a track according to policy rules.

    Args:
        track: Track metadata to classify.
        policy: Policy configuration.
        matcher: Commentary pattern matcher.

    Returns:
        TrackType enum value for sorting.
    """
    track_type = track.track_type.lower()

    if track_type == "video":
        return TrackType.VIDEO

    if track_type == "audio":
        # Check for commentary first
        if matcher.is_commentary(track.title):
            return TrackType.AUDIO_COMMENTARY
        # Check if language is in preference list
        lang = track.language or "und"
        if lang in policy.audio_language_preference:
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
) -> list[int]:
    """Compute desired track order according to policy.

    Args:
        tracks: List of track metadata.
        policy: Policy configuration.
        matcher: Commentary pattern matcher.

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
        classification = classify_track(track, policy, matcher)
        primary = track_order_map.get(classification, len(policy.track_order))

        # Secondary sort by language preference for main tracks
        secondary = 999  # Default for non-language-sorted tracks
        lang = track.language or "und"

        if classification == TrackType.AUDIO_MAIN:
            try:
                secondary = list(policy.audio_language_preference).index(lang)
            except ValueError:
                secondary = len(policy.audio_language_preference)
        elif classification == TrackType.SUBTITLE_MAIN:
            try:
                secondary = list(policy.subtitle_language_preference).index(lang)
            except ValueError:
                secondary = len(policy.subtitle_language_preference)

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
    for lang in language_preference:
        for track in non_commentary:
            track_lang = track.language or "und"
            if track_lang == lang:
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

        # Skip if language already matches
        if current_lang == detected_lang:
            continue

        # Get track index for output (TrackRecord has track_index, TrackInfo has index)
        track_index = getattr(track, "track_index", getattr(track, "index", None))

        # Only update if current language is undefined or explicitly differs
        # This prevents overwriting known-correct language tags
        if current_lang == "und" or current_lang != detected_lang:
            result[track_index] = detected_lang

    return result


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
    current_order = [t.index for t in sorted(tracks, key=lambda t: t.index)]
    desired_order = compute_desired_order(tracks, policy, matcher)

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
