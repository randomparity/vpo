"""Tests for server cleanup utilities."""

import time
from pathlib import Path

from vpo.server.cleanup import cleanup_orphaned_temp_files


class TestCleanupOrphanedTempFiles:
    """Tests for cleanup_orphaned_temp_files function."""

    def test_removes_old_vpo_temp_files(self, tmp_path: Path):
        """cleanup_orphaned_temp_files removes old .vpo_temp_* files."""
        temp_file = tmp_path / ".vpo_temp_abc123.mkv"
        temp_file.touch()
        # Make file appear old by setting mtime to 2 hours ago
        old_mtime = time.time() - 7200
        import os

        os.utime(temp_file, (old_mtime, old_mtime))

        cleaned = cleanup_orphaned_temp_files([tmp_path], max_age_hours=1.0)

        assert cleaned == 1
        assert not temp_file.exists()

    def test_removes_old_passlog_files(self, tmp_path: Path):
        """cleanup_orphaned_temp_files removes old vpo_passlog_* files."""
        passlog = tmp_path / "vpo_passlog_abc123.log"
        passlog.touch()
        # Make file appear old
        old_mtime = time.time() - 7200
        import os

        os.utime(passlog, (old_mtime, old_mtime))

        cleaned = cleanup_orphaned_temp_files([tmp_path], max_age_hours=1.0)

        assert cleaned == 1
        assert not passlog.exists()

    def test_preserves_recent_temp_files(self, tmp_path: Path):
        """cleanup_orphaned_temp_files preserves recently-modified files."""
        temp_file = tmp_path / ".vpo_temp_recent.mkv"
        temp_file.touch()
        # File is freshly created, mtime is now

        cleaned = cleanup_orphaned_temp_files([tmp_path], max_age_hours=1.0)

        assert cleaned == 0
        assert temp_file.exists()

    def test_preserves_non_temp_files(self, tmp_path: Path):
        """cleanup_orphaned_temp_files preserves files not matching patterns."""
        regular_file = tmp_path / "movie.mkv"
        regular_file.touch()
        # Make it old
        old_mtime = time.time() - 7200
        import os

        os.utime(regular_file, (old_mtime, old_mtime))

        cleaned = cleanup_orphaned_temp_files([tmp_path], max_age_hours=1.0)

        assert cleaned == 0
        assert regular_file.exists()

    def test_searches_nested_directories(self, tmp_path: Path):
        """cleanup_orphaned_temp_files searches recursively."""
        nested_dir = tmp_path / "subdir" / "nested"
        nested_dir.mkdir(parents=True)
        temp_file = nested_dir / ".vpo_temp_nested.mkv"
        temp_file.touch()
        # Make it old
        old_mtime = time.time() - 7200
        import os

        os.utime(temp_file, (old_mtime, old_mtime))

        cleaned = cleanup_orphaned_temp_files([tmp_path], max_age_hours=1.0)

        assert cleaned == 1
        assert not temp_file.exists()

    def test_handles_nonexistent_directory(self, tmp_path: Path):
        """cleanup_orphaned_temp_files handles non-existent search directory."""
        nonexistent = tmp_path / "does_not_exist"

        cleaned = cleanup_orphaned_temp_files([nonexistent], max_age_hours=1.0)

        assert cleaned == 0

    def test_searches_multiple_directories(self, tmp_path: Path):
        """cleanup_orphaned_temp_files searches multiple directories."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        temp1 = dir1 / ".vpo_temp_1.mkv"
        temp2 = dir2 / ".vpo_temp_2.mkv"
        temp1.touch()
        temp2.touch()

        # Make both old
        old_mtime = time.time() - 7200
        import os

        os.utime(temp1, (old_mtime, old_mtime))
        os.utime(temp2, (old_mtime, old_mtime))

        cleaned = cleanup_orphaned_temp_files([dir1, dir2], max_age_hours=1.0)

        assert cleaned == 2
        assert not temp1.exists()
        assert not temp2.exists()

    def test_custom_max_age_hours(self, tmp_path: Path):
        """cleanup_orphaned_temp_files respects custom max_age_hours."""
        temp_file = tmp_path / ".vpo_temp_test.mkv"
        temp_file.touch()
        # Make file 30 minutes old
        old_mtime = time.time() - 1800
        import os

        os.utime(temp_file, (old_mtime, old_mtime))

        # With 1 hour threshold, should preserve
        cleaned_1h = cleanup_orphaned_temp_files([tmp_path], max_age_hours=1.0)
        assert cleaned_1h == 0
        assert temp_file.exists()

        # With 0.25 hour (15 min) threshold, should remove
        cleaned_15m = cleanup_orphaned_temp_files([tmp_path], max_age_hours=0.25)
        assert cleaned_15m == 1
        assert not temp_file.exists()

    def test_skips_directories_matching_pattern(self, tmp_path: Path):
        """cleanup_orphaned_temp_files skips directories matching temp patterns."""
        # Create a directory that matches the pattern (edge case)
        temp_dir = tmp_path / ".vpo_temp_dir"
        temp_dir.mkdir()
        # Make it old
        old_mtime = time.time() - 7200
        import os

        os.utime(temp_dir, (old_mtime, old_mtime))

        cleaned = cleanup_orphaned_temp_files([tmp_path], max_age_hours=1.0)

        assert cleaned == 0
        assert temp_dir.exists()  # Directory should not be deleted

    def test_returns_total_count(self, tmp_path: Path):
        """cleanup_orphaned_temp_files returns total number of files cleaned."""
        # Create multiple temp files
        for i in range(5):
            temp_file = tmp_path / f".vpo_temp_{i}.mkv"
            temp_file.touch()
            old_mtime = time.time() - 7200
            import os

            os.utime(temp_file, (old_mtime, old_mtime))

        cleaned = cleanup_orphaned_temp_files([tmp_path], max_age_hours=1.0)

        assert cleaned == 5
