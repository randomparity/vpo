"""Unit tests for FfmpegMetadataExecutor."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.executor.ffmpeg_metadata import FfmpegMetadataExecutor
from vpo.policy.models import ActionType, Plan, PlannedAction

# =============================================================================
# Test Fixtures
# =============================================================================


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
def avi_plan() -> Plan:
    """Create a test plan for an AVI file."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/video.avi"),
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
        ),
        requires_remux=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def reorder_plan() -> Plan:
    """Create a test plan with REORDER action."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/video.mp4"),
        policy_version=12,
        actions=(
            PlannedAction(
                action_type=ActionType.REORDER,
                track_index=None,
                current_value=[0, 1, 2],
                desired_value=[0, 2, 1],
            ),
        ),
        requires_remux=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def empty_plan() -> Plan:
    """Create an empty test plan."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/video.mp4"),
        policy_version=12,
        actions=(),
        requires_remux=False,
        created_at=datetime.now(timezone.utc),
    )


# =============================================================================
# can_handle() Tests
# =============================================================================


class TestFfmpegCanHandle:
    """Tests for FfmpegMetadataExecutor.can_handle()."""

    def test_can_handle_mp4(self, mp4_plan: Plan) -> None:
        """Should handle MP4 files with metadata changes."""
        executor = FfmpegMetadataExecutor()
        assert executor.can_handle(mp4_plan) is True

    def test_can_handle_avi(self, avi_plan: Plan) -> None:
        """Should handle AVI files."""
        executor = FfmpegMetadataExecutor()
        assert executor.can_handle(avi_plan) is True

    def test_cannot_handle_mkv(self, mkv_plan: Plan) -> None:
        """Should NOT handle MKV files (use mkvpropedit instead)."""
        executor = FfmpegMetadataExecutor()
        assert executor.can_handle(mkv_plan) is False

    def test_cannot_handle_mka(self) -> None:
        """Should NOT handle MKA (Matroska audio) files."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/audio.mka"),
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
        executor = FfmpegMetadataExecutor()
        assert executor.can_handle(plan) is False

    def test_cannot_handle_reorder(self, reorder_plan: Plan) -> None:
        """Should NOT handle plans with REORDER actions."""
        executor = FfmpegMetadataExecutor()
        assert executor.can_handle(reorder_plan) is False


# =============================================================================
# execute() Tests
# =============================================================================


class TestFfmpegExecute:
    """Tests for FfmpegMetadataExecutor.execute()."""

    def test_execute_empty_plan_succeeds(self, empty_plan: Plan) -> None:
        """Empty plan should return success without modification."""
        executor = FfmpegMetadataExecutor()
        result = executor.execute(empty_plan)
        assert result.success is True
        assert "No changes" in result.message

    @patch("vpo.executor.ffmpeg_metadata.check_disk_space")
    @patch("vpo.executor.ffmpeg_metadata.create_backup")
    @patch("vpo.executor.ffmpeg_metadata.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_execute_success(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_backup: MagicMock,
        mock_disk_space: MagicMock,
        mp4_plan: Plan,
        temp_dir: Path,
    ) -> None:
        """Successful execution should return success result."""
        # Setup mocks
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        mock_backup.return_value = Path("/test/video.mp4.vpo-backup")

        # Mock temp file
        temp_path = temp_dir / "temp_output.mp4"
        temp_path.touch()
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__ = MagicMock(return_value=MagicMock(name=str(temp_path)))
        mock_temp_ctx.__exit__ = MagicMock(return_value=False)
        mock_tempfile.return_value = mock_temp_ctx

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Mock the Path.replace method
        with patch.object(Path, "replace"):
            executor = FfmpegMetadataExecutor()
            result = executor.execute(mp4_plan)

        assert result.success is True
        mock_backup.assert_called_once()

    @patch("vpo.executor.ffmpeg_metadata.check_disk_space")
    @patch("vpo.executor.ffmpeg_metadata.create_backup")
    @patch("vpo.executor.ffmpeg_metadata.restore_from_backup")
    @patch("vpo.executor.ffmpeg_metadata.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_execute_restores_on_failure(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mock_disk_space: MagicMock,
        mp4_plan: Plan,
    ) -> None:
        """Failed execution should restore from backup."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        backup_path = Path("/test/video.mp4.vpo-backup")
        mock_backup.return_value = backup_path

        # Mock temp file
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__ = MagicMock(
            return_value=MagicMock(name="/tmp/temp.mp4")
        )
        mock_temp_ctx.__exit__ = MagicMock(return_value=False)
        mock_tempfile.return_value = mock_temp_ctx

        # Simulate ffmpeg failure
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        with patch.object(Path, "unlink"):
            executor = FfmpegMetadataExecutor()
            result = executor.execute(mp4_plan)

        assert result.success is False
        mock_restore.assert_called_once_with(backup_path)

    @patch("vpo.executor.ffmpeg_metadata.check_disk_space")
    @patch("vpo.executor.ffmpeg_metadata.create_backup")
    @patch("vpo.executor.ffmpeg_metadata.restore_from_backup")
    @patch("vpo.executor.ffmpeg_metadata.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_execute_timeout_handling(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_restore: MagicMock,
        mock_backup: MagicMock,
        mock_disk_space: MagicMock,
        mp4_plan: Plan,
    ) -> None:
        """Timeout should restore from backup and return failure."""
        import subprocess

        mock_require.return_value = Path("/usr/bin/ffmpeg")
        backup_path = Path("/test/video.mp4.vpo-backup")
        mock_backup.return_value = backup_path

        # Mock temp file
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__ = MagicMock(
            return_value=MagicMock(name="/tmp/temp.mp4")
        )
        mock_temp_ctx.__exit__ = MagicMock(return_value=False)
        mock_tempfile.return_value = mock_temp_ctx

        # Simulate timeout
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 600)

        with patch.object(Path, "unlink"):
            executor = FfmpegMetadataExecutor()
            result = executor.execute(mp4_plan)

        assert result.success is False
        assert "timed out" in result.message
        mock_restore.assert_called_once()

    @patch("vpo.executor.ffmpeg_metadata.check_disk_space")
    @patch("vpo.executor.ffmpeg_metadata.create_backup")
    def test_execute_backup_failure(
        self,
        mock_backup: MagicMock,
        mock_disk_space: MagicMock,
        mp4_plan: Plan,
    ) -> None:
        """Backup failure should return failure result."""
        mock_backup.side_effect = FileNotFoundError("Source file not found")

        executor = FfmpegMetadataExecutor()
        result = executor.execute(mp4_plan)

        assert result.success is False
        assert "Backup failed" in result.message


# =============================================================================
# _build_command() Tests
# =============================================================================


class TestFfmpegBuildCommand:
    """Tests for FfmpegMetadataExecutor._build_command()."""

    def test_build_command_set_default(self, mp4_plan: Plan) -> None:
        """SET_DEFAULT action should generate correct ffmpeg args."""
        executor = FfmpegMetadataExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(mp4_plan, output_path)

        assert cmd[0] == "/usr/bin/ffmpeg"
        assert "-i" in cmd
        assert str(mp4_plan.file_path) in cmd
        assert "-map" in cmd
        assert "0" in cmd
        assert "-c" in cmd
        assert "copy" in cmd
        assert "-disposition:0" in cmd
        assert "default" in cmd

    def test_build_command_clear_default(self) -> None:
        """CLEAR_DEFAULT action should generate correct ffmpeg args."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mp4"),
            policy_version=12,
            actions=(
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

        executor = FfmpegMetadataExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(plan, output_path)

        assert "-disposition:1" in cmd
        assert "none" in cmd

    def test_build_command_set_forced(self) -> None:
        """SET_FORCED action should generate correct ffmpeg args."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mp4"),
            policy_version=12,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_FORCED,
                    track_index=2,
                    current_value=False,
                    desired_value=True,
                ),
            ),
            requires_remux=False,
            created_at=datetime.now(timezone.utc),
        )

        executor = FfmpegMetadataExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(plan, output_path)

        assert "-disposition:2" in cmd
        assert "forced" in cmd

    def test_build_command_clear_forced(self) -> None:
        """CLEAR_FORCED action should generate correct ffmpeg args."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mp4"),
            policy_version=12,
            actions=(
                PlannedAction(
                    action_type=ActionType.CLEAR_FORCED,
                    track_index=0,
                    current_value=True,
                    desired_value=False,
                ),
            ),
            requires_remux=False,
            created_at=datetime.now(timezone.utc),
        )

        executor = FfmpegMetadataExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(plan, output_path)

        assert "-disposition:0" in cmd
        assert "0" in cmd

    def test_build_command_set_title(self) -> None:
        """SET_TITLE action should generate correct ffmpeg args."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mp4"),
            policy_version=12,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_TITLE,
                    track_index=1,
                    current_value="Old Title",
                    desired_value="New Title",
                ),
            ),
            requires_remux=False,
            created_at=datetime.now(timezone.utc),
        )

        executor = FfmpegMetadataExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(plan, output_path)

        assert "-metadata:s:1" in cmd
        assert "title=New Title" in cmd

    def test_build_command_set_language(self) -> None:
        """SET_LANGUAGE action should generate correct ffmpeg args."""
        plan = Plan(
            file_id="test-id",
            file_path=Path("/test/video.mp4"),
            policy_version=12,
            actions=(
                PlannedAction(
                    action_type=ActionType.SET_LANGUAGE,
                    track_index=3,
                    current_value="und",
                    desired_value="eng",
                ),
            ),
            requires_remux=False,
            created_at=datetime.now(timezone.utc),
        )

        executor = FfmpegMetadataExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(plan, output_path)

        assert "-metadata:s:3" in cmd
        assert "language=eng" in cmd

    def test_build_command_output_path(self, mp4_plan: Plan) -> None:
        """Output path should be in the command."""
        executor = FfmpegMetadataExecutor()
        executor._tool_path = Path("/usr/bin/ffmpeg")
        output_path = Path("/tmp/output.mp4")

        cmd = executor._build_command(mp4_plan, output_path)

        assert "-y" in cmd
        assert str(output_path) in cmd


# =============================================================================
# _action_to_args() Tests
# =============================================================================


class TestFfmpegActionToArgs:
    """Tests for FfmpegMetadataExecutor._action_to_args()."""

    def test_action_to_args_requires_track_index(self) -> None:
        """Actions without track_index should raise ValueError."""
        executor = FfmpegMetadataExecutor()
        action = PlannedAction(
            action_type=ActionType.SET_DEFAULT,
            track_index=None,
            current_value=False,
            desired_value=True,
        )

        with pytest.raises(ValueError, match="requires track_index"):
            executor._action_to_args(action)

    def test_action_to_args_reorder_raises(self) -> None:
        """REORDER action should raise ValueError (unsupported)."""
        executor = FfmpegMetadataExecutor()
        action = PlannedAction(
            action_type=ActionType.REORDER,
            track_index=0,  # Even with track_index, REORDER is unsupported
            current_value=[0, 1],
            desired_value=[1, 0],
        )

        with pytest.raises(ValueError, match="Unsupported action type"):
            executor._action_to_args(action)

    def test_action_to_args_set_title_none_raises(self) -> None:
        """SET_TITLE with None desired_value should raise ValueError."""
        executor = FfmpegMetadataExecutor()
        action = PlannedAction(
            action_type=ActionType.SET_TITLE,
            track_index=1,
            current_value="Old Title",
            desired_value=None,
        )

        with pytest.raises(ValueError, match="non-None desired_value"):
            executor._action_to_args(action)

    def test_action_to_args_set_language_none_raises(self) -> None:
        """SET_LANGUAGE with None desired_value should raise ValueError."""
        executor = FfmpegMetadataExecutor()
        action = PlannedAction(
            action_type=ActionType.SET_LANGUAGE,
            track_index=1,
            current_value="und",
            desired_value=None,
        )

        with pytest.raises(ValueError, match="non-None desired_value"):
            executor._action_to_args(action)


# =============================================================================
# Disk Space Check Tests
# =============================================================================


class TestFfmpegDiskSpaceCheck:
    """Tests for disk space check in FfmpegMetadataExecutor."""

    @patch("vpo.executor.ffmpeg_metadata.check_disk_space")
    def test_execute_insufficient_disk_space(
        self,
        mock_check: MagicMock,
        mp4_plan: Plan,
    ) -> None:
        """Should return failure when disk space is insufficient."""
        from vpo.executor.backup import InsufficientDiskSpaceError

        mock_check.side_effect = InsufficientDiskSpaceError(
            "Insufficient disk space for remux operation"
        )

        executor = FfmpegMetadataExecutor()
        result = executor.execute(mp4_plan)

        assert result.success is False
        assert "Insufficient disk space" in result.message
        mock_check.assert_called_once_with(mp4_plan.file_path, multiplier=2.0)


# =============================================================================
# Backup Handling Tests
# =============================================================================


class TestFfmpegBackupHandling:
    """Tests for backup handling in FfmpegMetadataExecutor."""

    @patch("vpo.executor.ffmpeg_metadata.check_disk_space")
    @patch("vpo.executor.ffmpeg_metadata.create_backup")
    @patch("vpo.executor.ffmpeg_metadata.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_keeps_backup_when_requested(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_backup: MagicMock,
        mock_disk_space: MagicMock,
        mp4_plan: Plan,
    ) -> None:
        """Backup should be kept when keep_backup=True."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        backup_path = Path("/test/video.mp4.vpo-backup")
        mock_backup.return_value = backup_path

        # Mock temp file
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__ = MagicMock(
            return_value=MagicMock(name="/tmp/temp.mp4")
        )
        mock_temp_ctx.__exit__ = MagicMock(return_value=False)
        mock_tempfile.return_value = mock_temp_ctx

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(Path, "replace"), patch.object(Path, "unlink"):
            executor = FfmpegMetadataExecutor()
            result = executor.execute(mp4_plan, keep_backup=True)

        assert result.success is True
        assert result.backup_path == backup_path
        # unlink should NOT be called on backup_path when keeping
        # (it might be called for temp file cleanup)

    @patch("vpo.executor.ffmpeg_metadata.check_disk_space")
    @patch("vpo.executor.ffmpeg_metadata.create_backup")
    @patch("vpo.executor.ffmpeg_metadata.require_tool")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_removes_backup_when_not_requested(
        self,
        mock_tempfile: MagicMock,
        mock_run: MagicMock,
        mock_require: MagicMock,
        mock_backup: MagicMock,
        mock_disk_space: MagicMock,
        mp4_plan: Plan,
    ) -> None:
        """Backup should be removed when keep_backup=False."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        backup_path = MagicMock(spec=Path)
        mock_backup.return_value = backup_path

        # Mock temp file
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__ = MagicMock(
            return_value=MagicMock(name="/tmp/temp.mp4")
        )
        mock_temp_ctx.__exit__ = MagicMock(return_value=False)
        mock_tempfile.return_value = mock_temp_ctx

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(Path, "replace"):
            executor = FfmpegMetadataExecutor()
            result = executor.execute(mp4_plan, keep_backup=False)

        assert result.success is True
        assert result.backup_path is None
        backup_path.unlink.assert_called_once_with(missing_ok=True)
