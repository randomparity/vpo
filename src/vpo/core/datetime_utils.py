"""UTC datetime utilities.

This module provides utility functions for parsing and formatting datetime values.
All datetime operations follow the project's constitution: UTC storage, ISO-8601 format.
"""

import re
from datetime import datetime, timedelta, timezone

# Supported time filter values and their corresponding timedeltas
TIME_FILTER_DELTAS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def parse_iso_timestamp(timestamp: str) -> datetime:
    """Parse ISO-8601 timestamp, handling both Z and +00:00 suffixes.

    Args:
        timestamp: ISO-8601 timestamp string (e.g., "2024-01-15T10:30:00Z").

    Returns:
        Timezone-aware datetime object (always UTC if no offset specified).

    Note:
        Python 3.10 requires explicit +00:00 offset for fromisoformat(),
        so this function normalizes Z suffix to +00:00.
        Naive datetime strings (no timezone) are assumed to be UTC.
    """
    normalized = timestamp.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    # Ensure timezone awareness - assume UTC for naive timestamps
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


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


def parse_time_filter(since: str | None) -> str | None:
    """Parse time filter string to ISO-8601 timestamp.

    Converts a human-readable time filter value (e.g., "24h", "7d") to an
    ISO-8601 timestamp representing that duration before the current time.

    Args:
        since: Time filter string ("24h", "7d", "30d") or None.

    Returns:
        ISO-8601 timestamp string representing (now - duration),
        or None if since is None, empty string, or not a valid filter value.

    Examples:
        >>> parse_time_filter("24h")  # Returns timestamp for 24 hours ago
        '2024-01-14T10:30:00+00:00'
        >>> parse_time_filter(None)   # Returns None
        None
        >>> parse_time_filter("invalid")  # Returns None for unknown values
        None
    """
    if since is None or since not in TIME_FILTER_DELTAS:
        return None
    return (datetime.now(timezone.utc) - TIME_FILTER_DELTAS[since]).isoformat()


# Supported time unit suffixes and their timedelta keyword arguments
_TIME_UNIT_MAP: dict[str, str] = {
    "d": "days",
    "w": "weeks",
    "h": "hours",
    "m": "minutes",
}


def parse_relative_time(value: str) -> datetime:
    """Parse relative time string to UTC datetime.

    Converts a human-readable relative time value (e.g., "1d", "2w", "3h", "30m")
    to a UTC datetime representing that duration before the current time.

    Supported formats:
        - Nd: N days ago (e.g., "1d", "7d", "30d")
        - Nw: N weeks ago (e.g., "1w", "2w")
        - Nh: N hours ago (e.g., "2h", "24h")
        - Nm: N minutes ago (e.g., "30m", "90m")

    Args:
        value: Relative time string (case-insensitive).

    Returns:
        Timezone-aware UTC datetime representing (now - duration).

    Raises:
        ValueError: If format is invalid or unparseable.

    Examples:
        >>> parse_relative_time("1d")   # 1 day ago
        >>> parse_relative_time("2w")   # 2 weeks ago
        >>> parse_relative_time("3h")   # 3 hours ago
        >>> parse_relative_time("30m")  # 30 minutes ago
    """
    match = re.match(r"^(\d+)([dwhmDWHM])$", value.strip())
    if not match:
        units = ", ".join(f"{k} ({_TIME_UNIT_MAP[k]})" for k in _TIME_UNIT_MAP)
        raise ValueError(
            f"Invalid relative time format '{value}'. "
            f"Expected format: <number><unit> where unit is one of: {units}. "
            "Examples: '1d' (1 day), '2w' (2 weeks), '3h' (3 hours), "
            "'30m' (30 minutes)"
        )

    amount = int(match.group(1))
    unit = match.group(2).lower()

    # Build timedelta with appropriate keyword
    delta_kwargs = {_TIME_UNIT_MAP[unit]: amount}
    delta = timedelta(**delta_kwargs)

    return datetime.now(timezone.utc) - delta


def parse_relative_time_iso(value: str) -> str:
    """Parse relative time string to ISO-8601 timestamp.

    Convenience wrapper around parse_relative_time() that returns an
    ISO-8601 formatted string instead of a datetime object.

    Args:
        value: Relative time string (e.g., "1d", "2w", "3h", "30m").

    Returns:
        ISO-8601 timestamp string representing (now - duration).

    Raises:
        ValueError: If format is invalid or unparseable.

    Examples:
        >>> parse_relative_time_iso("7d")
        '2024-01-08T10:30:00+00:00'  # 7 days before current time
    """
    return parse_relative_time(value).isoformat()


def parse_relative_or_iso_time(value: str) -> str:
    """Parse either relative time or ISO-8601 timestamp to ISO-8601.

    Accepts either a relative time string (e.g., "7d", "1w") or an
    ISO-8601 timestamp. Returns an ISO-8601 formatted string.

    Args:
        value: Relative time string or ISO-8601 timestamp.

    Returns:
        ISO-8601 timestamp string.

    Raises:
        ValueError: If format is invalid and cannot be parsed as either format.

    Examples:
        >>> parse_relative_or_iso_time("7d")
        '2024-01-08T10:30:00+00:00'
        >>> parse_relative_or_iso_time("2024-01-15T10:30:00Z")
        '2024-01-15T10:30:00Z'
    """
    # Check if it looks like an ISO-8601 timestamp (contains 'T' or is date-like)
    # ISO timestamps have T separator or are at least 10 chars (YYYY-MM-DD)
    if "T" in value or len(value) >= 10:
        return value

    # Try parsing as relative time
    return parse_relative_time_iso(value)
