"""Unit tests for FFmpegExecutorBase class."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.executor.ffmpeg_base import FFmpegExecutorBase


class ConcreteFFmpegExecutor(FFmpegExecutorBase):
    """Concrete implementation for testing the abstract base class."""

    pass


class TestFFmpegExecutorBaseInit:
    """Tests for FFmpegExecutorBase initialization."""

    def test_uses_default_timeout(self) -> None:
        """Uses DEFAULT_TIMEOUT when no timeout specified."""
        executor = ConcreteFFmpegExecutor()
        assert executor._timeout == FFmpegExecutorBase.DEFAULT_TIMEOUT

    def test_uses_provided_timeout(self) -> None:
        """Uses provided timeout value."""
        executor = ConcreteFFmpegExecutor(timeout=3600)
        assert executor._timeout == 3600

    def test_tool_path_initially_none(self) -> None:
        """Tool path is initially None (lazy loaded)."""
        executor = ConcreteFFmpegExecutor()
        assert executor._tool_path is None


class TestFFmpegExecutorBaseToolPath:
    """Tests for tool_path property."""

    @patch("vpo.executor.ffmpeg_base.require_tool")
    def test_lazy_loads_tool_path(self, mock_require: MagicMock) -> None:
        """Lazily loads ffmpeg path on first access."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        executor = ConcreteFFmpegExecutor()

        # First access should call require_tool
        path = executor.tool_path
        mock_require.assert_called_once_with("ffmpeg")
        assert path == Path("/usr/bin/ffmpeg")

    @patch("vpo.executor.ffmpeg_base.require_tool")
    def test_caches_tool_path(self, mock_require: MagicMock) -> None:
        """Caches tool path after first lookup."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        executor = ConcreteFFmpegExecutor()

        # Access twice
        _ = executor.tool_path
        _ = executor.tool_path

        # Should only call require_tool once
        mock_require.assert_called_once()

    @patch("vpo.executor.ffmpeg_base.require_tool")
    def test_raises_on_missing_tool(self, mock_require: MagicMock) -> None:
        """Raises RuntimeError when ffmpeg is not available."""
        mock_require.side_effect = RuntimeError("Required tool not available: ffmpeg")
        executor = ConcreteFFmpegExecutor()

        with pytest.raises(RuntimeError, match="ffmpeg"):
            _ = executor.tool_path


class TestFFmpegExecutorBaseCheckDiskSpace:
    """Tests for check_disk_space method."""

    @patch("vpo.executor.ffmpeg_utils.check_disk_space_for_transcode")
    def test_delegates_to_ffmpeg_utils(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """Delegates to ffmpeg_utils.check_disk_space_for_transcode."""
        mock_check.return_value = None
        executor = ConcreteFFmpegExecutor()
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        result = executor.check_disk_space(test_file, target_codec="hevc")

        mock_check.assert_called_once_with(test_file, target_codec="hevc")
        assert result is None

    @patch("vpo.executor.ffmpeg_utils.check_disk_space_for_transcode")
    def test_returns_error_on_insufficient_space(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """Returns error message when space is insufficient."""
        mock_check.return_value = "Insufficient disk space"
        executor = ConcreteFFmpegExecutor()
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        result = executor.check_disk_space(test_file)

        assert result == "Insufficient disk space"


class TestFFmpegExecutorBaseCreateTempOutput:
    """Tests for create_temp_output method."""

    @patch("vpo.executor.ffmpeg_utils.create_temp_output")
    def test_delegates_to_ffmpeg_utils(self, mock_create: MagicMock) -> None:
        """Delegates to ffmpeg_utils.create_temp_output."""
        mock_create.return_value = Path("/tmp/.vpo_temp_output.mkv")
        executor = ConcreteFFmpegExecutor()

        result = executor.create_temp_output(Path("/videos/output.mkv"))

        mock_create.assert_called_once()
        assert result == Path("/tmp/.vpo_temp_output.mkv")

    @patch("vpo.executor.ffmpeg_utils.create_temp_output")
    def test_passes_temp_dir(self, mock_create: MagicMock, tmp_path: Path) -> None:
        """Passes temp_dir parameter to utility function."""
        mock_create.return_value = tmp_path / ".vpo_temp_output.mkv"
        executor = ConcreteFFmpegExecutor()

        executor.create_temp_output(Path("/videos/output.mkv"), temp_dir=tmp_path)

        mock_create.assert_called_once_with(Path("/videos/output.mkv"), tmp_path)


class TestFFmpegExecutorBaseValidateOutput:
    """Tests for validate_output method."""

    @patch("vpo.executor.ffmpeg_utils.validate_output")
    def test_delegates_to_ffmpeg_utils(
        self, mock_validate: MagicMock, tmp_path: Path
    ) -> None:
        """Delegates to ffmpeg_utils.validate_output."""
        mock_validate.return_value = (True, None)
        executor = ConcreteFFmpegExecutor()
        output_file = tmp_path / "output.mkv"
        output_file.write_bytes(b"x" * 1000)

        is_valid, error = executor.validate_output(output_file, input_size=2000)

        mock_validate.assert_called_once_with(output_file, 2000)
        assert is_valid is True
        assert error is None

    @patch("vpo.executor.ffmpeg_utils.validate_output")
    def test_returns_error_on_invalid_output(
        self, mock_validate: MagicMock, tmp_path: Path
    ) -> None:
        """Returns error tuple when output is invalid."""
        mock_validate.return_value = (False, "Output file is empty")
        executor = ConcreteFFmpegExecutor()

        is_valid, error = executor.validate_output(tmp_path / "output.mkv")

        assert is_valid is False
        assert error == "Output file is empty"


class TestFFmpegExecutorBaseComputeTimeout:
    """Tests for compute_timeout method."""

    @patch("vpo.executor.ffmpeg_utils.compute_timeout")
    def test_delegates_to_ffmpeg_utils(self, mock_compute: MagicMock) -> None:
        """Delegates to ffmpeg_utils.compute_timeout."""
        mock_compute.return_value = 3600
        executor = ConcreteFFmpegExecutor(timeout=1800)

        result = executor.compute_timeout(1024**3, is_transcode=True)

        mock_compute.assert_called_once_with(1024**3, True, 1800)
        assert result == 3600

    @patch("vpo.executor.ffmpeg_utils.compute_timeout")
    def test_uses_executor_timeout(self, mock_compute: MagicMock) -> None:
        """Uses executor's timeout value as base."""
        mock_compute.return_value = 3600
        executor = ConcreteFFmpegExecutor(timeout=2400)

        executor.compute_timeout(1024**3, is_transcode=False)

        # Should pass executor's timeout as base
        mock_compute.assert_called_once_with(1024**3, False, 2400)


class TestFFmpegExecutorBaseCleanupTemp:
    """Tests for cleanup_temp method."""

    @patch("vpo.executor.ffmpeg_utils.cleanup_temp_file")
    def test_delegates_to_ffmpeg_utils(
        self, mock_cleanup: MagicMock, tmp_path: Path
    ) -> None:
        """Delegates to ffmpeg_utils.cleanup_temp_file."""
        executor = ConcreteFFmpegExecutor()
        temp_file = tmp_path / "temp.mkv"

        executor.cleanup_temp(temp_file)

        mock_cleanup.assert_called_once_with(temp_file)


class TestFFmpegExecutorBaseInheritance:
    """Tests for proper inheritance behavior."""

    def test_ffmpeg_remux_executor_inherits_base(self) -> None:
        """FFmpegRemuxExecutor inherits from FFmpegExecutorBase."""
        from vpo.executor.ffmpeg_remux import FFmpegRemuxExecutor

        assert issubclass(FFmpegRemuxExecutor, FFmpegExecutorBase)

    def test_transcode_executor_inherits_base(self) -> None:
        """TranscodeExecutor inherits from FFmpegExecutorBase."""
        from vpo.executor.transcode.executor import TranscodeExecutor

        assert issubclass(TranscodeExecutor, FFmpegExecutorBase)
