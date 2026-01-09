"""Unit tests for executor classes."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.executor.ffmpeg_remux import FFmpegRemuxExecutor
from vpo.executor.mkvmerge import MkvmergeExecutor
from vpo.executor.mkvpropedit import MkvpropeditExecutor
from vpo.policy.types import (
    ActionType,
    ContainerChange,
    Plan,
    PlannedAction,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mkv_plan() -> Plan:
    """Create a test plan for an MKV file."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/video.mkv"),
        policy_version=12,
        actions=(
            PlannedAction(
                action_type=ActionType.SET_DEFAULT,
                track_index=0,
                current_value=False,
                desired_value=True,
            ),
            PlannedAction(
                action_type=ActionType.CLEAR_DEFAULT,
                track_index=1,
                current_value=True,
                desired_value=False,
            ),
        ),
        requires_remux=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mkv_reorder_plan() -> Plan:
    """Create a test plan with track reordering."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/video.mkv"),
        policy_version=12,
        actions=(
            PlannedAction(
                action_type=ActionType.REORDER,
                track_index=None,
                current_value=[0, 1, 2],
                desired_value=[0, 2, 1],
            ),
            PlannedAction(
                action_type=ActionType.SET_DEFAULT,
                track_index=0,
                current_value=False,
                desired_value=True,
            ),
        ),
        requires_remux=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mp4_plan() -> Plan:
    """Create a test plan for an MP4 file."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/video.mp4"),
        policy_version=12,
        actions=(
            PlannedAction(
                action_type=ActionType.SET_DEFAULT,
                track_index=0,
                current_value=False,
                desired_value=True,
            ),
        ),
        requires_remux=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def empty_plan() -> Plan:
    """Create an empty test plan."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/video.mkv"),
        policy_version=12,
        actions=(),
        requires_remux=False,
        created_at=datetime.now(timezone.utc),
    )


# =============================================================================
# MkvpropeditExecutor Tests
# =============================================================================


class TestMkvpropeditExecutor:
    """Tests for MkvpropeditExecutor class."""

    def test_can_handle_mkv_metadata_only(self, mkv_plan: Plan):
        """Should handle MKV files with metadata-only changes."""
        executor = MkvpropeditExecutor()
        assert executor.can_handle(mkv_plan) is True

    def test_cannot_handle_reorder_plan(self, mkv_reorder_plan: Plan):
        """Should not handle plans with REORDER actions."""
        executor = MkvpropeditExecutor()
        assert executor.can_handle(mkv_reorder_plan) is False

    def test_cannot_handle_mp4(self, mp4_plan: Plan):
        """Should not handle non-MKV files."""
        executor = MkvpropeditExecutor()
        assert executor.can_handle(mp4_plan) is False

    def test_execute_empty_plan_succeeds(self, empty_plan: Plan):
        """Empty plan should return success without modification."""
        executor = MkvpropeditExecutor()
        result = executor.execute(empty_plan)
        assert result.success is True
        assert "No changes" in result.message

    def test_build_command_set_default(self, mkv_plan: Plan):
        """SET_DEFAULT action should generate correct args."""
        executor = MkvpropeditExecutor()
        executor._tool_path = Path("/usr/bin/mkvpropedit")
        cmd = executor._build_command(mkv_plan)

        assert str(mkv_plan.file_path) in cmd
        assert "--edit" in cmd
        assert "track:1" in cmd  # 0-indexed to 1-indexed
        assert "flag-default=1" in cmd

    def test_build_command_clear_default(self, mkv_plan: Plan):
        """CLEAR_DEFAULT action should generate correct args."""
        executor = MkvpropeditExecutor()
        executor._tool_path = Path("/usr/bin/mkvpropedit")
        cmd = executor._build_command(mkv_plan)

        assert "track:2" in cmd  # 1-indexed
        assert "flag-default=0" in cmd

    def test_action_to_args_set_forced(self):
        """SET_FORCED action should generate correct args."""
        executor = MkvpropeditExecutor()
        action = PlannedAction(
            action_type=ActionType.SET_FORCED,
            track_index=2,
            current_value=False,
            desired_value=True,
        )
        args = executor._action_to_args(action)
        assert args == ["--edit", "track:3", "--set", "flag-forced=1"]

    def test_action_to_args_clear_forced(self):
        """CLEAR_FORCED action should generate correct args."""
        executor = MkvpropeditExecutor()
        action = PlannedAction(
            action_type=ActionType.CLEAR_FORCED,
            track_index=0,
            current_value=True,
            desired_value=False,
        )
        args = executor._action_to_args(action)
        assert args == ["--edit", "track:1", "--set", "flag-forced=0"]

    def test_action_to_args_set_title(self):
        """SET_TITLE action should generate correct args."""
        executor = MkvpropeditExecutor()
        action = PlannedAction(
            action_type=ActionType.SET_TITLE,
            track_index=1,
            current_value="Old Title",
            desired_value="New Title",
        )
        args = executor._action_to_args(action)
        assert args == ["--edit", "track:2", "--set", "name=New Title"]

    def test_action_to_args_set_language(self):
        """SET_LANGUAGE action should generate correct args."""
        executor = MkvpropeditExecutor()
        action = PlannedAction(
            action_type=ActionType.SET_LANGUAGE,
            track_index=3,
            current_value="und",
            desired_value="eng",
        )
        args = executor._action_to_args(action)
        assert args == ["--edit", "track:4", "--set", "language=eng"]

    def test_action_to_args_reorder_raises(self):
        """REORDER action should raise ValueError."""
        executor = MkvpropeditExecutor()
        action = PlannedAction(
            action_type=ActionType.REORDER,
            track_index=None,
            current_value=[0, 1],
            desired_value=[1, 0],
        )
        with pytest.raises(ValueError, match="requires track_index"):
            executor._action_to_args(action)


# =============================================================================
# MkvmergeExecutor Tests
# =============================================================================


class TestMkvmergeExecutor:
    """Tests for MkvmergeExecutor class."""

    def test_can_handle_mkv_with_reorder(self, mkv_reorder_plan: Plan):
        """Should handle MKV files with REORDER action."""
        executor = MkvmergeExecutor()
        assert executor.can_handle(mkv_reorder_plan) is True

    def test_cannot_handle_metadata_only(self, mkv_plan: Plan):
        """Should not handle plans without REORDER."""
        executor = MkvmergeExecutor()
        assert executor.can_handle(mkv_plan) is False

    def test_cannot_handle_mp4(self, mp4_plan: Plan):
        """Should not handle non-MKV files."""
        executor = MkvmergeExecutor()
        assert executor.can_handle(mp4_plan) is False

    def test_execute_empty_plan_succeeds(self, empty_plan: Plan):
        """Empty plan should return success without modification."""
        executor = MkvmergeExecutor()
        result = executor.execute(empty_plan)
        assert result.success is True
        assert "No changes" in result.message

    def test_build_command_track_order(self, mkv_reorder_plan: Plan):
        """Track order should be correctly formatted."""
        executor = MkvmergeExecutor()
        executor._tool_path = Path("/usr/bin/mkvmerge")
        output_path = Path("/tmp/output.mkv")

        cmd = executor._build_command(mkv_reorder_plan, output_path)

        assert "--track-order" in cmd
        track_order_idx = cmd.index("--track-order")
        order_spec = cmd[track_order_idx + 1]
        # Expected: 0:0,0:2,0:1 for desired order [0, 2, 1]
        assert order_spec == "0:0,0:2,0:1"

    def test_build_command_default_flags(self, mkv_reorder_plan: Plan):
        """Default flag changes should be included."""
        executor = MkvmergeExecutor()
        executor._tool_path = Path("/usr/bin/mkvmerge")
        output_path = Path("/tmp/output.mkv")

        cmd = executor._build_command(mkv_reorder_plan, output_path)

        assert "--default-track-flag" in cmd
        flag_idx = cmd.index("--default-track-flag")
        assert cmd[flag_idx + 1] == "0:1"  # SET_DEFAULT for track 0

    def test_build_command_output_path(self, mkv_reorder_plan: Plan):
        """Output path should be specified."""
        executor = MkvmergeExecutor()
        executor._tool_path = Path("/usr/bin/mkvmerge")
        output_path = Path("/tmp/output.mkv")

        cmd = executor._build_command(mkv_reorder_plan, output_path)

        assert "--output" in cmd
        output_idx = cmd.index("--output")
        assert cmd[output_idx + 1] == str(output_path)

    def test_build_command_input_file(self, mkv_reorder_plan: Plan):
        """Input file should be the last argument."""
        executor = MkvmergeExecutor()
        executor._tool_path = Path("/usr/bin/mkvmerge")
        output_path = Path("/tmp/output.mkv")

        cmd = executor._build_command(mkv_reorder_plan, output_path)

        assert cmd[-1] == str(mkv_reorder_plan.file_path)


# =============================================================================
# Backup Integration Tests
# =============================================================================


class TestBackupHandling:
    """Tests for backup/restore behavior in executors."""

    @patch("vpo.executor.mkvpropedit.create_backup")
    @patch("vpo.executor.mkvpropedit.require_tool")
    @patch("subprocess.run")
    def test_mkvpropedit_creates_backup(
        self,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_backup: MagicMock,
        mkv_plan: Plan,
    ):
        """Executor should create backup before execution."""
        mock_require.return_value = Path("/usr/bin/mkvpropedit")
        mock_backup.return_value = Path("/test/video.mkv.vpo-backup")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        executor = MkvpropeditExecutor()
        result = executor.execute(mkv_plan)

        mock_backup.assert_called_once_with(mkv_plan.file_path)
        assert result.success is True

    @patch("vpo.executor.mkvpropedit.create_backup")
    @patch("vpo.executor.mkvpropedit.safe_restore_from_backup")
    @patch("vpo.executor.mkvpropedit.require_tool")
    @patch("subprocess.run")
    def test_mkvpropedit_restores_on_failure(
        self,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mkv_plan: Plan,
    ):
        """Executor should restore backup on command failure."""
        mock_require.return_value = Path("/usr/bin/mkvpropedit")
        backup_path = Path("/test/video.mkv.vpo-backup")
        mock_backup.return_value = backup_path
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        executor = MkvpropeditExecutor()
        result = executor.execute(mkv_plan)

        mock_restore.assert_called_once_with(backup_path)
        assert result.success is False

    @patch("vpo.executor.mkvpropedit.create_backup")
    @patch("vpo.executor.mkvpropedit.require_tool")
    @patch("subprocess.run")
    def test_mkvpropedit_keeps_backup_when_requested(
        self,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_backup: MagicMock,
        mkv_plan: Plan,
    ):
        """Backup should be kept when keep_backup=True."""
        mock_require.return_value = Path("/usr/bin/mkvpropedit")
        backup_path = Path("/test/video.mkv.vpo-backup")
        mock_backup.return_value = backup_path
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        executor = MkvpropeditExecutor()
        result = executor.execute(mkv_plan, keep_backup=True)

        assert result.success is True
        assert result.backup_path == backup_path

    @patch("vpo.executor.mkvpropedit.create_backup")
    @patch("vpo.executor.mkvpropedit.require_tool")
    @patch("subprocess.run")
    def test_mkvpropedit_removes_backup_when_not_requested(
        self,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_backup: MagicMock,
        mkv_plan: Plan,
    ):
        """Backup should be removed when keep_backup=False."""
        mock_require.return_value = Path("/usr/bin/mkvpropedit")
        backup_path = MagicMock(spec=Path)
        mock_backup.return_value = backup_path
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        executor = MkvpropeditExecutor()
        result = executor.execute(mkv_plan, keep_backup=False)

        assert result.success is True
        assert result.backup_path is None
        backup_path.unlink.assert_called_once_with(missing_ok=True)


# =============================================================================
# Error Scenario Tests
# =============================================================================


class TestMkvpropeditErrorScenarios:
    """Tests for error handling in MkvpropeditExecutor."""

    @patch("vpo.executor.mkvpropedit.create_backup")
    @patch("vpo.executor.mkvpropedit.safe_restore_from_backup")
    @patch("vpo.executor.mkvpropedit.require_tool")
    @patch("subprocess.run")
    def test_mkvpropedit_timeout_handling(
        self,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mkv_plan: Plan,
    ):
        """Should handle subprocess timeout and restore backup."""
        import subprocess

        mock_require.return_value = Path("/usr/bin/mkvpropedit")
        backup_path = Path("/test/video.mkv.vpo-backup")
        mock_backup.return_value = backup_path
        mock_run.side_effect = subprocess.TimeoutExpired("mkvpropedit", 600)

        executor = MkvpropeditExecutor()
        result = executor.execute(mkv_plan)

        assert result.success is False
        assert (
            "timeout" in result.message.lower() or "timed out" in result.message.lower()
        )
        mock_restore.assert_called_once_with(backup_path)

    @patch("vpo.executor.mkvpropedit.create_backup")
    def test_mkvpropedit_backup_failure(
        self,
        mock_backup: MagicMock,
        mkv_plan: Plan,
    ):
        """Should handle backup creation failure."""
        mock_backup.side_effect = FileNotFoundError("Source file not found")

        executor = MkvpropeditExecutor()
        result = executor.execute(mkv_plan)

        assert result.success is False
        assert "Backup failed" in result.message

    @patch("vpo.executor.mkvpropedit.create_backup")
    @patch("vpo.executor.mkvpropedit.safe_restore_from_backup")
    @patch("vpo.executor.mkvpropedit.require_tool")
    @patch("subprocess.run")
    def test_mkvpropedit_returncode_error(
        self,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mkv_plan: Plan,
    ):
        """Should handle non-zero return code from mkvpropedit."""
        mock_require.return_value = Path("/usr/bin/mkvpropedit")
        backup_path = Path("/test/video.mkv.vpo-backup")
        mock_backup.return_value = backup_path
        mock_run.return_value = MagicMock(
            returncode=2, stdout="", stderr="Error: Could not write to file"
        )

        executor = MkvpropeditExecutor()
        result = executor.execute(mkv_plan)

        assert result.success is False
        assert (
            "Could not write to file" in result.message
            or "mkvpropedit failed" in result.message
        )


class TestMkvmergeErrorScenarios:
    """Tests for error handling in MkvmergeExecutor."""

    @patch("vpo.executor.mkvmerge.check_disk_space")
    @patch("vpo.executor.mkvmerge.create_backup")
    @patch("vpo.executor.mkvmerge.safe_restore_from_backup")
    @patch("vpo.executor.mkvmerge.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_mkvmerge_timeout_handling(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mock_disk_check: MagicMock,
        mkv_reorder_plan: Plan,
    ):
        """Should handle subprocess timeout and restore backup."""
        import subprocess

        mock_require.return_value = Path("/usr/bin/mkvmerge")
        backup_path = Path("/test/video.mkv.vpo-backup")
        mock_backup.return_value = backup_path

        # Mock temp file
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__ = MagicMock(
            return_value=MagicMock(name="/tmp/temp.mkv")
        )
        mock_temp_ctx.__exit__ = MagicMock(return_value=False)
        mock_tempfile.return_value = mock_temp_ctx

        mock_run.side_effect = subprocess.TimeoutExpired("mkvmerge", 600)

        with patch.object(Path, "unlink"):
            executor = MkvmergeExecutor()
            result = executor.execute(mkv_reorder_plan)

        assert result.success is False
        assert (
            "timeout" in result.message.lower() or "timed out" in result.message.lower()
        )

    @patch("vpo.executor.mkvmerge.check_disk_space")
    @patch("vpo.executor.mkvmerge.create_backup")
    def test_mkvmerge_backup_failure(
        self,
        mock_backup: MagicMock,
        mock_disk_check: MagicMock,
        mkv_reorder_plan: Plan,
    ):
        """Should handle backup creation failure."""
        mock_backup.side_effect = FileNotFoundError("Source file not found")

        executor = MkvmergeExecutor()
        result = executor.execute(mkv_reorder_plan)

        assert result.success is False
        assert "Backup failed" in result.message

    @patch("vpo.executor.mkvmerge.check_disk_space")
    @patch("vpo.executor.mkvmerge.create_backup")
    @patch("vpo.executor.mkvmerge.safe_restore_from_backup")
    @patch("vpo.executor.mkvmerge.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_mkvmerge_warning_returncode(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mock_disk_check: MagicMock,
        mkv_reorder_plan: Plan,
    ):
        """Should handle returncode 1 (warnings) as success with caution."""
        mock_require.return_value = Path("/usr/bin/mkvmerge")
        backup_path = Path("/test/video.mkv.vpo-backup")
        mock_backup.return_value = backup_path

        # Mock temp file
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__ = MagicMock(
            return_value=MagicMock(name="/tmp/temp.mkv")
        )
        mock_temp_ctx.__exit__ = MagicMock(return_value=False)
        mock_tempfile.return_value = mock_temp_ctx

        # Return code 1 = warnings in mkvmerge
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Warning: track title changed"
        )

        with patch.object(Path, "replace"), patch.object(Path, "unlink"):
            executor = MkvmergeExecutor()
            result = executor.execute(mkv_reorder_plan)

        # Returncode 1 should still be treated as success (warnings only)
        assert result.success is True

    @patch("vpo.executor.mkvmerge.check_disk_space")
    @patch("vpo.executor.mkvmerge.create_backup")
    @patch("vpo.executor.mkvmerge.safe_restore_from_backup")
    @patch("vpo.executor.mkvmerge.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_mkvmerge_error_returncode(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mock_disk_check: MagicMock,
        mkv_reorder_plan: Plan,
    ):
        """Should handle returncode 2 (error) as failure."""
        mock_require.return_value = Path("/usr/bin/mkvmerge")
        backup_path = Path("/test/video.mkv.vpo-backup")
        mock_backup.return_value = backup_path

        # Mock temp file
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__ = MagicMock(
            return_value=MagicMock(name="/tmp/temp.mkv")
        )
        mock_temp_ctx.__exit__ = MagicMock(return_value=False)
        mock_tempfile.return_value = mock_temp_ctx

        # Return code 2 = error in mkvmerge
        mock_run.return_value = MagicMock(
            returncode=2, stdout="", stderr="Error: File could not be opened"
        )

        with patch.object(Path, "unlink"):
            executor = MkvmergeExecutor()
            result = executor.execute(mkv_reorder_plan)

        assert result.success is False
        mock_restore.assert_called_once()


# =============================================================================
# Additional MkvmergeExecutor Tests
# =============================================================================


class TestMkvmergeAdditional:
    """Additional tests for MkvmergeExecutor."""

    def test_build_command_clear_default(self):
        """CLEAR_DEFAULT action should generate correct args."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mkv"),
            policy_version=12,
            actions=(
                PlannedAction(
                    action_type=ActionType.REORDER,
                    track_index=None,
                    current_value=[0, 1],
                    desired_value=[1, 0],
                ),
                PlannedAction(
                    action_type=ActionType.CLEAR_DEFAULT,
                    track_index=1,
                    current_value=True,
                    desired_value=False,
                ),
            ),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
        )

        executor = MkvmergeExecutor()
        executor._tool_path = Path("/usr/bin/mkvmerge")
        output_path = Path("/tmp/output.mkv")

        cmd = executor._build_command(plan, output_path)

        # Should have default-track-flag for CLEAR_DEFAULT
        assert "--default-track-flag" in cmd
        flag_idx = cmd.index("--default-track-flag")
        # Track 1, value 0 (clear)
        assert cmd[flag_idx + 1] == "1:0"


# =============================================================================
# MkvmergeExecutor Container Conversion Tests (T039)
# =============================================================================


class TestMkvmergeContainerConversion:
    """Tests for MkvmergeExecutor container conversion capability (T039)."""

    def test_can_handle_avi_to_mkv_conversion(self) -> None:
        """Should handle AVI to MKV container conversion."""
        from vpo.policy.types import ContainerChange

        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.avi"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="avi",
                target_format="mkv",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = MkvmergeExecutor()
        assert executor.can_handle(plan) is True

    def test_can_handle_mov_to_mkv_conversion(self) -> None:
        """Should handle MOV to MKV container conversion."""
        from vpo.policy.types import ContainerChange

        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mov"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mov",
                target_format="mkv",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = MkvmergeExecutor()
        assert executor.can_handle(plan) is True

    def test_can_handle_mp4_to_mkv_conversion(self) -> None:
        """Should handle MP4 to MKV container conversion."""
        from vpo.policy.types import ContainerChange

        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mp4"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mp4",
                target_format="mkv",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = MkvmergeExecutor()
        assert executor.can_handle(plan) is True

    def test_cannot_handle_mp4_target(self) -> None:
        """Should not handle conversion to MP4 (handled by FFmpegRemuxExecutor)."""
        from vpo.policy.types import ContainerChange

        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = MkvmergeExecutor()
        assert executor.can_handle(plan) is False

    def test_cannot_handle_non_mkv_without_conversion(self) -> None:
        """Should not handle AVI files without container_change."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.avi"),
            policy_version=3,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_DEFAULT,
                    track_index=0,
                    current_value=False,
                    desired_value=True,
                ),
            ),
            requires_remux=False,
            created_at=datetime.now(timezone.utc),
        )

        executor = MkvmergeExecutor()
        assert executor.can_handle(plan) is False


# =============================================================================
# FFmpegRemuxExecutor Tests (T048-T050)
# =============================================================================


class TestFFmpegRemuxExecutor:
    """Tests for FFmpegRemuxExecutor class."""

    def test_can_handle_mkv_to_mp4_conversion(self) -> None:
        """Should handle MKV to MP4 container conversion."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = FFmpegRemuxExecutor()
        assert executor.can_handle(plan) is True

    def test_cannot_handle_mkv_target(self) -> None:
        """Should not handle conversion to MKV (handled by MkvmergeExecutor)."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.avi"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="avi",
                target_format="mkv",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = FFmpegRemuxExecutor()
        assert executor.can_handle(plan) is False

    def test_cannot_handle_without_container_change(self) -> None:
        """Should not handle plans without container_change."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mkv"),
            policy_version=3,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_DEFAULT,
                    track_index=0,
                    current_value=False,
                    desired_value=True,
                ),
            ),
            requires_remux=False,
            created_at=datetime.now(timezone.utc),
        )

        executor = FFmpegRemuxExecutor()
        assert executor.can_handle(plan) is False

    def test_execute_empty_plan_succeeds(self) -> None:
        """Empty plan should return success without modification."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=False,
            created_at=datetime.now(timezone.utc),
        )

        executor = FFmpegRemuxExecutor()
        result = executor.execute(plan)
        assert result.success is True
        assert "No changes" in result.message

    def test_build_command_uses_stream_copy(self) -> None:
        """Command should use -c copy for lossless remux."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = FFmpegRemuxExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(plan, output_path)

        assert "-c" in cmd
        copy_idx = cmd.index("-c")
        assert cmd[copy_idx + 1] == "copy"

    def test_build_command_uses_faststart(self) -> None:
        """Command should use -movflags +faststart for streaming."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = FFmpegRemuxExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(plan, output_path)

        assert "-movflags" in cmd
        movflags_idx = cmd.index("-movflags")
        assert cmd[movflags_idx + 1] == "+faststart"

    def test_build_command_input_file(self) -> None:
        """Input file should be specified after -i."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = FFmpegRemuxExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(plan, output_path)

        assert "-i" in cmd
        input_idx = cmd.index("-i")
        assert cmd[input_idx + 1] == str(plan.file_path)


class TestFFmpegRemuxExecutorBackup:
    """Tests for FFmpegRemuxExecutor backup handling."""

    @patch("vpo.executor.ffmpeg_remux.check_disk_space")
    @patch("vpo.executor.ffmpeg_remux.create_backup")
    @patch("vpo.executor.ffmpeg_remux.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_creates_backup(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_backup: MagicMock,
        mock_disk_check: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Executor should create backup before execution."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        mock_backup.return_value = tmp_path / "video.mkv.vpo-backup"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Mock the temp file context manager
        mock_temp = MagicMock()
        mock_temp.name = str(tmp_path / "output.mp4")
        mock_tempfile.return_value.__enter__.return_value = mock_temp

        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "video.mkv",
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        with patch.object(Path, "replace"):
            executor = FFmpegRemuxExecutor()
            result = executor.execute(plan)

        mock_backup.assert_called_once_with(plan.file_path)
        assert result.success is True

    @patch("vpo.executor.ffmpeg_remux.check_disk_space")
    @patch("vpo.executor.ffmpeg_remux.create_backup")
    @patch("vpo.executor.ffmpeg_remux.safe_restore_from_backup")
    @patch("vpo.executor.ffmpeg_remux.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_restores_on_failure(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mock_disk_check: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Executor should restore backup on command failure."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        backup_path = tmp_path / "video.mkv.vpo-backup"
        mock_backup.return_value = backup_path
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        # Mock the temp file context manager
        mock_temp = MagicMock()
        mock_temp.name = str(tmp_path / "output.mp4")
        mock_tempfile.return_value.__enter__.return_value = mock_temp

        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "video.mkv",
            policy_version=3,
            actions=(),
            requires_remux=True,
            created_at=datetime.now(timezone.utc),
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        executor = FFmpegRemuxExecutor()
        result = executor.execute(plan)

        mock_restore.assert_called_once_with(backup_path)
        assert result.success is False
