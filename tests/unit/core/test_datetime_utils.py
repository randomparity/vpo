"""Tests for core datetime utilities."""

from datetime import datetime, timedelta, timezone

import pytest

from vpo.core.datetime_utils import (
    TIME_FILTER_DELTAS,
    parse_iso_timestamp,
    parse_relative_or_iso_time,
    parse_relative_time,
    parse_relative_time_iso,
    parse_time_filter,
)


class TestParseTimeFilter:
    """Tests for parse_time_filter function."""

    def test_returns_none_for_none_input(self):
        """parse_time_filter(None) returns None."""
        result = parse_time_filter(None)
        assert result is None

    def test_returns_none_for_invalid_value(self):
        """parse_time_filter returns None for unrecognized values."""
        result = parse_time_filter("invalid")
        assert result is None

        result = parse_time_filter("1h")
        assert result is None

        result = parse_time_filter("1w")
        assert result is None

    def test_returns_timestamp_for_24h(self):
        """parse_time_filter("24h") returns ISO timestamp 24 hours ago."""
        before = datetime.now(timezone.utc)
        result = parse_time_filter("24h")
        after = datetime.now(timezone.utc)

        assert result is not None
        parsed = datetime.fromisoformat(result)

        # Check the result is approximately 24 hours ago
        expected_start = before - timedelta(hours=24)
        expected_end = after - timedelta(hours=24)

        assert expected_start <= parsed <= expected_end

    def test_returns_timestamp_for_7d(self):
        """parse_time_filter("7d") returns ISO timestamp 7 days ago."""
        before = datetime.now(timezone.utc)
        result = parse_time_filter("7d")
        after = datetime.now(timezone.utc)

        assert result is not None
        parsed = datetime.fromisoformat(result)

        expected_start = before - timedelta(days=7)
        expected_end = after - timedelta(days=7)

        assert expected_start <= parsed <= expected_end

    def test_returns_timestamp_for_30d(self):
        """parse_time_filter("30d") returns ISO timestamp 30 days ago."""
        before = datetime.now(timezone.utc)
        result = parse_time_filter("30d")
        after = datetime.now(timezone.utc)

        assert result is not None
        parsed = datetime.fromisoformat(result)

        expected_start = before - timedelta(days=30)
        expected_end = after - timedelta(days=30)

        assert expected_start <= parsed <= expected_end

    def test_returns_iso_format_string(self):
        """parse_time_filter returns valid ISO-8601 formatted string."""
        result = parse_time_filter("24h")
        assert result is not None

        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(result)

        # Should be timezone aware (UTC)
        assert parsed.tzinfo is not None

    def test_empty_string_returns_none(self):
        """parse_time_filter("") returns None."""
        result = parse_time_filter("")
        assert result is None


class TestTimeFilterDeltas:
    """Tests for TIME_FILTER_DELTAS constant."""

    def test_contains_expected_keys(self):
        """TIME_FILTER_DELTAS has 24h, 7d, and 30d keys."""
        assert "24h" in TIME_FILTER_DELTAS
        assert "7d" in TIME_FILTER_DELTAS
        assert "30d" in TIME_FILTER_DELTAS

    def test_values_are_timedeltas(self):
        """TIME_FILTER_DELTAS values are timedelta objects."""
        for key, value in TIME_FILTER_DELTAS.items():
            assert isinstance(value, timedelta), f"{key} value should be timedelta"

    def test_24h_is_24_hours(self):
        """24h maps to 24 hour timedelta."""
        assert TIME_FILTER_DELTAS["24h"] == timedelta(hours=24)

    def test_7d_is_7_days(self):
        """7d maps to 7 day timedelta."""
        assert TIME_FILTER_DELTAS["7d"] == timedelta(days=7)

    def test_30d_is_30_days(self):
        """30d maps to 30 day timedelta."""
        assert TIME_FILTER_DELTAS["30d"] == timedelta(days=30)


class TestParseIsoTimestamp:
    """Tests for parse_iso_timestamp function."""

    def test_parses_z_suffix(self):
        """parse_iso_timestamp handles Z suffix (Zulu/UTC)."""
        result = parse_iso_timestamp("2025-01-15T10:30:00Z")

        assert result.tzinfo == timezone.utc
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parses_plus_zero_offset(self):
        """parse_iso_timestamp handles +00:00 offset."""
        result = parse_iso_timestamp("2025-01-15T10:30:00+00:00")

        assert result.tzinfo == timezone.utc
        assert result.hour == 10

    def test_handles_naive_datetime_as_utc(self):
        """Naive datetime strings should be assumed UTC."""
        result = parse_iso_timestamp("2025-01-15T10:30:00")

        assert result.tzinfo == timezone.utc
        assert result.hour == 10
        assert result.minute == 30

    def test_preserves_explicit_non_utc_offset(self):
        """Explicit timezone offsets should be preserved."""
        result = parse_iso_timestamp("2025-01-15T10:30:00+05:00")

        assert result.utcoffset() == timedelta(hours=5)
        assert result.hour == 10

    def test_preserves_negative_offset(self):
        """Negative timezone offsets should be preserved."""
        result = parse_iso_timestamp("2025-01-15T10:30:00-05:00")

        assert result.utcoffset() == timedelta(hours=-5)
        assert result.hour == 10

    def test_parses_with_microseconds(self):
        """parse_iso_timestamp handles microseconds."""
        result = parse_iso_timestamp("2025-01-15T10:30:00.123456Z")

        assert result.tzinfo == timezone.utc
        assert result.microsecond == 123456

    def test_raises_on_invalid_format(self):
        """parse_iso_timestamp raises ValueError for invalid input."""
        with pytest.raises(ValueError):
            parse_iso_timestamp("not-a-timestamp")

        with pytest.raises(ValueError):
            parse_iso_timestamp("2025/01/15")


class TestParseRelativeTime:
    """Tests for parse_relative_time function."""

    def test_parses_days(self):
        """parse_relative_time handles 'd' suffix for days."""
        before = datetime.now(timezone.utc)
        result = parse_relative_time("7d")
        after = datetime.now(timezone.utc)

        expected_start = before - timedelta(days=7)
        expected_end = after - timedelta(days=7)

        assert expected_start <= result <= expected_end
        assert result.tzinfo == timezone.utc

    def test_parses_weeks(self):
        """parse_relative_time handles 'w' suffix for weeks."""
        before = datetime.now(timezone.utc)
        result = parse_relative_time("2w")
        after = datetime.now(timezone.utc)

        expected_start = before - timedelta(weeks=2)
        expected_end = after - timedelta(weeks=2)

        assert expected_start <= result <= expected_end

    def test_parses_hours(self):
        """parse_relative_time handles 'h' suffix for hours."""
        before = datetime.now(timezone.utc)
        result = parse_relative_time("3h")
        after = datetime.now(timezone.utc)

        expected_start = before - timedelta(hours=3)
        expected_end = after - timedelta(hours=3)

        assert expected_start <= result <= expected_end

    def test_parses_minutes(self):
        """parse_relative_time handles 'm' suffix for minutes."""
        before = datetime.now(timezone.utc)
        result = parse_relative_time("30m")
        after = datetime.now(timezone.utc)

        expected_start = before - timedelta(minutes=30)
        expected_end = after - timedelta(minutes=30)

        assert expected_start <= result <= expected_end

    def test_case_insensitive(self):
        """parse_relative_time is case-insensitive."""
        before = datetime.now(timezone.utc)

        # Uppercase
        result_upper = parse_relative_time("1D")
        after = datetime.now(timezone.utc)

        expected_start = before - timedelta(days=1)
        expected_end = after - timedelta(days=1)

        assert expected_start <= result_upper <= expected_end

    def test_handles_whitespace(self):
        """parse_relative_time strips whitespace."""
        before = datetime.now(timezone.utc)
        result = parse_relative_time("  1d  ")
        after = datetime.now(timezone.utc)

        expected_start = before - timedelta(days=1)
        expected_end = after - timedelta(days=1)

        assert expected_start <= result <= expected_end

    def test_raises_on_invalid_format(self):
        """parse_relative_time raises ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid relative time format"):
            parse_relative_time("invalid")

    def test_raises_on_no_number(self):
        """parse_relative_time raises ValueError when number is missing."""
        with pytest.raises(ValueError, match="Invalid relative time format"):
            parse_relative_time("d")

    def test_raises_on_no_unit(self):
        """parse_relative_time raises ValueError when unit is missing."""
        with pytest.raises(ValueError, match="Invalid relative time format"):
            parse_relative_time("123")

    def test_raises_on_unknown_unit(self):
        """parse_relative_time raises ValueError for unknown units."""
        with pytest.raises(ValueError, match="Invalid relative time format"):
            parse_relative_time("5y")  # years not supported

    def test_returns_utc_datetime(self):
        """parse_relative_time returns timezone-aware UTC datetime."""
        result = parse_relative_time("1h")

        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc


class TestParseRelativeTimeIso:
    """Tests for parse_relative_time_iso function."""

    def test_returns_iso_string(self):
        """parse_relative_time_iso returns ISO-8601 formatted string."""
        result = parse_relative_time_iso("1d")

        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None

    def test_is_consistent_with_parse_relative_time(self):
        """parse_relative_time_iso matches parse_relative_time().isoformat()."""
        # They might differ by microseconds, so just check date/hour
        result_iso = parse_relative_time_iso("7d")
        result_dt = parse_relative_time("7d")

        # Parse the ISO string back
        parsed = datetime.fromisoformat(result_iso)

        # Should be within 1 second of each other
        diff = abs((parsed - result_dt).total_seconds())
        assert diff < 1.0

    def test_raises_on_invalid_format(self):
        """parse_relative_time_iso raises ValueError for invalid input."""
        with pytest.raises(ValueError):
            parse_relative_time_iso("invalid")


class TestParseRelativeOrIsoTime:
    """Tests for parse_relative_or_iso_time function."""

    def test_passes_through_iso_timestamp_with_t(self):
        """ISO timestamps with T separator are passed through unchanged."""
        iso_timestamp = "2025-01-15T10:30:00Z"
        result = parse_relative_or_iso_time(iso_timestamp)

        assert result == iso_timestamp

    def test_passes_through_date_string(self):
        """Date strings (>= 10 chars) are passed through unchanged."""
        date_string = "2025-01-15"
        result = parse_relative_or_iso_time(date_string)

        assert result == date_string

    def test_passes_through_iso_with_offset(self):
        """ISO timestamps with timezone offset are passed through."""
        iso_timestamp = "2025-01-15T10:30:00+05:00"
        result = parse_relative_or_iso_time(iso_timestamp)

        assert result == iso_timestamp

    def test_parses_relative_time(self):
        """Short relative time strings are parsed."""
        before = datetime.now(timezone.utc)
        result = parse_relative_or_iso_time("7d")
        after = datetime.now(timezone.utc)

        # Should be an ISO string
        parsed = datetime.fromisoformat(result)

        expected_start = before - timedelta(days=7)
        expected_end = after - timedelta(days=7)

        assert expected_start <= parsed <= expected_end

    def test_parses_all_relative_units(self):
        """All relative time units (d, w, h, m) are supported."""
        # Just verify they don't raise
        parse_relative_or_iso_time("1d")
        parse_relative_or_iso_time("1w")
        parse_relative_or_iso_time("1h")
        parse_relative_or_iso_time("1m")

    def test_raises_on_invalid_short_string(self):
        """Invalid short strings (not relative, not ISO) raise ValueError."""
        with pytest.raises(ValueError):
            parse_relative_or_iso_time("abc")
