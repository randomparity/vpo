"""Tests for backup module disk space checks."""

from pathlib import Path
from unittest.mock import patch

from vpo.executor.backup import check_min_free_disk_percent


class TestCheckMinFreeDiskPercent:
    """Tests for check_min_free_disk_percent function."""

    def test_returns_none_when_disabled(self, tmp_path: Path) -> None:
        """When min_free_percent is 0, check is disabled."""
        result = check_min_free_disk_percent(
            directory=tmp_path,
            required_bytes=1_000_000_000,  # 1 GB
            min_free_percent=0.0,
        )
        assert result is None

    def test_returns_none_when_plenty_of_space(self, tmp_path: Path) -> None:
        """When plenty of space available, returns None."""
        # Mock disk_usage to report 100GB total, 50GB free
        mock_usage = type(
            "usage", (), {"total": 100_000_000_000, "free": 50_000_000_000}
        )()

        with patch("vpo.executor.backup.shutil.disk_usage", return_value=mock_usage):
            result = check_min_free_disk_percent(
                directory=tmp_path,
                required_bytes=1_000_000_000,  # 1 GB
                min_free_percent=5.0,
            )
        assert result is None

    def test_returns_error_when_threshold_violated(self, tmp_path: Path) -> None:
        """When operation would violate threshold, returns error message."""
        # Mock disk_usage to report 100GB total, 6GB free
        # Operation needs 2GB, so post-op would be 4% (below 5% threshold)
        mock_usage = type(
            "usage", (), {"total": 100_000_000_000, "free": 6_000_000_000}
        )()

        with patch("vpo.executor.backup.shutil.disk_usage", return_value=mock_usage):
            result = check_min_free_disk_percent(
                directory=tmp_path,
                required_bytes=2_000_000_000,  # 2 GB
                min_free_percent=5.0,
            )

        assert result is not None
        assert "4.0%" in result
        assert "threshold: 5.0%" in result

    def test_handles_permission_error_gracefully(self, tmp_path: Path) -> None:
        """Permission errors should return None (allow operation to proceed)."""
        with patch(
            "vpo.executor.backup.shutil.disk_usage",
            side_effect=PermissionError("Access denied"),
        ):
            result = check_min_free_disk_percent(
                directory=tmp_path,
                required_bytes=1_000_000_000,
                min_free_percent=5.0,
            )
        assert result is None

    def test_handles_os_error_gracefully(self, tmp_path: Path) -> None:
        """OS errors should return None (allow operation to proceed)."""
        with patch(
            "vpo.executor.backup.shutil.disk_usage",
            side_effect=OSError("Disk not found"),
        ):
            result = check_min_free_disk_percent(
                directory=tmp_path,
                required_bytes=1_000_000_000,
                min_free_percent=5.0,
            )
        assert result is None

    def test_high_threshold_triggers_warning(self, tmp_path: Path) -> None:
        """High threshold values should work correctly."""
        # Mock disk_usage to report 100GB total, 80GB free
        # With 99% threshold, even 80% free should trigger warning
        mock_usage = type(
            "usage", (), {"total": 100_000_000_000, "free": 80_000_000_000}
        )()

        with patch("vpo.executor.backup.shutil.disk_usage", return_value=mock_usage):
            result = check_min_free_disk_percent(
                directory=tmp_path,
                required_bytes=0,  # No space needed
                min_free_percent=99.0,
            )

        assert result is not None
        assert "threshold: 99.0%" in result

    def test_exact_threshold_is_ok(self, tmp_path: Path) -> None:
        """Exactly at threshold should be OK (not below)."""
        # Mock disk_usage to report 100GB total, 10GB free
        # Operation needs 5GB, so post-op would be exactly 5%
        mock_usage = type(
            "usage", (), {"total": 100_000_000_000, "free": 10_000_000_000}
        )()

        with patch("vpo.executor.backup.shutil.disk_usage", return_value=mock_usage):
            result = check_min_free_disk_percent(
                directory=tmp_path,
                required_bytes=5_000_000_000,  # 5 GB
                min_free_percent=5.0,  # Would leave exactly 5%
            )

        assert result is None  # Should pass

    def test_negative_post_operation_space_handled(self, tmp_path: Path) -> None:
        """When operation needs more space than available, handle gracefully."""
        # Mock disk_usage to report 100GB total, 1GB free
        # Operation needs 10GB (more than available)
        mock_usage = type(
            "usage", (), {"total": 100_000_000_000, "free": 1_000_000_000}
        )()

        with patch("vpo.executor.backup.shutil.disk_usage", return_value=mock_usage):
            result = check_min_free_disk_percent(
                directory=tmp_path,
                required_bytes=10_000_000_000,  # 10 GB (more than free)
                min_free_percent=5.0,
            )

        assert result is not None
        # Post-operation free should be reported as 0%
        assert "0.0% free disk space" in result

    def test_zero_total_disk_handled_gracefully(self, tmp_path: Path) -> None:
        """Pseudo-filesystems with zero total size should not crash."""
        # Mock disk_usage to report 0 total (can occur on pseudo-filesystems)
        mock_usage = type("usage", (), {"total": 0, "free": 0})()

        with patch("vpo.executor.backup.shutil.disk_usage", return_value=mock_usage):
            result = check_min_free_disk_percent(
                directory=tmp_path,
                required_bytes=1_000_000,
                min_free_percent=5.0,
            )

        # Should return None (allow operation to proceed) rather than crash
        assert result is None
