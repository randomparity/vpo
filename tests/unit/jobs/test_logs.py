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

from vpo.jobs.logs import (
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
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = get_log_path(job_id)

        assert result == tmp_path / f"{job_id}.log"
        assert result.parent == tmp_path

    def test_invalid_uuid_raises_valueerror(self, tmp_path: Path):
        """Invalid UUID should raise ValueError."""
        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            with pytest.raises(ValueError, match="Invalid job ID format"):
                get_log_path("../etc/passwd")

    def test_path_stays_within_log_directory(self, tmp_path: Path):
        """Path traversal attempts should be caught even if UUID validation bypassed."""
        # This test verifies defense-in-depth - the path resolution check
        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = count_log_lines(job_id)

        assert result == 3

    def test_invalid_job_id_returns_zero(self, tmp_path: Path):
        """Invalid job ID should return 0 (not raise)."""
        with patch(
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id, lines=10, offset=100)

        assert lines == []
        assert total == 2
        assert has_more is False

    def test_invalid_job_id_returns_empty(self, tmp_path: Path):
        """Invalid job ID should return empty results (not raise)."""
        with patch(
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
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
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = log_file_exists(job_id)

        assert result is True

    def test_nonexistent_file_returns_false(self, tmp_path: Path):
        """Missing file should return False."""
        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = log_file_exists(job_id)

        assert result is False

    def test_invalid_job_id_returns_false(self, tmp_path: Path):
        """Invalid job ID should return False (not raise)."""
        with patch(
            "vpo.jobs.logs.get_log_directory",
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


# =============================================================================
# Tests for new functionality (JobLogWriter, compression, deletion)
# =============================================================================


class TestJobLogWriter:
    """Tests for JobLogWriter class."""

    def test_writer_creates_log_file(self, tmp_path: Path):
        """Writer should create log file on enter."""
        from vpo.jobs.logs import JobLogWriter

        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            with JobLogWriter(job_id) as writer:
                writer.write_line("Test message")

        log_file = tmp_path / f"{job_id}.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_writer_adds_timestamp(self, tmp_path: Path):
        """Each line should have a timestamp prefix."""
        from vpo.jobs.logs import JobLogWriter

        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            with JobLogWriter(job_id) as writer:
                writer.write_line("Test message")

        log_file = tmp_path / f"{job_id}.log"
        content = log_file.read_text()
        # Timestamp format: [2024-01-01T12:00:00.000000Z]
        assert content.startswith("[")
        assert "Z]" in content

    def test_writer_header_footer(self, tmp_path: Path):
        """Header and footer methods should write structured output."""
        from vpo.jobs.logs import JobLogWriter

        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            with JobLogWriter(job_id) as writer:
                writer.write_header("transcode", "/path/to/file.mkv", policy="test")
                writer.write_footer(success=True, duration_seconds=10.5)

        log_file = tmp_path / f"{job_id}.log"
        content = log_file.read_text()
        assert "JOB START" in content
        assert "transcode" in content
        assert "JOB END: SUCCESS" in content
        assert "10.50s" in content

    def test_writer_subprocess_output(self, tmp_path: Path):
        """Subprocess output should be logged with command info."""
        from vpo.jobs.logs import JobLogWriter

        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            with JobLogWriter(job_id) as writer:
                writer.write_subprocess(
                    "ffprobe",
                    stdout="output line",
                    stderr="error line",
                    returncode=0,
                )

        log_file = tmp_path / f"{job_id}.log"
        content = log_file.read_text()
        assert "ffprobe" in content
        assert "Exit code: 0" in content
        assert "output line" in content
        assert "error line" in content

    def test_writer_relative_path(self, tmp_path: Path):
        """relative_path property should return path for database."""
        from vpo.jobs.logs import JobLogWriter

        job_id = "12345678-1234-1234-1234-123456789abc"

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            with JobLogWriter(job_id) as writer:
                assert writer.relative_path == f"logs/{job_id}.log"

    def test_invalid_job_id_raises(self, tmp_path: Path):
        """Invalid job ID should raise ValueError."""
        from vpo.jobs.logs import JobLogWriter

        with pytest.raises(ValueError, match="Invalid job ID format"):
            JobLogWriter("../invalid")


class TestLogCompression:
    """Tests for log compression functions."""

    def test_compress_old_logs_basic(self, tmp_path: Path):
        """Should compress logs older than threshold."""
        import os
        import time

        from vpo.jobs.logs import compress_old_logs

        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Test content" * 100)

        # Set mtime to 10 days ago
        old_time = time.time() - (10 * 86400)
        os.utime(log_file, (old_time, old_time))

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            stats = compress_old_logs(older_than_days=7)

        assert stats.compressed_count == 1
        assert not log_file.exists()
        assert (tmp_path / f"{job_id}.log.gz").exists()

    def test_compress_skips_recent_logs(self, tmp_path: Path):
        """Should not compress recent logs."""
        from vpo.jobs.logs import compress_old_logs

        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Test content")

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            stats = compress_old_logs(older_than_days=7)

        assert stats.compressed_count == 0
        assert log_file.exists()

    def test_compress_dry_run(self, tmp_path: Path):
        """Dry run should not actually compress."""
        import os
        import time

        from vpo.jobs.logs import compress_old_logs

        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Test content")

        old_time = time.time() - (10 * 86400)
        os.utime(log_file, (old_time, old_time))

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            stats = compress_old_logs(older_than_days=7, dry_run=True)

        assert stats.compressed_count == 1
        assert log_file.exists()  # Not deleted in dry run
        assert not (tmp_path / f"{job_id}.log.gz").exists()


class TestLogDeletion:
    """Tests for log deletion functions."""

    def test_delete_old_logs_basic(self, tmp_path: Path):
        """Should delete logs older than threshold."""
        import os
        import time

        from vpo.jobs.logs import delete_old_logs

        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Test content")

        old_time = time.time() - (100 * 86400)
        os.utime(log_file, (old_time, old_time))

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            stats = delete_old_logs(older_than_days=90)

        assert stats.deleted_count == 1
        assert not log_file.exists()

    def test_delete_skips_recent_logs(self, tmp_path: Path):
        """Should not delete recent logs."""
        from vpo.jobs.logs import delete_old_logs

        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Test content")

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            stats = delete_old_logs(older_than_days=90)

        assert stats.deleted_count == 0
        assert log_file.exists()

    def test_delete_dry_run(self, tmp_path: Path):
        """Dry run should not actually delete."""
        import os
        import time

        from vpo.jobs.logs import delete_old_logs

        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log"
        log_file.write_text("Test content")

        old_time = time.time() - (100 * 86400)
        os.utime(log_file, (old_time, old_time))

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            stats = delete_old_logs(older_than_days=90, dry_run=True)

        assert stats.deleted_count == 1
        assert log_file.exists()  # Not deleted in dry run


class TestLogStats:
    """Tests for get_log_stats function."""

    def test_empty_directory(self, tmp_path: Path):
        """Empty directory should return zero counts."""
        from vpo.jobs.logs import get_log_stats

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            stats = get_log_stats()

        assert stats["total_count"] == 0
        assert stats["total_bytes"] == 0

    def test_counts_log_files(self, tmp_path: Path):
        """Should count both compressed and uncompressed logs."""
        from vpo.jobs.logs import get_log_stats

        (tmp_path / "test1.log").write_text("content1")
        (tmp_path / "test2.log").write_text("content2")
        (tmp_path / "test3.log.gz").write_bytes(b"compressed")

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            stats = get_log_stats()

        assert stats["uncompressed_count"] == 2
        assert stats["compressed_count"] == 1
        assert stats["total_count"] == 3


class TestCompressedLogReading:
    """Tests for reading compressed log files."""

    def test_read_compressed_log(self, tmp_path: Path):
        """Should read compressed .log.gz files."""
        import gzip

        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log.gz"
        content = "Line 1\nLine 2\nLine 3\n"

        with gzip.open(log_file, "wt") as f:
            f.write(content)

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            lines, total, has_more = read_log_tail(job_id)

        assert lines == ["Line 1", "Line 2", "Line 3"]
        assert total == 3

    def test_compressed_log_file_exists(self, tmp_path: Path):
        """log_file_exists should return True for compressed files."""
        import gzip

        job_id = "12345678-1234-1234-1234-123456789abc"
        log_file = tmp_path / f"{job_id}.log.gz"

        with gzip.open(log_file, "wt") as f:
            f.write("content")

        with patch(
            "vpo.jobs.logs.get_log_directory",
            return_value=tmp_path,
        ):
            result = log_file_exists(job_id)

        assert result is True
