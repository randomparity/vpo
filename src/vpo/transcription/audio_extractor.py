"""Audio extraction module using ffmpeg for streaming audio data.

This module provides functions to extract audio streams from video files
for transcription processing. It uses the version-aware FFmpegAdapter
to handle ffmpeg command-line differences across versions.
"""

import logging
from pathlib import Path

from vpo.transcription.interface import TranscriptionError

logger = logging.getLogger(__name__)


class AudioExtractionError(TranscriptionError):
    """Raised when audio extraction fails."""

    pass


def extract_audio_stream(
    file_path: Path,
    track_index: int,
    sample_duration: int = 60,
    sample_rate: int = 16000,
    start_offset: float = 0.0,
) -> bytes:
    """Extract audio from a specific track as WAV data.

    Uses ffmpeg to extract audio from a video file, converting it to
    mono 16kHz WAV format suitable for Whisper processing. Automatically
    handles version-specific ffmpeg command differences.

    Args:
        file_path: Path to the video file.
        track_index: Index of the audio track to extract.
        sample_duration: Duration in seconds to extract (0 = full track).
        sample_rate: Output sample rate in Hz (default 16000 for Whisper).
        start_offset: Start position in seconds from beginning of track.

    Returns:
        Raw WAV audio data as bytes.

    Raises:
        AudioExtractionError: If extraction fails.
    """
    from vpo.tools.ffmpeg_adapter import (
        FFmpegError,
        get_ffmpeg_adapter,
    )

    try:
        adapter = get_ffmpeg_adapter()
        wav_data = adapter.extract_audio_stream(
            input_path=file_path,
            track_index=track_index,
            sample_rate=sample_rate,
            sample_duration=sample_duration if sample_duration > 0 else None,
            start_offset=start_offset,
        )
        logger.debug("Extracted %d bytes of audio data", len(wav_data))
        return wav_data

    except FFmpegError as e:
        raise AudioExtractionError(str(e)) from e


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system.

    Uses the tool registry to check ffmpeg availability, ensuring
    configured paths are respected.

    Returns:
        True if ffmpeg is available, False otherwise.
    """
    try:
        from vpo.tools.cache import get_tool_registry

        registry = get_tool_registry()
        return registry.ffmpeg.is_available()
    except Exception:
        return False


def get_file_duration(file_path: Path) -> float:
    """Get the duration of a media file in seconds.

    Uses ffprobe to extract duration from file format metadata.
    Respects configured tool paths.

    Args:
        file_path: Path to the media file.

    Returns:
        Duration in seconds as a float.

    Raises:
        AudioExtractionError: If duration cannot be determined.
    """
    from vpo.tools.ffmpeg_adapter import (
        FFmpegError,
        get_ffmpeg_adapter,
    )

    try:
        adapter = get_ffmpeg_adapter()
        return adapter.get_file_duration(file_path)
    except FFmpegError as e:
        raise AudioExtractionError(str(e)) from e


__all__ = [
    "AudioExtractionError",
    "extract_audio_stream",
    "get_file_duration",
    "is_ffmpeg_available",
]
