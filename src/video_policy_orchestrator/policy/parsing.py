"""Shared parsing utilities for policy values.

This module provides parsing functions for file sizes, durations, and other
value formats used in policy definitions. These functions are used both for
YAML validation (in loader.py) and for runtime evaluation (in skip_conditions.py).
"""

import re


def parse_file_size(value: str) -> int | None:
    """Parse file size string (e.g., '5GB', '500MB') to bytes.

    Supports units: B, KB, MB, GB, TB (case-insensitive).
    Uses binary units (1 KB = 1024 bytes).

    Args:
        value: File size string like "5GB", "500MB", "1.5TB"

    Returns:
        Size in bytes, or None if the format is invalid.

    Examples:
        >>> parse_file_size("5GB")
        5368709120
        >>> parse_file_size("500MB")
        524288000
        >>> parse_file_size("invalid")
        None
    """
    match = re.match(
        r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)$", value.strip(), re.IGNORECASE
    )
    if not match:
        return None
    num = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(num * multipliers[unit])


def parse_duration(value: str) -> float | None:
    """Parse duration string (e.g., '30m', '2h', '1h30m') to seconds.

    Supports formats:
    - Simple: '30m', '2h', '90s'
    - Compound: '1h30m'

    Args:
        value: Duration string like "30m", "2h", "1h30m"

    Returns:
        Duration in seconds, or None if the format is invalid.

    Examples:
        >>> parse_duration("30m")
        1800.0
        >>> parse_duration("2h")
        7200.0
        >>> parse_duration("1h30m")
        5400.0
        >>> parse_duration("invalid")
        None
    """
    # Try simple formats first: '30m', '2h', '90s'
    simple_match = re.match(
        r"^(\d+(?:\.\d+)?)\s*(s|m|h)$", value.strip(), re.IGNORECASE
    )
    if simple_match:
        num = float(simple_match.group(1))
        unit = simple_match.group(2).lower()
        multipliers = {"s": 1, "m": 60, "h": 3600}
        return num * multipliers[unit]

    # Try compound format: '1h30m'
    compound_match = re.match(r"^(\d+)h(?:(\d+)m)?$", value.strip(), re.IGNORECASE)
    if compound_match:
        hours = int(compound_match.group(1))
        minutes = int(compound_match.group(2)) if compound_match.group(2) else 0
        return hours * 3600 + minutes * 60

    return None
