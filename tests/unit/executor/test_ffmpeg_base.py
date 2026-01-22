"""Tests for FFmpegExecutorBase."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.executor.ffmpeg_base import FFmpegExecutorBase
from vpo.tools.ffmpeg_progress import FFmpegProgress


class ConcreteExecutor(FFmpegExecutorBase):
    """Concrete implementation for testing abstract base class."""

    pass


# ============================================================================
# Initialization Tests
# ============================================================================


class TestFFmpegExecutorBaseInit:
    """Tests for FFmpegExecutorBase initialization."""

    def test_uses_default_timeout(self) -> None:
        """Uses DEFAULT_TIMEOUT when no timeout specified."""
        executor = ConcreteExecutor()
        assert executor._timeout == FFmpegExecutorBase.DEFAULT_TIMEOUT

    def test_uses_provided_timeout(self) -> None:
        """Uses provided timeout value."""
        executor = ConcreteExecutor(timeout=3600)
        assert executor._timeout == 3600

    def test_tool_path_initially_none(self) -> None:
        """Tool path is initially None (lazy loaded)."""
        executor = ConcreteExecutor()
        assert executor._tool_path is None


# ============================================================================
# Tool Path Tests
# ============================================================================


class TestFFmpegExecutorBaseToolPath:
    """Tests for tool_path property."""

    @patch("vpo.executor.ffmpeg_base.require_tool")
    def test_lazy_loads_tool_path(self, mock_require: MagicMock) -> None:
        """Lazily loads ffmpeg path on first access."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        executor = ConcreteExecutor()

        # First access should call require_tool
        path = executor.tool_path
        mock_require.assert_called_once_with("ffmpeg")
        assert path == Path("/usr/bin/ffmpeg")

    @patch("vpo.executor.ffmpeg_base.require_tool")
    def test_caches_tool_path(self, mock_require: MagicMock) -> None:
        """Caches tool path after first lookup."""
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        executor = ConcreteExecutor()

        # Access twice
        _ = executor.tool_path
        _ = executor.tool_path

        # Should only call require_tool once
        mock_require.assert_called_once()

    @patch("vpo.executor.ffmpeg_base.require_tool")
    def test_raises_on_missing_tool(self, mock_require: MagicMock) -> None:
        """Raises RuntimeError when ffmpeg is not available."""
        mock_require.side_effect = RuntimeError("Required tool not available: ffmpeg")
        executor = ConcreteExecutor()

        with pytest.raises(RuntimeError, match="ffmpeg"):
            _ = executor.tool_path


# ============================================================================
# Disk Space Check Tests
# ============================================================================


class TestFFmpegExecutorBaseCheckDiskSpace:
    """Tests for check_disk_space method."""

    @patch("vpo.executor.ffmpeg_utils.check_disk_space_for_transcode")
    def test_delegates_to_ffmpeg_utils(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """Delegates to ffmpeg_utils.check_disk_space_for_transcode."""
        mock_check.return_value = None
        executor = ConcreteExecutor()
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
        executor = ConcreteExecutor()
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        result = executor.check_disk_space(test_file)

        assert result == "Insufficient disk space"


# ============================================================================
# Temp Output Tests
# ============================================================================


class TestFFmpegExecutorBaseCreateTempOutput:
    """Tests for create_temp_output method."""

    @patch("vpo.executor.ffmpeg_utils.create_temp_output")
    def test_delegates_to_ffmpeg_utils(self, mock_create: MagicMock) -> None:
        """Delegates to ffmpeg_utils.create_temp_output."""
        mock_create.return_value = Path("/tmp/.vpo_temp_output.mkv")
        executor = ConcreteExecutor()

        result = executor.create_temp_output(Path("/videos/output.mkv"))

        mock_create.assert_called_once()
        assert result == Path("/tmp/.vpo_temp_output.mkv")

    @patch("vpo.executor.ffmpeg_utils.create_temp_output")
    def test_passes_temp_dir(self, mock_create: MagicMock, tmp_path: Path) -> None:
        """Passes temp_dir parameter to utility function."""
        mock_create.return_value = tmp_path / ".vpo_temp_output.mkv"
        executor = ConcreteExecutor()

        executor.create_temp_output(Path("/videos/output.mkv"), temp_dir=tmp_path)

        mock_create.assert_called_once_with(Path("/videos/output.mkv"), tmp_path)


# ============================================================================
# Output Validation Tests
# ============================================================================


class TestFFmpegExecutorBaseValidateOutput:
    """Tests for validate_output method."""

    @patch("vpo.executor.ffmpeg_utils.validate_output")
    def test_delegates_to_ffmpeg_utils(
        self, mock_validate: MagicMock, tmp_path: Path
    ) -> None:
        """Delegates to ffmpeg_utils.validate_output."""
        mock_validate.return_value = (True, None)
        executor = ConcreteExecutor()
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
        executor = ConcreteExecutor()

        is_valid, error = executor.validate_output(tmp_path / "output.mkv")

        assert is_valid is False
        assert error == "Output file is empty"


# ============================================================================
# Timeout Computation Tests
# ============================================================================


class TestFFmpegExecutorBaseComputeTimeout:
    """Tests for compute_timeout method."""

    @patch("vpo.executor.ffmpeg_utils.compute_timeout")
    def test_delegates_to_ffmpeg_utils(self, mock_compute: MagicMock) -> None:
        """Delegates to ffmpeg_utils.compute_timeout."""
        mock_compute.return_value = 3600
        executor = ConcreteExecutor(timeout=1800)

        result = executor.compute_timeout(1024**3, is_transcode=True)

        mock_compute.assert_called_once_with(1024**3, True, 1800)
        assert result == 3600

    @patch("vpo.executor.ffmpeg_utils.compute_timeout")
    def test_uses_executor_timeout(self, mock_compute: MagicMock) -> None:
        """Uses executor's timeout value as base."""
        mock_compute.return_value = 3600
        executor = ConcreteExecutor(timeout=2400)

        executor.compute_timeout(1024**3, is_transcode=False)

        # Should pass executor's timeout as base
        mock_compute.assert_called_once_with(1024**3, False, 2400)


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestFFmpegExecutorBaseCleanupTemp:
    """Tests for cleanup_temp method."""

    @patch("vpo.executor.ffmpeg_utils.cleanup_temp_file")
    def test_delegates_to_ffmpeg_utils(
        self, mock_cleanup: MagicMock, tmp_path: Path
    ) -> None:
        """Delegates to ffmpeg_utils.cleanup_temp_file."""
        executor = ConcreteExecutor()
        temp_file = tmp_path / "temp.mkv"

        executor.cleanup_temp(temp_file)

        mock_cleanup.assert_called_once_with(temp_file)


# ============================================================================
# Inheritance Tests
# ============================================================================


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


# ============================================================================
# _run_ffmpeg_with_timeout Tests
# ============================================================================


class TestRunFFmpegWithTimeout:
    """Tests for _run_ffmpeg_with_timeout method."""

    def test_success_returns_true_and_zero_returncode(self):
        """Should return success=True and returncode=0 on successful execution."""
        executor = ConcreteExecutor()
        with patch("vpo.executor.ffmpeg_base.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.poll.side_effect = [None, 0]
            mock_process.stderr.readline.return_value = ""
            mock_process.stderr.__iter__ = lambda self: iter([])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            success, rc, stderr_lines, metrics = executor._run_ffmpeg_with_timeout(
                ["ffmpeg", "-i", "input.mkv", "output.mp4"],
                "test operation",
            )

            assert success is True
            assert rc == 0

    def test_failure_returns_false_and_nonzero_returncode(self):
        """Should return success=False and actual returncode on failure."""
        executor = ConcreteExecutor()
        with patch("vpo.executor.ffmpeg_base.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 1
            mock_process.poll.side_effect = [None, 1]
            mock_process.stderr.__iter__ = lambda self: iter([])
            mock_process.wait.return_value = 1
            mock_popen.return_value = mock_process

            success, rc, stderr_lines, metrics = executor._run_ffmpeg_with_timeout(
                ["ffmpeg", "-i", "input.mkv", "output.mp4"],
                "test operation",
            )

            assert success is False
            assert rc == 1

    def test_timeout_returns_false_and_minus_one(self):
        """Should return success=False and rc=-1 when timeout expires."""
        executor = ConcreteExecutor()

        with (
            patch("vpo.executor.ffmpeg_base.subprocess.Popen") as mock_popen,
            patch("vpo.executor.ffmpeg_base.time.monotonic") as mock_time,
        ):
            mock_process = MagicMock()
            mock_process.returncode = -9
            mock_process.poll.return_value = None  # Process never completes
            mock_process.stderr.__iter__ = lambda self: iter([])
            mock_process.stderr.close.return_value = None
            mock_process.kill.return_value = None
            mock_process.wait.return_value = -9
            mock_popen.return_value = mock_process

            # Simulate time progressing past the timeout
            mock_time.side_effect = [0.0, 100.0]  # start_time=0, elapsed=100

            success, rc, stderr_lines, metrics = executor._run_ffmpeg_with_timeout(
                ["ffmpeg", "-i", "input.mkv", "output.mp4"],
                "test operation",
                timeout=10.0,
            )

            assert success is False
            assert rc == -1
            mock_process.kill.assert_called_once()

    def test_progress_callback_invoked_with_parsed_progress(self):
        """Should invoke progress callback when progress lines are parsed."""
        executor = ConcreteExecutor()
        callback_calls = []

        def mock_callback(progress: FFmpegProgress):
            callback_calls.append(progress)

        with patch("vpo.executor.ffmpeg_base.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.poll.side_effect = [None, None, 0]

            # Simulate FFmpeg stderr output with progress line
            progress_line = (
                "frame=  100 fps= 30 time=00:00:03.33 bitrate=1000kbits/s speed=1.0x"
            )
            mock_process.stderr.__iter__ = lambda self: iter([progress_line])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            success, rc, stderr_lines, metrics = executor._run_ffmpeg_with_timeout(
                ["ffmpeg", "-i", "input.mkv", "output.mp4"],
                "test operation",
                progress_callback=mock_callback,
            )

            assert success is True
            assert len(callback_calls) == 1
            assert callback_calls[0].frame == 100
            assert callback_calls[0].fps == 30.0

    def test_no_callback_when_none_provided(self):
        """Should not fail when progress_callback is None."""
        executor = ConcreteExecutor()
        with patch("vpo.executor.ffmpeg_base.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.poll.side_effect = [None, 0]
            mock_process.stderr.__iter__ = lambda self: iter(
                ["frame=  100 fps= 30 time=00:00:03.33 bitrate=1000kbits/s speed=1.0x"]
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            # Should not raise even without callback
            success, rc, stderr_lines, metrics = executor._run_ffmpeg_with_timeout(
                ["ffmpeg", "-i", "input.mkv", "output.mp4"],
                "test operation",
                progress_callback=None,
            )

            assert success is True

    def test_metrics_aggregator_collects_fps_samples(self):
        """Should collect metrics from progress lines."""
        executor = ConcreteExecutor()
        with patch("vpo.executor.ffmpeg_base.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.poll.side_effect = [None, None, None, 0]

            # Multiple progress lines
            progress_lines = [
                "frame=  100 fps= 30 time=00:00:03.33 bitrate=1000kbits/s speed=1.0x",
                "frame=  200 fps= 35 time=00:00:06.66 bitrate=1200kbits/s speed=1.2x",
            ]
            mock_process.stderr.__iter__ = lambda self: iter(progress_lines)
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            success, rc, stderr_lines, metrics = executor._run_ffmpeg_with_timeout(
                ["ffmpeg", "-i", "input.mkv", "output.mp4"],
                "test operation",
            )

            assert success is True
            assert metrics is not None
            assert metrics.sample_count == 2
            assert metrics.avg_fps is not None
            assert metrics.avg_fps > 0

    def test_stderr_lines_collected(self):
        """Should collect all stderr lines in output."""
        executor = ConcreteExecutor()
        with patch("vpo.executor.ffmpeg_base.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.poll.side_effect = [None, None, 0]

            stderr_lines = [
                "Some info line\n",
                "frame=  100 fps= 30 time=00:00:03.33 bitrate=1000kbits/s speed=1.0x\n",
            ]
            mock_process.stderr.__iter__ = lambda self: iter(stderr_lines)
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            success, rc, result_lines, metrics = executor._run_ffmpeg_with_timeout(
                ["ffmpeg", "-i", "input.mkv", "output.mp4"],
                "test operation",
            )

            assert success is True
            assert len(result_lines) == 2
            assert "Some info line" in result_lines[0]


# ============================================================================
# FFmpegRemuxExecutor Progress Callback Tests
# ============================================================================


class TestFFmpegRemuxExecutorProgressCallback:
    """Tests for FFmpegRemuxExecutor with progress callback."""

    def test_constructor_accepts_progress_callback(self):
        """Should accept progress_callback in constructor."""
        from vpo.executor.ffmpeg_remux import FFmpegRemuxExecutor

        callback = MagicMock()
        executor = FFmpegRemuxExecutor(progress_callback=callback)

        assert executor.progress_callback is callback

    def test_constructor_defaults_progress_callback_to_none(self):
        """Should default progress_callback to None."""
        from vpo.executor.ffmpeg_remux import FFmpegRemuxExecutor

        executor = FFmpegRemuxExecutor()

        assert executor.progress_callback is None
