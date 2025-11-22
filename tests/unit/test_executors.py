"""Unit tests for executor classes."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.executor.mkvmerge import MkvmergeExecutor
from video_policy_orchestrator.executor.mkvpropedit import MkvpropeditExecutor
from video_policy_orchestrator.policy.models import ActionType, Plan, PlannedAction

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mkv_plan() -> Plan:
    """Create a test plan for an MKV file."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/video.mkv"),
        policy_version=1,
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
        policy_version=1,
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
        policy_version=1,
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
        policy_version=1,
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

    @patch("video_policy_orchestrator.executor.mkvpropedit.create_backup")
    @patch("video_policy_orchestrator.executor.mkvpropedit.require_tool")
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

    @patch("video_policy_orchestrator.executor.mkvpropedit.create_backup")
    @patch("video_policy_orchestrator.executor.mkvpropedit.restore_from_backup")
    @patch("video_policy_orchestrator.executor.mkvpropedit.require_tool")
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

    @patch("video_policy_orchestrator.executor.mkvpropedit.create_backup")
    @patch("video_policy_orchestrator.executor.mkvpropedit.require_tool")
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

    @patch("video_policy_orchestrator.executor.mkvpropedit.create_backup")
    @patch("video_policy_orchestrator.executor.mkvpropedit.require_tool")
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
