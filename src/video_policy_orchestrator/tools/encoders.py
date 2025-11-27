"""Hardware encoder detection and selection.

This module provides utilities for detecting available hardware encoders
and selecting the best encoder for a given codec with fallback support.

Functions in this module:
- get_software_encoder: Get FFmpeg software encoder name for a codec
- check_encoder_available: Check if an encoder is available via FFmpeg
- select_encoder: Select best available encoder with fallback support
- detect_hw_encoder_error: Detect hardware encoder errors in FFmpeg output
"""

import logging
import subprocess  # nosec B404 - subprocess is required for FFmpeg detection
from dataclasses import dataclass
from typing import Literal

from video_policy_orchestrator.executor.interface import require_tool

logger = logging.getLogger(__name__)


# Software encoder mappings by codec
SOFTWARE_ENCODERS: dict[str, str] = {
    "hevc": "libx265",
    "h265": "libx265",
    "h264": "libx264",
    "vp9": "libvpx-vp9",
    "av1": "libaom-av1",
}

# Hardware encoder mappings by codec and hardware type
HARDWARE_ENCODERS: dict[str, dict[str, str]] = {
    "hevc": {
        "nvenc": "hevc_nvenc",
        "qsv": "hevc_qsv",
        "vaapi": "hevc_vaapi",
    },
    "h265": {
        "nvenc": "hevc_nvenc",
        "qsv": "hevc_qsv",
        "vaapi": "hevc_vaapi",
    },
    "h264": {
        "nvenc": "h264_nvenc",
        "qsv": "h264_qsv",
        "vaapi": "h264_vaapi",
    },
    "av1": {
        "nvenc": "av1_nvenc",  # RTX 40 series only
        "qsv": "av1_qsv",  # Intel Arc / newer iGPU
    },
}

# Patterns in FFmpeg output that indicate hardware encoder memory/resource errors
HW_ENCODER_ERROR_PATTERNS = (
    "cannot load",
    "not found",
    "not supported",
    "nvenc",
    "cuda",
    "device",
    "memory",
    "resource",
    "initialization failed",
    "encoder not found",
    "could not open",
)


@dataclass(frozen=True)
class EncoderSelection:
    """Result of encoder selection process.

    This dataclass encapsulates all information about the selected encoder,
    including whether a fallback occurred and the hardware platform used.
    """

    encoder: str
    """FFmpeg encoder name (e.g., 'libx265', 'hevc_nvenc')."""

    encoder_type: Literal["hardware", "software"]
    """Whether this is a hardware or software encoder."""

    hw_platform: str | None = None
    """Hardware platform if hardware encoder (e.g., 'nvenc', 'qsv', 'vaapi')."""

    fallback_occurred: bool = False
    """True if fell back from preferred encoder to alternative."""


def get_software_encoder(codec: str) -> str:
    """Get FFmpeg encoder name for a codec (software encoders only).

    Args:
        codec: Target video codec (hevc, h264, vp9, av1).

    Returns:
        FFmpeg software encoder name.
    """
    return SOFTWARE_ENCODERS.get(codec.lower(), "libx265")


def check_encoder_available(encoder: str) -> bool:
    """Check if an encoder is available on this system.

    Uses FFmpeg to test if the encoder is listed in available encoders.

    Args:
        encoder: FFmpeg encoder name (e.g., 'hevc_nvenc').

    Returns:
        True if encoder appears to be available.
    """
    try:
        ffmpeg_path = require_tool("ffmpeg")
        # Use ffmpeg -encoders to check if encoder is listed
        result = subprocess.run(  # nosec B603
            [str(ffmpeg_path), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return encoder in result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return False


def select_encoder(
    codec: str,
    hw_mode: str = "auto",
    fallback_to_cpu: bool = True,
) -> EncoderSelection:
    """Select the best available encoder with fallback support.

    This function attempts to find the best encoder for the given codec,
    respecting the hardware mode preference while providing fallback
    to software encoding when hardware is unavailable.

    Args:
        codec: Target video codec (hevc, h264, vp9, av1).
        hw_mode: Hardware acceleration mode:
            - "auto": Try hardware encoders in priority order (nvenc > qsv > vaapi)
            - "nvenc": Prefer NVIDIA NVENC
            - "qsv": Prefer Intel Quick Sync Video
            - "vaapi": Prefer VA-API (Linux)
            - "none": Use software encoder only
        fallback_to_cpu: Whether to fall back to CPU if hardware unavailable.

    Returns:
        EncoderSelection with encoder name, type, and fallback info.

    Raises:
        RuntimeError: If requested hardware encoder not available and
            fallback_to_cpu is False.
    """
    codec_lower = codec.lower()

    # If explicitly set to none, use software encoder
    if hw_mode == "none":
        return EncoderSelection(
            encoder=get_software_encoder(codec_lower),
            encoder_type="software",
            hw_platform=None,
            fallback_occurred=False,
        )

    # Get hardware encoders for this codec
    hw_encoders = HARDWARE_ENCODERS.get(codec_lower, {})

    if hw_mode == "auto":
        # Try each hardware encoder in preferred order
        hw_priority = ["nvenc", "qsv", "vaapi"]
        for hw_type in hw_priority:
            if hw_type in hw_encoders:
                encoder = hw_encoders[hw_type]
                if check_encoder_available(encoder):
                    logger.info("Selected hardware encoder: %s", encoder)
                    return EncoderSelection(
                        encoder=encoder,
                        encoder_type="hardware",
                        hw_platform=hw_type,
                        fallback_occurred=False,
                    )
    else:
        # Specific hardware type requested
        if hw_mode in hw_encoders:
            encoder = hw_encoders[hw_mode]
            if check_encoder_available(encoder):
                logger.info("Selected requested hardware encoder: %s", encoder)
                return EncoderSelection(
                    encoder=encoder,
                    encoder_type="hardware",
                    hw_platform=hw_mode,
                    fallback_occurred=False,
                )
            elif not fallback_to_cpu:
                logger.error(
                    "Requested hardware encoder %s not available and "
                    "fallback_to_cpu is disabled",
                    encoder,
                )
                raise RuntimeError(
                    f"Hardware encoder {encoder} not available. "
                    "Enable fallback_to_cpu or use a different hardware mode."
                )

    # Fall back to software encoder
    logger.info("Hardware encoder not available for %s, using software encoder", codec)
    return EncoderSelection(
        encoder=get_software_encoder(codec_lower),
        encoder_type="software",
        hw_platform=None,
        fallback_occurred=hw_mode != "none",  # Only true if we tried hardware first
    )


def detect_hw_encoder_error(stderr_output: str) -> bool:
    """Check if FFmpeg stderr output indicates a hardware encoder error.

    This function analyzes FFmpeg output to detect common hardware encoder
    failures that would suggest retrying with a software encoder.

    Args:
        stderr_output: FFmpeg stderr output to analyze.

    Returns:
        True if output suggests a hardware encoder failure.
    """
    stderr_lower = stderr_output.lower()
    return any(pattern in stderr_lower for pattern in HW_ENCODER_ERROR_PATTERNS)


# Legacy compatibility function - same signature as old executor function
def select_encoder_with_fallback(
    codec: str,
    hw_mode: str = "auto",
    fallback_to_cpu: bool = True,
) -> tuple[str, str]:
    """Select the best available encoder with fallback support.

    This is a compatibility wrapper around select_encoder() that returns
    a tuple instead of EncoderSelection dataclass.

    Args:
        codec: Target video codec (hevc, h264, etc.).
        hw_mode: Hardware acceleration mode (auto, nvenc, qsv, vaapi, none).
        fallback_to_cpu: Whether to fall back to CPU if HW unavailable.

    Returns:
        Tuple of (encoder_name, encoder_type) where encoder_type is
        'hardware' or 'software'.
    """
    selection = select_encoder(codec, hw_mode, fallback_to_cpu)
    return selection.encoder, selection.encoder_type
