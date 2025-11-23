"""Time filtering utilities for reports."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class TimeFilter:
    """Time range filter for report queries.

    Attributes:
        since: Start of time range (UTC, inclusive).
        until: End of time range (UTC, inclusive).
    """

    since: datetime | None = None
    until: datetime | None = None

    @classmethod
    def from_strings(cls, since: str | None, until: str | None) -> "TimeFilter":
        """Create TimeFilter from CLI string arguments.

        Args:
            since: Start time as relative (7d, 1w, 2h) or ISO-8601 string.
            until: End time as relative (7d, 1w, 2h) or ISO-8601 string.

        Returns:
            TimeFilter with parsed datetime values.

        Raises:
            ValueError: If time format is invalid.
        """
        since_dt = parse_relative_date(since) if since else None
        until_dt = parse_relative_date(until) if until else None

        # Validate since is before until
        if since_dt and until_dt and since_dt > until_dt:
            raise ValueError(f"--since ({since}) must be before --until ({until})")

        return cls(since=since_dt, until=until_dt)

    def to_iso_strings(self) -> tuple[str | None, str | None]:
        """Convert to ISO-8601 strings for SQL queries.

        Returns:
            Tuple of (since_iso, until_iso) strings or None.
        """
        since_iso = self.since.isoformat() if self.since else None
        until_iso = self.until.isoformat() if self.until else None
        return since_iso, until_iso


def parse_relative_date(value: str) -> datetime:
    """Parse relative date string or ISO-8601 datetime.

    Supports:
        - Nd: N days ago (e.g., "7d")
        - Nw: N weeks ago (e.g., "2w")
        - Nh: N hours ago (e.g., "24h")
        - ISO-8601: Full datetime (e.g., "2025-01-01" or "2025-01-01T00:00:00")

    Args:
        value: Relative date string or ISO-8601 datetime.

    Returns:
        datetime in UTC.

    Raises:
        ValueError: If format is invalid.
    """
    # Try relative format first
    match = re.match(r"^(\d+)([dwh])$", value.lower())
    if match:
        amount = int(match.group(1))
        unit = match.group(2)

        now = datetime.now(timezone.utc)
        if unit == "d":
            return now - timedelta(days=amount)
        elif unit == "w":
            return now - timedelta(weeks=amount)
        else:  # unit == "h"
            return now - timedelta(hours=amount)

    # Try ISO-8601 format
    try:
        # Handle date-only format (YYYY-MM-DD)
        if "T" not in value and len(value) == 10:
            dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)

        # Handle full ISO format
        # Remove Z suffix and replace with +00:00 for fromisoformat compatibility
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)

        # If no timezone info, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except ValueError:
        pass

    # Invalid format
    raise ValueError(
        f"Invalid time format '{value}'. "
        "Use ISO-8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) or relative (7d, 1w, 2h)."
    )
