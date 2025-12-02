"""FFmpeg adapter for version-aware command execution.

This module provides a high-level interface for FFmpeg operations that
automatically adapts to the detected FFmpeg version's capabilities.
It handles common operations like audio extraction while abstracting
away version-specific command-line differences.

Example:
    >>> from video_policy_orchestrator.tools.ffmpeg_adapter import get_ffmpeg_adapter
    >>> adapter = get_ffmpeg_adapter()
    >>> wav_data = adapter.extract_audio_stream(
    ...     input_path=Path("/path/to/video.mkv"),
    ...     track_index=1,
    ...     sample_duration=30,
    ... )
"""

import subprocess  # nosec B404 - subprocess is required for FFmpeg execution
from dataclasses import dataclass
from pathlib import Path

from video_policy_orchestrator.tools.ffmpeg_builder import FFmpegCommandBuilder
from video_policy_orchestrator.tools.models import ToolRegistry


class FFmpegError(Exception):
    """Base class for FFmpeg-related errors."""

    pass


class FFmpegVersionError(FFmpegError):
    """Error due to FFmpeg version incompatibility.

    Raised when the installed FFmpeg version is too old for a required feature.
    """

    def __init__(
        self,
        feature: str,
        required_version: tuple[int, ...],
        actual_version: tuple[int, ...] | None,
    ):
        self.feature = feature
        self.required_version = required_version
        self.actual_version = actual_version

        req_str = ".".join(str(v) for v in required_version)
        act_str = (
            ".".join(str(v) for v in actual_version) if actual_version else "unknown"
        )
        super().__init__(
            f"FFmpeg {req_str}+ required for {feature}, but found {act_str}. "
            f"Upgrade FFmpeg: https://ffmpeg.org/download.html"
        )


class FFmpegCapabilityError(FFmpegError):
    """Error due to missing FFmpeg capability.

    Raised when FFmpeg is missing a required encoder, decoder, or feature.
    """

    def __init__(self, capability: str, suggestion: str = ""):
        self.capability = capability
        msg = f"FFmpeg missing required capability: {capability}"
        if suggestion:
            msg += f". {suggestion}"
        super().__init__(msg)


@dataclass
class FFmpegAdapter:
    """High-level adapter for version-aware FFmpeg operations.

    Provides a clean interface for common FFmpeg operations while
    automatically handling version-specific command-line differences.

    Attributes:
        registry: ToolRegistry containing detected tool capabilities.
    """

    registry: ToolRegistry

    @property
    def builder(self) -> FFmpegCommandBuilder:
        """Get FFmpegCommandBuilder for the detected FFmpeg.

        Returns:
            Configured FFmpegCommandBuilder.

        Raises:
            FFmpegError: If FFmpeg is not available.
        """
        ffmpeg = self.registry.ffmpeg
        if not ffmpeg.is_available():
            raise FFmpegError("FFmpeg is not available")
        if ffmpeg.path is None:
            raise FFmpegError("FFmpeg path is None")
        return FFmpegCommandBuilder(
            capabilities=ffmpeg.capabilities,
            ffmpeg_path=ffmpeg.path,
        )

    def extract_audio_stream(
        self,
        input_path: Path,
        track_index: int,
        sample_rate: int = 16000,
        sample_duration: int | None = None,
        start_offset: float = 0.0,
        timeout: int = 300,
    ) -> bytes:
        """Extract audio stream as WAV data.

        Extracts audio from a specific track, converting to mono WAV
        suitable for Whisper transcription. Handles version-specific
        codec requirements automatically.

        Args:
            input_path: Source media file path.
            track_index: Index of the audio track to extract.
            sample_rate: Output sample rate in Hz (default 16000 for Whisper).
            sample_duration: Duration limit in seconds (None for full track).
            start_offset: Start position in seconds from beginning.
            timeout: Command timeout in seconds (default 300 = 5 minutes).

        Returns:
            Raw WAV audio data as bytes.

        Raises:
            FFmpegError: If extraction fails.
        """
        if not input_path.exists():
            raise FFmpegError(f"File not found: {input_path}")

        cmd = self.builder.audio_extract_args(
            input_path=input_path,
            track_index=track_index,
            sample_rate=sample_rate,
            channels=1,
            start_offset=start_offset,
            duration=sample_duration,
        )

        try:
            result = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                check=True,
                timeout=timeout,
            )
            return result.stdout

        except subprocess.TimeoutExpired as e:
            raise FFmpegError(
                f"FFmpeg timed out after {timeout}s extracting audio from {input_path}"
            ) from e

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise FFmpegError(
                f"FFmpeg failed to extract audio from {input_path}: {stderr}"
            ) from e

        except FileNotFoundError as e:
            raise FFmpegError(
                "FFmpeg not found. Install FFmpeg and ensure it's in PATH."
            ) from e

    def get_file_duration(self, file_path: Path, timeout: int = 30) -> float:
        """Get the duration of a media file in seconds.

        Uses ffprobe to extract duration from file format metadata.

        Args:
            file_path: Path to the media file.
            timeout: Command timeout in seconds.

        Returns:
            Duration in seconds as a float.

        Raises:
            FFmpegError: If duration cannot be determined.
        """
        import json

        if not file_path.exists():
            raise FFmpegError(f"File not found: {file_path}")

        ffprobe = self.registry.ffprobe
        if not ffprobe.is_available() or ffprobe.path is None:
            raise FFmpegError("ffprobe is not available")

        cmd = [
            str(ffprobe.path),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(file_path),
        ]

        try:
            result = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )
            data = json.loads(result.stdout)
            duration_str = data.get("format", {}).get("duration")

            if duration_str is None:
                raise FFmpegError(f"Could not determine duration for {file_path}")

            return float(duration_str)

        except subprocess.TimeoutExpired as e:
            raise FFmpegError(
                f"ffprobe timed out getting duration for {file_path}"
            ) from e

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else ""
            raise FFmpegError(f"ffprobe failed for {file_path}: {error_msg}") from e

        except (json.JSONDecodeError, ValueError) as e:
            raise FFmpegError(f"Could not parse duration for {file_path}: {e}") from e


# Module-level cached adapter
_adapter_cache: FFmpegAdapter | None = None


def get_ffmpeg_adapter() -> FFmpegAdapter:
    """Get cached FFmpegAdapter instance.

    Creates and caches an FFmpegAdapter using the tool registry.
    The adapter is cached for efficiency across multiple calls.

    Returns:
        Configured FFmpegAdapter.

    Example:
        >>> adapter = get_ffmpeg_adapter()
        >>> wav = adapter.extract_audio_stream(path, track_index=1)
    """
    global _adapter_cache
    if _adapter_cache is None:
        from video_policy_orchestrator.tools.cache import get_tool_registry

        _adapter_cache = FFmpegAdapter(get_tool_registry())
    return _adapter_cache


def reset_ffmpeg_adapter() -> None:
    """Reset the cached FFmpegAdapter.

    Call this after refreshing the tool registry to ensure the adapter
    picks up new capabilities.
    """
    global _adapter_cache
    _adapter_cache = None
