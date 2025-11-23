"""Log file utilities for job execution logs.

This module provides utilities for reading and managing job log files.
Logs are stored as plain text files in the VPO data directory.
"""

from pathlib import Path

# Default number of lines to return when reading logs
DEFAULT_LOG_LINES = 500


def get_log_directory() -> Path:
    """Get the logs directory path.

    Returns:
        Path to the logs directory (~/.vpo/logs/).
    """
    from video_policy_orchestrator.config.loader import get_data_dir

    return get_data_dir() / "logs"


def get_log_path(job_id: str) -> Path:
    """Get the log file path for a job.

    Args:
        job_id: The job UUID.

    Returns:
        Path to the log file for the job.
    """
    return get_log_directory() / f"{job_id}.log"


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
        Total number of lines in the log file, or 0 if file doesn't exist.
    """
    log_path = get_log_path(job_id)
    if not log_path.exists():
        return 0

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def read_log_tail(
    job_id: str,
    lines: int = DEFAULT_LOG_LINES,
    offset: int = 0,
) -> tuple[list[str], int, bool]:
    """Read log lines from a job's log file.

    Reads lines starting from the given offset.

    Args:
        job_id: The job UUID.
        lines: Maximum number of lines to return (default 500).
        offset: Number of lines to skip from the beginning (default 0).

    Returns:
        Tuple of:
            - List of log lines (strings without trailing newlines)
            - Total number of lines in the file
            - Boolean indicating whether more lines are available
    """
    log_path = get_log_path(job_id)
    if not log_path.exists():
        return [], 0, False

    # Read all lines from the file
    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        all_lines = f.read().splitlines()

    total = len(all_lines)

    # Calculate slice indices
    start = offset
    end = offset + lines
    chunk = all_lines[start:end]
    has_more = end < total

    return chunk, total, has_more


def log_file_exists(job_id: str) -> bool:
    """Check if a log file exists for a job.

    Args:
        job_id: The job UUID.

    Returns:
        True if the log file exists, False otherwise.
    """
    return get_log_path(job_id).exists()
