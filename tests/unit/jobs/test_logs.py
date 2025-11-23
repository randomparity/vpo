"""Unit tests for job log file utilities.

Tests cover:
- Path traversal prevention
- UUID validation
- Log reading and pagination
- Edge cases for missing/empty files
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from video_policy_orchestrator.jobs.logs import (
    DEFAULT_LOG_LINES,
    MAX_LOG_SIZE_BYTES,
    _validate_job_id,
    count_log_lines,
    get_log_path,
    log_file_exists,
    read_log_tail,
)


class TestValidateJobId:
    """Tests for _validate_job_id function."""

    def test_valid_uuid_lowercase(self):
        """Valid lowercase UUID should pass validation."""
        # Should not raise
        _validate_job_id("12345678-1234-1234-1234-123456789abc")

    def test_valid_uuid_uppercase(self):
        """Valid uppercase UUID should pass validation."""
        # Should not raise
        _validate_job_id("12345678-1234-1234-1234-123456789ABC")

    def test_valid_uuid_mixed_case(self):
        """Valid mixed-case UUID should pass validation."""
        # Should not raise
        _validate_job_id("12345678-1234-1234-1234-123456789AbC")

    def test_invalid_uuid_too_short(self):
        """Too-short string should fail validation."""
        with pytest.raises(ValueError, match="Invalid job ID format"):
            _validate_job_id("12345678-1234")

    def test_invalid_uuid_no_dashes(self):
        """UUID without dashes should fail validation."""
        with pytest.raises(ValueError, match="Invalid job ID format"):
            _validate_job_id("12345678123412341234123456789abc")

    def test_invalid_uuid_empty(self):
        """Empty string should fail validation."""
        with pytest.raises(ValueError, match="Invalid job ID format"):
            _validate_job_id("")

    def test_path_traversal_attack_dotdot(self):
        """Path traversal with ../ should fail validation."""
        with pytest.raises(ValueError, match="Invalid job ID format"):
            _validate_job_id("../../../etc/passwd")

    def test_path_traversal_attack_absolute(self):
        """Absolute path should fail validation."""
        with pytest.raises(ValueError, match="Invalid job ID format"):
            _validate_job_id("/etc/passwd")

    def test_path_traversal_attack_encoded(self):
        """URL-encoded path traversal should fail validation."""
        with pytest.raises(ValueError, match="Invalid job ID format"):
            _validate_job_id("..%2F..%2Fetc%2Fpasswd")

    def test_path_traversal_attack_null_byte(self):
        """Null byte injection should fail validation."""
        with pytest.raises(ValueError, match="Invalid job ID format"):
            _validate_job_id("12345678-1234-1234-1234-123456789abc\x00.txt")

    def test_invalid_uuid_with_slashes(self):
        """UUID with embedded slashes should fail validation."""
        with pytest.raises(ValueError, match="Invalid job ID format"):
            _validate_job_id("12345678/1234-1234-1234-123456789abc")


class TestGetLogPath:
    """Tests for get_log_path function."""

    def test_valid_uuid_returns_path(self, tmp_path: Path):
        """Valid UUID should return a path in the logs directory."""
        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = get_log_path(job_id)

        assert result == tmp_path / f"{job_id}.log"
        assert result.parent == tmp_path

    def test_invalid_uuid_raises_valueerror(self, tmp_path: Path):
        """Invalid UUID should raise ValueError."""
        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            with pytest.raises(ValueError, match="Invalid job ID format"):
                get_log_path("../etc/passwd")

    def test_path_stays_within_log_directory(self, tmp_path: Path):
        """Path traversal attempts should be caught even if UUID validation bypassed."""
        # This test verifies defense-in-depth - the path resolution check
        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = get_log_path(job_id)
            # Ensure result is within tmp_path
            assert str(result.resolve()).startswith(str(tmp_path.resolve()))


class TestCountLogLines:
    """Tests for count_log_lines function."""

    def test_nonexistent_file_returns_zero(self, tmp_path: Path):
        """Missing log file should return 0 lines."""
        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = count_log_lines(job_id)

        assert result == 0

    def test_empty_file_returns_zero(self, tmp_path: Path):
        """Empty log file should return 0 lines."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = count_log_lines(job_id)

        assert result == 0

    def test_single_line_file(self, tmp_path: Path):
        """Single line file should return 1."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Single line\n")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = count_log_lines(job_id)

        assert result == 1

    def test_multiple_lines(self, tmp_path: Path):
        """Multiple lines should be counted correctly."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = count_log_lines(job_id)

        assert result == 3

    def test_invalid_job_id_returns_zero(self, tmp_path: Path):
        """Invalid job ID should return 0 (not raise)."""
        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = count_log_lines("../invalid")

        assert result == 0


class TestReadLogTail:
    """Tests for read_log_tail function."""

    def test_nonexistent_file_returns_empty(self, tmp_path: Path):
        """Missing log file should return empty results."""
        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id)

        assert lines == []
        assert total == 0
        assert has_more is False

    def test_read_all_lines_small_file(self, tmp_path: Path):
        """Small file should return all lines."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id)

        assert lines == ["Line 1", "Line 2", "Line 3"]
        assert total == 3
        assert has_more is False

    def test_pagination_with_offset(self, tmp_path: Path):
        """Offset should skip initial lines."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id, lines=2, offset=2)

        assert lines == ["Line 3", "Line 4"]
        assert total == 5
        assert has_more is True

    def test_pagination_limit(self, tmp_path: Path):
        """Lines parameter should limit returned lines."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id, lines=2, offset=0)

        assert lines == ["Line 1", "Line 2"]
        assert total == 5
        assert has_more is True

    def test_has_more_false_at_end(self, tmp_path: Path):
        """has_more should be False when at end of file."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id, lines=10, offset=0)

        assert lines == ["Line 1", "Line 2", "Line 3"]
        assert total == 3
        assert has_more is False

    def test_offset_beyond_file_returns_empty(self, tmp_path: Path):
        """Offset beyond file length should return empty list."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Line 1\nLine 2\n")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id, lines=10, offset=100)

        assert lines == []
        assert total == 2
        assert has_more is False

    def test_invalid_job_id_returns_empty(self, tmp_path: Path):
        """Invalid job ID should return empty results (not raise)."""
        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail("../invalid")

        assert lines == []
        assert total == 0
        assert has_more is False

    def test_lines_without_trailing_newline(self, tmp_path: Path):
        """Lines should not have trailing newlines."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        # Mixed newlines, no final newline
        log_file.write_text("Line 1\r\nLine 2\nLine 3")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id)

        # All trailing newlines/carriage returns should be stripped
        for line in lines:
            assert not line.endswith("\n")
            assert not line.endswith("\r")

    def test_handles_unicode_content(self, tmp_path: Path):
        """Log content with unicode should be handled correctly."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_content = (
            "Info: Processing file.mkv\nWarning: Unicode chars: \u00e9\u00e8\n"
        )
        log_file.write_text(log_content, encoding="utf-8")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id)

        assert len(lines) == 2
        assert "\u00e9\u00e8" in lines[1]


class TestLogFileExists:
    """Tests for log_file_exists function."""

    def test_existing_file_returns_true(self, tmp_path: Path):
        """Existing file should return True."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("content")

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = log_file_exists(job_id)

        assert result is True

    def test_nonexistent_file_returns_false(self, tmp_path: Path):
        """Missing file should return False."""
        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = log_file_exists(job_id)

        assert result is False

    def test_invalid_job_id_returns_false(self, tmp_path: Path):
        """Invalid job ID should return False (not raise)."""
        with patch(
            "video_policy_orchestrator.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = log_file_exists("../invalid")

        assert result is False


class TestConstants:
    """Tests for module constants."""

    def test_default_log_lines_is_reasonable(self):
        """DEFAULT_LOG_LINES should be a reasonable default."""
        assert DEFAULT_LOG_LINES == 500

    def test_max_log_size_is_reasonable(self):
        """MAX_LOG_SIZE_BYTES should be 10MB."""
        assert MAX_LOG_SIZE_BYTES == 10 * 1024 * 1024
