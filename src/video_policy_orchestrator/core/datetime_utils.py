"""UTC datetime utilities.

This module provides utility functions for parsing and formatting datetime values.
All datetime operations follow the project's constitution: UTC storage, ISO-8601 format.
"""

from datetime import datetime, timezone


def parse_iso_timestamp(timestamp: str) -> datetime:
    """Parse ISO-8601 timestamp, handling both Z and +00:00 suffixes.

    Args:
        timestamp: ISO-8601 timestamp string (e.g., "2024-01-15T10:30:00Z").

    Returns:
        Timezone-aware datetime object.

    Note:
        Python 3.10 requires explicit +00:00 offset for fromisoformat(),
        so this function normalizes Z suffix to +00:00.
    """
    normalized = timestamp.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def calculate_duration_seconds(created_at: str, completed_at: str) -> int | None:
    """Calculate duration between two ISO timestamps.

    Args:
        created_at: Start timestamp (ISO-8601).
        completed_at: End timestamp (ISO-8601).

    Returns:
        Duration in seconds, or None if parsing fails.
    """
    try:
        created = parse_iso_timestamp(created_at)
        completed = parse_iso_timestamp(completed_at)
        return int((completed - created).total_seconds())
    except (ValueError, TypeError):
        return None


def mtime_to_utc_iso(mtime: float) -> str:
    """Convert file modification time to UTC ISO-8601 string.

    Args:
        mtime: File modification time as returned by os.stat().st_mtime.

    Returns:
        UTC ISO-8601 timestamp string.
    """
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
