"""FFmpeg encoder detection and configuration.

This module provides utilities for:
- Detecting available FFmpeg audio encoders
- Mapping AudioCodec enum to FFmpeg encoder names
- Looking up default bitrates by codec and channel count
"""

import logging
import subprocess  # nosec B404 - subprocess needed for FFmpeg encoder detection
from functools import lru_cache

from vpo.policy.synthesis.exceptions import (
    EncoderUnavailableError,
)
from vpo.policy.synthesis.models import (
    AudioCodec,
    get_default_bitrate,
)

logger = logging.getLogger(__name__)


# FFmpeg encoder names for each AudioCodec
CODEC_TO_ENCODER: dict[AudioCodec, str] = {
    AudioCodec.EAC3: "eac3",
    AudioCodec.AAC: "aac",
    AudioCodec.AC3: "ac3",
    AudioCodec.OPUS: "libopus",
    AudioCodec.FLAC: "flac",
}


# FFmpeg output format for each codec
CODEC_TO_FORMAT: dict[AudioCodec, str] = {
    AudioCodec.EAC3: "eac3",
    AudioCodec.AAC: "adts",  # ADTS container for standalone AAC
    AudioCodec.AC3: "ac3",
    AudioCodec.OPUS: "opus",
    AudioCodec.FLAC: "flac",
}


@lru_cache(maxsize=1)
def get_available_encoders() -> frozenset[str]:
    """Query FFmpeg for available audio encoders.

    This function is cached since encoder availability doesn't change
    during a session.

    Returns:
        Frozenset of available encoder names.
    """
    try:
        result = subprocess.run(  # nosec B603 B607 - safe fixed command
            ["ffmpeg", "-encoders", "-hide_banner"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.warning("Failed to query FFmpeg encoders: %s", result.stderr)
            return frozenset()

        encoders: set[str] = set()
        for line in result.stdout.splitlines():
            # Encoder lines start with flags like "A..... " followed by name
            # Example: " A..... aac                  AAC (Advanced Audio Coding)"
            line = line.strip()
            if line.startswith("A"):
                # Skip the flags (6 chars) and extract encoder name
                parts = line[6:].strip().split()
                if parts:
                    encoders.add(parts[0])

        logger.debug("Detected %d FFmpeg audio encoders", len(encoders))
        return frozenset(encoders)

    except subprocess.TimeoutExpired:
        logger.warning("Timeout querying FFmpeg encoders")
        return frozenset()
    except FileNotFoundError:
        logger.warning("FFmpeg not found in PATH")
        return frozenset()
    except Exception as e:
        logger.warning("Error querying FFmpeg encoders: %s", e)
        return frozenset()


def is_encoder_available(codec: AudioCodec) -> bool:
    """Check if the encoder for a codec is available.

    Args:
        codec: The audio codec to check.

    Returns:
        True if FFmpeg has the required encoder.
    """
    encoder = CODEC_TO_ENCODER.get(codec)
    if encoder is None:
        return False

    available = get_available_encoders()
    return encoder in available


def require_encoder(codec: AudioCodec) -> str:
    """Get the FFmpeg encoder name for a codec, raising if unavailable.

    Args:
        codec: The target audio codec.

    Returns:
        FFmpeg encoder name (e.g., 'eac3', 'libopus').

    Raises:
        EncoderUnavailableError: If the required encoder is not available.
    """
    encoder = CODEC_TO_ENCODER.get(codec)
    if encoder is None:
        raise ValueError(f"Unknown audio codec: {codec}")

    if not is_encoder_available(codec):
        raise EncoderUnavailableError(encoder=encoder, codec=codec.value)

    return encoder


def get_encoder_for_codec(codec: AudioCodec) -> str:
    """Get the FFmpeg encoder name for a codec.

    Args:
        codec: The target audio codec.

    Returns:
        FFmpeg encoder name.

    Raises:
        ValueError: If codec is not supported.
    """
    encoder = CODEC_TO_ENCODER.get(codec)
    if encoder is None:
        raise ValueError(f"Unknown audio codec: {codec}")
    return encoder


def get_format_for_codec(codec: AudioCodec) -> str:
    """Get the FFmpeg output format for a codec.

    Args:
        codec: The target audio codec.

    Returns:
        FFmpeg format name for the -f flag.

    Raises:
        ValueError: If codec is not supported.
    """
    fmt = CODEC_TO_FORMAT.get(codec)
    if fmt is None:
        raise ValueError(f"Unknown audio codec: {codec}")
    return fmt


def parse_bitrate(bitrate_str: str) -> int:
    """Parse a bitrate string to bits per second.

    Supports formats like '640k', '1.5M', '192000'.

    Args:
        bitrate_str: Bitrate string with optional k/M suffix.

    Returns:
        Bitrate in bits per second.

    Raises:
        ValueError: If the format is invalid.
    """
    bitrate_str = bitrate_str.strip().casefold()

    try:
        if bitrate_str.endswith("k"):
            return int(float(bitrate_str[:-1]) * 1000)
        elif bitrate_str.endswith("m"):
            return int(float(bitrate_str[:-1]) * 1000000)
        else:
            return int(bitrate_str)
    except ValueError as e:
        raise ValueError(f"Invalid bitrate format: {bitrate_str}") from e


def get_bitrate(
    codec: AudioCodec,
    channels: int,
    specified_bitrate: str | None = None,
) -> int | None:
    """Get the bitrate to use for encoding.

    Uses the specified bitrate if provided, otherwise falls back to
    the codec-specific default for the channel count.

    Args:
        codec: Target audio codec.
        channels: Number of output channels.
        specified_bitrate: User-specified bitrate string, or None.

    Returns:
        Bitrate in bits per second, or None for lossless codecs.
    """
    if specified_bitrate:
        return parse_bitrate(specified_bitrate)

    return get_default_bitrate(codec, channels)


def check_all_encoders() -> dict[AudioCodec, bool]:
    """Check availability of all supported encoders.

    Returns:
        Dict mapping each AudioCodec to its availability.
    """
    return {codec: is_encoder_available(codec) for codec in AudioCodec}


def get_unavailable_encoders() -> list[tuple[AudioCodec, str]]:
    """Get list of unavailable encoders.

    Returns:
        List of (codec, encoder_name) tuples for unavailable encoders.
    """
    result: list[tuple[AudioCodec, str]] = []
    for codec in AudioCodec:
        if not is_encoder_available(codec):
            encoder = CODEC_TO_ENCODER.get(codec, "unknown")
            result.append((codec, encoder))
    return result
