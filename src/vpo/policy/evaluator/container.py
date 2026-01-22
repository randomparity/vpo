"""Container conversion evaluation.

This module provides functions for evaluating container format changes,
including codec compatibility checking for MP4 conversion.
"""

from __future__ import annotations

from vpo.domain import TrackInfo
from vpo.policy.exceptions import IncompatibleCodecError
from vpo.policy.types import (
    ContainerChange,
    EvaluationPolicy,
)

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


def _is_codec_mp4_compatible(codec: str, track_type: str) -> bool:
    """Check if a codec is compatible with MP4 container.

    Args:
        codec: Codec name (e.g., 'hevc', 'truehd').
        track_type: Track type ('video', 'audio', 'subtitle').

    Returns:
        True if codec is compatible with MP4.
    """
    codec = codec.casefold().strip()

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


def evaluate_container_change_with_policy(
    tracks: list[TrackInfo],
    source_format: str,
    policy: EvaluationPolicy,
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
