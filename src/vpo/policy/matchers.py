"""Pattern matching utilities for track classification.

This module provides regex-based pattern matching for identifying
special audio tracks (commentary, music, sfx) based on their titles.
"""

import re
from re import Pattern


class _PatternMatcher:
    """Base class for pattern-based track matching.

    Patterns are compiled once and reused for performance.
    All matching is case-insensitive.
    """

    def __init__(
        self, patterns: tuple[str, ...], pattern_name: str = "pattern"
    ) -> None:
        """Initialize the matcher with regex patterns.

        Args:
            patterns: Tuple of regex pattern strings.
            pattern_name: Name for error messages (e.g., "music_patterns").

        Raises:
            ValueError: If any pattern is invalid regex.
        """
        self._patterns = patterns
        self._pattern_name = pattern_name
        self._compiled: list[Pattern[str]] = []

        for idx, pattern in enumerate(patterns):
            try:
                self._compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                raise ValueError(
                    f"Invalid regex pattern at {pattern_name}[{idx}]: {e}"
                ) from e

    @property
    def patterns(self) -> tuple[str, ...]:
        """Get the original pattern strings."""
        return self._patterns

    def _matches(self, title: str | None) -> bool:
        """Check if a track title matches any pattern.

        Args:
            title: Track title to check. None or empty returns False.

        Returns:
            True if the title matches any pattern.
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


class CommentaryMatcher(_PatternMatcher):
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
        super().__init__(patterns, "commentary_patterns")

    def is_commentary(self, title: str | None) -> bool:
        """Check if a track title matches any commentary pattern.

        Args:
            title: Track title to check. None or empty returns False.

        Returns:
            True if the title matches any commentary pattern.
        """
        return self._matches(title)


class MusicMatcher(_PatternMatcher):
    """Matches track titles against music track patterns.

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
        super().__init__(patterns, "music_patterns")

    def is_music(self, title: str | None) -> bool:
        """Check if a track title matches any music pattern.

        Args:
            title: Track title to check. None or empty returns False.

        Returns:
            True if the title matches any music pattern.
        """
        return self._matches(title)


class SfxMatcher(_PatternMatcher):
    """Matches track titles against SFX (sound effects) patterns.

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
        super().__init__(patterns, "sfx_patterns")

    def is_sfx(self, title: str | None) -> bool:
        """Check if a track title matches any SFX pattern.

        Args:
            title: Track title to check. None or empty returns False.

        Returns:
            True if the title matches any SFX pattern.
        """
        return self._matches(title)


def validate_regex_patterns(
    patterns: list[str], pattern_name: str = "patterns"
) -> list[str]:
    """Validate a list of regex patterns and return error messages.

    Args:
        patterns: List of pattern strings to validate.
        pattern_name: Name for error messages.

    Returns:
        List of error messages (empty if all patterns are valid).
    """
    errors = []
    for idx, pattern in enumerate(patterns):
        try:
            re.compile(pattern)
        except re.error as e:
            errors.append(f"Invalid regex pattern at {pattern_name}[{idx}]: {e}")
    return errors
