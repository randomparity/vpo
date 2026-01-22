"""Tests for vpo.core.file_utils module."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from vpo.core.file_utils import copy_file_mtime, get_file_mtime, set_file_mtime


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
        """Should raise FileNotFoundError for missing file."""
        missing_file = tmp_path / "missing.txt"

        with pytest.raises(FileNotFoundError):
            get_file_mtime(missing_file)


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
        """Should raise FileNotFoundError for missing file."""
        missing_file = tmp_path / "missing.txt"

        with pytest.raises(FileNotFoundError):
            set_file_mtime(missing_file, 1577836800.0)


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
        """Should raise FileNotFoundError for missing source."""
        target = tmp_path / "target.txt"
        target.write_text("content")
        missing_source = tmp_path / "missing.txt"

        with pytest.raises(FileNotFoundError):
            copy_file_mtime(missing_source, target)

    def test_raises_on_missing_target(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing target."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        missing_target = tmp_path / "missing.txt"

        with pytest.raises(FileNotFoundError):
            copy_file_mtime(source, missing_target)
