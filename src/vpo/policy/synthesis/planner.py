"""Synthesis plan generation.

This module creates synthesis plans by evaluating track definitions against
available audio tracks and determining which operations are needed.

Key Functions:
    plan_synthesis: Generate a complete synthesis plan for a file
    resolve_synthesis_operation: Create a single operation from definition
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from vpo.domain import PluginMetadataDict
from vpo.policy.conditions import evaluate_condition
from vpo.policy.synthesis.downmix import (
    get_downmix_filter,
    validate_downmix,
)
from vpo.policy.synthesis.encoders import (
    get_bitrate,
    is_encoder_available,
)
from vpo.policy.synthesis.models import (
    AudioCodec,
    ChannelConfig,
    ChannelPreference,
    Position,
    PreferenceCriterion,
    SkippedSynthesis,
    SkipReason,
    SourcePreferences,
    SynthesisOperation,
    SynthesisPlan,
    SynthesisTrackDefinition,
    TrackOrderEntry,
)
from vpo.policy.synthesis.source_selector import (
    _is_commentary_track,
    filter_audio_tracks,
    select_source_track,
)

if TYPE_CHECKING:
    from vpo.domain import TrackInfo
    from vpo.policy.types import (
        AudioSynthesisConfig,
        Comparison,
        Condition,
        SkipIfExistsCriteria,
        SynthesisTrackDefinitionRef,
    )

logger = logging.getLogger(__name__)


def _compare_channels(
    actual: int,
    criteria: int | Comparison,
) -> bool:
    """Compare actual channel count against criteria.

    Args:
        actual: The actual channel count from the track.
        criteria: Either an exact int or a Comparison object.

    Returns:
        True if the comparison passes.
    """
    from vpo.policy.types import (
        ComparisonOperator,
    )

    if isinstance(criteria, int):
        return actual == criteria

    # It's a Comparison object
    op = criteria.operator
    value = criteria.value

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


def _evaluate_skip_if_exists(
    criteria: SkipIfExistsCriteria,
    audio_tracks: list[TrackInfo],
    commentary_patterns: tuple[str, ...] | None = None,
) -> tuple[bool, str | None]:
    """Evaluate skip_if_exists criteria against existing audio tracks.

    Checks if any existing audio track matches ALL specified criteria.
    If a match is found, synthesis should be skipped.

    Args:
        criteria: The skip criteria from the synthesis definition.
        audio_tracks: List of audio tracks in the file.
        commentary_patterns: Patterns to identify commentary tracks.

    Returns:
        Tuple of (should_skip, reason) where should_skip is True if a
        matching track exists and reason describes the match.
    """
    from vpo.language import languages_match

    for track in audio_tracks:
        # Check codec criteria
        if criteria.codec is not None:
            codecs = (
                criteria.codec
                if isinstance(criteria.codec, tuple)
                else (criteria.codec,)
            )
            if not track.codec or not any(
                track.codec.casefold() == c.casefold() for c in codecs
            ):
                continue  # Codec doesn't match, try next track

        # Check channels criteria
        if criteria.channels is not None:
            if track.channels is None:
                continue  # No channel info, try next track
            if not _compare_channels(track.channels, criteria.channels):
                continue  # Channels don't match, try next track

        # Check language criteria
        if criteria.language is not None:
            languages = (
                criteria.language
                if isinstance(criteria.language, tuple)
                else (criteria.language,)
            )
            if not track.language or not any(
                languages_match(track.language, lang) for lang in languages
            ):
                continue  # Language doesn't match, try next track

        # Check not_commentary criteria
        if criteria.not_commentary is True:
            if _is_commentary_track(track, commentary_patterns):
                continue  # Is commentary, try next track

        # All criteria matched!
        reason_parts = []
        if criteria.codec:
            reason_parts.append(f"codec={track.codec}")
        if criteria.channels:
            reason_parts.append(f"channels={track.channels}")
        if criteria.language:
            reason_parts.append(f"language={track.language}")
        if criteria.not_commentary:
            reason_parts.append("not_commentary")

        reason = (
            f"Track {track.index} matches skip_if_exists criteria "
            f"({', '.join(reason_parts)})"
        )
        logger.debug(
            "skip_if_exists matched: track %d (%s)",
            track.index,
            ", ".join(reason_parts),
        )
        return (True, reason)

    # No matching track found
    return (False, None)


def _convert_ref_to_definition(
    ref: SynthesisTrackDefinitionRef,
) -> SynthesisTrackDefinition:
    """Convert a policy reference to a full definition.

    Args:
        ref: The policy reference to convert.

    Returns:
        Full SynthesisTrackDefinition.
    """
    # Parse codec
    codec = AudioCodec(ref.codec)

    # Parse channels
    if isinstance(ref.channels, int):
        channels = ref.channels
    else:
        # String channel config
        channel_map = {
            "mono": ChannelConfig.MONO,
            "stereo": ChannelConfig.STEREO,
            "5.1": ChannelConfig.SURROUND_51,
            "7.1": ChannelConfig.SURROUND_71,
        }
        channels = channel_map.get(ref.channels.casefold(), ChannelConfig.STEREO)

    # Parse source preferences
    prefer_list: list[PreferenceCriterion] = []
    for pref_dict in ref.source_prefer:
        # Convert dict to PreferenceCriterion
        lang = pref_dict.get("language")
        not_commentary = pref_dict.get("not_commentary")
        ch = pref_dict.get("channels")
        codec_pref = pref_dict.get("codec")

        # Handle channels preference
        channels_val = None
        if ch is not None:
            if ch == "max":
                channels_val = ChannelPreference.MAX
            elif ch == "min":
                channels_val = ChannelPreference.MIN
            elif isinstance(ch, int):
                channels_val = ch

        prefer_list.append(
            PreferenceCriterion(
                language=lang,
                not_commentary=not_commentary,
                channels=channels_val,
                codec=codec_pref,
            )
        )

    source = SourcePreferences(prefer=tuple(prefer_list))

    # Parse position
    if isinstance(ref.position, int):
        position = ref.position
    elif ref.position == "after_source":
        position = Position.AFTER_SOURCE
    else:
        position = Position.END

    return SynthesisTrackDefinition(
        name=ref.name,
        codec=codec,
        channels=channels,
        source=source,
        bitrate=ref.bitrate,
        create_if=ref.create_if,
        title=ref.title,
        language=ref.language,
        position=position,
    )


def _evaluate_create_condition(
    condition: Condition | None,
    tracks: list[TrackInfo],
    definition_name: str,
    plugin_metadata: PluginMetadataDict | None = None,
) -> tuple[bool, str]:
    """Evaluate a create_if condition.

    Args:
        condition: The condition to evaluate, or None.
        tracks: List of all tracks in the file.
        definition_name: Name of the synthesis definition (for logging).
        plugin_metadata: Plugin-provided metadata for condition evaluation.

    Returns:
        Tuple of (should_create, reason).
    """
    if condition is None:
        return True, "no condition specified"

    result, reason = evaluate_condition(
        condition, tracks, plugin_metadata=plugin_metadata
    )
    logger.debug(
        "create_if condition for '%s': %s (%s)",
        definition_name,
        result,
        reason,
    )
    return result, reason


def _resolve_track_position(
    position: Position | int,
    source_track_index: int,
    audio_tracks: list[TrackInfo],
    existing_synth_count: int,
) -> int:
    """Resolve the position specifier to an actual track index.

    Args:
        position: Position specification from definition.
        source_track_index: Index of the source track.
        audio_tracks: List of existing audio tracks.
        existing_synth_count: Number of already-planned synthesis tracks.

    Returns:
        Final position index for the synthesized track.
    """
    if isinstance(position, int):
        # Explicit position (1-based in config, 0-based internally)
        return position - 1

    if position == Position.AFTER_SOURCE:
        # Find position of source track in audio track list
        for i, track in enumerate(audio_tracks):
            if track.index == source_track_index:
                return i + 1 + existing_synth_count
        # Fallback to end if source not found
        return len(audio_tracks) + existing_synth_count

    # Position.END
    return len(audio_tracks) + existing_synth_count


def resolve_synthesis_operation(
    definition: SynthesisTrackDefinition,
    all_tracks: list[TrackInfo],
    commentary_patterns: tuple[str, ...] | None = None,
    existing_operations: list[SynthesisOperation] | None = None,
    plugin_metadata: PluginMetadataDict | None = None,
) -> SynthesisOperation | SkippedSynthesis:
    """Resolve a single synthesis definition to an operation or skip record.

    Args:
        definition: The synthesis track definition.
        all_tracks: All tracks in the file.
        commentary_patterns: Patterns to identify commentary tracks.
        existing_operations: Already-planned operations (for position calculation).
        plugin_metadata: Plugin-provided metadata for condition evaluation.

    Returns:
        Either a SynthesisOperation or SkippedSynthesis.
    """
    existing_ops = existing_operations or []

    # Filter to audio tracks
    audio_tracks = filter_audio_tracks(all_tracks)

    # Evaluate create_if condition
    should_create, reason = _evaluate_create_condition(
        definition.create_if,
        all_tracks,
        definition.name,
        plugin_metadata,
    )
    if not should_create:
        return SkippedSynthesis(
            definition_name=definition.name,
            reason=SkipReason.CONDITION_NOT_MET,
            details=f"Condition not satisfied: {reason}",
        )

    # Check encoder availability
    if not is_encoder_available(definition.codec):
        return SkippedSynthesis(
            definition_name=definition.name,
            reason=SkipReason.ENCODER_UNAVAILABLE,
            details=f"FFmpeg encoder for {definition.codec.value} not available",
        )

    # Select source track
    selection = select_source_track(
        audio_tracks,
        definition.source,
        commentary_patterns,
    )
    if selection is None:
        return SkippedSynthesis(
            definition_name=definition.name,
            reason=SkipReason.NO_SOURCE_AVAILABLE,
            details="No audio tracks available",
        )

    # Check downmix validity
    source_channels = selection.track_info.channels or 2
    target_channels = definition.target_channels

    is_valid, error_msg = validate_downmix(source_channels, target_channels)
    if not is_valid:
        return SkippedSynthesis(
            definition_name=definition.name,
            reason=SkipReason.WOULD_UPMIX,
            details=error_msg,
        )

    # Generate downmix filter if needed
    downmix_filter = None
    if source_channels != target_channels:
        downmix_filter = get_downmix_filter(source_channels, target_channels)

    # Get target bitrate
    target_bitrate = get_bitrate(
        definition.codec,
        target_channels,
        definition.bitrate,
    )

    # Resolve title
    if definition.title == "inherit":
        target_title = selection.track_info.title or ""
    else:
        target_title = definition.title

    # Resolve language
    if definition.language == "inherit":
        target_language = selection.track_info.language or "und"
    else:
        target_language = definition.language

    # Resolve position
    target_position = _resolve_track_position(
        definition.position,
        selection.track_index,
        audio_tracks,
        len(existing_ops),
    )

    return SynthesisOperation(
        definition_name=definition.name,
        source_track=selection,
        target_codec=definition.codec,
        target_channels=target_channels,
        target_bitrate=target_bitrate,
        target_title=target_title,
        target_language=target_language,
        target_position=target_position,
        downmix_filter=downmix_filter,
    )


def _build_final_track_order(
    audio_tracks: list[TrackInfo],
    operations: list[SynthesisOperation],
) -> tuple[TrackOrderEntry, ...]:
    """Build the projected final track order after synthesis.

    Args:
        audio_tracks: Original audio tracks.
        operations: Synthesis operations to perform.

    Returns:
        Tuple of TrackOrderEntry objects representing final order.
    """
    # Create entries for original tracks
    entries: list[tuple[int, TrackOrderEntry]] = []

    for i, track in enumerate(audio_tracks):
        entries.append(
            (
                i,
                TrackOrderEntry(
                    index=i,
                    track_type="original",
                    codec=track.codec or "unknown",
                    channels=track.channels or 2,
                    language=track.language or "und",
                    title=track.title,
                    original_index=track.index,
                ),
            )
        )

    # Insert synthesis operations at their target positions
    for op in operations:
        insert_pos = op.target_position

        entry = TrackOrderEntry(
            index=insert_pos,
            track_type="synthesized",
            codec=op.target_codec.value,
            channels=op.target_channels,
            language=op.target_language,
            title=op.target_title,
            synthesis_name=op.definition_name,
        )

        # Insert at position (adjusting existing indices)
        entries.insert(insert_pos, (insert_pos, entry))

    # Renumber indices
    final_entries: list[TrackOrderEntry] = []
    for i, (_, entry) in enumerate(entries):
        new_entry = TrackOrderEntry(
            index=i,
            track_type=entry.track_type,
            codec=entry.codec,
            channels=entry.channels,
            language=entry.language,
            title=entry.title,
            original_index=entry.original_index,
            synthesis_name=entry.synthesis_name,
        )
        final_entries.append(new_entry)

    return tuple(final_entries)


def plan_synthesis(
    file_id: str,
    file_path: Path,
    tracks: list[TrackInfo],
    synthesis_config: AudioSynthesisConfig,
    commentary_patterns: tuple[str, ...] | None = None,
    plugin_metadata: PluginMetadataDict | None = None,
) -> SynthesisPlan:
    """Generate a complete synthesis plan for a file.

    Args:
        file_id: UUID of the file.
        file_path: Path to the media file.
        tracks: All tracks in the file.
        synthesis_config: Audio synthesis configuration from policy.
        commentary_patterns: Patterns to identify commentary tracks.
        plugin_metadata: Plugin-provided metadata for condition evaluation.

    Returns:
        Complete SynthesisPlan with operations and skipped tracks.
    """
    operations: list[SynthesisOperation] = []
    skipped: list[SkippedSynthesis] = []

    audio_tracks = filter_audio_tracks(tracks)

    for ref in synthesis_config.tracks:
        # Evaluate skip_if_exists FIRST (V8 feature)
        if ref.skip_if_exists is not None:
            should_skip, skip_reason = _evaluate_skip_if_exists(
                ref.skip_if_exists,
                audio_tracks,
                commentary_patterns,
            )
            if should_skip:
                skipped.append(
                    SkippedSynthesis(
                        definition_name=ref.name,
                        reason=SkipReason.ALREADY_EXISTS,
                        details=skip_reason or "Matching track already exists",
                    )
                )
                logger.info(
                    "Skipped synthesis '%s': %s - %s",
                    ref.name,
                    SkipReason.ALREADY_EXISTS.value,
                    skip_reason,
                )
                continue

        definition = _convert_ref_to_definition(ref)

        result = resolve_synthesis_operation(
            definition,
            tracks,
            commentary_patterns,
            operations,
            plugin_metadata,
        )

        if isinstance(result, SynthesisOperation):
            operations.append(result)
            logger.info(
                "Planned synthesis '%s': %s %dch from track %d",
                definition.name,
                definition.codec.value,
                definition.target_channels,
                result.source_track.track_index,
            )
        else:
            skipped.append(result)
            logger.info(
                "Skipped synthesis '%s': %s - %s",
                definition.name,
                result.reason.value,
                result.details,
            )

    # Build final track order projection
    final_order = _build_final_track_order(audio_tracks, operations)

    return SynthesisPlan(
        file_id=file_id,
        file_path=file_path,
        operations=tuple(operations),
        skipped=tuple(skipped),
        final_track_order=final_order,
        audio_tracks=tuple(audio_tracks),
    )


# =============================================================================
# Dry-Run Formatting Functions
# =============================================================================


def format_synthesis_operation(operation: SynthesisOperation) -> str:
    """Format a synthesis operation for CLI output.

    Args:
        operation: The operation to format.

    Returns:
        Formatted string for display.
    """
    lines = [f"  {operation.definition_name}:"]
    lines.append(
        f"    Source: Track {operation.source_track.track_index} "
        f"({operation.source_track.track_info.codec or 'unknown'} "
        f"{operation.source_track.track_info.channels or '?'}ch)"
    )
    lines.append(
        f"    Target: {operation.target_codec.value.upper()} "
        f"{operation.target_channels}ch"
    )
    if operation.target_bitrate:
        lines.append(f"    Bitrate: {operation.target_bitrate // 1000}k")
    if operation.downmix_filter:
        src_ch = operation.source_track.track_info.channels
        lines.append(f"    Downmix: {src_ch}ch -> {operation.target_channels}ch")
    if operation.target_title:
        lines.append(f"    Title: {operation.target_title}")
    lines.append(f"    Language: {operation.target_language}")
    lines.append(f"    Position: audio track {operation.target_position}")
    return "\n".join(lines)


def format_skipped_synthesis(skipped: SkippedSynthesis) -> str:
    """Format a skipped synthesis for CLI output.

    Args:
        skipped: The skipped record to format.

    Returns:
        Formatted string for display.
    """
    reason_display = {
        SkipReason.CONDITION_NOT_MET: "Condition not met",
        SkipReason.NO_SOURCE_AVAILABLE: "No source track",
        SkipReason.WOULD_UPMIX: "Would require upmix",
        SkipReason.ENCODER_UNAVAILABLE: "Encoder not available",
        SkipReason.ALREADY_EXISTS: "Already exists",
    }
    reason_str = reason_display.get(skipped.reason, skipped.reason.value)
    return f"  {skipped.definition_name}: SKIPPED ({reason_str})\n    {skipped.details}"


def format_synthesis_plan(plan: SynthesisPlan) -> str:
    """Format a complete synthesis plan for CLI dry-run output.

    Args:
        plan: The synthesis plan to format.

    Returns:
        Formatted string for display.
    """
    lines = [f"Audio Synthesis Plan for {plan.file_path.name}:"]

    if not plan.operations and not plan.skipped:
        lines.append("  No synthesis operations defined")
        return "\n".join(lines)

    if plan.operations:
        lines.append(f"\nTracks to create ({len(plan.operations)}):")
        for op in plan.operations:
            lines.append(format_synthesis_operation(op))

    if plan.skipped:
        lines.append(f"\nSkipped ({len(plan.skipped)}):")
        for skip in plan.skipped:
            lines.append(format_skipped_synthesis(skip))

    if plan.final_track_order:
        lines.append("\nProjected final audio track order:")
        lines.append(format_final_track_order(plan.final_track_order))

    return "\n".join(lines)


def format_final_track_order(order: tuple[TrackOrderEntry, ...]) -> str:
    """Format the projected final track order for display.

    Args:
        order: Tuple of TrackOrderEntry objects.

    Returns:
        Formatted string for display.
    """
    lines = []
    for entry in order:
        marker = "*" if entry.track_type == "synthesized" else " "
        title = entry.title or "(no title)"
        lines.append(
            f"  {marker} [{entry.index}] {entry.codec.upper()} {entry.channels}ch "
            f"{entry.language} - {title}"
        )
    if any(e.track_type == "synthesized" for e in order):
        lines.append("  (* = synthesized)")
    return "\n".join(lines)
