"""Unit tests for db/queries/helpers.py."""

from vpo.db.queries.helpers import _escape_like_pattern


class TestEscapeLikePattern:
    """Tests for LIKE pattern escaping."""

    def test_escapes_percent(self) -> None:
        """Percent sign is escaped."""
        assert _escape_like_pattern("100%") == "100\\%"

    def test_escapes_underscore(self) -> None:
        """Underscore is escaped."""
        assert _escape_like_pattern("file_name") == "file\\_name"

    def test_escapes_backslash(self) -> None:
        """Backslash is escaped."""
        assert _escape_like_pattern("path\\to") == "path\\\\to"

    def test_escapes_bracket(self) -> None:
        """Open bracket is escaped (SQLite character class)."""
        assert _escape_like_pattern("test[1]") == "test\\[1]"

    def test_escapes_multiple_chars(self) -> None:
        """Multiple special characters are all escaped."""
        result = _escape_like_pattern("100%_[test]\\end")
        assert result == "100\\%\\_\\[test]\\\\end"

    def test_empty_string(self) -> None:
        """Empty string returns empty."""
        assert _escape_like_pattern("") == ""

    def test_no_special_chars(self) -> None:
        """Normal text passes through unchanged."""
        assert _escape_like_pattern("normaltext") == "normaltext"

    def test_multiple_percent_signs(self) -> None:
        """Multiple percent signs are all escaped."""
        assert _escape_like_pattern("50%+50%=100%") == "50\\%+50\\%=100\\%"

    def test_multiple_underscores(self) -> None:
        """Multiple underscores are all escaped."""
        assert _escape_like_pattern("a_b_c") == "a\\_b\\_c"

    def test_unicode_preserved(self) -> None:
        """Unicode characters pass through unchanged."""
        assert _escape_like_pattern("file\u2026name") == "file\u2026name"

    def test_escapes_in_path(self) -> None:
        """Real-world path with special chars."""
        result = _escape_like_pattern("/videos/100%_complete[1].mkv")
        assert result == "/videos/100\\%\\_complete\\[1].mkv"
