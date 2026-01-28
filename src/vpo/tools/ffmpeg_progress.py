"""FFmpeg progress parsing utilities.

This module provides utilities for parsing FFmpeg progress output, both from
the -progress flag output and from stderr progress lines.
"""

import re
from dataclasses import dataclass


@dataclass
class FFmpegProgress:
    """Parsed FFmpeg progress output."""

    frame: int | None = None
    fps: float | None = None
    bitrate: str | None = None
    total_size: int | None = None
    out_time_us: int | None = None  # Output time in microseconds
    speed: str | None = None

    @property
    def out_time_seconds(self) -> float | None:
        """Get output time in seconds."""
        if self.out_time_us is not None:
            return self.out_time_us / 1_000_000
        return None

    def get_percent(self, duration_seconds: float | None) -> float:
        """Calculate progress percentage based on duration.

        Args:
            duration_seconds: Total duration of the file in seconds.

        Returns:
            Progress percentage (0.0 to 100.0), or 0.0 if unknown.
        """
        if duration_seconds is None or duration_seconds <= 0:
            return 0.0
        out_time = self.out_time_seconds
        if out_time is None:
            return 0.0
        return min(100.0, (out_time / duration_seconds) * 100)


# Regex patterns for FFmpeg progress output
PROGRESS_PATTERNS = {
    "frame": re.compile(r"frame=\s*(\d+)"),
    "fps": re.compile(r"fps=\s*([\d.]+)"),
    "bitrate": re.compile(r"bitrate=\s*([^\s]+)"),
    "total_size": re.compile(r"total_size=\s*(\d+)"),
    "out_time_us": re.compile(r"out_time_us=\s*(\d+)"),
    "speed": re.compile(r"speed=\s*([^\s]+)"),
}

# Keys that require numeric conversion (return None on parse failure)
_NUMERIC_KEYS = frozenset(("frame", "total_size", "out_time_us", "fps"))

# All valid progress keys
_VALID_KEYS = frozenset(
    ("frame", "total_size", "out_time_us", "fps", "bitrate", "speed")
)


def _convert_progress_value(key: str, value: str) -> int | float | str | None:
    """Convert a progress value to the appropriate type.

    Args:
        key: The field name.
        value: The string value to convert.

    Returns:
        Converted value or None.
    """
    if key in ("frame", "total_size", "out_time_us"):
        try:
            return int(value)
        except ValueError:
            return None
    if key == "fps":
        try:
            return float(value)
        except ValueError:
            return None
    return value if value != "N/A" else None


def parse_progress_line(line: str) -> dict[str, str | int | float | None]:
    """Parse a single line from FFmpeg progress output.

    Args:
        line: A line from FFmpeg's -progress output.

    Returns:
        Dictionary with parsed key-value pair, or empty dict if not parseable.
    """
    line = line.strip()
    if "=" not in line:
        return {}

    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip()

    if key not in _VALID_KEYS:
        return {}

    converted = _convert_progress_value(key, value)
    if converted is None and key in _NUMERIC_KEYS:
        return {}
    return {key: converted}


def parse_progress_block(block: str) -> FFmpegProgress:
    """Parse a complete FFmpeg progress block.

    FFmpeg with -progress outputs blocks separated by "progress=" lines.

    Args:
        block: A block of progress output lines.

    Returns:
        Parsed FFmpegProgress object.
    """
    result = FFmpegProgress()
    for line in block.split("\n"):
        parsed = parse_progress_line(line)
        for key, value in parsed.items():
            if hasattr(result, key):
                setattr(result, key, value)
    return result


def parse_stderr_progress(line: str) -> FFmpegProgress | None:
    """Parse FFmpeg stderr progress line.

    FFmpeg outputs progress to stderr in format:
    frame= 1234 fps= 30 ... time=00:01:23.45 bitrate=5000kbits/s speed=2.0x

    Args:
        line: A line from FFmpeg stderr.

    Returns:
        Parsed FFmpegProgress or None if not a progress line.
    """
    if "frame=" not in line:
        return None

    result = FFmpegProgress()

    for key, pattern in PROGRESS_PATTERNS.items():
        match = pattern.search(line)
        if match:
            converted = _convert_progress_value(key, match.group(1))
            if converted is not None:
                setattr(result, key, converted)

    # Also try to parse time= format from stderr
    time_match = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", line)
    if time_match:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        seconds = int(time_match.group(3))
        centiseconds = int(time_match.group(4))
        result.out_time_us = (
            hours * 3600 + minutes * 60 + seconds
        ) * 1_000_000 + centiseconds * 10_000

    return result
