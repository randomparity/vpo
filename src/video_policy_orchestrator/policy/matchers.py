"""Commentary pattern matching utilities.

This module provides regex-based pattern matching for identifying
commentary tracks based on their titles.
"""

import re
from re import Pattern


class CommentaryMatcher:
    """Matches track titles against commentary patterns.

    Patterns are compiled once and reused for performance.
    All matching is case-insensitive.
    """

    def __init__(self, patterns: tuple[str, ...]) -> None:
        """Initialize the matcher with regex patterns.

        Args:
            patterns: Tuple of regex pattern strings.

        Raises:
            ValueError: If any pattern is invalid regex.
        """
        self._patterns = patterns
        self._compiled: list[Pattern[str]] = []

        for idx, pattern in enumerate(patterns):
            try:
                self._compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                raise ValueError(
                    f"Invalid regex pattern at commentary_patterns[{idx}]: {e}"
                ) from e

    @property
    def patterns(self) -> tuple[str, ...]:
        """Get the original pattern strings."""
        return self._patterns

    def is_commentary(self, title: str | None) -> bool:
        """Check if a track title matches any commentary pattern.

        Args:
            title: Track title to check. None or empty returns False.

        Returns:
            True if the title matches any commentary pattern.
        """
        if not title:
            return False

        for compiled in self._compiled:
            if compiled.search(title):
                return True

        return False

    def match(self, title: str | None) -> str | None:
        """Find the first pattern that matches the title.

        Args:
            title: Track title to check.

        Returns:
            The pattern string that matched, or None if no match.
        """
        if not title:
            return None

        for pattern, compiled in zip(self._patterns, self._compiled):
            if compiled.search(title):
                return pattern

        return None


def validate_regex_patterns(patterns: list[str]) -> list[str]:
    """Validate a list of regex patterns and return error messages.

    Args:
        patterns: List of pattern strings to validate.

    Returns:
        List of error messages (empty if all patterns are valid).
    """
    errors = []
    for idx, pattern in enumerate(patterns):
        try:
            re.compile(pattern)
        except re.error as e:
            errors.append(f"Invalid regex pattern at commentary_patterns[{idx}]: {e}")
    return errors
