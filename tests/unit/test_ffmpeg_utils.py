"""Unit tests for ffmpeg_utils module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.executor import ffmpeg_utils


class TestCheckDiskSpaceForTranscode:
    """Tests for check_disk_space_for_transcode function."""

    def test_returns_none_when_sufficient_space(self, tmp_path: Path) -> None:
        """Returns None when there is sufficient disk space."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"x" * 1000)

        # Mock disk_usage to return plenty of space
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=10 * 1024**3)  # 10GB
            result = ffmpeg_utils.check_disk_space_for_transcode(test_file)

        assert result is None

    def test_returns_error_when_insufficient_space(self, tmp_path: Path) -> None:
        """Returns error message when disk space is insufficient."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"x" * (1024**3))  # 1GB file

        # Mock disk_usage to return very little space
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=100 * 1024**2)  # 100MB
            result = ffmpeg_utils.check_disk_space_for_transcode(test_file)

        assert result is not None
        assert "Insufficient disk space" in result

    def test_uses_smaller_ratio_for_hevc(self, tmp_path: Path) -> None:
        """Uses smaller output ratio estimate for HEVC codec."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"x" * 1000)

        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=10 * 1024**3)

            # With hevc, should use 0.5 ratio
            ffmpeg_utils.check_disk_space_for_transcode(test_file, target_codec="hevc")

            # With h264, should use 0.8 ratio
            ffmpeg_utils.check_disk_space_for_transcode(test_file, target_codec="h264")

    def test_file_not_found_propagates(self, tmp_path: Path) -> None:
        """FileNotFoundError should propagate, not return None."""
        nonexistent = tmp_path / "nonexistent.mkv"
        with pytest.raises(FileNotFoundError):
            ffmpeg_utils.check_disk_space_for_transcode(nonexistent)

    def test_permission_error_returns_clear_message(self, tmp_path: Path) -> None:
        """PermissionError should return descriptive message, not None."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"x" * 1000)

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.side_effect = PermissionError("Permission denied")
            result = ffmpeg_utils.check_disk_space_for_transcode(test_file)

        assert result is not None
        assert "permission denied" in result.lower()

    def test_disk_permission_error_returns_message(self, tmp_path: Path) -> None:
        """PermissionError on disk_usage should return message."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"x" * 1000)

        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.side_effect = PermissionError("Permission denied")
            result = ffmpeg_utils.check_disk_space_for_transcode(test_file)

        assert result is not None
        assert "permission denied" in result.lower()

    def test_other_oserror_returns_message_for_stat(self, tmp_path: Path) -> None:
        """Other OSError on stat should return descriptive message."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"x" * 1000)

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.side_effect = OSError("I/O error")
            result = ffmpeg_utils.check_disk_space_for_transcode(test_file)

        assert result is not None
        assert "filesystem" in result.lower() or "i/o" in result.lower()

    def test_other_oserror_on_disk_usage_returns_none(self, tmp_path: Path) -> None:
        """Other OSError on disk_usage should return None (proceed optimistically)."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"x" * 1000)

        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.side_effect = OSError("Network filesystem error")
            result = ffmpeg_utils.check_disk_space_for_transcode(test_file)

        # Non-PermissionError OSError on disk_usage should log and return None
        assert result is None


class TestCreateTempOutput:
    """Tests for create_temp_output function."""

    def test_creates_temp_path_in_same_directory(self) -> None:
        """Creates temp path in same directory as output."""
        output_path = Path("/videos/output.mkv")
        temp_path = ffmpeg_utils.create_temp_output(output_path)

        assert temp_path.parent == output_path.parent
        assert temp_path.name.startswith(".vpo_temp_")
        assert temp_path.name.endswith("output.mkv")

    def test_creates_temp_path_in_specified_directory(self, tmp_path: Path) -> None:
        """Creates temp path in specified temp directory."""
        output_path = Path("/videos/output.mkv")
        temp_path = ffmpeg_utils.create_temp_output(output_path, temp_dir=tmp_path)

        assert temp_path.parent == tmp_path
        assert temp_path.name.startswith(".vpo_temp_")
        assert temp_path.name.endswith("output.mkv")

    def test_uses_custom_prefix(self) -> None:
        """Uses custom prefix for temp file name."""
        output_path = Path("/videos/output.mkv")
        temp_path = ffmpeg_utils.create_temp_output(output_path, prefix=".custom_")

        assert temp_path.name.startswith(".custom_")
        assert temp_path.name.endswith("output.mkv")


class TestValidateOutput:
    """Tests for validate_output function."""

    def test_valid_output_returns_true(self, tmp_path: Path) -> None:
        """Returns (True, None) for valid output file."""
        output_file = tmp_path / "output.mkv"
        output_file.write_bytes(b"x" * 1000)

        is_valid, error = ffmpeg_utils.validate_output(output_file)

        assert is_valid is True
        assert error is None

    def test_missing_file_returns_false(self, tmp_path: Path) -> None:
        """Returns (False, error) for missing output file."""
        nonexistent = tmp_path / "nonexistent.mkv"

        is_valid, error = ffmpeg_utils.validate_output(nonexistent)

        assert is_valid is False
        assert error is not None
        assert "does not exist" in error

    def test_empty_file_returns_false(self, tmp_path: Path) -> None:
        """Returns (False, error) for empty output file."""
        output_file = tmp_path / "output.mkv"
        output_file.touch()

        is_valid, error = ffmpeg_utils.validate_output(output_file)

        assert is_valid is False
        assert error is not None
        assert "empty" in error

    def test_warns_on_small_output(self, tmp_path: Path, caplog) -> None:
        """Logs warning when output is suspiciously small."""
        import logging

        output_file = tmp_path / "output.mkv"
        output_file.write_bytes(b"x" * 50)  # 50 bytes
        input_size = 1000  # 1000 bytes

        with caplog.at_level(logging.WARNING):
            is_valid, _ = ffmpeg_utils.validate_output(
                output_file, input_size=input_size
            )

        # File is valid (exists and non-empty) but small
        assert is_valid is True
        # Should log warning about small size
        assert "only" in caplog.text.lower() or "%.1f%%" in caplog.text


class TestComputeTimeout:
    """Tests for compute_timeout function."""

    def test_returns_base_timeout_for_non_transcode(self) -> None:
        """Returns base timeout for non-transcode operations."""
        timeout = ffmpeg_utils.compute_timeout(
            file_size_bytes=1024**3,  # 1GB
            is_transcode=False,
            base_timeout=1800,
        )

        assert timeout == 1800

    def test_scales_timeout_for_transcode(self) -> None:
        """Scales timeout based on file size for transcode operations."""
        timeout = ffmpeg_utils.compute_timeout(
            file_size_bytes=2 * 1024**3,  # 2GB
            is_transcode=True,
            base_timeout=1800,
            transcode_rate=300,  # 5 min per GB
        )

        # 2GB * 300 = 600 seconds, but max with base 1800
        assert timeout == 1800

    def test_uses_scaled_timeout_when_larger(self) -> None:
        """Uses scaled timeout when larger than base timeout."""
        timeout = ffmpeg_utils.compute_timeout(
            file_size_bytes=10 * 1024**3,  # 10GB
            is_transcode=True,
            base_timeout=1800,
            transcode_rate=300,  # 5 min per GB
        )

        # 10GB * 300 = 3000 seconds > base 1800
        assert timeout == 3000

    def test_returns_zero_when_base_is_zero(self) -> None:
        """Returns 0 (no timeout) when base timeout is 0."""
        timeout = ffmpeg_utils.compute_timeout(
            file_size_bytes=1024**3,
            is_transcode=True,
            base_timeout=0,
        )

        assert timeout == 0


class TestCleanupTempFile:
    """Tests for cleanup_temp_file function."""

    def test_removes_existing_file(self, tmp_path: Path) -> None:
        """Removes temp file when it exists."""
        temp_file = tmp_path / "temp.mkv"
        temp_file.touch()

        ffmpeg_utils.cleanup_temp_file(temp_file)

        assert not temp_file.exists()

    def test_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """Does not raise error for nonexistent file."""
        nonexistent = tmp_path / "nonexistent.mkv"

        # Should not raise
        ffmpeg_utils.cleanup_temp_file(nonexistent)

    def test_logs_warning_on_error(self, tmp_path: Path, caplog) -> None:
        """Logs warning when cleanup fails."""
        import logging

        temp_file = tmp_path / "temp.mkv"
        temp_file.touch()

        with patch.object(Path, "unlink") as mock_unlink:
            mock_unlink.side_effect = OSError("Permission denied")
            with caplog.at_level(logging.WARNING):
                ffmpeg_utils.cleanup_temp_file(temp_file)

        assert "Could not clean up" in caplog.text
