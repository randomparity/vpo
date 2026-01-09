"""Unit tests for backup module."""

import threading
import time
from pathlib import Path

import pytest

from vpo.executor.backup import (
    BACKUP_SUFFIX,
    FileLockError,
    cleanup_backup,
    create_backup,
    file_lock,
    get_backup_path,
    has_backup,
    restore_from_backup,
)

# =============================================================================
# create_backup() Tests
# =============================================================================


class TestCreateBackup:
    """Tests for create_backup function."""

    def test_create_backup_success(self, temp_dir: Path) -> None:
        """Should create a backup file with the correct suffix."""
        original = temp_dir / "test.mkv"
        original.write_bytes(b"test content")

        backup_path = create_backup(original)

        assert backup_path.exists()
        assert backup_path == original.with_suffix(original.suffix + BACKUP_SUFFIX)
        assert backup_path.read_bytes() == b"test content"

    def test_create_backup_file_not_found(self, temp_dir: Path) -> None:
        """Should raise FileNotFoundError for non-existent file."""
        nonexistent = temp_dir / "nonexistent.mkv"

        with pytest.raises(FileNotFoundError, match="Cannot backup"):
            create_backup(nonexistent)

    def test_create_backup_replaces_existing(self, temp_dir: Path) -> None:
        """Should replace an existing backup file."""
        original = temp_dir / "test.mkv"
        original.write_bytes(b"new content")

        # Create an existing backup
        existing_backup = original.with_suffix(original.suffix + BACKUP_SUFFIX)
        existing_backup.write_bytes(b"old backup content")

        backup_path = create_backup(original)

        assert backup_path.exists()
        assert backup_path.read_bytes() == b"new content"

    def test_create_backup_preserves_metadata(self, temp_dir: Path) -> None:
        """Should preserve file metadata (using shutil.copy2)."""
        original = temp_dir / "test.mkv"
        original.write_bytes(b"test content")

        # Modify the mtime
        import os

        os.utime(original, (1000000, 1000000))

        backup_path = create_backup(original)

        # copy2 preserves mtime
        assert backup_path.stat().st_mtime == original.stat().st_mtime


# =============================================================================
# restore_from_backup() Tests
# =============================================================================


class TestRestoreFromBackup:
    """Tests for restore_from_backup function."""

    def test_restore_from_backup_success(self, temp_dir: Path) -> None:
        """Should restore original file from backup."""
        original = temp_dir / "test.mkv"
        original.write_bytes(b"original content")

        backup_path = create_backup(original)

        # Modify original
        original.write_bytes(b"corrupted content")

        # Restore
        restored_path = restore_from_backup(backup_path)

        assert restored_path == original
        assert original.read_bytes() == b"original content"
        assert not backup_path.exists()  # Backup moved, not copied

    def test_restore_from_backup_explicit_path(self, temp_dir: Path) -> None:
        """Should restore to explicitly specified path."""
        backup = temp_dir / "backup.dat"
        backup.write_bytes(b"backup content")

        target = temp_dir / "target.mkv"

        restored_path = restore_from_backup(backup, original_path=target)

        assert restored_path == target
        assert target.read_bytes() == b"backup content"
        assert not backup.exists()

    def test_restore_from_backup_not_found(self, temp_dir: Path) -> None:
        """Should raise FileNotFoundError when backup doesn't exist."""
        nonexistent = temp_dir / "nonexistent.mkv.vpo-backup"

        with pytest.raises(FileNotFoundError, match="Backup file not found"):
            restore_from_backup(nonexistent)

    def test_restore_from_backup_infer_path(self, temp_dir: Path) -> None:
        """Should correctly infer original path from backup path."""
        original = temp_dir / "test.mkv"
        original.write_bytes(b"original")
        backup_path = create_backup(original)

        # Remove original to verify restoration works
        original.unlink()

        restored_path = restore_from_backup(backup_path)

        assert restored_path == original
        assert original.exists()
        assert original.read_bytes() == b"original"

    def test_restore_from_backup_invalid_suffix(self, temp_dir: Path) -> None:
        """Should raise ValueError when backup suffix can't be parsed."""
        invalid_backup = temp_dir / "invalid_backup.dat"
        invalid_backup.write_bytes(b"data")

        with pytest.raises(ValueError, match="Cannot infer original path"):
            restore_from_backup(invalid_backup)


# =============================================================================
# cleanup_backup() Tests
# =============================================================================


class TestCleanupBackup:
    """Tests for cleanup_backup function."""

    def test_cleanup_backup_removes_file(self, temp_dir: Path) -> None:
        """Should remove the backup file."""
        backup = temp_dir / "test.mkv.vpo-backup"
        backup.write_bytes(b"backup content")

        cleanup_backup(backup)

        assert not backup.exists()

    def test_cleanup_backup_nonexistent_is_safe(self, temp_dir: Path) -> None:
        """Should not raise when backup doesn't exist."""
        nonexistent = temp_dir / "nonexistent.vpo-backup"

        # Should not raise
        cleanup_backup(nonexistent)


# =============================================================================
# get_backup_path() Tests
# =============================================================================


class TestGetBackupPath:
    """Tests for get_backup_path function."""

    def test_get_backup_path_mkv(self) -> None:
        """Should return correct backup path for MKV file."""
        original = Path("/test/video.mkv")
        backup_path = get_backup_path(original)
        assert backup_path == Path("/test/video.mkv.vpo-backup")

    def test_get_backup_path_mp4(self) -> None:
        """Should return correct backup path for MP4 file."""
        original = Path("/test/video.mp4")
        backup_path = get_backup_path(original)
        assert backup_path == Path("/test/video.mp4.vpo-backup")

    def test_get_backup_path_complex_name(self) -> None:
        """Should handle files with dots in the name."""
        original = Path("/test/video.part1.en.mkv")
        backup_path = get_backup_path(original)
        assert backup_path == Path("/test/video.part1.en.mkv.vpo-backup")


# =============================================================================
# has_backup() Tests
# =============================================================================


class TestHasBackup:
    """Tests for has_backup function."""

    def test_has_backup_true(self, temp_dir: Path) -> None:
        """Should return True when backup exists."""
        original = temp_dir / "test.mkv"
        original.touch()
        backup = get_backup_path(original)
        backup.touch()

        assert has_backup(original) is True

    def test_has_backup_false(self, temp_dir: Path) -> None:
        """Should return False when backup doesn't exist."""
        original = temp_dir / "test.mkv"
        original.touch()

        assert has_backup(original) is False


# =============================================================================
# file_lock() Tests
# =============================================================================


class TestFileLock:
    """Tests for file_lock context manager."""

    def test_file_lock_acquires_and_releases(self, temp_dir: Path) -> None:
        """Should acquire and release lock successfully."""
        test_file = temp_dir / "test.mkv"
        test_file.touch()

        # Lock should be acquired
        with file_lock(test_file):
            # Verify lock file exists during lock
            lock_path = test_file.with_suffix(test_file.suffix + ".vpo-lock")
            assert lock_path.exists()

        # Lock file should be cleaned up
        assert not lock_path.exists()

    def test_file_lock_concurrent_raises(self, temp_dir: Path) -> None:
        """Should raise FileLockError when file is already locked."""
        test_file = temp_dir / "test.mkv"
        test_file.touch()

        with file_lock(test_file):
            # Try to acquire another lock on the same file
            with pytest.raises(FileLockError, match="being modified"):
                with file_lock(test_file):
                    pass

    def test_file_lock_cleanup_on_exception(self, temp_dir: Path) -> None:
        """Should clean up lock file even on exception."""
        test_file = temp_dir / "test.mkv"
        test_file.touch()
        lock_path = test_file.with_suffix(test_file.suffix + ".vpo-lock")

        with pytest.raises(RuntimeError):
            with file_lock(test_file):
                raise RuntimeError("Test exception")

        # Lock file should be cleaned up
        assert not lock_path.exists()

    def test_file_lock_different_files(self, temp_dir: Path) -> None:
        """Should allow locking different files simultaneously."""
        file1 = temp_dir / "test1.mkv"
        file2 = temp_dir / "test2.mkv"
        file1.touch()
        file2.touch()

        with file_lock(file1):
            # Should be able to lock a different file
            with file_lock(file2):
                pass

    def test_file_lock_threaded_contention(self, temp_dir: Path) -> None:
        """Should block concurrent threads from acquiring the same lock."""
        test_file = temp_dir / "test.mkv"
        test_file.touch()

        results = []
        lock_acquired = threading.Event()

        def thread_work():
            try:
                with file_lock(test_file):
                    lock_acquired.set()
                    time.sleep(0.2)  # Hold lock for a bit
                    results.append("first")
            except FileLockError:
                results.append("failed")

        def thread_contender():
            lock_acquired.wait()  # Wait for first thread to acquire lock
            time.sleep(0.05)  # Small delay to ensure first thread has lock
            try:
                with file_lock(test_file):
                    results.append("second")
            except FileLockError:
                results.append("blocked")

        t1 = threading.Thread(target=thread_work)
        t2 = threading.Thread(target=thread_contender)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Second thread should be blocked since first thread holds lock
        assert "first" in results
        assert "blocked" in results

    def test_file_lock_does_not_delete_others_lock(self, temp_dir: Path) -> None:
        """Should not delete lock file when acquisition fails.

        This tests the fix for a race condition where a failed lock acquisition
        would delete another process's lock file in the finally block.
        """
        test_file = temp_dir / "test.mkv"
        test_file.touch()
        lock_path = test_file.with_suffix(test_file.suffix + ".vpo-lock")

        with file_lock(test_file):
            # Lock file should exist while we hold the lock
            assert lock_path.exists()

            # Another process tries to acquire - should fail but NOT delete our lock
            with pytest.raises(FileLockError):
                with file_lock(test_file):
                    pass

            # Our lock file should STILL exist after failed acquisition
            assert lock_path.exists(), (
                "Lock file was deleted by failed acquisition! "
                "This indicates the race condition fix is not working."
            )


# =============================================================================
# FileLockError Tests
# =============================================================================


class TestFileLockError:
    """Tests for FileLockError exception."""

    def test_file_lock_error_message(self) -> None:
        """Should include the file path in error message."""
        msg = "File is being modified by another operation: /test/file.mkv"
        error = FileLockError(msg)
        assert "/test/file.mkv" in str(error)

    def test_file_lock_error_is_exception(self) -> None:
        """FileLockError should be an Exception."""
        error = FileLockError("test")
        assert isinstance(error, Exception)
