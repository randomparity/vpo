"""String manipulation utilities.

This module provides Unicode-safe string operations used across the codebase.
All case-insensitive operations use casefold() for proper Unicode handling
as required by the project constitution.
"""

from __future__ import annotations


def normalize_string(s: str) -> str:
    """Normalize string for case-insensitive comparison.

    Uses casefold() for proper Unicode case folding, which handles
    special characters like German eszett (ß → ss) correctly.

    Args:
        s: String to normalize.

    Returns:
        Normalized string (casefolded and stripped of leading/trailing whitespace).

    Example:
        >>> normalize_string("  Hello World  ")
        'hello world'
        >>> normalize_string("Straße")
        'strasse'
    """
    return s.casefold().strip()


def compare_strings_ci(a: str, b: str) -> bool:
    """Compare strings case-insensitively.

    Uses casefold() for proper Unicode-safe comparison.

    Args:
        a: First string.
        b: Second string.

    Returns:
        True if strings are equal (case-insensitive).

    Example:
        >>> compare_strings_ci("Hello", "hello")
        True
        >>> compare_strings_ci("HELLO", "hellö")
        False
    """
    return a.casefold() == b.casefold()


def contains_ci(haystack: str, needle: str) -> bool:
    """Check if string contains substring (case-insensitive).

    Uses casefold() for proper Unicode-safe comparison.

    Args:
        haystack: String to search in.
        needle: Substring to search for.

    Returns:
        True if haystack contains needle (case-insensitive).

    Example:
        >>> contains_ci("Hello World", "WORLD")
        True
        >>> contains_ci("Hello World", "foo")
        False
    """
    return needle.casefold() in haystack.casefold()
