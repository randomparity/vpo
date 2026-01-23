"""Output formatting utilities for reports."""

import csv
import io
import json
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any

from vpo.core.formatting import format_file_size


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


def format_size_change(size_before: int | None, size_after: int | None) -> str:
    """Format size change with human-readable size and percentage.

    Args:
        size_before: File size in bytes before processing.
        size_after: File size in bytes after processing.

    Returns:
        Formatted string like "-1.2 GB (48%)" for reduction,
        "+500 MB (12%)" for increase, "0 B (0%)" for no change,
        or "N/A" if either value is None.
    """
    if size_before is None or size_after is None:
        return "N/A"

    if size_before == 0:
        # Avoid division by zero
        if size_after == 0:
            return "0 B (0%)"
        return f"+{format_file_size(size_after)} (N/A)"

    change = size_after - size_before
    percent = abs(change) / size_before * 100

    if change < 0:
        # Size reduction (positive outcome for transcoding)
        return f"-{format_file_size(abs(change))} ({percent:.0f}%)"
    elif change > 0:
        # Size increase
        return f"+{format_file_size(change)} ({percent:.0f}%)"
    else:
        return "0 B (0%)"


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


def _atomic_write_text(path: Path, content: str) -> None:
    """Write content to file atomically using temp file + rename.

    Creates a temp file in the same directory as the target, writes content,
    then atomically replaces the target. This ensures the file is never
    left in a partial state if the process crashes during write.

    Args:
        path: Target file path.
        content: Content to write.

    Raises:
        OSError: If write or rename fails.
        PermissionError: If permission denied.
    """
    # Create temp file in same directory (ensures same filesystem for atomic rename)
    fd, temp_path_str = tempfile.mkstemp(
        suffix=path.suffix,
        dir=path.parent,
        text=True,
    )
    temp_path = Path(temp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        temp_path.replace(path)  # Atomic on POSIX
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def write_report_to_file(
    content: str,
    output_path: Path,
    force: bool = False,
) -> None:
    """Write report content to file with overwrite protection.

    Uses atomic write (temp file + rename) to prevent corrupted partial
    files if the process crashes during write.

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

    # Write atomically using temp file + rename
    _atomic_write_text(output_path, content)
