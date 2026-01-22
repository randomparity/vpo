"""Tests for vpo.core.file_utils module."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from vpo.core.file_utils import (
    FileTimestampError,
    copy_file_mtime,
    get_file_mtime,
    set_file_mtime,
)


class TestGetFileMtime:
    """Tests for get_file_mtime function."""

    def test_returns_float_timestamp(self, tmp_path: Path) -> None:
        """Should return modification time as float."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = get_file_mtime(test_file)

        assert isinstance(result, float)
        # Should be recent (within last minute)
        assert time.time() - result < 60

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """Should raise FileTimestampError for missing file."""
        missing_file = tmp_path / "missing.txt"

        with pytest.raises(FileTimestampError) as exc_info:
            get_file_mtime(missing_file)

        assert "file not found" in str(exc_info.value)
        assert str(missing_file) in str(exc_info.value)


class TestSetFileMtime:
    """Tests for set_file_mtime function."""

    def test_sets_modification_time(self, tmp_path: Path) -> None:
        """Should set file modification time."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Set to a specific time (2020-01-01 00:00:00 UTC)
        target_mtime = 1577836800.0
        set_file_mtime(test_file, target_mtime)

        result = get_file_mtime(test_file)
        assert abs(result - target_mtime) < 1.0  # Allow 1 second tolerance

    def test_preserves_access_time(self, tmp_path: Path) -> None:
        """Should preserve access time when setting mtime."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Get original access time
        stat_before = test_file.stat()
        original_atime = stat_before.st_atime

        # Set mtime to different value
        set_file_mtime(test_file, 1577836800.0)

        # Check access time is preserved (within tolerance)
        stat_after = test_file.stat()
        assert abs(stat_after.st_atime - original_atime) < 1.0

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """Should raise FileTimestampError for missing file."""
        missing_file = tmp_path / "missing.txt"

        with pytest.raises(FileTimestampError) as exc_info:
            set_file_mtime(missing_file, 1577836800.0)

        assert "file not found" in str(exc_info.value)
        assert str(missing_file) in str(exc_info.value)


class TestCopyFileMtime:
    """Tests for copy_file_mtime function."""

    def test_copies_mtime_from_source(self, tmp_path: Path) -> None:
        """Should copy modification time from source to target."""
        source = tmp_path / "source.txt"
        target = tmp_path / "target.txt"
        source.write_text("source content")
        target.write_text("target content")

        # Set source to specific time
        source_mtime = 1577836800.0
        set_file_mtime(source, source_mtime)

        # Copy mtime to target
        copy_file_mtime(source, target)

        target_mtime = get_file_mtime(target)
        assert abs(target_mtime - source_mtime) < 1.0

    def test_raises_on_missing_source(self, tmp_path: Path) -> None:
        """Should raise FileTimestampError for missing source."""
        target = tmp_path / "target.txt"
        target.write_text("content")
        missing_source = tmp_path / "missing.txt"

        with pytest.raises(FileTimestampError):
            copy_file_mtime(missing_source, target)

    def test_raises_on_missing_target(self, tmp_path: Path) -> None:
        """Should raise FileTimestampError for missing target."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        missing_target = tmp_path / "missing.txt"

        with pytest.raises(FileTimestampError):
            copy_file_mtime(source, missing_target)


class TestTimestampBoundsValidation:
    """Tests for timestamp bounds validation in set_file_mtime."""

    def test_rejects_negative_timestamp(self, tmp_path: Path) -> None:
        """Should reject timestamp before Unix epoch."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with pytest.raises(FileTimestampError) as exc_info:
            set_file_mtime(test_file, -1.0)

        assert "before Unix epoch" in str(exc_info.value)

    def test_rejects_far_future_timestamp(self, tmp_path: Path) -> None:
        """Should reject timestamp more than 100 years in the future."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # 200 years from now
        far_future = time.time() + (200 * 365.25 * 24 * 60 * 60)

        with pytest.raises(FileTimestampError) as exc_info:
            set_file_mtime(test_file, far_future)

        assert "100 years" in str(exc_info.value)

    def test_accepts_valid_past_timestamp(self, tmp_path: Path) -> None:
        """Should accept valid timestamp in the past."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # 2000-01-01 00:00:00 UTC
        y2k_timestamp = 946684800.0
        set_file_mtime(test_file, y2k_timestamp)

        result = get_file_mtime(test_file)
        assert abs(result - y2k_timestamp) < 1.0

    def test_accepts_epoch_timestamp(self, tmp_path: Path) -> None:
        """Should accept Unix epoch timestamp (0)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        set_file_mtime(test_file, 0.0)

        result = get_file_mtime(test_file)
        assert abs(result - 0.0) < 1.0


class TestContextualErrorMessages:
    """Tests for contextual error messages in file operations."""

    def test_get_mtime_file_not_found_includes_path(self, tmp_path: Path) -> None:
        """get_file_mtime error should include file path."""
        missing = tmp_path / "nonexistent.mkv"

        with pytest.raises(FileTimestampError) as exc_info:
            get_file_mtime(missing)

        error_msg = str(exc_info.value)
        assert "nonexistent.mkv" in error_msg
        assert "file not found" in error_msg.lower()

    def test_set_mtime_permission_error_includes_guidance(self, tmp_path: Path) -> None:
        """set_file_mtime permission error should include recovery guidance."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("os.utime", side_effect=PermissionError("Permission denied")):
            with pytest.raises(FileTimestampError) as exc_info:
                set_file_mtime(test_file, 1577836800.0)

        error_msg = str(exc_info.value)
        assert "permission denied" in error_msg.lower()
        # Should include recovery guidance
        assert "permission" in error_msg.lower() or "privileges" in error_msg.lower()
