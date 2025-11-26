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

from video_policy_orchestrator.policy.conditions import evaluate_condition
from video_policy_orchestrator.policy.synthesis.downmix import (
    get_downmix_filter,
    validate_downmix,
)
from video_policy_orchestrator.policy.synthesis.encoders import (
    get_bitrate,
    is_encoder_available,
)
from video_policy_orchestrator.policy.synthesis.models import (
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
from video_policy_orchestrator.policy.synthesis.source_selector import (
    filter_audio_tracks,
    select_source_track,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.db.models import TrackInfo
    from video_policy_orchestrator.policy.models import (
        AudioSynthesisConfig,
        Condition,
        SynthesisTrackDefinitionRef,
    )

logger = logging.getLogger(__name__)


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
        channels = channel_map.get(ref.channels.lower(), ChannelConfig.STEREO)

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
) -> tuple[bool, str]:
    """Evaluate a create_if condition.

    Args:
        condition: The condition to evaluate, or None.
        tracks: List of all tracks in the file.
        definition_name: Name of the synthesis definition (for logging).

    Returns:
        Tuple of (should_create, reason).
    """
    if condition is None:
        return True, "no condition specified"

    result, reason = evaluate_condition(condition, tracks)
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
) -> SynthesisOperation | SkippedSynthesis:
    """Resolve a single synthesis definition to an operation or skip record.

    Args:
        definition: The synthesis track definition.
        all_tracks: All tracks in the file.
        commentary_patterns: Patterns to identify commentary tracks.
        existing_operations: Already-planned operations (for position calculation).

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
) -> SynthesisPlan:
    """Generate a complete synthesis plan for a file.

    Args:
        file_id: UUID of the file.
        file_path: Path to the media file.
        tracks: All tracks in the file.
        synthesis_config: Audio synthesis configuration from policy.
        commentary_patterns: Patterns to identify commentary tracks.

    Returns:
        Complete SynthesisPlan with operations and skipped tracks.
    """
    operations: list[SynthesisOperation] = []
    skipped: list[SkippedSynthesis] = []

    audio_tracks = filter_audio_tracks(tracks)

    for ref in synthesis_config.tracks:
        definition = _convert_ref_to_definition(ref)

        result = resolve_synthesis_operation(
            definition,
            tracks,
            commentary_patterns,
            operations,
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
    )
