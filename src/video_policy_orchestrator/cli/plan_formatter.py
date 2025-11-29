"""Plan output formatting for dry-run mode.

This module provides functions to format Plan objects for human-readable
or JSON output. These formatters are used by the process command to show
detailed information about what changes would be made.
"""

from enum import Enum, auto
from typing import Any

from video_policy_orchestrator.policy.models import (
    Plan,
    PlannedAction,
    TrackDisposition,
)


class OutputStyle(Enum):
    """Output verbosity/style options."""

    NORMAL = auto()  # Summary + bulleted changes
    VERBOSE = auto()  # Full BEFORE/AFTER tables


def format_plan_human(plan: Plan, style: OutputStyle = OutputStyle.NORMAL) -> str:
    """Format plan for human-readable output.

    Args:
        plan: The plan to format.
        style: Output style (NORMAL or VERBOSE).

    Returns:
        Formatted string for terminal output.
    """
    if plan.is_empty:
        return "No changes required - file already matches policy"

    if style == OutputStyle.VERBOSE:
        return _format_verbose(plan)
    return _format_normal(plan)


def format_plan_json(plan: Plan) -> dict[str, Any]:
    """Format plan for JSON output.

    Args:
        plan: The plan to format.

    Returns:
        JSON-serializable dictionary.
    """
    return {
        "summary": plan.summary,
        "requires_remux": plan.requires_remux,
        "tracks_kept": plan.tracks_kept,
        "tracks_removed": plan.tracks_removed,
        "is_empty": plan.is_empty,
        "actions": [_action_to_dict(a) for a in plan.actions],
        "track_dispositions": [
            _disposition_to_dict(d) for d in plan.track_dispositions
        ],
        "container_change": _container_change_to_dict(plan.container_change),
    }


# =============================================================================
# Normal Format (Summary + Bulleted Changes)
# =============================================================================


def _format_normal(plan: Plan) -> str:
    """Format with summary and bulleted list of changes."""
    lines: list[str] = []

    # Summary line
    lines.append(f"Plan: {plan.summary}")
    lines.append("")

    # Actions (metadata changes)
    if plan.actions:
        lines.append("Actions:")
        for action in plan.actions:
            lines.append(f"  - {action.description}")
        lines.append("")

    # Track removals
    removed = [d for d in plan.track_dispositions if d.action == "REMOVE"]
    if removed:
        lines.append("Track Removals:")
        for disp in removed:
            track_desc = _format_track_brief(disp)
            lines.append(f"  - {track_desc} - {disp.reason}")
        lines.append("")

    # Container change
    if plan.container_change:
        cc = plan.container_change
        lines.append(
            f"Container: {cc.source_format.upper()} -> {cc.target_format.upper()}"
        )
        for warning in cc.warnings:
            lines.append(f"  Warning: {warning}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_track_brief(disp: TrackDisposition) -> str:
    """Format a track disposition as a brief description."""
    parts = [f"Track {disp.track_index} ({disp.track_type}"]

    if disp.codec:
        parts.append(f", {disp.codec}")
    if disp.language:
        parts.append(f", {disp.language}")

    parts.append(")")
    return "".join(parts)


# =============================================================================
# Verbose Format (BEFORE/AFTER Tables)
# =============================================================================


def _format_verbose(plan: Plan) -> str:
    """Format with full BEFORE/AFTER tables."""
    lines: list[str] = []

    # Summary line
    lines.append(f"Plan: {plan.summary}")
    lines.append("")

    if plan.track_dispositions:
        # Find REORDER action if present
        reorder_action = None
        for action in plan.actions:
            if action.action_type.value == "reorder":
                reorder_action = action
                break

        # Compute final track order
        final_order = _compute_final_track_order(
            plan.track_dispositions, reorder_action
        )

        # Build index mapping
        new_index_map = {t.track_index: i for i, t in enumerate(final_order)}

        # BEFORE table
        lines.append("BEFORE:")
        before_rows = _build_before_rows(plan.track_dispositions, new_index_map)
        before_headers = (
            "TRACK",
            "TYPE",
            "CODEC",
            "LANG",
            "DETAILS",
            "TITLE",
            "ACTION",
            "AFTER",
        )
        lines.extend(
            _format_table(
                headers=before_headers,
                rows=before_rows,
                indent=2,
            )
        )
        lines.append("")

        # AFTER table
        lines.append("AFTER:")
        after_rows = _build_after_rows(final_order)
        lines.extend(
            _format_table(
                headers=("TRACK", "TYPE", "CODEC", "LANG", "DETAILS", "TITLE"),
                rows=after_rows,
                indent=2,
            )
        )
        lines.append("")

        # Summary
        removed_tracks = [d for d in plan.track_dispositions if d.action != "KEEP"]
        if removed_tracks:
            removed_by_type: dict[str, int] = {}
            for t in removed_tracks:
                removed_by_type[t.track_type] = removed_by_type.get(t.track_type, 0) + 1
            removed_summary = ", ".join(
                f"{count} {ttype}" for ttype, count in sorted(removed_by_type.items())
            )
            lines.append(
                f"Summary: {len(final_order)} kept, "
                f"{len(removed_tracks)} removed ({removed_summary})"
            )
        else:
            lines.append(f"Summary: {len(final_order)} tracks (no removals)")

    # Container change
    if plan.container_change:
        lines.append("")
        cc = plan.container_change
        lines.append(
            f"Container: {cc.source_format.upper()} -> {cc.target_format.upper()}"
        )
        for warning in cc.warnings:
            lines.append(f"  Warning: {warning}")

    return "\n".join(lines).rstrip()


def _compute_final_track_order(
    dispositions: tuple[TrackDisposition, ...],
    reorder_action: PlannedAction | None,
) -> list[TrackDisposition]:
    """Compute final track order after policy application."""
    # Get kept tracks
    kept_indices = {d.track_index for d in dispositions if d.action == "KEEP"}
    disp_by_index = {d.track_index: d for d in dispositions}

    if reorder_action and reorder_action.desired_value:
        # Use the desired order from REORDER action
        desired_order = reorder_action.desired_value
        ordered = []
        for idx in desired_order:
            if idx in kept_indices and idx in disp_by_index:
                ordered.append(disp_by_index[idx])
        return ordered

    # No REORDER action - use standard type-based ordering
    type_order = {"video": 0, "audio": 1, "subtitle": 2, "attachment": 3}
    kept_disps = [d for d in dispositions if d.action == "KEEP"]
    return sorted(
        kept_disps,
        key=lambda d: (type_order.get(d.track_type, 99), d.track_index),
    )


def _build_before_rows(
    dispositions: tuple[TrackDisposition, ...],
    new_index_map: dict[int, int],
) -> list[tuple[str, ...]]:
    """Build rows for BEFORE table."""
    type_abbrev = {"video": "V", "audio": "A", "subtitle": "S", "attachment": "X"}
    rows: list[tuple[str, ...]] = []

    for disp in sorted(dispositions, key=lambda d: d.track_index):
        track_id = f"[T:{disp.track_index}]"
        track_type = type_abbrev.get(disp.track_type, "?")
        codec = (disp.codec or "").upper()
        lang = disp.language or ""
        details = _get_track_details(disp)
        title = _truncate(disp.title or "", 20)
        action = "KEEP" if disp.action == "KEEP" else "DELETE"
        if disp.action == "KEEP":
            after = f"[T:{new_index_map[disp.track_index]}]"
        else:
            after = "-"

        rows.append((track_id, track_type, codec, lang, details, title, action, after))

    return rows


def _build_after_rows(final_order: list[TrackDisposition]) -> list[tuple[str, ...]]:
    """Build rows for AFTER table."""
    type_abbrev = {"video": "V", "audio": "A", "subtitle": "S", "attachment": "X"}
    rows: list[tuple[str, ...]] = []

    for i, disp in enumerate(final_order):
        track_id = f"[T:{i}]"
        track_type = type_abbrev.get(disp.track_type, "?")
        codec = (disp.codec or "").upper()
        lang = disp.language or ""
        details = _get_track_details(disp)
        title = _truncate(disp.title or "", 20)

        rows.append((track_id, track_type, codec, lang, details, title))

    return rows


def _get_track_details(disp: TrackDisposition) -> str:
    """Get details column for a track (resolution or channel layout)."""
    if disp.track_type == "video" and disp.resolution:
        return disp.resolution
    if disp.track_type == "audio" and disp.channels:
        return _channels_to_layout(disp.channels)
    return ""


def _channels_to_layout(channels: int) -> str:
    """Convert channel count to layout description."""
    layouts = {1: "mono", 2: "stereo", 6: "5.1", 8: "7.1"}
    return layouts.get(channels, f"{channels}ch")


def _truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis if too long."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _format_table(
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
    indent: int = 0,
) -> list[str]:
    """Format a table with headers and rows."""
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    # Format lines
    prefix = " " * indent
    lines: list[str] = []

    # Header
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(f"{prefix}{header_line}")

    # Separator
    sep = "  ".join("-" * w for w in widths)
    lines.append(f"{prefix}{sep}")

    # Rows
    for row in rows:
        row_line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        lines.append(f"{prefix}{row_line}")

    return lines


# =============================================================================
# JSON Helpers
# =============================================================================


def _action_to_dict(action: PlannedAction) -> dict[str, Any]:
    """Convert PlannedAction to JSON-serializable dict."""
    return {
        "action_type": action.action_type.value.upper(),
        "track_index": action.track_index,
        "current_value": _serialize_value(action.current_value),
        "desired_value": _serialize_value(action.desired_value),
        "description": action.description,
    }


def _disposition_to_dict(disp: TrackDisposition) -> dict[str, Any]:
    """Convert TrackDisposition to JSON-serializable dict."""
    return {
        "track_index": disp.track_index,
        "track_type": disp.track_type,
        "codec": disp.codec,
        "language": disp.language,
        "title": disp.title,
        "channels": disp.channels,
        "resolution": disp.resolution,
        "action": disp.action,
        "reason": disp.reason,
    }


def _container_change_to_dict(cc) -> dict[str, Any] | None:
    """Convert ContainerChange to JSON-serializable dict."""
    if cc is None:
        return None
    return {
        "source_format": cc.source_format,
        "target_format": cc.target_format,
        "warnings": list(cc.warnings),
        "incompatible_tracks": list(cc.incompatible_tracks),
    }


def _serialize_value(value: Any) -> Any:
    """Serialize a value for JSON output."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return value
