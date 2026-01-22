"""Container conversion evaluation.

This module provides functions for evaluating container format changes,
including codec compatibility checking for MP4 conversion.
"""

from __future__ import annotations

from vpo.core.codecs import (
    BITMAP_SUBTITLE_CODECS,
    DEFAULT_AUDIO_TRANSCODE_TARGET,
    MP4_AUDIO_TRANSCODE_DEFAULTS,
    MP4_CONVERTIBLE_SUBTITLE_CODECS,
    is_codec_mp4_compatible,
)
from vpo.domain import TrackInfo
from vpo.policy.exceptions import IncompatibleCodecError
from vpo.policy.types import (
    CodecTranscodeMapping,
    ContainerChange,
    ContainerTranscodePlan,
    EvaluationPolicy,
    IncompatibleTrackPlan,
)


def normalize_container_format(container: str) -> str:
    """Normalize container format names.

    Handles common aliases from ffprobe output (e.g., 'matroska' -> 'mkv',
    'mov,mp4,m4a,3gp,3g2,mj2' -> 'mp4').

    Args:
        container: Container format string (from ffprobe or file extension).

    Returns:
        Normalized format name (lowercase, standardized).
    """
    container = container.casefold().strip()

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


def _create_incompatible_track_plan(
    track: TrackInfo,
    codec_mappings: dict[str, CodecTranscodeMapping] | None = None,
) -> IncompatibleTrackPlan:
    """Create a plan for handling an incompatible track.

    Determines the appropriate action (transcode, convert, or remove)
    based on the track type and codec. Custom codec_mappings override
    the default behavior.

    Args:
        track: Track metadata for the incompatible track.
        codec_mappings: Optional per-codec override mappings from policy.

    Returns:
        IncompatibleTrackPlan with the appropriate action.
    """
    codec = (track.codec or "").casefold().strip()
    track_type = track.track_type.casefold()

    # Check for custom mapping override first
    if codec_mappings and codec in codec_mappings:
        mapping = codec_mappings[codec]
        # Determine action: use explicit action or infer from track type
        if mapping.action is not None:
            action = mapping.action
        elif track_type == "audio":
            action = "transcode"
        elif track_type == "subtitle":
            if codec in BITMAP_SUBTITLE_CODECS:
                action = "remove"
            else:
                action = "convert"
        else:
            action = "transcode"

        # Build reason string based on action
        if action == "remove":
            reason = f"{codec} removed (custom mapping)"
        else:
            reason = f"{codec} -> {mapping.codec} (custom mapping)"

        return IncompatibleTrackPlan(
            track_index=track.index,
            track_type=track_type,
            source_codec=codec,
            action=action,
            target_codec=mapping.codec if action != "remove" else None,
            target_bitrate=mapping.bitrate if action == "transcode" else None,
            reason=reason,
        )

    # Fall back to default behavior
    if track_type == "audio":
        # Check if we have a known transcode mapping
        if codec in MP4_AUDIO_TRANSCODE_DEFAULTS:
            target = MP4_AUDIO_TRANSCODE_DEFAULTS[codec]
            return IncompatibleTrackPlan(
                track_index=track.index,
                track_type=track_type,
                source_codec=codec,
                action="transcode",
                target_codec=target.codec,
                target_bitrate=target.bitrate,
                reason=f"{codec} is not MP4-compatible, transcoding to {target.codec}",
            )
        else:
            # Unknown audio codec - use generic AAC transcode
            default_target = DEFAULT_AUDIO_TRANSCODE_TARGET
            reason = (
                f"{codec} is not MP4-compatible, transcoding to {default_target.codec}"
            )
            return IncompatibleTrackPlan(
                track_index=track.index,
                track_type=track_type,
                source_codec=codec,
                action="transcode",
                target_codec=default_target.codec,
                target_bitrate=default_target.bitrate,
                reason=reason,
            )

    elif track_type == "subtitle":
        if codec in MP4_CONVERTIBLE_SUBTITLE_CODECS:
            # Text subtitles can be converted to mov_text
            return IncompatibleTrackPlan(
                track_index=track.index,
                track_type=track_type,
                source_codec=codec,
                action="convert",
                target_codec="mov_text",
                reason=f"Converting {codec} to mov_text (styling may be lost)",
            )
        elif codec in BITMAP_SUBTITLE_CODECS:
            # Bitmap subtitles must be removed
            return IncompatibleTrackPlan(
                track_index=track.index,
                track_type=track_type,
                source_codec=codec,
                action="remove",
                reason=f"Removing {codec} (bitmap subtitles cannot be converted)",
            )
        else:
            # Unknown subtitle codec - try removal
            return IncompatibleTrackPlan(
                track_index=track.index,
                track_type=track_type,
                source_codec=codec,
                action="remove",
                reason=f"Removing {codec} (unknown subtitle format)",
            )

    # For video or other track types, remove the track since we cannot
    # auto-transcode video (requires explicit transcode phase configuration).
    # Video incompatibility is rare since most codecs are MP4-supported.
    return IncompatibleTrackPlan(
        track_index=track.index,
        track_type=track_type,
        source_codec=codec,
        action="remove",
        target_codec=None,
        reason=f"{codec} is not MP4-compatible; track will be removed",
    )


def _evaluate_container_change(
    tracks: list[TrackInfo],
    source_format: str,
    policy: EvaluationPolicy,
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

    target = policy.container.target.casefold()
    source = normalize_container_format(source_format)

    # Skip if already in target format
    if source == target:
        return None

    warnings: list[str] = []
    incompatible_tracks: list[int] = []

    # Check codec compatibility for MP4 target
    if target == "mp4":
        for track in tracks:
            codec = (track.codec or "").casefold()
            track_type = track.track_type.casefold()

            if not is_codec_mp4_compatible(codec, track_type):
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


def evaluate_container_change_with_policy(
    tracks: list[TrackInfo],
    source_format: str,
    policy: EvaluationPolicy,
) -> ContainerChange | None:
    """Evaluate container change with policy error handling.

    This function applies the policy's on_incompatible_codec setting
    to determine whether to raise an error, skip conversion, or transcode.

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
        elif mode == "transcode":
            # Create transcode plan for incompatible tracks
            track_plans: list[IncompatibleTrackPlan] = []
            warnings: list[str] = []
            codec_mappings = policy.container.codec_mappings

            for idx in change.incompatible_tracks:
                track = next(t for t in tracks if t.index == idx)
                plan = _create_incompatible_track_plan(track, codec_mappings)
                track_plans.append(plan)

                # Add warnings for removed tracks and conversions that lose data
                if plan.action == "remove":
                    warnings.append(
                        f"Track {idx} ({plan.source_codec}) will be removed"
                    )
                elif plan.action == "convert" and plan.source_codec in ("ass", "ssa"):
                    warnings.append(
                        f"Track {idx} ({plan.source_codec}) will lose styling "
                        f"when converted to mov_text"
                    )

            transcode_plan = ContainerTranscodePlan(
                track_plans=tuple(track_plans),
                warnings=tuple(warnings),
            )

            # Return updated ContainerChange with transcode plan
            return ContainerChange(
                source_format=change.source_format,
                target_format=change.target_format,
                warnings=change.warnings + transcode_plan.warnings,
                incompatible_tracks=change.incompatible_tracks,
                transcode_plan=transcode_plan,
            )

    return change
