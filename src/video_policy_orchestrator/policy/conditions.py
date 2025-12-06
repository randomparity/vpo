"""Condition evaluation for conditional policy rules.

This module implements the evaluation logic for conditional expressions
in VPO policies. It provides functions to evaluate existence conditions,
count conditions, and boolean operators (and/or/not) against track metadata.

Key Functions:
    evaluate_condition: Main entry point for condition evaluation
    evaluate_exists: Check if tracks match criteria
    evaluate_count: Count matching tracks and compare
    matches_track: Check if a single track matches filter criteria

Usage:
    from video_policy_orchestrator.policy.conditions import evaluate_condition
    from video_policy_orchestrator.policy.models import ExistsCondition, TrackFilters

    condition = ExistsCondition(track_type="video", filters=TrackFilters())
    result = evaluate_condition(condition, tracks)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from video_policy_orchestrator.db.types import OriginalDubbedStatus, PluginMetadataDict
from video_policy_orchestrator.language import languages_match
from video_policy_orchestrator.language_analysis.models import (
    LanguageAnalysisResult,
    LanguageClassification,
)
from video_policy_orchestrator.policy.models import (
    AndCondition,
    AudioIsMultiLanguageCondition,
    Comparison,
    ComparisonOperator,
    Condition,
    CountCondition,
    ExistsCondition,
    IsDubbedCondition,
    IsOriginalCondition,
    NotCondition,
    OrCondition,
    PluginMetadataCondition,
    PluginMetadataOperator,
    TitleMatch,
    TrackFilters,
)
from video_policy_orchestrator.track_classification.models import (
    TrackClassificationResult,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.db.models import TrackInfo


# Default patterns for identifying commentary tracks
DEFAULT_COMMENTARY_PATTERNS = ("commentary", "director", "cast")


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

    patterns = commentary_patterns or DEFAULT_COMMENTARY_PATTERNS
    title_lower = track.title.lower()

    for pattern in patterns:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            if compiled.search(title_lower):
                return True
        except re.error:
            # Invalid regex, fall back to substring match
            if pattern.lower() in title_lower:
                return True

    return False


def _compare_value(actual: int, comparison: Comparison) -> bool:
    """Compare an actual value against a comparison spec.

    Args:
        actual: The actual value from the track.
        comparison: The comparison specification.

    Returns:
        True if comparison passes, False otherwise.
    """
    op = comparison.operator
    value = comparison.value

    if op == ComparisonOperator.EQ:
        return actual == value
    elif op == ComparisonOperator.LT:
        return actual < value
    elif op == ComparisonOperator.LTE:
        return actual <= value
    elif op == ComparisonOperator.GT:
        return actual > value
    elif op == ComparisonOperator.GTE:
        return actual >= value

    return False


def _matches_string_or_list(
    actual: str | None,
    pattern: str | tuple[str, ...],
    *,
    use_language_match: bool = False,
) -> bool:
    """Check if actual value matches a string or any item in a list.

    Args:
        actual: The actual string value (may be None).
        pattern: A single string or tuple of strings to match against.
        use_language_match: If True, use languages_match() for comparison.

    Returns:
        True if actual matches pattern (or any pattern in tuple).
    """
    if actual is None:
        return False

    if isinstance(pattern, str):
        patterns = (pattern,)
    else:
        patterns = pattern

    for p in patterns:
        if use_language_match:
            if languages_match(actual, p):
                return True
        else:
            if actual.lower() == p.lower():
                return True

    return False


def _matches_title(actual: str | None, pattern: str | TitleMatch) -> bool:
    """Check if actual title matches the title pattern.

    Args:
        actual: The actual title value (may be None).
        pattern: A string (substring match) or TitleMatch spec.

    Returns:
        True if title matches.
    """
    if actual is None:
        return False

    if isinstance(pattern, str):
        # Simple substring match (case-insensitive)
        return pattern.lower() in actual.lower()

    # TitleMatch object
    if pattern.contains is not None:
        return pattern.contains.lower() in actual.lower()

    if pattern.regex is not None:
        try:
            return bool(re.search(pattern.regex, actual, re.IGNORECASE))
        except re.error:
            # Invalid regex - shouldn't happen due to validation
            return False

    # Should never reach here due to loader validation
    raise ValueError("TitleMatch must have either 'contains' or 'regex' set")


def matches_track(
    track: TrackInfo,
    filters: TrackFilters,
    commentary_patterns: tuple[str, ...] | None = None,
) -> bool:
    """Check if a track matches all filter criteria.

    Args:
        track: Track metadata to check.
        filters: Filter criteria to apply.
        commentary_patterns: Patterns to identify commentary tracks
            (for not_commentary filter).

    Returns:
        True if track matches all specified criteria.
        Unspecified criteria (None values) always match.
    """
    # Language filter
    if filters.language is not None:
        if not _matches_string_or_list(
            track.language, filters.language, use_language_match=True
        ):
            return False

    # Codec filter
    if filters.codec is not None:
        if not _matches_string_or_list(track.codec, filters.codec):
            return False

    # Boolean filters
    if filters.is_default is not None:
        if track.is_default != filters.is_default:
            return False

    if filters.is_forced is not None:
        if track.is_forced != filters.is_forced:
            return False

    # Numeric filters
    if filters.channels is not None:
        if track.channels is None:
            return False
        if isinstance(filters.channels, int):
            if track.channels != filters.channels:
                return False
        else:
            if not _compare_value(track.channels, filters.channels):
                return False

    if filters.width is not None:
        if track.width is None:
            return False
        if isinstance(filters.width, int):
            if track.width != filters.width:
                return False
        else:
            if not _compare_value(track.width, filters.width):
                return False

    if filters.height is not None:
        if track.height is None:
            return False
        if isinstance(filters.height, int):
            if track.height != filters.height:
                return False
        else:
            if not _compare_value(track.height, filters.height):
                return False

    # Title filter
    if filters.title is not None:
        if not _matches_title(track.title, filters.title):
            return False

    # Not commentary filter (V8)
    if filters.not_commentary is True:
        if _is_commentary_track(track, commentary_patterns):
            return False

    return True


def evaluate_exists(
    condition: ExistsCondition,
    tracks: list[TrackInfo],
    commentary_patterns: tuple[str, ...] | None = None,
) -> tuple[bool, str]:
    """Evaluate an existence condition.

    Args:
        condition: The existence condition to evaluate.
        tracks: List of tracks to check.
        commentary_patterns: Patterns to identify commentary tracks.

    Returns:
        Tuple of (result, reason) where result is True if at least one
        track matches and reason is a human-readable explanation.
    """
    track_type = condition.track_type.lower()
    filters = condition.filters

    matching_tracks = []
    for track in tracks:
        if track.track_type.lower() != track_type:
            continue
        if matches_track(track, filters, commentary_patterns):
            matching_tracks.append(track)

    if matching_tracks:
        # Build reason with first matching track info
        first = matching_tracks[0]
        reason = f"exists({track_type}) → True (track[{first.index}]"
        if first.codec:
            reason += f" {first.codec}"
        if first.language:
            reason += f" {first.language}"
        reason += ")"
        return (True, reason)

    reason = f"exists({track_type}) → False (no matching tracks)"
    return (False, reason)


def evaluate_count(
    condition: CountCondition,
    tracks: list[TrackInfo],
    commentary_patterns: tuple[str, ...] | None = None,
) -> tuple[bool, str]:
    """Evaluate a count condition.

    Args:
        condition: The count condition to evaluate.
        tracks: List of tracks to count.
        commentary_patterns: Patterns to identify commentary tracks.

    Returns:
        Tuple of (result, reason) where result is True if count
        comparison passes and reason is a human-readable explanation.
    """
    track_type = condition.track_type.lower()
    filters = condition.filters

    count = 0
    for track in tracks:
        if track.track_type.lower() != track_type:
            continue
        if matches_track(track, filters, commentary_patterns):
            count += 1

    comparison = Comparison(operator=condition.operator, value=condition.value)
    result = _compare_value(count, comparison)

    op_str = condition.operator.value
    reason = (
        f"count({track_type}) {op_str} {condition.value} → {result} (count={count})"
    )
    return (result, reason)


def evaluate_audio_is_multi_language(
    condition: AudioIsMultiLanguageCondition,
    tracks: list[TrackInfo],
    language_results: dict[int, LanguageAnalysisResult] | None = None,
) -> tuple[bool, str]:
    """Evaluate an audio multi-language condition.

    Args:
        condition: The multi-language condition to evaluate.
        tracks: List of tracks (to filter audio tracks).
        language_results: Dict mapping track_id to LanguageAnalysisResult.

    Returns:
        Tuple of (result, reason) where result is True if any audio track
        has multi-language content above the threshold.
    """
    if language_results is None:
        return (
            False,
            "audio_is_multi_language → False (no language analysis available)",
        )

    # Filter to audio tracks
    audio_tracks = [t for t in tracks if t.track_type.lower() == "audio"]

    # If specific track_index, filter to that track
    if condition.track_index is not None:
        audio_tracks = [t for t in audio_tracks if t.index == condition.track_index]
        if not audio_tracks:
            return (
                False,
                f"audio_is_multi_language → False "
                f"(track {condition.track_index} not found)",
            )

    # Check each audio track for multi-language analysis
    for track in audio_tracks:
        # Skip tracks without database ID (can't lookup language results)
        if track.id is None:
            continue

        # Get analysis result by track database ID
        result = language_results.get(track.id)
        if result is None:
            continue

        # Check classification
        if result.classification != LanguageClassification.MULTI_LANGUAGE:
            continue

        # Check if primary language matches (if specified)
        if condition.primary_language is not None:
            if not languages_match(result.primary_language, condition.primary_language):
                continue

        # Check secondary language percentage threshold
        # A track is multi-language if any secondary language exceeds threshold
        has_significant_secondary = False
        for secondary in result.secondary_languages:
            if secondary.percentage >= condition.threshold:
                has_significant_secondary = True
                break

        if has_significant_secondary:
            reason = (
                f"audio_is_multi_language → True "
                f"(track[{track.index}] {result.primary_language} "
                f"{result.primary_percentage:.0%}, "
                f"secondary above {condition.threshold:.0%})"
            )
            return (True, reason)

    # No track matched
    if condition.track_index is not None:
        reason = (
            f"audio_is_multi_language → False "
            f"(track {condition.track_index} not multi-language)"
        )
    else:
        reason = "audio_is_multi_language → False (no multi-language audio tracks)"

    return (False, reason)


def evaluate_is_original(
    condition: IsOriginalCondition,
    tracks: list[TrackInfo],
    classification_results: dict[int, TrackClassificationResult] | None = None,
) -> tuple[bool, str]:
    """Evaluate an is_original condition.

    Args:
        condition: The is_original condition to evaluate.
        tracks: List of tracks to check.
        classification_results: Dict mapping track_id to TrackClassificationResult.

    Returns:
        Tuple of (result, reason) where result is True if any track matches
        the original/dubbed status with sufficient confidence.
    """
    if classification_results is None:
        return (
            False,
            "is_original → False (no classification results available)",
        )

    # Filter to audio tracks
    audio_tracks = [t for t in tracks if t.track_type.lower() == "audio"]

    for track in audio_tracks:
        if track.id is None:
            continue

        classification = classification_results.get(track.id)
        if classification is None:
            continue

        # Check confidence threshold
        if classification.confidence < condition.min_confidence:
            continue

        # Check language filter if specified
        if condition.language is not None:
            if classification.language is None:
                continue
            if not languages_match(classification.language, condition.language):
                continue

        # Check original status
        is_original = (
            classification.original_dubbed_status == OriginalDubbedStatus.ORIGINAL
        )

        if condition.value == is_original:
            status_str = "original" if is_original else "dubbed"
            reason = (
                f"is_original → True "
                f"(track[{track.index}] is {status_str}, "
                f"confidence={classification.confidence:.0%})"
            )
            return (True, reason)

    # No matching track found
    expected = "original" if condition.value else "not original"
    return (False, f"is_original → False (no {expected} tracks found)")


def evaluate_is_dubbed(
    condition: IsDubbedCondition,
    tracks: list[TrackInfo],
    classification_results: dict[int, TrackClassificationResult] | None = None,
) -> tuple[bool, str]:
    """Evaluate an is_dubbed condition.

    Args:
        condition: The is_dubbed condition to evaluate.
        tracks: List of tracks to check.
        classification_results: Dict mapping track_id to TrackClassificationResult.

    Returns:
        Tuple of (result, reason) where result is True if any track matches
        the dubbed status with sufficient confidence.
    """
    if classification_results is None:
        return (
            False,
            "is_dubbed → False (no classification results available)",
        )

    # Filter to audio tracks
    audio_tracks = [t for t in tracks if t.track_type.lower() == "audio"]

    for track in audio_tracks:
        if track.id is None:
            continue

        classification = classification_results.get(track.id)
        if classification is None:
            continue

        # Check confidence threshold
        if classification.confidence < condition.min_confidence:
            continue

        # Check language filter if specified
        if condition.language is not None:
            if classification.language is None:
                continue
            if not languages_match(classification.language, condition.language):
                continue

        # Check dubbed status
        is_dubbed = classification.original_dubbed_status == OriginalDubbedStatus.DUBBED

        if condition.value == is_dubbed:
            status_str = "dubbed" if is_dubbed else "original"
            reason = (
                f"is_dubbed → True "
                f"(track[{track.index}] is {status_str}, "
                f"confidence={classification.confidence:.0%})"
            )
            return (True, reason)

    # No matching track found
    expected = "dubbed" if condition.value else "not dubbed"
    return (False, f"is_dubbed → False (no {expected} tracks found)")


def evaluate_plugin_metadata(
    condition: PluginMetadataCondition,
    plugin_metadata: PluginMetadataDict | None,
) -> tuple[bool, str]:
    """Evaluate a plugin metadata condition.

    Args:
        condition: The plugin metadata condition to evaluate.
        plugin_metadata: Dict of plugin metadata keyed by plugin name,
            e.g., {"radarr": {"original_language": "jpn", ...}}.

    Returns:
        Tuple of (result, reason) where result is True if the condition
        matches and reason is a human-readable explanation.
    """
    plugin_name = condition.plugin.lower()
    field_name = condition.field.lower()
    expected_value = condition.value
    op = condition.operator

    # Check if plugin metadata is available
    if plugin_metadata is None:
        return (
            False,
            f"plugin_metadata({plugin_name}.{field_name}) → False "
            "(no plugin metadata available)",
        )

    # Check if plugin exists in metadata (case-insensitive lookup)
    plugin_data = None
    for key, value in plugin_metadata.items():
        if key.lower() == plugin_name:
            plugin_data = value
            break
    if plugin_data is None:
        return (
            False,
            f"plugin_metadata({plugin_name}.{field_name}) → False "
            f"(plugin '{plugin_name}' not in metadata)",
        )

    # Check if field exists in plugin data (case-insensitive lookup)
    actual_value = None
    field_found = False
    for key, value in plugin_data.items():
        if key.lower() == field_name:
            actual_value = value
            field_found = True
            break
    if not field_found:
        return (
            False,
            f"plugin_metadata({plugin_name}.{field_name}) → False "
            f"(field '{field_name}' not found)",
        )

    # Handle EXISTS operator - field was found, so it exists
    if op == PluginMetadataOperator.EXISTS:
        return (
            True,
            f"plugin_metadata({plugin_name}.{field_name}) exists → True",
        )

    # Handle None values
    if actual_value is None:
        return (
            False,
            f"plugin_metadata({plugin_name}.{field_name}) → False "
            "(field value is null)",
        )

    # Evaluate based on operator
    result = _evaluate_plugin_metadata_op(actual_value, expected_value, op)

    op_str = op.value
    if result:
        reason = (
            f"plugin_metadata({plugin_name}.{field_name}) {op_str} "
            f"{expected_value!r} → True (actual={actual_value!r})"
        )
    else:
        reason = (
            f"plugin_metadata({plugin_name}.{field_name}) {op_str} "
            f"{expected_value!r} → False (actual={actual_value!r})"
        )

    return (result, reason)


def _evaluate_plugin_metadata_op(
    actual: str | int | float | bool,
    expected: str | int | float | bool,
    op: PluginMetadataOperator,
) -> bool:
    """Evaluate a plugin metadata comparison operation.

    Args:
        actual: The actual value from plugin metadata.
        expected: The expected value from the condition.
        op: The comparison operator.

    Returns:
        True if the comparison succeeds, False otherwise.
    """
    if op == PluginMetadataOperator.EQ:
        # String comparison is case-insensitive
        if isinstance(actual, str) and isinstance(expected, str):
            return actual.lower() == expected.lower()
        return actual == expected

    if op == PluginMetadataOperator.NEQ:
        # String comparison is case-insensitive
        if isinstance(actual, str) and isinstance(expected, str):
            return actual.lower() != expected.lower()
        return actual != expected

    if op == PluginMetadataOperator.CONTAINS:
        # Substring match (strings only)
        if isinstance(actual, str) and isinstance(expected, str):
            return expected.lower() in actual.lower()
        # Non-string types: convert to string and match
        return str(expected).lower() in str(actual).lower()

    # Numeric comparisons (integers/floats only)
    if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
        # Comparison operators only work on numeric types
        return False

    if op == PluginMetadataOperator.LT:
        return actual < expected
    if op == PluginMetadataOperator.LTE:
        return actual <= expected
    if op == PluginMetadataOperator.GT:
        return actual > expected
    if op == PluginMetadataOperator.GTE:
        return actual >= expected

    return False


def evaluate_condition(
    condition: Condition,
    tracks: list[TrackInfo],
    language_results: dict[int, LanguageAnalysisResult] | None = None,
    commentary_patterns: tuple[str, ...] | None = None,
    plugin_metadata: PluginMetadataDict | None = None,
    classification_results: dict[int, TrackClassificationResult] | None = None,
) -> tuple[bool, str]:
    """Evaluate a condition against track metadata.

    This is the main entry point for condition evaluation. It handles
    all condition types: exists, count, audio_is_multi_language,
    plugin_metadata, is_original, is_dubbed, and, or, not.

    Args:
        condition: The condition to evaluate.
        tracks: List of tracks to evaluate against.
        language_results: Optional dict mapping track_id to LanguageAnalysisResult
            (required for audio_is_multi_language conditions).
        commentary_patterns: Patterns to identify commentary tracks
            (for not_commentary filter).
        plugin_metadata: Optional dict of plugin metadata keyed by plugin name
            (required for plugin_metadata conditions).
        classification_results: Optional dict mapping track_id to
            TrackClassificationResult (required for is_original/is_dubbed conditions).

    Returns:
        Tuple of (result, reason) where result is the boolean outcome
        and reason is a human-readable explanation for dry-run output.
    """
    if isinstance(condition, ExistsCondition):
        return evaluate_exists(condition, tracks, commentary_patterns)

    if isinstance(condition, CountCondition):
        return evaluate_count(condition, tracks, commentary_patterns)

    if isinstance(condition, AudioIsMultiLanguageCondition):
        return evaluate_audio_is_multi_language(condition, tracks, language_results)

    if isinstance(condition, PluginMetadataCondition):
        return evaluate_plugin_metadata(condition, plugin_metadata)

    if isinstance(condition, IsOriginalCondition):
        return evaluate_is_original(condition, tracks, classification_results)

    if isinstance(condition, IsDubbedCondition):
        return evaluate_is_dubbed(condition, tracks, classification_results)

    if isinstance(condition, AndCondition):
        for sub in condition.conditions:
            result, reason = evaluate_condition(
                sub,
                tracks,
                language_results,
                commentary_patterns,
                plugin_metadata,
                classification_results,
            )
            if not result:
                return (False, f"and → False ({reason})")
        return (True, f"and → True ({len(condition.conditions)} conditions)")

    if isinstance(condition, OrCondition):
        for sub in condition.conditions:
            result, reason = evaluate_condition(
                sub,
                tracks,
                language_results,
                commentary_patterns,
                plugin_metadata,
                classification_results,
            )
            if result:
                return (True, f"or → True ({reason})")
        return (False, f"or → False ({len(condition.conditions)} conditions failed)")

    if isinstance(condition, NotCondition):
        result, reason = evaluate_condition(
            condition.inner,
            tracks,
            language_results,
            commentary_patterns,
            plugin_metadata,
            classification_results,
        )
        return (not result, f"not({reason}) → {not result}")

    # Should never reach here - all condition types handled above
    raise TypeError(f"Unknown condition type: {type(condition).__name__}")
