"""Audio extraction module using ffmpeg for streaming audio data."""

import json
import logging
import subprocess
from pathlib import Path

from video_policy_orchestrator.transcription.interface import TranscriptionError

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
    mono 16kHz WAV format suitable for Whisper processing.

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
    if not file_path.exists():
        raise AudioExtractionError(f"File not found: {file_path}")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
    ]

    # Add seek position before input for fast seeking
    if start_offset > 0:
        cmd.extend(["-ss", str(start_offset)])

    cmd.extend(
        [
            "-i",
            str(file_path),
            "-map",
            f"0:{track_index}",
            "-ac",
            "1",  # Mono
            "-ar",
            str(sample_rate),  # Sample rate
            "-f",
            "wav",  # WAV format
        ]
    )

    # Add duration limit if specified
    if sample_duration > 0:
        cmd.extend(["-t", str(sample_duration)])

    # Output to stdout
    cmd.append("pipe:1")

    logger.debug("Running ffmpeg command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=300,  # 5 minute timeout
        )
        logger.debug("Extracted %d bytes of audio data", len(result.stdout))
        return result.stdout
    except subprocess.TimeoutExpired as e:
        raise AudioExtractionError(
            f"Audio extraction timed out after 300 seconds: {file_path}"
        ) from e
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        raise AudioExtractionError(
            f"ffmpeg failed to extract audio from {file_path}: {error_msg}"
        ) from e
    except FileNotFoundError as e:
        raise AudioExtractionError(
            "ffmpeg not found. Please install ffmpeg and ensure it's in PATH."
        ) from e


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system.

    Returns:
        True if ffmpeg is available, False otherwise.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_file_duration(file_path: Path) -> float:
    """Get the duration of a media file in seconds.

    Uses ffprobe to extract duration from file format metadata.

    Args:
        file_path: Path to the media file.

    Returns:
        Duration in seconds as a float.

    Raises:
        AudioExtractionError: If duration cannot be determined.
    """
    if not file_path.exists():
        raise AudioExtractionError(f"File not found: {file_path}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(file_path),
    ]

    logger.debug("Running ffprobe command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        duration_str = data.get("format", {}).get("duration")

        if duration_str is None:
            raise AudioExtractionError(f"Could not determine duration for {file_path}")

        return float(duration_str)

    except subprocess.TimeoutExpired as e:
        raise AudioExtractionError(
            f"ffprobe timed out getting duration for {file_path}"
        ) from e
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else ""
        raise AudioExtractionError(
            f"ffprobe failed for {file_path}: {error_msg}"
        ) from e
    except (json.JSONDecodeError, ValueError) as e:
        raise AudioExtractionError(
            f"Could not parse duration for {file_path}: {e}"
        ) from e
    except FileNotFoundError as e:
        raise AudioExtractionError(
            "ffprobe not found. Please install ffmpeg and ensure it's in PATH."
        ) from e
