"""Tests for WorkflowProcessor disk space pre-flight checks."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from vpo.executor.backup import InsufficientDiskSpaceError
from vpo.policy.types import (
    GlobalConfig,
    PhaseDefinition,
    PhaseResult,
    PolicySchema,
)
from vpo.workflow.processor import WorkflowProcessor


def make_mock_phase_result() -> PhaseResult:
    """Create a minimal PhaseResult for testing."""
    return PhaseResult(
        phase_name="test",
        success=True,
        duration_seconds=0.1,
        operations_executed=(),
        changes_made=0,
    )


def make_minimal_policy() -> PolicySchema:
    """Create a minimal policy for testing."""
    return PolicySchema(
        schema_version=12,
        phases=(
            PhaseDefinition(
                name="test",
                conditional=None,
                transcription=None,
                transcode=None,
                container=None,
            ),
        ),
        config=GlobalConfig(),
    )


class TestWorkflowProcessorDiskCheck:
    """Tests for pre-flight disk space check in WorkflowProcessor."""

    def test_disk_check_runs_before_processing(self, tmp_path: Path) -> None:
        """Pre-flight disk check should run before any processing."""
        # Create a test file
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"\x00" * 1000)  # 1KB file

        conn = MagicMock(spec=sqlite3.Connection)
        policy = make_minimal_policy()

        processor = WorkflowProcessor(
            conn=conn,
            policy=policy,
            dry_run=False,
        )

        # Mock the disk check to raise an error
        with patch.object(
            processor,
            "_check_min_free_disk_threshold",
            side_effect=InsufficientDiskSpaceError("Disk space too low"),
        ):
            result = processor.process_file(test_file)

        # Should fail with disk space error
        assert result.success is False
        assert "Disk space too low" in result.error_message
        assert result.phases_skipped == 1
        assert result.phases_completed == 0

    def test_disk_check_called_in_dry_run_but_warns(
        self, tmp_path: Path, caplog
    ) -> None:
        """Pre-flight disk check runs in dry-run mode but only warns on failure."""
        import logging

        # Create a test file
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"\x00" * 1000)

        conn = MagicMock(spec=sqlite3.Connection)
        policy = make_minimal_policy()

        processor = WorkflowProcessor(
            conn=conn,
            policy=policy,
            dry_run=True,  # Dry run mode
        )

        # Mock the disk check to raise an error - now gets called but just warns
        check_mock = MagicMock(
            side_effect=InsufficientDiskSpaceError("Disk check failed")
        )

        with (
            patch.object(processor, "_check_min_free_disk_threshold", check_mock),
            patch.object(processor, "_get_file_info", return_value=MagicMock()),
            patch.object(processor._executor, "execute_phase") as exec_mock,
            caplog.at_level(logging.WARNING),
        ):
            exec_mock.return_value = make_mock_phase_result()
            result = processor.process_file(test_file)

        # Check WAS called in dry-run mode
        check_mock.assert_called_once()
        # But processing continued (succeeded)
        assert result.success is True
        # And a warning was logged
        assert "dry-run, continuing" in caplog.text

    def test_check_uses_config_threshold(self, tmp_path: Path) -> None:
        """Pre-flight check should use threshold from config."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"\x00" * 1000)

        conn = MagicMock(spec=sqlite3.Connection)
        policy = make_minimal_policy()

        processor = WorkflowProcessor(
            conn=conn,
            policy=policy,
            dry_run=False,
        )

        # Mock get_config to return a config with custom threshold
        mock_config = MagicMock()
        mock_config.jobs.min_free_disk_percent = 10.0

        # Mock check_min_free_disk_percent to verify it gets called with correct args
        with (
            patch("vpo.workflow.processor.get_config", return_value=mock_config),
            patch(
                "vpo.workflow.processor.check_min_free_disk_percent", return_value=None
            ) as check_mock,
            patch.object(processor, "_get_file_info", return_value=MagicMock()),
            patch.object(processor._executor, "execute_phase") as exec_mock,
        ):
            exec_mock.return_value = make_mock_phase_result()
            processor.process_file(test_file)

        # Verify check was called with correct threshold
        check_mock.assert_called_once()
        call_args = check_mock.call_args
        assert call_args.kwargs["min_free_percent"] == 10.0

    def test_check_disabled_when_threshold_zero(self, tmp_path: Path) -> None:
        """Pre-flight check should skip when threshold is 0."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"\x00" * 1000)

        conn = MagicMock(spec=sqlite3.Connection)
        policy = make_minimal_policy()

        processor = WorkflowProcessor(
            conn=conn,
            policy=policy,
            dry_run=False,
        )

        # Mock get_config to return a config with disabled threshold
        mock_config = MagicMock()
        mock_config.jobs.min_free_disk_percent = 0.0

        # Mock check_min_free_disk_percent - should NOT be called when disabled
        with (
            patch("vpo.workflow.processor.get_config", return_value=mock_config),
            patch("vpo.workflow.processor.check_min_free_disk_percent") as check_mock,
            patch.object(processor, "_get_file_info", return_value=MagicMock()),
            patch.object(processor._executor, "execute_phase") as exec_mock,
        ):
            exec_mock.return_value = make_mock_phase_result()
            processor.process_file(test_file)

        # check_min_free_disk_percent should NOT have been called
        # because the private method returns early when threshold is 0
        check_mock.assert_not_called()

    def test_dry_run_warns_but_continues_on_disk_error(
        self, tmp_path: Path, caplog
    ) -> None:
        """Dry-run mode should warn about disk issues but not block."""
        import logging

        # Create a test file
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"\x00" * 1000)

        conn = MagicMock(spec=sqlite3.Connection)
        policy = make_minimal_policy()

        processor = WorkflowProcessor(
            conn=conn,
            policy=policy,
            dry_run=True,  # Dry run mode
        )

        # Mock the disk check to raise an error
        with (
            patch.object(
                processor,
                "_check_min_free_disk_threshold",
                side_effect=InsufficientDiskSpaceError("Disk space too low"),
            ),
            patch.object(processor, "_get_file_info", return_value=MagicMock()),
            patch.object(processor._executor, "execute_phase") as exec_mock,
            caplog.at_level(logging.WARNING),
        ):
            exec_mock.return_value = make_mock_phase_result()
            result = processor.process_file(test_file)

        # Should succeed (not blocked) but log a warning
        assert result.success is True
        assert "dry-run, continuing" in caplog.text

    def test_file_stat_error_raises_insufficient_disk_space(
        self, tmp_path: Path
    ) -> None:
        """File stat errors should raise, not silently proceed."""
        # Create a test file (doesn't matter, we'll mock stat)
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"\x00" * 1000)

        conn = MagicMock(spec=sqlite3.Connection)
        policy = make_minimal_policy()

        processor = WorkflowProcessor(
            conn=conn,
            policy=policy,
            dry_run=False,
        )

        # Mock get_config to return a config with enabled threshold
        mock_config = MagicMock()
        mock_config.jobs.min_free_disk_percent = 5.0

        # Create a mock Path whose stat raises OSError
        original_stat = Path.stat

        def mock_stat(self):
            if str(self).endswith("test.mkv"):
                raise OSError("Permission denied")
            return original_stat(self)

        # Mock Path.stat at the class level
        with (
            patch("vpo.workflow.processor.get_config", return_value=mock_config),
            patch.object(Path, "stat", mock_stat),
        ):
            # The check should raise InsufficientDiskSpaceError
            result = processor.process_file(test_file)

        # Should fail with disk space error message about stat
        assert result.success is False
        assert "Cannot read file size" in result.error_message
