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
from video_policy_orchestrator.policy.exceptions import (
    IncompatibleCodecError,
    InsufficientTracksError,
)
from video_policy_orchestrator.policy.matchers import CommentaryMatcher
from video_policy_orchestrator.policy.models import (
    ActionType,
    AttachmentFilterConfig,
    AudioFilterConfig,
    ConditionalResult,
    ConditionalRule,
    ContainerChange,
    Plan,
    PlannedAction,
    PolicySchema,
    RuleEvaluation,
    SkipFlags,
    SubtitleFilterConfig,
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


def _evaluate_subtitle_track(
    track: TrackInfo,
    config: SubtitleFilterConfig,
) -> tuple[Literal["KEEP", "REMOVE"], str]:
    """Evaluate a single subtitle track against subtitle filter config.

    Args:
        track: Subtitle track to evaluate.
        config: Subtitle filter configuration.

    Returns:
        Tuple of (action, reason) for the track.
    """
    # remove_all overrides all other settings
    if config.remove_all:
        return ("REMOVE", "remove_all enabled")

    # Check forced flag first (if preserve_forced is enabled)
    if config.preserve_forced and track.is_forced:
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
        if track.track_type.lower() == "audio":
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
        if track.track_type.lower() == "subtitle":
            codec = (track.codec or "").lower()
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
    codec = (track.codec or "").lower()
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

    # Pre-compute whether we have styled subtitles (for font warning)
    has_styled_subs = _has_styled_subtitles(tracks)

    # First pass: evaluate each track
    audio_actions: dict[int, tuple[Literal["KEEP", "REMOVE"], str]] = {}

    for track in tracks:
        track_type = track.track_type.lower()
        action: Literal["KEEP", "REMOVE"] = "KEEP"
        reason = "no filter applied"

        if track_type == "audio" and policy.audio_filter:
            action, reason = _evaluate_audio_track(track, policy.audio_filter)
            audio_actions[track.index] = (action, reason)
        elif track_type == "subtitle" and policy.subtitle_filter:
            action, reason = _evaluate_subtitle_track(track, policy.subtitle_filter)
        elif track_type == "attachment" and policy.attachment_filter:
            action, reason = _evaluate_attachment_track(
                track, policy.attachment_filter, has_styled_subs
            )

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


# =============================================================================
# Container Conversion Functions (V3)
# =============================================================================

# Codecs compatible with MP4 container
_MP4_COMPATIBLE_VIDEO_CODECS = frozenset(
    {
        "h264",
        "avc",
        "avc1",
        "hevc",
        "h265",
        "hvc1",
        "hev1",
        "av1",
        "av01",
        "mpeg4",
        "mp4v",
        "vp9",
    }
)

_MP4_COMPATIBLE_AUDIO_CODECS = frozenset(
    {
        "aac",
        "mp4a",
        "ac3",
        "eac3",
        "mp3",
        "mp3float",
        "flac",
        "opus",
        "alac",
    }
)

_MP4_COMPATIBLE_SUBTITLE_CODECS = frozenset(
    {
        "mov_text",
        "tx3g",
        "webvtt",
    }
)


def _normalize_container_format(container: str) -> str:
    """Normalize container format names.

    Args:
        container: Container format string (from ffprobe or file extension).

    Returns:
        Normalized format name (lowercase, standardized).
    """
    container = container.lower().strip()

    # First try exact match for common names
    format_aliases = {
        "matroska": "mkv",
        "matroska,webm": "mkv",
        "mov,mp4,m4a,3gp,3g2,mj2": "mp4",
        "quicktime": "mov",
    }

    if container in format_aliases:
        return format_aliases[container]

    # Use substring matching for more robust detection
    # (handles different ffprobe versions and format variations)
    if "matroska" in container or container == "webm":
        return "mkv"
    if any(x in container for x in ("mp4", "m4a", "m4v")):
        return "mp4"
    if "mov" in container or "quicktime" in container:
        return "mov"
    if "avi" in container:
        return "avi"

    return container


def _is_codec_mp4_compatible(codec: str, track_type: str) -> bool:
    """Check if a codec is compatible with MP4 container.

    Args:
        codec: Codec name (e.g., 'hevc', 'truehd').
        track_type: Track type ('video', 'audio', 'subtitle').

    Returns:
        True if codec is compatible with MP4.
    """
    codec = codec.lower().strip()

    if track_type == "video":
        return codec in _MP4_COMPATIBLE_VIDEO_CODECS
    elif track_type == "audio":
        return codec in _MP4_COMPATIBLE_AUDIO_CODECS
    elif track_type == "subtitle":
        return codec in _MP4_COMPATIBLE_SUBTITLE_CODECS

    # Unknown track types (data, attachment) - skip for MP4
    return False


def _evaluate_container_change(
    tracks: list[TrackInfo],
    source_format: str,
    policy: PolicySchema,
) -> ContainerChange | None:
    """Evaluate if container conversion is needed.

    Args:
        tracks: List of track metadata.
        source_format: Current container format.
        policy: Policy configuration.

    Returns:
        ContainerChange if conversion needed, None otherwise.
    """
    if policy.container is None:
        return None

    target = policy.container.target.lower()
    source = _normalize_container_format(source_format)

    # Skip if already in target format
    if source == target:
        return None

    warnings: list[str] = []
    incompatible_tracks: list[int] = []

    # Check codec compatibility for MP4 target
    if target == "mp4":
        for track in tracks:
            codec = (track.codec or "").lower()
            track_type = track.track_type.lower()

            if not _is_codec_mp4_compatible(codec, track_type):
                incompatible_tracks.append(track.index)
                warnings.append(
                    f"Track {track.index} ({track_type}, {codec}) "
                    f"is not compatible with MP4"
                )

    # MKV accepts all codecs - no compatibility checking needed

    return ContainerChange(
        source_format=source,
        target_format=target,
        warnings=tuple(warnings),
        incompatible_tracks=tuple(incompatible_tracks),
    )


# =============================================================================
# Conditional Rule Evaluation Functions (V4)
# =============================================================================


def evaluate_conditional_rules(
    rules: tuple[ConditionalRule, ...],
    tracks: list[TrackInfo],
    file_path: Path,
) -> ConditionalResult:
    """Evaluate conditional rules and execute matching actions.

    Rules are evaluated in document order. The first rule whose 'when'
    condition matches wins, and its 'then' actions are executed.
    If no rules match and the last rule has an 'else' clause, that
    else clause is executed.

    Args:
        rules: Tuple of ConditionalRule from PolicySchema.
        tracks: List of TrackInfo from the file.
        file_path: Path to the file being processed.

    Returns:
        ConditionalResult with matched rule, skip flags, warnings, and trace.

    Raises:
        ConditionalFailError: If a matched rule has a fail action.
    """
    from video_policy_orchestrator.policy.actions import ActionContext, execute_actions
    from video_policy_orchestrator.policy.conditions import evaluate_condition

    # Empty rules - return empty result
    if not rules:
        return ConditionalResult(
            matched_rule=None,
            matched_branch=None,
            warnings=(),
            evaluation_trace=(),
        )

    evaluation_trace: list[RuleEvaluation] = []
    matched_rule: str | None = None
    matched_branch: Literal["then", "else"] | None = None
    skip_flags = SkipFlags()
    warnings: list[str] = []

    for i, rule in enumerate(rules):
        # Evaluate the condition
        result, reason = evaluate_condition(rule.when, tracks)

        if result:
            # Condition matched - execute then_actions
            evaluation_trace.append(
                RuleEvaluation(
                    rule_name=rule.name,
                    matched=True,
                    reason=reason,
                )
            )

            matched_rule = rule.name
            matched_branch = "then"

            # Execute actions
            context = ActionContext(
                file_path=file_path,
                rule_name=rule.name,
            )
            context = execute_actions(rule.then_actions, context)
            skip_flags = context.skip_flags
            warnings = context.warnings

            # First match wins - stop evaluation
            break

        else:
            # Condition didn't match
            evaluation_trace.append(
                RuleEvaluation(
                    rule_name=rule.name,
                    matched=False,
                    reason=reason,
                )
            )

            # Check if this is the last rule and has else_actions
            is_last_rule = i == len(rules) - 1
            if is_last_rule and rule.else_actions is not None:
                # Execute else_actions for the last rule
                matched_rule = rule.name
                matched_branch = "else"

                context = ActionContext(
                    file_path=file_path,
                    rule_name=rule.name,
                )
                context = execute_actions(rule.else_actions, context)
                skip_flags = context.skip_flags
                warnings = context.warnings

    # Store skip_flags on a temporary attribute for extraction
    result = ConditionalResult(
        matched_rule=matched_rule,
        matched_branch=matched_branch,
        warnings=tuple(warnings),
        evaluation_trace=tuple(evaluation_trace),
    )
    # Attach skip_flags as a transient attribute (not part of frozen dataclass)
    object.__setattr__(result, "_skip_flags", skip_flags)
    return result


def _extract_skip_flags_from_result(result: ConditionalResult) -> SkipFlags:
    """Extract skip flags from a ConditionalResult.

    Args:
        result: The conditional result from rule evaluation.

    Returns:
        SkipFlags accumulated during action execution.
    """
    return getattr(result, "_skip_flags", SkipFlags())


def evaluate_container_change_with_policy(
    tracks: list[TrackInfo],
    source_format: str,
    policy: PolicySchema,
) -> ContainerChange | None:
    """Evaluate container change with policy error handling.

    This function applies the policy's on_incompatible_codec setting
    to determine whether to raise an error or skip conversion.

    Args:
        tracks: List of track metadata.
        source_format: Current container format.
        policy: Policy configuration.

    Returns:
        ContainerChange if conversion should proceed, None if skipped.

    Raises:
        IncompatibleCodecError: If incompatible codecs found and mode is 'error'.
    """
    change = _evaluate_container_change(tracks, source_format, policy)

    if change is None:
        return None

    if change.incompatible_tracks and policy.container:
        mode = policy.container.on_incompatible_codec

        if mode == "error":
            # Build list of incompatible track info
            incompatible_track_info: list[tuple[int, str, str]] = []
            for idx in change.incompatible_tracks:
                track = next(t for t in tracks if t.index == idx)
                incompatible_track_info.append(
                    (idx, track.track_type, track.codec or "unknown")
                )
            raise IncompatibleCodecError(
                target_container=change.target_format,
                incompatible_tracks=incompatible_track_info,
            )
        elif mode == "skip":
            # Skip conversion entirely
            return None

    return change


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
        ConditionalFailError: If a conditional rule triggers a fail action.

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

    # V4: Evaluate conditional rules first (may raise ConditionalFailError)
    conditional_result: ConditionalResult | None = None
    skip_flags = SkipFlags()

    if policy.has_conditional_rules:
        conditional_result = evaluate_conditional_rules(
            rules=policy.conditional_rules,
            tracks=tracks,
            file_path=file_path,
        )
        # Extract skip flags from result (stored on result, not as separate field)
        # We need to rebuild skip flags from evaluation context
        # The skip_flags are returned via the ConditionalResult
        # by inspecting which actions were executed
        # For now, we derive from the actions that were executed
        skip_flags = _extract_skip_flags_from_result(conditional_result)

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

    # Compute track dispositions for V3 track filtering
    track_dispositions: tuple[TrackDisposition, ...] = ()
    tracks_removed = 0
    # Default: all tracks kept when no filtering is active
    tracks_kept = len(tracks)

    # V4: Check skip_track_filter flag before applying track filtering
    should_filter = policy.has_track_filtering and not skip_flags.skip_track_filter
    if should_filter:
        track_dispositions = compute_track_dispositions(tracks, policy)
        tracks_removed = sum(1 for d in track_dispositions if d.action == "REMOVE")
        tracks_kept = sum(1 for d in track_dispositions if d.action == "KEEP")
        if tracks_removed > 0:
            requires_remux = True

    # Compute container change for V3 container conversion
    container_change: ContainerChange | None = None
    if policy.has_container_config:
        container_change = evaluate_container_change_with_policy(
            tracks, container, policy
        )
        if container_change is not None:
            requires_remux = True

    return Plan(
        file_id=file_id,
        file_path=file_path,
        policy_version=policy.schema_version,
        actions=tuple(actions),
        requires_remux=requires_remux,
        created_at=datetime.now(timezone.utc),
        track_dispositions=track_dispositions,
        container_change=container_change,
        conditional_result=conditional_result,
        skip_flags=skip_flags,
        tracks_removed=tracks_removed,
        tracks_kept=tracks_kept,
    )
