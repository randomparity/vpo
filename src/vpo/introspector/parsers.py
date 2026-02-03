"""Pure parsing functions for ffprobe JSON output.

These functions transform ffprobe JSON data into VPO domain objects.
All functions are pure (no I/O, no side effects) for easy testing.
"""

import logging
from pathlib import Path

from vpo.db.types import IntrospectionResult, TrackInfo
from vpo.introspector.mappings import (
    map_channel_layout,
    map_track_type,
)
from vpo.language import normalize_language

logger = logging.getLogger(__name__)


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


def _log_validation_warning(
    message: str,
    field_name: str,
    file_path: str | None,
    *args: object,
) -> None:
    """Log a validation warning with optional file context."""
    context = f" in {file_path}" if file_path else ""
    logger.warning(f"{message}{context}", field_name, *args)


def validate_positive_int(
    value: int | None,
    field_name: str,
    file_path: str | None = None,
) -> int | None:
    """Validate that a value is a positive integer or None.

    Args:
        value: Value to validate.
        field_name: Field name for warning messages.
        file_path: File path context for warnings.

    Returns:
        Validated value or None if invalid.
    """
    if value is None:
        return None
    if not isinstance(value, int):
        _log_validation_warning(
            "Expected int for %s, got %s", field_name, file_path, type(value).__name__
        )
        return None
    if value < 0:
        _log_validation_warning("Invalid negative %s: %d", field_name, file_path, value)
        return None
    return value


def validate_positive_float(
    value: float | None,
    field_name: str,
    file_path: str | None = None,
) -> float | None:
    """Validate that a value is a positive float or None.

    Args:
        value: Value to validate.
        field_name: Field name for warning messages.
        file_path: File path context for warnings.

    Returns:
        Validated value or None if invalid.
    """
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        _log_validation_warning(
            "Expected float for %s, got %s", field_name, file_path, type(value).__name__
        )
        return None
    if value < 0:
        _log_validation_warning("Invalid negative %s: %s", field_name, file_path, value)
        return None
    return float(value)


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
    validated_duration = validate_positive_float(
        stream_duration, "duration_seconds", file_path
    )
    if validated_duration is not None:
        track.duration_seconds = validated_duration
    elif container_duration is not None:
        track.duration_seconds = container_duration

    # Add audio-specific fields
    if track_type == "audio":
        channels = validate_positive_int(stream.get("channels"), "channels", file_path)
        if channels is not None:
            track.channels = channels
            track.channel_layout = map_channel_layout(channels)

    # Add video-specific fields
    if track_type == "video":
        width = validate_positive_int(stream.get("width"), "width", file_path)
        height = validate_positive_int(stream.get("height"), "height", file_path)
        if width is not None:
            track.width = width
        if height is not None:
            track.height = height
        # Get frame rate (prefer r_frame_rate, fallback to avg_frame_rate)
        frame_rate = stream.get("r_frame_rate") or stream.get("avg_frame_rate")
        if frame_rate and frame_rate != "0/0":
            track.frame_rate = frame_rate
        # Extract HDR color metadata
        for field in (
            "color_transfer",
            "color_primaries",
            "color_space",
            "color_range",
        ):
            if value := stream.get(field):
                setattr(track, field, value)

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


_MAX_TAG_KEY_LENGTH = 255
_MAX_TAG_VALUE_LENGTH = 4096


def _parse_container_tags(
    tags: dict,
    file_path: str | None = None,
) -> dict[str, str] | None:
    """Parse and sanitize container-level metadata tags.

    Args:
        tags: Raw tags dict from ffprobe format.tags.
        file_path: Optional file path for context in warning messages.

    Returns:
        Dict of lowercase key → sanitized string value, or None if no tags.
    """
    if not tags:
        return None

    result: dict[str, str] = {}
    for key, value in tags.items():
        if len(key) > _MAX_TAG_KEY_LENGTH:
            logger.warning(
                "Container tag key %r (%d chars) exceeds max length %d, skipping in %s",
                key[:50] + "...",
                len(key),
                _MAX_TAG_KEY_LENGTH,
                file_path or "unknown",
            )
            continue
        if not isinstance(value, str):
            logger.debug(
                "Container tag %r has non-string value of type %s, "
                "coercing to string in %s",
                key,
                type(value).__name__,
                file_path or "unknown",
            )
            value = str(value)
        sanitized = sanitize_string(value)
        if sanitized is None:
            continue
        if len(sanitized) > _MAX_TAG_VALUE_LENGTH:
            logger.warning(
                "Container tag %r value (%d chars) exceeds max length %d, "
                "skipping in %s",
                key,
                len(sanitized),
                _MAX_TAG_VALUE_LENGTH,
                file_path or "unknown",
            )
            continue
        result[key.casefold()] = sanitized

    return result if result else None


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

    # Extract container-level metadata tags
    container_tags = _parse_container_tags(format_info.get("tags", {}), str(path))

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
        container_tags=container_tags,
    )
