"""Log formatting utilities for enhanced workflow logging.

This module provides functions to format detailed phase execution information
for CLI output and job logs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vpo.core.formatting import format_file_size

if TYPE_CHECKING:
    from vpo.policy.types import ContainerChange, PhaseResult, TrackDisposition


def format_phase_details(pr: PhaseResult) -> list[str]:
    """Format detailed transformation information for a phase result.

    Args:
        pr: PhaseResult containing execution details.

    Returns:
        List of formatted detail lines (without leading indent).

    Example output lines:
        - "Container: avi -> mkv"
        - "Audio removed (2):"
        - "  - Track 2: fra (ac3, 6ch)"
        - "Video: h264 -> hevc"
        - "Size: 8.2 GB -> 4.1 GB (-50.0%)"
    """
    lines: list[str] = []

    # Container conversion
    if pr.container_change:
        lines.extend(_format_container_change(pr.container_change))

    # Track dispositions (grouped by type)
    if pr.track_dispositions:
        lines.extend(_format_track_dispositions(pr.track_dispositions))

    # Track reordering
    if pr.track_order_change:
        lines.extend(_format_track_order(pr.track_order_change))

    # Audio synthesis
    if pr.audio_synthesis_created:
        lines.extend(_format_audio_synthesis(pr.audio_synthesis_created))

    # Transcription results
    if pr.transcription_results:
        lines.extend(_format_transcription_results(pr.transcription_results))

    # Operation failures (when on_error=continue/skip)
    if pr.operation_failures:
        lines.extend(_format_operation_failures(pr.operation_failures))

    # Transcode results
    if pr.size_before is not None and pr.size_after is not None:
        lines.extend(
            _format_transcode_result(
                pr.size_before,
                pr.size_after,
                pr.encoder_type,
                pr.encoding_fps,
                pr.video_source_codec,
                pr.video_target_codec,
            )
        )
    elif pr.transcode_skip_reason:
        lines.append(f"Transcode skipped: {pr.transcode_skip_reason}")

    return lines


def _format_container_change(cc: ContainerChange) -> list[str]:
    """Format container conversion details.

    Args:
        cc: ContainerChange with source and target formats.

    Returns:
        List of formatted lines.
    """
    if cc.source_format == cc.target_format:
        lines = [f"Container: {cc.source_format} (no change)"]
    else:
        lines = [f"Container: {cc.source_format} -> {cc.target_format}"]

    # Add warnings if any
    for warning in cc.warnings:
        lines.append(f"  Warning: {warning}")

    return lines


def _format_track_dispositions(dispositions: tuple[TrackDisposition, ...]) -> list[str]:
    """Format track removal/retention information grouped by type.

    Args:
        dispositions: Tuple of TrackDisposition records.

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []

    # Group removed tracks by type
    removed_by_type: dict[str, list[TrackDisposition]] = {}
    for td in dispositions:
        if td.action == "REMOVE":
            removed_by_type.setdefault(td.track_type, []).append(td)

    # Format each track type's removals
    for track_type in ["video", "audio", "subtitle", "attachment"]:
        removed = removed_by_type.get(track_type, [])
        if not removed:
            continue

        type_label = track_type.capitalize()
        lines.append(f"{type_label} removed ({len(removed)}):")

        for td in removed:
            # Build track description parts (metadata comes after colon)
            parts: list[str] = []

            if td.language:
                parts.append(td.language)

            # Codec and channels for audio
            if td.codec:
                if td.channels:
                    parts.append(f"({td.codec}, {td.channels}ch)")
                else:
                    parts.append(f"({td.codec})")

            # Title if present
            if td.title:
                parts.append(f'"{td.title}"')

            # Build track description - only add colon if there's content after it
            track_desc = f"Track {td.track_index}"
            if parts:
                track_desc += ": " + " ".join(parts)
            lines.append("  - " + track_desc)

    return lines


def _format_track_order(
    order_change: tuple[tuple[int, ...], tuple[int, ...]],
) -> list[str]:
    """Format track reordering information.

    Args:
        order_change: Tuple of (before_indices, after_indices).

    Returns:
        List of formatted lines.
    """
    before, after = order_change
    if before == after:
        return []

    before_str = ", ".join(str(i) for i in before)
    after_str = ", ".join(str(i) for i in after)
    return [f"Track order: [{before_str}] -> [{after_str}]"]


def _format_audio_synthesis(tracks_created: tuple[str, ...]) -> list[str]:
    """Format audio synthesis track creation info.

    Args:
        tracks_created: Tuple of track descriptions.

    Returns:
        List of formatted lines.
    """
    if not tracks_created:
        return []

    lines = [f"Audio synthesized ({len(tracks_created)}):"]
    for desc in tracks_created:
        lines.append(f"  - {desc}")
    return lines


def _format_transcription_results(
    results: tuple[tuple[int, str | None, float, str], ...],
) -> list[str]:
    """Format transcription analysis results.

    Args:
        results: Tuple of (track_index, language, confidence, track_type).

    Returns:
        List of formatted lines.
    """
    if not results:
        return []

    lines = [f"Transcription analyzed ({len(results)}):"]
    for track_idx, lang, confidence, track_type in results:
        pct = int(confidence * 100)
        lang_str = lang if lang else "unknown"
        lines.append(f"  - Track {track_idx}: {lang_str} ({track_type}, {pct}%)")
    return lines


def _format_operation_failures(
    failures: tuple[tuple[str, str], ...],
) -> list[str]:
    """Format operation failures.

    Args:
        failures: Tuple of (operation_name, error_message).

    Returns:
        List of formatted lines.
    """
    if not failures:
        return []

    lines = [f"Failures ({len(failures)}):"]
    for op_name, error_msg in failures:
        # Truncate long error messages
        if len(error_msg) > 80:
            error_msg = error_msg[:77] + "..."
        lines.append(f"  - {op_name}: {error_msg}")
    return lines


def _format_transcode_result(
    size_before: int,
    size_after: int,
    encoder_type: str | None,
    encoding_fps: float | None,
    source_codec: str | None = None,
    target_codec: str | None = None,
) -> list[str]:
    """Format transcode size change, encoder type, and speed.

    Args:
        size_before: File size in bytes before transcode.
        size_after: File size in bytes after transcode.
        encoder_type: 'hardware', 'software', or None.
        encoding_fps: Average encoding speed in FPS.
        source_codec: Source video codec (e.g., 'h264').
        target_codec: Target video codec (e.g., 'hevc').

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []

    # Codec conversion (shown first)
    if source_codec and target_codec:
        lines.append(f"Video: {source_codec} -> {target_codec}")

    # Size change with percentage
    before_str = format_file_size(size_before)
    after_str = format_file_size(size_after)

    if size_before > 0:
        change_pct = ((size_after - size_before) / size_before) * 100
        sign = "+" if change_pct >= 0 else ""
        lines.append(f"Size: {before_str} -> {after_str} ({sign}{change_pct:.1f}%)")
    else:
        lines.append(f"Size: {before_str} -> {after_str}")

    # Encoder type
    if encoder_type:
        encoder_label = "hardware" if encoder_type == "hardware" else "software"
        lines.append(f"Encoder: {encoder_label}")

    # Encoding speed
    if encoding_fps is not None and encoding_fps > 0:
        lines.append(f"Speed: {encoding_fps:.1f} fps")

    return lines
