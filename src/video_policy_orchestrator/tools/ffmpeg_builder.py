"""Version-aware FFmpeg command builder.

This module provides utilities for building FFmpeg commands that respect
the capabilities of the detected FFmpeg version. It centralizes command
construction to handle version-specific argument differences.

Example:
    >>> from video_policy_orchestrator.tools.ffmpeg_builder import get_ffmpeg_builder
    >>> builder = get_ffmpeg_builder()
    >>> cmd = builder.base_command()
    >>> cmd = builder.with_progress(cmd)
    >>> cmd.extend(["-i", "input.mkv", "-c", "copy", "output.mkv"])
"""

from dataclasses import dataclass
from pathlib import Path

from video_policy_orchestrator.tools.models import FFmpegCapabilities


@dataclass
class FFmpegCommandBuilder:
    """Version-aware FFmpeg command builder.

    Builds FFmpeg command-line arguments that adapt to the capabilities
    of the detected FFmpeg version. This handles differences like:
    - WAV output requiring explicit codec on some builds
    - -stats_period flag (FFmpeg 4.3+) vs -stats (older)
    - -fps_mode flag (FFmpeg 5.1+) vs -vsync (older)

    Attributes:
        capabilities: FFmpegCapabilities from tool detection.
        ffmpeg_path: Path to the ffmpeg executable.
    """

    capabilities: FFmpegCapabilities
    ffmpeg_path: Path

    def base_command(self) -> list[str]:
        """Get base ffmpeg command with standard flags.

        Returns:
            Command list starting with ffmpeg path and common flags.
        """
        return [str(self.ffmpeg_path), "-hide_banner", "-y"]

    def with_loglevel(self, cmd: list[str], level: str = "error") -> list[str]:
        """Add log level control to command.

        Args:
            cmd: Existing command list.
            level: Log level (error, warning, info, verbose, debug).

        Returns:
            Command list with loglevel flags appended.
        """
        return cmd + ["-loglevel", level]

    def with_progress(self, cmd: list[str], period_seconds: int = 1) -> list[str]:
        """Add progress reporting flags (version-aware).

        Uses -stats_period for FFmpeg 4.3+, falls back to -stats for older.

        Args:
            cmd: Existing command list.
            period_seconds: Progress update interval in seconds.

        Returns:
            Command list with progress flags appended.
        """
        if self.capabilities.supports_stats_period:
            return cmd + ["-stats_period", str(period_seconds)]
        return cmd + ["-stats"]

    def wav_output_args(self, output: str = "pipe:1") -> list[str]:
        """Get arguments for WAV output (version-aware).

        Some FFmpeg builds require explicit -acodec pcm_s16le for WAV output.
        This method handles that variation automatically.

        Args:
            output: Output path or pipe specification.

        Returns:
            List of arguments for WAV output.
        """
        args: list[str] = []
        if self.capabilities.requires_explicit_pcm_codec:
            args.extend(["-acodec", "pcm_s16le"])
        args.extend(["-f", "wav", output])
        return args

    def fps_args(self, mode: str = "vfr") -> list[str]:
        """Get arguments for frame rate mode (version-aware).

        Uses -fps_mode for FFmpeg 5.1+, falls back to -vsync for older.

        Args:
            mode: Frame rate mode (vfr, cfr, passthrough, drop).

        Returns:
            List of arguments for fps mode.
        """
        if self.capabilities.supports_fps_mode:
            return ["-fps_mode", mode]
        return ["-vsync", mode]

    def audio_extract_args(
        self,
        input_path: Path,
        track_index: int,
        sample_rate: int = 16000,
        channels: int = 1,
        start_offset: float = 0.0,
        duration: int | None = None,
    ) -> list[str]:
        """Build complete audio extraction command.

        Args:
            input_path: Source media file path.
            track_index: Audio track index to extract.
            sample_rate: Output sample rate in Hz (default 16000 for Whisper).
            channels: Number of output channels (default 1 for mono).
            start_offset: Start position in seconds (0 = beginning).
            duration: Duration limit in seconds (None for full track).

        Returns:
            Complete command list for audio extraction.
        """
        cmd = self.base_command()
        cmd = self.with_loglevel(cmd, "error")

        # Add seek position before input for fast seeking
        if start_offset > 0:
            cmd.extend(["-ss", str(start_offset)])

        # Input file
        cmd.extend(["-i", str(input_path)])

        # Stream selection
        cmd.extend(["-map", f"0:{track_index}"])

        # Audio conversion
        cmd.extend(["-ac", str(channels)])
        cmd.extend(["-ar", str(sample_rate)])

        # Duration limit
        if duration is not None and duration > 0:
            cmd.extend(["-t", str(duration)])

        # Output format (version-aware)
        cmd.extend(self.wav_output_args("pipe:1"))

        return cmd


def get_ffmpeg_builder() -> FFmpegCommandBuilder:
    """Get FFmpegCommandBuilder using detected tool capabilities.

    This is a convenience function that creates a builder using the
    cached tool registry.

    Returns:
        FFmpegCommandBuilder configured with detected capabilities.

    Raises:
        RuntimeError: If FFmpeg is not available.
    """
    from video_policy_orchestrator.tools.cache import get_tool_registry

    registry = get_tool_registry()
    if not registry.ffmpeg.is_available():
        raise RuntimeError(
            "FFmpeg is not available. Install FFmpeg and ensure it's in PATH."
        )
    if registry.ffmpeg.path is None:
        raise RuntimeError("FFmpeg path is None despite being available.")

    return FFmpegCommandBuilder(
        capabilities=registry.ffmpeg.capabilities,
        ffmpeg_path=registry.ffmpeg.path,
    )
