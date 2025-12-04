"""Pure parsing functions for ffprobe JSON output.

These functions transform ffprobe JSON data into VPO domain objects.
All functions are pure (no I/O, no side effects) for easy testing.
"""

from pathlib import Path

from video_policy_orchestrator.db.types import IntrospectionResult, TrackInfo
from video_policy_orchestrator.introspector.mappings import (
    map_channel_layout,
    map_track_type,
)
from video_policy_orchestrator.language import normalize_language


def sanitize_string(value: str | None) -> str | None:
    """Sanitize a string by replacing invalid UTF-8 characters.

    Args:
        value: String value to sanitize.

    Returns:
        Sanitized string or None if input was None.
    """
    if value is None:
        return None
    # Replace any remaining problematic characters
    return value.encode("utf-8", errors="replace").decode("utf-8")


def parse_duration(value: str | None) -> float | None:
    """Parse duration string from ffprobe into seconds.

    Args:
        value: Duration string from ffprobe (e.g., "3600.000") or None.

    Returns:
        Duration in seconds as float, or None if parsing fails.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_stream(
    stream: dict,
    container_duration: float | None = None,
    file_path: str | None = None,
) -> TrackInfo:
    """Parse a single ffprobe stream dict into a TrackInfo.

    Args:
        stream: Stream dictionary from ffprobe JSON.
        container_duration: Fallback duration from container format.
        file_path: Optional file path for context in warning messages.

    Returns:
        TrackInfo domain object.
    """
    index = stream.get("index", 0)
    codec_type = stream.get("codec_type", "")
    track_type = map_track_type(codec_type)

    # Get disposition flags
    disposition = stream.get("disposition", {})
    is_default = disposition.get("default", 0) == 1
    is_forced = disposition.get("forced", 0) == 1

    # Get tags (sanitize strings to handle non-UTF8 characters)
    tags = stream.get("tags", {})
    raw_language = tags.get("language") or "und"
    # Normalize language code to configured standard (default: ISO 639-2/B)
    language = normalize_language(raw_language, context=file_path)
    title = sanitize_string(tags.get("title"))

    # Build track info
    track = TrackInfo(
        index=index,
        track_type=track_type,
        codec=stream.get("codec_name"),
        language=language,
        title=title,
        is_default=is_default,
        is_forced=is_forced,
    )

    # Extract stream duration (fall back to container duration)
    stream_duration = parse_duration(stream.get("duration"))
    if stream_duration is not None:
        track.duration_seconds = stream_duration
    elif container_duration is not None:
        track.duration_seconds = container_duration

    # Add audio-specific fields
    if track_type == "audio":
        channels = stream.get("channels")
        if channels is not None:
            track.channels = channels
            track.channel_layout = map_channel_layout(channels)

    # Add video-specific fields
    if track_type == "video":
        width = stream.get("width")
        height = stream.get("height")
        if width is not None:
            track.width = width
        if height is not None:
            track.height = height
        # Get frame rate (prefer r_frame_rate, fallback to avg_frame_rate)
        frame_rate = stream.get("r_frame_rate") or stream.get("avg_frame_rate")
        if frame_rate and frame_rate != "0/0":
            track.frame_rate = frame_rate
        # Extract HDR color metadata
        color_transfer = stream.get("color_transfer")
        if color_transfer:
            track.color_transfer = color_transfer
        color_primaries = stream.get("color_primaries")
        if color_primaries:
            track.color_primaries = color_primaries
        color_space = stream.get("color_space")
        if color_space:
            track.color_space = color_space
        color_range = stream.get("color_range")
        if color_range:
            track.color_range = color_range

    return track


def parse_streams(
    streams: list[dict],
    container_duration: float | None = None,
    file_path: str | None = None,
) -> tuple[list[TrackInfo], list[str]]:
    """Parse stream data into TrackInfo objects.

    Args:
        streams: List of stream dictionaries from ffprobe.
        container_duration: Container-level duration as fallback.
        file_path: Optional file path for context in warning messages.

    Returns:
        Tuple of (tracks list, warnings list).
    """
    tracks: list[TrackInfo] = []
    warnings: list[str] = []
    seen_indices: set[int] = set()

    for stream in streams:
        index = stream.get("index", 0)

        # Check for duplicate indices
        if index in seen_indices:
            warnings.append(f"Duplicate stream index {index}, skipping")
            continue
        seen_indices.add(index)

        track = parse_stream(stream, container_duration, file_path)
        tracks.append(track)

    return tracks, warnings


def parse_ffprobe_output(
    path: Path,
    data: dict,
) -> IntrospectionResult:
    """Parse ffprobe JSON output into IntrospectionResult.

    Args:
        path: Path to the video file.
        data: Parsed ffprobe JSON output.

    Returns:
        IntrospectionResult with tracks and warnings.
    """
    # Extract container format and duration
    format_info = data.get("format", {})
    container_format = format_info.get("format_name")
    # Container duration (used as fallback for streams without duration)
    container_duration = parse_duration(format_info.get("duration"))

    # Parse streams
    streams = data.get("streams", [])
    tracks, warnings = parse_streams(streams, container_duration, str(path))

    if not tracks:
        warnings.append("No streams found in file")

    return IntrospectionResult(
        file_path=path,
        container_format=container_format,
        tracks=tracks,
        warnings=warnings,
    )
