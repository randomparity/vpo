"""Base class for FFmpeg-based executors.

Provides shared tool path management, disk space checking, and delegates
to ffmpeg_utils for common operations.
"""

from abc import ABC
from pathlib import Path

from vpo.executor import ffmpeg_utils
from vpo.executor.interface import require_tool


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
