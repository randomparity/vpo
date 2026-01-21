"""Tests for core string utilities."""

from vpo.core.string_utils import (
    compare_strings_ci,
    contains_ci,
    normalize_string,
)


class TestNormalizeString:
    """Tests for normalize_string function."""

    def test_lowercases_basic_string(self):
        """normalize_string lowercases ASCII characters."""
        result = normalize_string("Hello World")
        assert result == "hello world"

    def test_strips_leading_whitespace(self):
        """normalize_string strips leading whitespace."""
        result = normalize_string("   hello")
        assert result == "hello"

    def test_strips_trailing_whitespace(self):
        """normalize_string strips trailing whitespace."""
        result = normalize_string("hello   ")
        assert result == "hello"

    def test_strips_both_ends(self):
        """normalize_string strips whitespace from both ends."""
        result = normalize_string("  Hello World  ")
        assert result == "hello world"

    def test_handles_empty_string(self):
        """normalize_string handles empty string."""
        result = normalize_string("")
        assert result == ""

    def test_handles_whitespace_only_string(self):
        """normalize_string handles whitespace-only string."""
        result = normalize_string("   ")
        assert result == ""

    def test_german_eszett_to_ss(self):
        """normalize_string converts German eszett (ß) to ss via casefold."""
        result = normalize_string("Straße")
        assert result == "strasse"

    def test_preserves_internal_whitespace(self):
        """normalize_string preserves internal whitespace."""
        result = normalize_string("hello   world")
        assert result == "hello   world"

    def test_handles_uppercase_string(self):
        """normalize_string handles all-uppercase string."""
        result = normalize_string("HELLO WORLD")
        assert result == "hello world"

    def test_handles_mixed_case(self):
        """normalize_string handles mixed case string."""
        result = normalize_string("HeLLo WoRLD")
        assert result == "hello world"

    def test_handles_unicode_characters(self):
        """normalize_string handles various Unicode characters."""
        result = normalize_string("Café")
        assert result == "café"

    def test_handles_tabs_and_newlines(self):
        """normalize_string strips tabs and newlines at ends."""
        result = normalize_string("\tHello\n")
        assert result == "hello"


class TestCompareStringsCi:
    """Tests for compare_strings_ci function."""

    def test_equal_same_case(self):
        """compare_strings_ci returns True for identical strings."""
        assert compare_strings_ci("hello", "hello") is True

    def test_equal_different_case(self):
        """compare_strings_ci returns True for same string different case."""
        assert compare_strings_ci("Hello", "hello") is True
        assert compare_strings_ci("HELLO", "hello") is True
        assert compare_strings_ci("hello", "HELLO") is True

    def test_not_equal(self):
        """compare_strings_ci returns False for different strings."""
        assert compare_strings_ci("hello", "world") is False

    def test_empty_strings_equal(self):
        """compare_strings_ci returns True for two empty strings."""
        assert compare_strings_ci("", "") is True

    def test_empty_string_not_equal_to_non_empty(self):
        """compare_strings_ci returns False for empty vs non-empty."""
        assert compare_strings_ci("", "hello") is False
        assert compare_strings_ci("hello", "") is False

    def test_unicode_case_folding(self):
        """compare_strings_ci handles Unicode case folding."""
        assert compare_strings_ci("CAFÉ", "café") is True

    def test_german_eszett_comparison(self):
        """compare_strings_ci handles German eszett correctly."""
        # With casefold, ß becomes ss, so STRASSE == Straße
        assert compare_strings_ci("STRASSE", "Straße") is True
        assert compare_strings_ci("strasse", "Straße") is True

    def test_different_unicode_characters(self):
        """compare_strings_ci distinguishes different Unicode chars."""
        assert compare_strings_ci("hello", "hellö") is False


class TestContainsCi:
    """Tests for contains_ci function."""

    def test_contains_exact_match(self):
        """contains_ci finds exact substring."""
        assert contains_ci("Hello World", "World") is True

    def test_contains_case_insensitive(self):
        """contains_ci finds substring regardless of case."""
        assert contains_ci("Hello World", "WORLD") is True
        assert contains_ci("Hello World", "world") is True
        assert contains_ci("Hello World", "WoRlD") is True

    def test_contains_at_start(self):
        """contains_ci finds substring at start."""
        assert contains_ci("Hello World", "hello") is True

    def test_contains_at_end(self):
        """contains_ci finds substring at end."""
        assert contains_ci("Hello World", "world") is True

    def test_not_contains(self):
        """contains_ci returns False when substring not present."""
        assert contains_ci("Hello World", "foo") is False

    def test_empty_needle_in_non_empty(self):
        """contains_ci returns True for empty needle in non-empty haystack."""
        assert contains_ci("Hello", "") is True

    def test_empty_haystack_empty_needle(self):
        """contains_ci returns True for empty needle in empty haystack."""
        assert contains_ci("", "") is True

    def test_non_empty_needle_in_empty_haystack(self):
        """contains_ci returns False for non-empty needle in empty haystack."""
        assert contains_ci("", "hello") is False

    def test_unicode_substring(self):
        """contains_ci handles Unicode substrings."""
        assert contains_ci("Welcome to the Café", "CAFÉ") is True

    def test_german_eszett_substring(self):
        """contains_ci handles German eszett in substring search."""
        # "strasse" is found in "Straße" via casefold
        assert contains_ci("Straße", "STRASSE") is True
        assert contains_ci("Hauptstraße", "strasse") is True
