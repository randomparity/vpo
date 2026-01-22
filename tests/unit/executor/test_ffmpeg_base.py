"""Tests for FFmpegExecutorBase."""

from unittest.mock import MagicMock, patch

from vpo.executor.ffmpeg_base import FFmpegExecutorBase
from vpo.tools.ffmpeg_progress import FFmpegProgress


class ConcreteExecutor(FFmpegExecutorBase):
    """Concrete implementation for testing abstract base class."""

    pass


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
