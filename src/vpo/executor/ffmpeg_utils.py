"""FFmpeg executor utilities.

Shared utilities for FFmpeg-based executors including disk space checks,
temp file management, output validation, and timeout computation.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def check_disk_space_for_transcode(
    path: Path,
    target_codec: str | None = None,
    ratio_hevc: float = 0.5,
    ratio_other: float = 0.8,
    buffer: float = 1.2,
) -> str | None:
    """Check disk space with codec-aware estimation for transcode operations.

    Use this function for video transcode operations where the output file
    may be significantly smaller than the input (e.g., transcoding to HEVC/AV1).
    This function returns an error message string if space is insufficient,
    or None if OK. It does NOT raise exceptions for space issues.

    For backup+remux operations where output ~= input size, use
    backup.check_disk_space() instead, which raises InsufficientDiskSpaceError
    and uses a simpler 2.5x multiplier.

    Estimates required space based on target codec - HEVC/AV1 typically
    produce smaller files than other codecs.

    Args:
        path: Path to input file.
        target_codec: Target codec (e.g., 'hevc', 'h264', 'av1').
        ratio_hevc: Estimated output/input size ratio for HEVC/AV1 codecs.
        ratio_other: Estimated output/input size ratio for other codecs.
        buffer: Buffer multiplier for safety margin.

    Returns:
        Error message if insufficient space, None if OK.

    Raises:
        FileNotFoundError: If the input file does not exist.
    """
    try:
        input_size = path.stat().st_size
    except FileNotFoundError:
        # Caller passed a non-existent path; propagate so they can fix it
        raise
    except PermissionError:
        return f"Cannot access file (permission denied): {path}"
    except OSError as e:
        return f"Cannot stat file: {e}. Check filesystem health."

    # Estimate output size based on target codec
    codec = target_codec or "hevc"
    if codec.lower() in ("hevc", "h265", "av1"):
        ratio = ratio_hevc
    else:
        ratio = ratio_other

    estimated_size = int(input_size * ratio * buffer)

    # Check temp directory space
    temp_path = path.parent

    try:
        disk_usage = shutil.disk_usage(temp_path)
        if disk_usage.free < estimated_size:
            free_gb = disk_usage.free / (1024**3)
            need_gb = estimated_size / (1024**3)
            return (
                f"Insufficient disk space: {free_gb:.1f}GB free, need ~{need_gb:.1f}GB"
            )
    except PermissionError:
        return f"Cannot check disk space (permission denied): {temp_path}"
    except OSError as e:
        # Log but proceed optimistically for other OS errors (e.g., network fs issues)
        logger.warning("Could not check disk space: %s", e)

    return None


def create_temp_output(
    output_path: Path,
    temp_dir: Path | None = None,
    prefix: str = ".vpo_temp_",
) -> Path:
    """Generate temp output path for safe write-then-move pattern.

    Creates a path for a temporary output file that will be atomically
    moved to the final output location on success.

    Args:
        output_path: Final output path.
        temp_dir: Directory for temp files (None = same as output).
        prefix: Prefix for temp file name.

    Returns:
        Path for temporary output file.
    """
    if temp_dir:
        return temp_dir / f"{prefix}{output_path.name}"
    return output_path.with_name(f"{prefix}{output_path.name}")


def validate_output(
    output_path: Path,
    input_size: int | None = None,
    min_ratio: float = 0.1,
) -> tuple[bool, str | None]:
    """Validate FFmpeg output file.

    Checks that the output file exists, is non-empty, and optionally
    that it's not suspiciously small relative to the input.

    Args:
        output_path: Path to output file.
        input_size: Original input file size in bytes (optional).
        min_ratio: Minimum acceptable output/input size ratio.

    Returns:
        Tuple of (is_valid, error_message).
        error_message is None if valid.
    """
    if not output_path.exists():
        return False, f"Output file does not exist: {output_path}"

    try:
        output_size = output_path.stat().st_size
    except OSError as e:
        return False, f"Could not stat output file: {e}"

    if output_size == 0:
        return False, f"Output file is empty: {output_path}"

    # Warn if output is suspiciously small (but don't fail)
    if input_size is not None and input_size > 0:
        ratio = output_size / input_size
        if ratio < min_ratio:
            logger.warning(
                "Output file for %s is only %.1f%% of input size "
                "(%.2f MB vs %.2f MB). This may indicate a problem.",
                output_path,
                ratio * 100,
                output_size / (1024 * 1024),
                input_size / (1024 * 1024),
            )

    return True, None


def compute_timeout(
    file_size_bytes: int,
    is_transcode: bool = False,
    base_timeout: int = 1800,
    transcode_rate: int = 300,
) -> int:
    """Compute appropriate timeout based on file size and operation type.

    For transcoding operations, scales timeout based on file size since
    transcoding takes significantly longer than remuxing.

    Args:
        file_size_bytes: Size of input file in bytes.
        is_transcode: True if operation involves transcoding (not just remux).
        base_timeout: Base timeout in seconds for non-transcode operations.
        transcode_rate: Additional seconds per GB for transcode operations.

    Returns:
        Timeout in seconds.
    """
    if base_timeout <= 0:
        return 0  # No timeout

    if is_transcode:
        # Scale timeout for transcoding operations
        # Estimate ~5 minutes per GB of file size
        file_size_gb = file_size_bytes / (1024**3)
        scaled_timeout = int(file_size_gb * transcode_rate)
        return max(base_timeout, scaled_timeout)

    return base_timeout


def cleanup_temp_file(path: Path) -> None:
    """Remove a temporary file, logging any errors.

    Args:
        path: Path to temp file to remove.
    """
    if path.exists():
        try:
            path.unlink()
            logger.debug("Cleaned up temp file: %s", path)
        except OSError as e:
            logger.warning("Could not clean up temp file %s: %s", path, e)
