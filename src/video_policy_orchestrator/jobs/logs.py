"""Log file utilities for job execution logs.

This module provides utilities for reading and managing job log files.
Logs are stored as plain text files in the VPO data directory.
"""

import re
from itertools import islice
from pathlib import Path

# Default number of lines to return when reading logs
DEFAULT_LOG_LINES = 500

# Maximum log file size to read entirely into memory (10MB)
MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024

# Regex for validating UUID format (prevents path traversal)
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_job_id(job_id: str) -> None:
    """Validate that a job ID is a valid UUID format.

    This is a security measure to prevent path traversal attacks.
    A valid UUID cannot contain path separators or traversal sequences.

    Args:
        job_id: The job ID to validate.

    Raises:
        ValueError: If job_id is not a valid UUID format.
    """
    if not _UUID_PATTERN.match(job_id):
        raise ValueError(f"Invalid job ID format: {job_id}")


def get_log_directory() -> Path:
    """Get the logs directory path.

    Returns:
        Path to the logs directory (~/.vpo/logs/).
    """
    from video_policy_orchestrator.config.loader import get_data_dir

    return get_data_dir() / "logs"


def get_log_path(job_id: str) -> Path:
    """Get the log file path for a job.

    Validates the job ID to prevent path traversal attacks.

    Args:
        job_id: The job UUID.

    Returns:
        Path to the log file for the job.

    Raises:
        ValueError: If job_id is not a valid UUID format.
    """
    _validate_job_id(job_id)
    log_path = get_log_directory() / f"{job_id}.log"

    # Defense in depth: verify resolved path is within log directory
    log_dir = get_log_directory().resolve()
    resolved_path = log_path.resolve()
    if not str(resolved_path).startswith(str(log_dir)):
        raise ValueError(f"Invalid job ID - path traversal detected: {job_id}")

    return log_path


def ensure_log_directory() -> Path:
    """Ensure the logs directory exists.

    Returns:
        Path to the logs directory.
    """
    log_dir = get_log_directory()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def count_log_lines(job_id: str) -> int:
    """Count total lines in a job's log file.

    Args:
        job_id: The job UUID.

    Returns:
        Total number of lines in the log file, or 0 if file doesn't exist
        or cannot be read.

    Raises:
        ValueError: If job_id is not a valid UUID format.
    """
    try:
        log_path = get_log_path(job_id)
    except ValueError:
        # Invalid job ID format
        return 0

    if not log_path.exists():
        return 0

    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        # File may be locked or inaccessible
        return 0


def read_log_tail(
    job_id: str,
    lines: int = DEFAULT_LOG_LINES,
    offset: int = 0,
) -> tuple[list[str], int, bool]:
    """Read log lines from a job's log file.

    Reads lines starting from the given offset. Uses memory-efficient
    line-by-line iteration for large files.

    Args:
        job_id: The job UUID.
        lines: Maximum number of lines to return (default 500).
        offset: Number of lines to skip from the beginning (default 0).

    Returns:
        Tuple of:
            - List of log lines (strings without trailing newlines)
            - Total number of lines in the file
            - Boolean indicating whether more lines are available

    Raises:
        ValueError: If job_id is not a valid UUID format.
    """
    try:
        log_path = get_log_path(job_id)
    except ValueError:
        # Invalid job ID format
        return [], 0, False

    if not log_path.exists():
        return [], 0, False

    try:
        file_size = log_path.stat().st_size
    except OSError:
        return [], 0, False

    try:
        # For small files, read all at once (faster)
        if file_size <= MAX_LOG_SIZE_BYTES:
            with log_path.open("r", encoding="utf-8", errors="replace") as f:
                all_lines = f.read().splitlines()

            total = len(all_lines)
            chunk = all_lines[offset : offset + lines]
            has_more = offset + lines < total
            return chunk, total, has_more

        # For large files, use memory-efficient iteration
        return _read_log_tail_streaming(log_path, lines, offset)

    except OSError:
        # File may be locked or inaccessible
        return [], 0, False


def _read_log_tail_streaming(
    log_path: Path,
    lines: int,
    offset: int,
) -> tuple[list[str], int, bool]:
    """Read log lines using memory-efficient streaming for large files.

    Args:
        log_path: Path to the log file.
        lines: Maximum number of lines to return.
        offset: Number of lines to skip from the beginning.

    Returns:
        Tuple of (lines, total, has_more).
    """
    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        # Count total lines first (memory-efficient generator)
        total = sum(1 for _ in f)

        # Seek back to beginning
        f.seek(0)

        # Skip to offset and read requested lines
        chunk = [line.rstrip("\n\r") for line in islice(f, offset, offset + lines)]

    has_more = offset + len(chunk) < total
    return chunk, total, has_more


def log_file_exists(job_id: str) -> bool:
    """Check if a log file exists for a job.

    Args:
        job_id: The job UUID.

    Returns:
        True if the log file exists, False otherwise.
        Returns False if job_id is invalid.
    """
    try:
        return get_log_path(job_id).exists()
    except ValueError:
        # Invalid job ID format
        return False
