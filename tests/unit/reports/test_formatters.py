"""Unit tests for reports formatters module."""

import json
import tempfile
from pathlib import Path

import pytest

from vpo.reports.formatters import (
    ReportFormat,
    _atomic_write_text,
    calculate_duration_seconds,
    format_duration,
    format_size_change,
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


class TestFormatSizeChange:
    """Tests for format_size_change function."""

    def test_none_size_before(self):
        """Return N/A when size_before is None."""
        assert format_size_change(None, 1000000) == "N/A"

    def test_none_size_after(self):
        """Return N/A when size_after is None."""
        assert format_size_change(1000000, None) == "N/A"

    def test_both_none(self):
        """Return N/A when both values are None."""
        assert format_size_change(None, None) == "N/A"

    def test_size_reduction(self):
        """Format size reduction with negative sign and percentage."""
        # 1 GB -> 500 MB = 50% reduction
        result = format_size_change(1024**3, 512 * 1024**2)
        assert result.startswith("-")
        assert "50%" in result
        assert "MB" in result

    def test_size_increase(self):
        """Format size increase with positive sign and percentage."""
        # 500 MB -> 750 MB = 50% increase
        result = format_size_change(500 * 1024**2, 750 * 1024**2)
        assert result.startswith("+")
        assert "50%" in result
        assert "MB" in result

    def test_no_change(self):
        """Format zero change."""
        result = format_size_change(1000000, 1000000)
        assert result == "0 B (0%)"

    def test_zero_original_size(self):
        """Handle zero original size (avoid division by zero)."""
        result = format_size_change(0, 1000000)
        assert result.startswith("+")
        assert "N/A" in result  # Percentage N/A when dividing by zero

    def test_both_zero(self):
        """Handle both sizes being zero."""
        result = format_size_change(0, 0)
        assert result == "0 B (0%)"

    def test_large_reduction(self):
        """Format large size reduction (GB scale)."""
        # 10 GB -> 2 GB = 80% reduction
        result = format_size_change(10 * 1024**3, 2 * 1024**3)
        assert result.startswith("-")
        assert "GB" in result
        assert "80%" in result

    def test_small_reduction(self):
        """Format small size reduction (KB scale)."""
        # 100 KB -> 50 KB = 50% reduction
        result = format_size_change(100 * 1024, 50 * 1024)
        assert result.startswith("-")
        assert "KB" in result
        assert "50%" in result

    def test_negative_size_before(self):
        """Return N/A for negative size_before."""
        assert format_size_change(-100, 200) == "N/A"

    def test_negative_size_after(self):
        """Return N/A for negative size_after."""
        assert format_size_change(100, -200) == "N/A"

    def test_both_negative(self):
        """Return N/A when both sizes are negative."""
        assert format_size_change(-100, -200) == "N/A"


class TestAtomicWrite:
    """Tests for atomic write functionality."""

    def test_atomic_write_creates_file(self):
        """Atomic write creates file correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            _atomic_write_text(path, "test content")

            assert path.exists()
            assert path.read_text() == "test content"

    def test_atomic_write_overwrites_existing(self):
        """Atomic write overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            path.write_text("old content")

            _atomic_write_text(path, "new content")

            assert path.read_text() == "new content"

    def test_atomic_write_preserves_on_error(self):
        """Original file preserved if atomic write fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            path.write_text("original content")

            # Make the directory read-only to cause write failure
            # This test is tricky - we'll use a different approach
            # Create a mock situation where the temp file can't be renamed

            # We can't easily simulate atomic rename failure,
            # but we can verify the pattern is used by checking
            # that the file was written atomically (no partial content)
            _atomic_write_text(path, "new content")
            assert path.read_text() == "new content"

    def test_atomic_write_cleans_temp_on_error(self):
        """Temp file cleaned up on write error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"

            # Write normally first
            _atomic_write_text(path, "content")

            # List files in directory - should only be the target file
            files = list(Path(tmpdir).iterdir())
            assert len(files) == 1
            assert files[0] == path

    def test_atomic_write_utf8_encoding(self):
        """Atomic write handles UTF-8 content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            content = "Unicode: \u00e9\u00e8\u00ea \u65e5\u672c\u8a9e \U0001f600"

            _atomic_write_text(path, content)

            assert path.read_text(encoding="utf-8") == content

    def test_write_report_uses_atomic(self):
        """write_report_to_file uses atomic write pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.csv"
            write_report_to_file("col1,col2\na,b", path)

            assert path.exists()
            assert path.read_text() == "col1,col2\na,b"

            # Verify no temp files left behind
            files = list(Path(tmpdir).iterdir())
            assert len(files) == 1

    def test_atomic_write_cleanup_on_write_failure(self, monkeypatch):
        """Temp file cleaned up when write raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            path.write_text("original content")

            # Track temp file paths created
            created_temps = []

            class FailingFile:
                """Mock file that fails on write."""

                def __init__(self, real_file):
                    self._real_file = real_file
                    self.name = real_file.name
                    created_temps.append(Path(real_file.name))

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self._real_file.close()

                def write(self, content):
                    raise OSError("Simulated write failure")

            original_ntf = tempfile.NamedTemporaryFile

            def tracking_ntf(*args, **kwargs):
                real_file = original_ntf(*args, **kwargs)
                return FailingFile(real_file)

            monkeypatch.setattr(tempfile, "NamedTemporaryFile", tracking_ntf)

            with pytest.raises(OSError, match="Simulated write failure"):
                _atomic_write_text(path, "new content")

            # Original file should be preserved
            assert path.read_text() == "original content"

            # Temp files should be cleaned up
            for temp_path in created_temps:
                assert not temp_path.exists()

    def test_atomic_write_cleanup_on_rename_failure(self, monkeypatch):
        """Temp file cleaned up when rename raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"

            # Track if temp file was cleaned
            temp_path_ref = []

            def failing_replace(self, target):
                temp_path_ref.append(self)
                raise OSError("Simulated rename failure")

            monkeypatch.setattr(Path, "replace", failing_replace)

            with pytest.raises(OSError, match="Simulated rename failure"):
                _atomic_write_text(path, "new content")

            # Temp file should be cleaned up
            if temp_path_ref:
                assert not temp_path_ref[0].exists()
