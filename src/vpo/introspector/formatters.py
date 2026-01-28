"""Formatters for introspection results.

This module provides functions to format IntrospectionResult and TrackInfo
objects for human-readable or JSON output. These formatters are shared
between the CLI and potentially other consumers (web UI, API).
"""

import json
from typing import Any

from vpo.db.types import IntrospectionResult, TrackInfo


def format_human(result: IntrospectionResult) -> str:
    """Format introspection result for human-readable output.

    Args:
        result: The introspection result to format.

    Returns:
        Formatted string for terminal output.
    """
    lines: list[str] = []

    # File info header
    lines.append(f"File: {result.file_path}")
    if result.container_format:
        # Make container format more readable
        container = result.container_format.split(",")[0].title()
        lines.append(f"Container: {container}")
    lines.append("")

    # Group tracks by type
    video_tracks = [t for t in result.tracks if t.track_type == "video"]
    audio_tracks = [t for t in result.tracks if t.track_type == "audio"]
    subtitle_tracks = [t for t in result.tracks if t.track_type == "subtitle"]
    other_tracks = [
        t for t in result.tracks if t.track_type not in ("video", "audio", "subtitle")
    ]

    lines.append("Tracks:")

    if video_tracks:
        lines.append("  Video:")
        for track in video_tracks:
            lines.append(f"    {format_track_line(track)}")

    if audio_tracks:
        lines.append("  Audio:")
        for track in audio_tracks:
            lines.append(f"    {format_track_line(track)}")

    if subtitle_tracks:
        lines.append("  Subtitles:")
        for track in subtitle_tracks:
            lines.append(f"    {format_track_line(track)}")

    if other_tracks:
        lines.append("  Other:")
        for track in other_tracks:
            lines.append(f"    {format_track_line(track)}")

    if not result.tracks:
        lines.append("  (no tracks found)")

    # Add warnings if any
    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines)


def format_track_line(track: TrackInfo) -> str:
    """Format a single track for human output.

    Args:
        track: The track to format.

    Returns:
        Formatted track line.
    """
    parts = [f"#{track.index}", f"[{track.track_type}]"]

    if track.codec:
        parts.append(track.codec)

    # Video-specific: resolution, frame rate, and HDR indicator
    if track.track_type == "video":
        if track.width and track.height:
            parts.append(f"{track.width}x{track.height}")
        if track.frame_rate:
            # Convert frame rate to decimal for display
            fps = frame_rate_to_fps(track.frame_rate)
            if fps:
                parts.append(f"@ {fps}fps")
        # HDR indicator based on color transfer function
        if track.color_transfer:
            hdr_transfers = {"smpte2084", "arib-std-b67"}  # PQ and HLG
            if track.color_transfer.casefold() in hdr_transfers:
                parts.append("[HDR]")

    # Audio-specific: channel layout and language
    if track.track_type == "audio":
        if track.channel_layout:
            parts.append(track.channel_layout)

    # Language (for audio/subtitle)
    if track.language and track.language != "und":
        parts.append(track.language)

    # Title in quotes
    if track.title:
        parts.append(f'"{track.title}"')

    # Flags
    flags = []
    if track.is_default:
        flags.append("default")
    if track.is_forced:
        flags.append("forced")
    if flags:
        parts.append(f"({', '.join(flags)})")

    return " ".join(parts)


def frame_rate_to_fps(frame_rate: str) -> str | None:
    """Convert frame rate string to decimal FPS.

    Args:
        frame_rate: Frame rate as "N/D" or decimal string.

    Returns:
        Formatted FPS string or None if invalid.
    """
    try:
        if "/" in frame_rate:
            num, denom = frame_rate.split("/")
            fps = int(num) / int(denom)
        else:
            fps = float(frame_rate)

        # Format nicely (e.g., 23.976 or 30)
        if fps == int(fps):
            return str(int(fps))
        return f"{fps:.3f}".rstrip("0").rstrip(".")
    except (ValueError, ZeroDivisionError):
        return None


def format_json(result: IntrospectionResult) -> str:
    """Format introspection result as JSON.

    Args:
        result: The introspection result to format.

    Returns:
        JSON string.
    """
    data = {
        "file": str(result.file_path),
        "container": result.container_format,
        "duration_seconds": result.duration_seconds,
        "tracks": [track_to_dict(t) for t in result.tracks],
        "warnings": result.warnings,
    }
    return json.dumps(data, indent=2)


def track_to_dict(track: TrackInfo) -> dict[str, Any]:
    """Convert TrackInfo to JSON-serializable dict.

    Args:
        track: The track to convert.

    Returns:
        Dictionary representation.
    """
    d: dict[str, Any] = {
        "index": track.index,
        "type": track.track_type,
        "codec": track.codec,
        "language": track.language,
        "title": track.title,
        "is_default": track.is_default,
        "is_forced": track.is_forced,
    }

    # Add optional fields if present (video, audio, and duration)
    optional_fields = (
        "width",
        "height",
        "frame_rate",
        "color_transfer",
        "color_primaries",
        "color_space",
        "color_range",
        "channels",
        "channel_layout",
        "duration_seconds",
    )
    for field in optional_fields:
        if (value := getattr(track, field, None)) is not None:
            d[field] = value

    return d
