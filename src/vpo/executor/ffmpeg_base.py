"""Base class for FFmpeg-based executors.

Provides shared tool path management, disk space checking, and delegates
to ffmpeg_utils for common operations.
"""

import logging
import queue
import subprocess  # nosec B404 - subprocess is required for FFmpeg invocation
import threading
import time
from abc import ABC
from collections.abc import Callable
from pathlib import Path

from vpo.executor import ffmpeg_utils
from vpo.executor.interface import require_tool
from vpo.tools.ffmpeg_metrics import FFmpegMetricsAggregator, FFmpegMetricsSummary
from vpo.tools.ffmpeg_progress import FFmpegProgress, parse_stderr_progress

logger = logging.getLogger(__name__)


class FFmpegExecutorBase(ABC):
    """Base class for executors that use FFmpeg.

    Provides shared functionality for FFmpeg-based executors including:
    - Lazy tool path resolution
    - Codec-aware disk space checking
    - Temp file path generation
    - Output validation
    - Timeout computation

    Subclasses must implement their own execute() method appropriate
    to their use case.
    """

    DEFAULT_TIMEOUT: int = 1800  # 30 minutes
    STDERR_DRAIN_TIMEOUT: float = 5.0  # Timeout for draining stderr after process ends

    def __init__(self, timeout: int | None = None) -> None:
        """Initialize the executor.

        Args:
            timeout: Base timeout in seconds. None uses DEFAULT_TIMEOUT.
        """
        self._tool_path: Path | None = None
        self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

    @property
    def tool_path(self) -> Path:
        """Get path to ffmpeg, verifying availability.

        Returns:
            Path to ffmpeg executable.

        Raises:
            RuntimeError: If ffmpeg is not available.
        """
        if self._tool_path is None:
            self._tool_path = require_tool("ffmpeg")
        return self._tool_path

    def check_disk_space(
        self,
        path: Path,
        target_codec: str | None = None,
    ) -> str | None:
        """Check if sufficient disk space is available for the operation.

        Uses codec-aware estimation for transcode operations.

        Args:
            path: Path to input file.
            target_codec: Target codec for transcode operations.

        Returns:
            Error message if insufficient space, None if OK.
        """
        return ffmpeg_utils.check_disk_space_for_transcode(
            path, target_codec=target_codec
        )

    def create_temp_output(
        self,
        output_path: Path,
        temp_dir: Path | None = None,
    ) -> Path:
        """Create temp output path for safe write-then-move pattern.

        Args:
            output_path: Final output path.
            temp_dir: Optional directory for temp files.

        Returns:
            Path for temporary output file.
        """
        return ffmpeg_utils.create_temp_output(output_path, temp_dir)

    def validate_output(
        self,
        output_path: Path,
        input_size: int | None = None,
    ) -> tuple[bool, str | None]:
        """Validate output file after FFmpeg completes.

        Args:
            output_path: Path to output file.
            input_size: Original input file size for ratio check.

        Returns:
            Tuple of (is_valid, error_message).
        """
        return ffmpeg_utils.validate_output(output_path, input_size)

    def compute_timeout(
        self,
        file_size_bytes: int,
        is_transcode: bool = False,
    ) -> int:
        """Compute timeout for FFmpeg operation.

        Args:
            file_size_bytes: Size of input file.
            is_transcode: True if operation involves transcoding.

        Returns:
            Timeout in seconds.
        """
        return ffmpeg_utils.compute_timeout(
            file_size_bytes, is_transcode, self._timeout
        )

    def cleanup_temp(self, path: Path) -> None:
        """Remove a temporary file.

        Args:
            path: Path to temp file to remove.
        """
        ffmpeg_utils.cleanup_temp_file(path)

    def _run_ffmpeg_with_timeout(
        self,
        cmd: list[str],
        description: str,
        timeout: float | None = None,
        progress_callback: Callable[[FFmpegProgress], None] | None = None,
    ) -> tuple[bool, int, list[str], FFmpegMetricsSummary | None]:
        """Run FFmpeg command with timeout and threaded stderr reading.

        This method runs an FFmpeg command with proper timeout handling and
        optional progress reporting via callback. It uses a separate thread
        to read stderr to avoid blocking while still supporting timeouts.

        Args:
            cmd: FFmpeg command arguments.
            description: Description for logging (e.g., "pass 1", "transcode").
            timeout: Maximum time in seconds for the operation. None = no limit.
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (success, return_code, stderr_lines, metrics_summary).
            success is False if timeout expired or process failed.
            return_code is -1 on timeout, otherwise the process return code.
            metrics_summary contains aggregated encoding metrics if available.
        """
        process = subprocess.Popen(  # nosec B603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Read stderr in a separate thread to support timeout
        stderr_output: list[str] = []
        stderr_queue: queue.Queue[str | None] = queue.Queue()
        stop_event = threading.Event()

        # Metrics aggregator for collecting encoding stats
        metrics_aggregator = FFmpegMetricsAggregator()

        def read_stderr() -> None:
            """Read stderr lines and put them in the queue."""
            try:
                assert process.stderr is not None
                for line in process.stderr:
                    if stop_event.is_set():
                        break
                    stderr_queue.put(line)
            except (ValueError, OSError) as e:
                # Pipe closed or process terminated
                logger.debug("Stderr reader stopped: %s", e)
            except Exception as e:
                # Unexpected error - log for debugging
                logger.debug("Stderr reader encountered unexpected error: %s", e)
            finally:
                stderr_queue.put(None)  # Signal end of output

        reader_thread = threading.Thread(target=read_stderr, daemon=True)
        reader_thread.start()

        # Process stderr output while waiting for completion
        timeout_expired = False
        start_time = time.monotonic()

        while True:
            # Check timeout
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    timeout_expired = True
                    break

            # Check if process finished
            if process.poll() is not None:
                break

            # Read from queue with timeout to allow checking process status
            try:
                line = stderr_queue.get(timeout=1.0)
                if line is None:
                    break  # End of stderr
                stderr_output.append(line)
                # Parse progress with exception protection to avoid killing the loop
                try:
                    progress = parse_stderr_progress(line)
                    if progress:
                        # Collect metrics
                        metrics_aggregator.add_sample(progress)
                        if progress_callback:
                            try:
                                progress_callback(progress)
                            except Exception as e:
                                logger.warning("Progress callback error: %s", e)
                except Exception as e:
                    logger.debug("Failed to parse progress line: %s", e)
            except queue.Empty:
                continue

        # Handle timeout
        if timeout_expired:
            logger.warning("%s timed out after %s seconds", description, timeout)
            stop_event.set()  # Signal thread to stop
            process.kill()
            # Close stderr to unblock reader thread
            if process.stderr:
                try:
                    process.stderr.close()
                except Exception:  # nosec B110 - Intentionally ignoring close errors
                    pass
            process.wait()  # Clean up zombie process
            # Wait for reader thread to finish with shorter timeout
            reader_thread.join(timeout=2.0)
            if reader_thread.is_alive():
                logger.error(
                    "Stderr reader thread failed to terminate after timeout. "
                    "Thread will be abandoned (potential leak)."
                )
            return (False, -1, stderr_output, metrics_aggregator.summarize())

        # Signal thread to stop (process completed normally)
        stop_event.set()

        # Drain any remaining stderr output
        reader_thread.join(timeout=self.STDERR_DRAIN_TIMEOUT)
        while True:
            try:
                line = stderr_queue.get_nowait()
                if line is None:
                    break
                stderr_output.append(line)
            except queue.Empty:
                break

        # Wait for process to finish (should already be done)
        process.wait()

        return (
            process.returncode == 0,
            process.returncode,
            stderr_output,
            metrics_aggregator.summarize(),
        )
