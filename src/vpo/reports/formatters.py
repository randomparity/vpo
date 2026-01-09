"""Output formatting utilities for reports."""

import csv
import io
import json
import os
from enum import Enum
from pathlib import Path
from typing import Any


class ReportFormat(Enum):
    """Supported output formats for reports."""

    TEXT = "text"
    CSV = "csv"
    JSON = "json"


def format_timestamp_local(utc_iso: str | None) -> str:
    """Convert UTC ISO timestamp to local time display.

    Args:
        utc_iso: ISO-8601 UTC timestamp string.

    Returns:
        Local time string formatted as "YYYY-MM-DD HH:MM:SS" or "-" if None.
    """
    if not utc_iso:
        return "-"

    from datetime import datetime, timezone

    try:
        # Handle Z suffix and various ISO formats
        normalized = utc_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)

        # If no timezone, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Convert to local time
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return utc_iso[:19] if len(utc_iso) >= 19 else utc_iso


def format_duration(seconds: float | None) -> str:
    """Format duration as human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Human-readable duration string or "-" if None.
    """
    if seconds is None:
        return "-"

    seconds = float(seconds)
    if seconds < 0:
        return "-"

    if seconds < 60:
        return f"{seconds:.0f}s"

    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"


def calculate_duration_seconds(
    started_at: str | None, completed_at: str | None
) -> float | None:
    """Calculate duration between two ISO timestamps.

    Args:
        started_at: Start timestamp in ISO-8601 format.
        completed_at: End timestamp in ISO-8601 format.

    Returns:
        Duration in seconds or None if either timestamp is missing.
    """
    if not started_at or not completed_at:
        return None

    from datetime import datetime, timezone

    try:
        start_normalized = started_at.replace("Z", "+00:00")
        end_normalized = completed_at.replace("Z", "+00:00")

        start_dt = datetime.fromisoformat(start_normalized)
        end_dt = datetime.fromisoformat(end_normalized)

        # Ensure timezone info
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        delta = end_dt - start_dt
        return delta.total_seconds()
    except (ValueError, TypeError):
        return None


def render_text_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str, int]],
) -> str:
    """Render rows as aligned text table.

    Args:
        rows: List of row dictionaries.
        columns: List of (header, key, width) tuples defining column layout.

    Returns:
        Formatted table string.
    """
    if not rows:
        return ""

    # Build header
    header_parts = []
    for header, _key, width in columns:
        header_parts.append(f"{header:<{width}}")
    header_line = " ".join(header_parts)

    # Get terminal width for separator
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        terminal_width = 120

    separator = "-" * min(len(header_line), terminal_width)

    # Build rows
    lines = [header_line, separator]
    for row in rows:
        row_parts = []
        for _header, key, width in columns:
            value = str(row.get(key, "-"))
            # Truncate long values
            if len(value) > width:
                value = value[: width - 3] + "..."
            row_parts.append(f"{value:<{width}}")
        lines.append(" ".join(row_parts))

    return "\n".join(lines)


def render_csv(
    rows: list[dict[str, Any]],
    columns: list[str],
) -> str:
    """Render rows as CSV with headers.

    Args:
        rows: List of row dictionaries.
        columns: List of column keys for CSV headers.

    Returns:
        CSV formatted string with headers.
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=columns,
        extrasaction="ignore",
    )
    writer.writeheader()

    for row in rows:
        # Ensure all values are serializable
        clean_row = {}
        for col in columns:
            value = row.get(col)
            if value is None:
                clean_row[col] = ""
            elif isinstance(value, bool):
                clean_row[col] = str(value).casefold()
            else:
                clean_row[col] = str(value)
        writer.writerow(clean_row)

    return output.getvalue()


def render_json(rows: list[dict[str, Any]]) -> str:
    """Render rows as JSON array.

    Args:
        rows: List of row dictionaries.

    Returns:
        JSON formatted string with stable key ordering.
    """
    return json.dumps(rows, indent=2, sort_keys=True, default=str)


def write_report_to_file(
    content: str,
    output_path: Path,
    force: bool = False,
) -> None:
    """Write report content to file with overwrite protection.

    Args:
        content: Report content to write.
        output_path: Target file path.
        force: If True, overwrite existing file.

    Raises:
        FileExistsError: If file exists and force is False.
        OSError: If write fails.
    """
    if output_path.exists() and not force:
        raise FileExistsError(f"File exists: {output_path}. Use --force to overwrite.")

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write with UTF-8 encoding
    output_path.write_text(content, encoding="utf-8")
