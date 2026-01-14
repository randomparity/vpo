"""Validation utilities.

This module provides pure functions for validating data formats.
These utilities are used across the codebase for consistent validation.
"""

import re

# Pre-compiled UUID pattern for performance
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID format.

    Args:
        value: String to validate.

    Returns:
        True if valid UUID format, False otherwise.
    """
    return bool(_UUID_PATTERN.match(value))
