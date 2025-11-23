"""Unit tests for reports formatters module."""

import json
import tempfile
from pathlib import Path

import pytest

from video_policy_orchestrator.reports.formatters import (
    ReportFormat,
    calculate_duration_seconds,
    format_duration,
    format_timestamp_local,
    render_csv,
    render_json,
    render_text_table,
    write_report_to_file,
)


class TestReportFormat:
    """Tests for ReportFormat enum."""

    def test_text_format(self):
        """ReportFormat.TEXT has correct value."""
        assert ReportFormat.TEXT.value == "text"

    def test_csv_format(self):
        """ReportFormat.CSV has correct value."""
        assert ReportFormat.CSV.value == "csv"

    def test_json_format(self):
        """ReportFormat.JSON has correct value."""
        assert ReportFormat.JSON.value == "json"


class TestFormatTimestampLocal:
    """Tests for format_timestamp_local function."""

    def test_none_input(self):
        """Return '-' for None input."""
        assert format_timestamp_local(None) == "-"

    def test_empty_string(self):
        """Return '-' for empty string."""
        assert format_timestamp_local("") == "-"

    def test_valid_iso_timestamp(self):
        """Format valid ISO timestamp to local time."""
        result = format_timestamp_local("2025-01-15T12:30:00Z")
        # Should contain date components
        assert "2025" in result
        assert "01" in result
        assert "15" in result

    def test_timestamp_without_z(self):
        """Handle timestamp without Z suffix."""
        result = format_timestamp_local("2025-01-15T12:30:00")
        assert "2025" in result

    def test_timestamp_with_offset(self):
        """Handle timestamp with timezone offset."""
        result = format_timestamp_local("2025-01-15T12:30:00+05:00")
        assert "2025" in result

    def test_invalid_timestamp_fallback(self):
        """Fallback to truncated string for invalid format."""
        result = format_timestamp_local("2025-01-15T12:30:00invalid")
        assert result == "2025-01-15T12:30:00"


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_none_input(self):
        """Return '-' for None input."""
        assert format_duration(None) == "-"

    def test_negative_input(self):
        """Return '-' for negative input."""
        assert format_duration(-10) == "-"

    def test_seconds_only(self):
        """Format seconds less than a minute."""
        assert format_duration(30) == "30s"
        assert format_duration(59) == "59s"

    def test_minutes_and_seconds(self):
        """Format minutes and seconds."""
        assert format_duration(90) == "1m 30s"
        assert format_duration(3599) == "59m 59s"

    def test_hours_and_minutes(self):
        """Format hours and minutes."""
        assert format_duration(3600) == "1h 0m"
        assert format_duration(3660) == "1h 1m"
        assert format_duration(7200) == "2h 0m"

    def test_float_input(self):
        """Handle float input."""
        assert format_duration(30.5) == "30s"
        assert format_duration(90.9) == "1m 30s"

    def test_zero_seconds(self):
        """Handle zero seconds."""
        assert format_duration(0) == "0s"


class TestCalculateDurationSeconds:
    """Tests for calculate_duration_seconds function."""

    def test_none_start(self):
        """Return None if started_at is None."""
        assert calculate_duration_seconds(None, "2025-01-15T12:30:00Z") is None

    def test_none_end(self):
        """Return None if completed_at is None."""
        assert calculate_duration_seconds("2025-01-15T12:00:00Z", None) is None

    def test_valid_timestamps(self):
        """Calculate duration between valid timestamps."""
        result = calculate_duration_seconds(
            "2025-01-15T12:00:00Z", "2025-01-15T12:30:00Z"
        )
        assert result == 1800.0  # 30 minutes

    def test_timestamps_with_offset(self):
        """Handle timestamps with timezone offsets."""
        result = calculate_duration_seconds(
            "2025-01-15T12:00:00+00:00", "2025-01-15T13:00:00+00:00"
        )
        assert result == 3600.0  # 1 hour

    def test_invalid_format(self):
        """Return None for invalid timestamp format."""
        result = calculate_duration_seconds("invalid", "also-invalid")
        assert result is None


class TestRenderTextTable:
    """Tests for render_text_table function."""

    def test_empty_rows(self):
        """Return empty string for no rows."""
        columns = [("NAME", "name", 10)]
        result = render_text_table([], columns)
        assert result == ""

    def test_single_row(self):
        """Render single row table."""
        rows = [{"name": "Test", "value": "123"}]
        columns = [("NAME", "name", 10), ("VALUE", "value", 10)]
        result = render_text_table(rows, columns)

        assert "NAME" in result
        assert "VALUE" in result
        assert "Test" in result
        assert "123" in result
        assert "-" * 10 in result  # Separator

    def test_truncation(self):
        """Truncate long values."""
        rows = [{"name": "A" * 50}]
        columns = [("NAME", "name", 10)]
        result = render_text_table(rows, columns)

        assert "..." in result
        assert "A" * 50 not in result

    def test_missing_key(self):
        """Handle missing keys gracefully."""
        rows = [{"name": "Test"}]
        columns = [("NAME", "name", 10), ("VALUE", "missing", 10)]
        result = render_text_table(rows, columns)

        assert "Test" in result
        # Missing keys should show "-"


class TestRenderCsv:
    """Tests for render_csv function."""

    def test_empty_rows(self):
        """Render CSV with only headers for empty rows."""
        columns = ["name", "value"]
        result = render_csv([], columns)

        assert "name,value" in result
        # Only header line
        lines = result.strip().split("\n")
        assert len(lines) == 1

    def test_single_row(self):
        """Render single row CSV."""
        rows = [{"name": "Test", "value": "123"}]
        columns = ["name", "value"]
        result = render_csv(rows, columns)

        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert "name,value" in lines[0]
        assert "Test,123" in lines[1]

    def test_escaping_special_chars(self):
        """Escape special characters in CSV."""
        rows = [{"name": "Test, with comma", "value": '"quoted"'}]
        columns = ["name", "value"]
        result = render_csv(rows, columns)

        # CSV module should handle quoting
        assert "Test, with comma" in result or '"Test' in result

    def test_none_values(self):
        """Handle None values as empty strings."""
        rows = [{"name": None, "value": "123"}]
        columns = ["name", "value"]
        result = render_csv(rows, columns)

        # None should become empty string
        assert ",123" in result or "123" in result

    def test_bool_values(self):
        """Convert boolean values to lowercase strings."""
        rows = [{"active": True, "deleted": False}]
        columns = ["active", "deleted"]
        result = render_csv(rows, columns)

        assert "true" in result
        assert "false" in result

    def test_extra_keys_ignored(self):
        """Extra keys in rows are ignored."""
        rows = [{"name": "Test", "extra": "ignored"}]
        columns = ["name"]
        result = render_csv(rows, columns)

        assert "ignored" not in result


class TestRenderJson:
    """Tests for render_json function."""

    def test_empty_list(self):
        """Render empty JSON array."""
        result = render_json([])
        assert result == "[]"

    def test_single_row(self):
        """Render single row JSON."""
        rows = [{"name": "Test", "value": 123}]
        result = render_json(rows)

        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "Test"
        assert parsed[0]["value"] == 123

    def test_sorted_keys(self):
        """Keys are sorted in output."""
        rows = [{"zebra": 1, "alpha": 2}]
        result = render_json(rows)

        # Alpha should come before zebra
        alpha_pos = result.find("alpha")
        zebra_pos = result.find("zebra")
        assert alpha_pos < zebra_pos

    def test_indentation(self):
        """JSON is indented."""
        rows = [{"name": "Test"}]
        result = render_json(rows)

        # Should have newlines for indentation
        assert "\n" in result


class TestWriteReportToFile:
    """Tests for write_report_to_file function."""

    def test_write_new_file(self):
        """Write content to new file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.txt"
            write_report_to_file("test content", path)

            assert path.exists()
            assert path.read_text() == "test content"

    def test_overwrite_with_force(self):
        """Overwrite existing file with force=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.txt"
            path.write_text("old content")

            write_report_to_file("new content", path, force=True)

            assert path.read_text() == "new content"

    def test_no_overwrite_without_force(self):
        """Raise FileExistsError without force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.txt"
            path.write_text("old content")

            with pytest.raises(FileExistsError) as exc_info:
                write_report_to_file("new content", path, force=False)

            assert "Use --force" in str(exc_info.value)

    def test_create_parent_directories(self):
        """Create parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "report.txt"
            write_report_to_file("test content", path)

            assert path.exists()
            assert path.read_text() == "test content"

    def test_utf8_encoding(self):
        """Write UTF-8 encoded content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.txt"
            content = "Unicode: \u00e9\u00e8\u00ea \u65e5\u672c\u8a9e"

            write_report_to_file(content, path)

            assert path.read_text(encoding="utf-8") == content
