"""Unit tests for reports filters module."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from vpo.reports.filters import (
    TimeFilter,
    parse_relative_date,
)


class TestParseRelativeDate:
    """Tests for parse_relative_date function."""

    def test_parse_days(self):
        """Parse relative days correctly."""
        fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("vpo.reports.filters.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            result = parse_relative_date("7d")
            expected = datetime(2025, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
            assert result == expected

    def test_parse_weeks(self):
        """Parse relative weeks correctly."""
        fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("vpo.reports.filters.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            result = parse_relative_date("2w")
            expected = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            assert result == expected

    def test_parse_hours(self):
        """Parse relative hours correctly."""
        fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("vpo.reports.filters.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            result = parse_relative_date("24h")
            expected = datetime(2025, 1, 14, 12, 0, 0, tzinfo=timezone.utc)
            assert result == expected

    def test_parse_iso_date_only(self):
        """Parse ISO date-only format."""
        result = parse_relative_date("2025-01-15")
        expected = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_iso_datetime(self):
        """Parse full ISO datetime."""
        result = parse_relative_date("2025-01-15T14:30:00")
        expected = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_iso_with_z(self):
        """Parse ISO datetime with Z suffix."""
        result = parse_relative_date("2025-01-15T14:30:00Z")
        assert result.tzinfo == timezone.utc
        assert result.hour == 14

    def test_parse_iso_with_offset(self):
        """Parse ISO datetime with timezone offset."""
        result = parse_relative_date("2025-01-15T14:30:00+05:00")
        assert result.tzinfo is not None

    def test_parse_invalid_format(self):
        """Raise ValueError for invalid format."""
        with pytest.raises(ValueError) as exc_info:
            parse_relative_date("invalid")
        assert "Invalid time format" in str(exc_info.value)

    def test_parse_invalid_relative(self):
        """Raise ValueError for invalid relative format."""
        with pytest.raises(ValueError):
            parse_relative_date("7x")

    def test_parse_case_insensitive(self):
        """Relative formats are case insensitive."""
        fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("vpo.reports.filters.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            result_lower = parse_relative_date("7d")
            result_upper = parse_relative_date("7D")
            assert result_lower == result_upper


class TestTimeFilter:
    """Tests for TimeFilter dataclass."""

    def test_from_strings_since_only(self):
        """Create TimeFilter with since only."""
        fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("vpo.reports.filters.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            tf = TimeFilter.from_strings("7d", None)
            assert tf.since is not None
            assert tf.until is None
            expected_since = datetime(2025, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
            assert tf.since == expected_since

    def test_from_strings_until_only(self):
        """Create TimeFilter with until only."""
        fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("vpo.reports.filters.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            tf = TimeFilter.from_strings(None, "1d")
            assert tf.since is None
            assert tf.until is not None

    def test_from_strings_both(self):
        """Create TimeFilter with both since and until."""
        fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("vpo.reports.filters.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            tf = TimeFilter.from_strings("7d", "1d")
            assert tf.since is not None
            assert tf.until is not None
            assert tf.since < tf.until

    def test_from_strings_invalid_range(self):
        """Raise ValueError when since is after until."""
        with pytest.raises(ValueError) as exc_info:
            TimeFilter.from_strings("2025-01-20", "2025-01-10")
        assert "must be before" in str(exc_info.value)

    def test_from_strings_none(self):
        """Create TimeFilter with no values."""
        tf = TimeFilter.from_strings(None, None)
        assert tf.since is None
        assert tf.until is None

    def test_to_iso_strings_with_values(self):
        """Convert TimeFilter to ISO strings."""
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        tf = TimeFilter(since=dt, until=dt)
        since_iso, until_iso = tf.to_iso_strings()
        assert since_iso is not None
        assert until_iso is not None
        assert "2025-01-15" in since_iso

    def test_to_iso_strings_none(self):
        """Convert empty TimeFilter to ISO strings."""
        tf = TimeFilter()
        since_iso, until_iso = tf.to_iso_strings()
        assert since_iso is None
        assert until_iso is None
