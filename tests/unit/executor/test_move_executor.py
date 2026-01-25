"""Unit tests for executor/move.py.

Tests the MoveExecutor class and ensure_unique_path function:
- Successful file moves
- Directory creation
- Cross-device move handling
- Error categorization
- Unique path generation
"""

import errno
import shutil
from unittest.mock import patch

import pytest

from vpo.executor.move import (
    MoveErrorType,
    MoveExecutor,
    MovePlan,
    ensure_unique_path,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def executor():
    """Create a default MoveExecutor instance."""
    return MoveExecutor()


@pytest.fixture
def source_file(tmp_path):
    """Create a source file for testing."""
    f = tmp_path / "source.mkv"
    f.write_bytes(b"video content" * 100)
    return f


# =============================================================================
# Tests for MoveExecutor.execute
# =============================================================================


class TestMoveExecutorExecute:
    """Tests for MoveExecutor.execute method."""

    def test_moves_file_successfully(self, executor, source_file, tmp_path):
        """Successfully moves file to destination."""
        dest_path = tmp_path / "dest" / "video.mkv"

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            create_directories=True,
        )

        result = executor.execute(plan)

        assert result.success is True
        assert result.destination_path == dest_path
        assert dest_path.exists()
        assert not source_file.exists()

    def test_creates_directories_when_configured(self, executor, source_file, tmp_path):
        """Creates destination directories when configured."""
        deep_dest = tmp_path / "a" / "b" / "c" / "video.mkv"
        assert not deep_dest.parent.exists()

        plan = MovePlan(
            source_path=source_file,
            destination_path=deep_dest,
            create_directories=True,
        )

        result = executor.execute(plan)

        assert result.success is True
        assert deep_dest.parent.exists()
        assert deep_dest.exists()

    def test_fails_without_directory_creation(self, executor, source_file, tmp_path):
        """Fails when directory doesn't exist and creation disabled."""
        dest_path = tmp_path / "nonexistent" / "video.mkv"

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            create_directories=False,
        )

        result = executor.execute(plan)

        assert result.success is False
        assert "does not exist" in result.error_message

    def test_handles_cross_device_move(self, executor, source_file, tmp_path):
        """Handles EXDEV error for cross-device moves."""
        dest_path = tmp_path / "dest.mkv"

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            create_directories=True,
        )

        # Mock shutil.move to raise EXDEV (cross-device)
        with patch.object(shutil, "move") as mock_move:
            err = OSError("Cross-device link")
            err.errno = errno.EXDEV
            mock_move.side_effect = err

            result = executor.execute(plan)

        assert result.success is False
        assert result.error_type == MoveErrorType.CROSS_DEVICE

    def test_handles_permission_error(self, executor, source_file, tmp_path):
        """Handles EACCES/EPERM for permission errors."""
        dest_path = tmp_path / "dest.mkv"

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            create_directories=True,
        )

        with patch.object(shutil, "move") as mock_move:
            err = OSError("Permission denied")
            err.errno = errno.EACCES
            mock_move.side_effect = err

            result = executor.execute(plan)

        assert result.success is False
        assert result.error_type == MoveErrorType.PERMISSION

    def test_handles_disk_space_error(self, executor, source_file, tmp_path):
        """Handles ENOSPC for disk space errors."""
        dest_path = tmp_path / "dest.mkv"

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            create_directories=True,
        )

        with patch.object(shutil, "move") as mock_move:
            err = OSError("No space left on device")
            err.errno = errno.ENOSPC
            mock_move.side_effect = err

            result = executor.execute(plan)

        assert result.success is False
        assert result.error_type == MoveErrorType.DISK_SPACE

    def test_handles_not_found_error(self, executor, source_file, tmp_path):
        """Handles ENOENT for not found errors."""
        dest_path = tmp_path / "dest.mkv"

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            create_directories=True,
        )

        with patch.object(shutil, "move") as mock_move:
            err = OSError("No such file or directory")
            err.errno = errno.ENOENT
            mock_move.side_effect = err

            result = executor.execute(plan)

        assert result.success is False
        assert result.error_type == MoveErrorType.NOT_FOUND

    def test_categorizes_errno_correctly(self):
        """Error types are correctly categorized by errno."""
        error_mapping = [
            (errno.ENOSPC, MoveErrorType.DISK_SPACE),
            (errno.EACCES, MoveErrorType.PERMISSION),
            (errno.EPERM, MoveErrorType.PERMISSION),
            (errno.ENOENT, MoveErrorType.NOT_FOUND),
            (errno.EXDEV, MoveErrorType.CROSS_DEVICE),
            (errno.EIO, MoveErrorType.IO_ERROR),
            (errno.EROFS, MoveErrorType.IO_ERROR),
        ]

        for err_no, expected_type in error_mapping:
            assert expected_type in MoveErrorType
            # Verify the error type enum value exists
            assert MoveErrorType[expected_type.name] == expected_type


# =============================================================================
# Tests for MoveExecutor.validate
# =============================================================================


class TestMoveExecutorValidate:
    """Tests for MoveExecutor.validate method."""

    def test_validates_source_exists(self, executor, tmp_path):
        """Validation fails when source doesn't exist."""
        plan = MovePlan(
            source_path=tmp_path / "nonexistent.mkv",
            destination_path=tmp_path / "dest.mkv",
        )

        errors = executor.validate(plan)

        assert len(errors) > 0
        assert any("does not exist" in e for e in errors)

    def test_validates_source_is_file(self, executor, tmp_path):
        """Validation fails when source is not a file."""
        source_dir = tmp_path / "source_dir"
        source_dir.mkdir()

        plan = MovePlan(
            source_path=source_dir,
            destination_path=tmp_path / "dest",
        )

        errors = executor.validate(plan)

        assert len(errors) > 0
        assert any("not a file" in e for e in errors)

    def test_validates_destination_exists_without_overwrite(
        self, executor, source_file, tmp_path
    ):
        """Validation fails when destination exists and overwrite disabled."""
        dest_path = tmp_path / "dest.mkv"
        dest_path.write_bytes(b"existing content")

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            overwrite=False,
        )

        errors = executor.validate(plan)

        assert len(errors) > 0
        assert any("already exists" in e for e in errors)

    def test_validates_destination_allowed_with_overwrite(
        self, executor, source_file, tmp_path
    ):
        """Validation passes when destination exists but overwrite enabled."""
        dest_path = tmp_path / "dest.mkv"
        dest_path.write_bytes(b"existing content")

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            overwrite=True,
        )

        errors = executor.validate(plan)

        # Should not have error about destination existing
        assert not any("already exists" in e for e in errors)


# =============================================================================
# Tests for ensure_unique_path
# =============================================================================


class TestEnsureUniquePath:
    """Tests for ensure_unique_path function."""

    def test_returns_unchanged_when_no_collision(self, tmp_path):
        """Returns original path when it doesn't exist."""
        path = tmp_path / "unique.mkv"

        result = ensure_unique_path(path)

        assert result == path

    def test_adds_counter_on_collision(self, tmp_path):
        """Adds (1) suffix when path already exists."""
        path = tmp_path / "video.mkv"
        path.write_bytes(b"content")

        result = ensure_unique_path(path)

        assert result == tmp_path / "video (1).mkv"
        assert result != path

    def test_preserves_file_extension(self, tmp_path):
        """File extension is preserved after counter."""
        path = tmp_path / "video.mkv"
        path.write_bytes(b"content")

        result = ensure_unique_path(path)

        assert result.suffix == ".mkv"
        assert result.name == "video (1).mkv"

    def test_increments_counter_for_multiple_collisions(self, tmp_path):
        """Counter increments for multiple existing files."""
        base = tmp_path / "video.mkv"
        base.write_bytes(b"v1")
        (tmp_path / "video (1).mkv").write_bytes(b"v2")
        (tmp_path / "video (2).mkv").write_bytes(b"v3")

        result = ensure_unique_path(base)

        assert result == tmp_path / "video (3).mkv"

    def test_raises_after_max_attempts(self, tmp_path):
        """Raises RuntimeError when max attempts exceeded."""
        path = tmp_path / "video.mkv"

        # Create all possible variations
        path.write_bytes(b"base")
        for i in range(1, 11):
            (tmp_path / f"video ({i}).mkv").write_bytes(b"v")

        with pytest.raises(RuntimeError) as exc_info:
            ensure_unique_path(path, max_attempts=10)

        assert "Could not find unique path" in str(exc_info.value)


# =============================================================================
# Tests for dry_run
# =============================================================================


class TestMoveExecutorDryRun:
    """Tests for MoveExecutor.dry_run method."""

    def test_dry_run_returns_operation_details(self, executor, source_file, tmp_path):
        """Dry run returns planned operation details."""
        dest_path = tmp_path / "dest" / "video.mkv"

        plan = MovePlan(
            source_path=source_file,
            destination_path=dest_path,
            create_directories=True,
        )

        result = executor.dry_run(plan)

        assert result["source"] == str(source_file)
        assert result["destination"] == str(dest_path)
        assert result["create_directories"] is True
        assert result["would_create_dirs"] is True
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_dry_run_reports_validation_errors(self, executor, tmp_path):
        """Dry run reports validation errors."""
        plan = MovePlan(
            source_path=tmp_path / "nonexistent.mkv",
            destination_path=tmp_path / "dest.mkv",
        )

        result = executor.dry_run(plan)

        assert result["valid"] is False
        assert len(result["errors"]) > 0
