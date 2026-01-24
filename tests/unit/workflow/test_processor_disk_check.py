"""Tests for WorkflowProcessor disk space pre-flight checks."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from vpo.executor.backup import InsufficientDiskSpaceError
from vpo.policy.types import (
    GlobalConfig,
    PhaseDefinition,
    PolicySchema,
)
from vpo.workflow.processor import WorkflowProcessor


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

    def test_disk_check_skipped_in_dry_run(self, tmp_path: Path) -> None:
        """Pre-flight disk check should be skipped in dry-run mode."""
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

        # Mock the disk check to raise an error - should NOT be called
        check_mock = MagicMock(side_effect=InsufficientDiskSpaceError("Should not run"))

        with patch.object(processor, "_check_min_free_disk_threshold", check_mock):
            # Mock _get_file_info to return None (file not in DB)
            with patch.object(processor, "_get_file_info", return_value=None):
                # Mock _executor.execute_phase to return a successful result
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.changes_made = 0
                mock_result.phase_name = "test"
                mock_result.duration_seconds = 0.1
                mock_result.operations_executed = ()
                mock_result.message = None
                mock_result.error = None
                mock_result.planned_actions = None
                mock_result.transcode_skip_reason = None
                mock_result.encoding_fps = None
                mock_result.encoding_bitrate_kbps = None
                mock_result.encoder_type = None

                with patch.object(processor._executor, "execute_phase") as exec_mock:
                    exec_mock.return_value = mock_result
                    processor.process_file(test_file)

        # Check should not have been called in dry-run mode
        check_mock.assert_not_called()

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
            patch.object(processor, "_get_file_info", return_value=None),
            patch.object(processor._executor, "execute_phase") as exec_mock,
        ):
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.changes_made = 0
            mock_result.phase_name = "test"
            mock_result.duration_seconds = 0.1
            mock_result.operations_executed = ()
            mock_result.message = None
            mock_result.error = None
            mock_result.planned_actions = None
            mock_result.transcode_skip_reason = None
            mock_result.encoding_fps = None
            mock_result.encoding_bitrate_kbps = None
            mock_result.encoder_type = None
            exec_mock.return_value = mock_result

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
            patch.object(processor, "_get_file_info", return_value=None),
            patch.object(processor._executor, "execute_phase") as exec_mock,
        ):
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.changes_made = 0
            mock_result.phase_name = "test"
            mock_result.duration_seconds = 0.1
            mock_result.operations_executed = ()
            mock_result.message = None
            mock_result.error = None
            mock_result.planned_actions = None
            mock_result.transcode_skip_reason = None
            mock_result.encoding_fps = None
            mock_result.encoding_bitrate_kbps = None
            mock_result.encoder_type = None
            exec_mock.return_value = mock_result

            processor.process_file(test_file)

        # check_min_free_disk_percent should NOT have been called
        # because the private method returns early when threshold is 0
        check_mock.assert_not_called()
