"""Log file utilities for job execution logs.

This module provides utilities for reading, writing, and managing job log files.
Logs are stored as plain text files in the VPO data directory (~/.vpo/logs/).

Log lifecycle:
1. Created during job execution via JobLogWriter
2. Compressed (gzip) after log_compression_days (default 7 days)
3. Deleted after log_deletion_days (default 90 days)
"""

from __future__ import annotations

import gzip
import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

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
    line-by-line iteration for large files. Supports both uncompressed
    (.log) and compressed (.log.gz) files.

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

    # Check for compressed version first, then uncompressed
    gz_path = log_path.with_suffix(".log.gz")
    if gz_path.exists():
        return _read_compressed_log(gz_path, lines, offset)

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
        log_path = get_log_path(job_id)
        # Check for both uncompressed and compressed versions
        return log_path.exists() or log_path.with_suffix(".log.gz").exists()
    except ValueError:
        # Invalid job ID format
        return False


class JobLogWriter:
    """Context manager for writing job execution logs.

    Thread-safe log writer that buffers writes and flushes periodically.
    Uses context manager pattern for automatic cleanup.

    Example:
        with JobLogWriter(job_id) as log:
            log.write_header("scan", "/path/to/files")
            log.write_line("Processing file...")
            log.write_subprocess("ffprobe", stdout, stderr, returncode)
            log.write_footer(success=True)
    """

    def __init__(self, job_id: str, buffer_size: int = 100) -> None:
        """Initialize log writer.

        Args:
            job_id: The job UUID.
            buffer_size: Number of lines to buffer before flushing.

        Raises:
            ValueError: If job_id is not a valid UUID format.
        """
        _validate_job_id(job_id)
        self.job_id = job_id
        self.buffer_size = buffer_size
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        self._file_handle: open | None = None
        self._log_path: Path | None = None
        self._closed = False

    def __enter__(self) -> JobLogWriter:
        """Open log file for writing."""
        ensure_log_directory()
        self._log_path = get_log_path(self.job_id)
        self._file_handle = self._log_path.open("a", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Flush and close log file."""
        self.close()

    def close(self) -> None:
        """Flush buffer and close the file handle."""
        if self._closed:
            return
        with self._lock:
            self._flush_unlocked()
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None
            self._closed = True

    def _flush_unlocked(self) -> None:
        """Flush buffer to file. Must be called with lock held."""
        if self._buffer and self._file_handle:
            self._file_handle.write("\n".join(self._buffer) + "\n")
            self._file_handle.flush()
            self._buffer.clear()

    def flush(self) -> None:
        """Flush buffered lines to disk."""
        with self._lock:
            self._flush_unlocked()

    def write_line(self, line: str) -> None:
        """Write a single line to the log.

        Args:
            line: Line to write (newline added automatically).
        """
        if self._closed:
            return
        with self._lock:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self._buffer.append(f"[{timestamp}] {line}")
            if len(self._buffer) >= self.buffer_size:
                self._flush_unlocked()

    def write_lines(self, lines: list[str]) -> None:
        """Write multiple lines to the log.

        Args:
            lines: Lines to write.
        """
        for line in lines:
            self.write_line(line)

    def write_header(self, job_type: str, file_path: str, **metadata: str) -> None:
        """Write a job header with metadata.

        Args:
            job_type: Type of job (scan, apply, transcode, move).
            file_path: Path to the file being processed.
            **metadata: Additional key-value pairs to include.
        """
        self.write_line("=" * 60)
        self.write_line(f"JOB START: {self.job_id}")
        self.write_line(f"Type: {job_type}")
        self.write_line(f"File: {file_path}")
        for key, value in metadata.items():
            self.write_line(f"{key}: {value}")
        self.write_line("=" * 60)

    def write_footer(
        self, success: bool, duration_seconds: float | None = None
    ) -> None:
        """Write a job footer with completion status.

        Args:
            success: Whether the job completed successfully.
            duration_seconds: Optional duration of the job.
        """
        self.write_line("=" * 60)
        status = "SUCCESS" if success else "FAILED"
        self.write_line(f"JOB END: {status}")
        if duration_seconds is not None:
            self.write_line(f"Duration: {duration_seconds:.2f}s")
        self.write_line("=" * 60)

    def write_section(self, title: str) -> None:
        """Write a section header.

        Args:
            title: Section title.
        """
        self.write_line("-" * 40)
        self.write_line(title)
        self.write_line("-" * 40)

    def write_subprocess(
        self,
        command_name: str,
        stdout: str | None,
        stderr: str | None,
        returncode: int,
    ) -> None:
        """Write subprocess output to the log.

        Args:
            command_name: Name of the command (e.g., "ffprobe", "mkvpropedit").
            stdout: Standard output from the subprocess.
            stderr: Standard error from the subprocess.
            returncode: Exit code from the subprocess.
        """
        self.write_section(f"Command: {command_name}")
        self.write_line(f"Exit code: {returncode}")
        if stdout and stdout.strip():
            self.write_line("STDOUT:")
            for line in stdout.strip().split("\n"):
                self.write_line(f"  {line}")
        if stderr and stderr.strip():
            self.write_line("STDERR:")
            for line in stderr.strip().split("\n"):
                self.write_line(f"  {line}")

    def write_error(self, error: str, exception: BaseException | None = None) -> None:
        """Write an error message to the log.

        Args:
            error: Error description.
            exception: Optional exception that caused the error.
        """
        self.write_line(f"ERROR: {error}")
        if exception:
            self.write_line(f"Exception: {type(exception).__name__}: {exception}")

    @property
    def path(self) -> Path | None:
        """Get the log file path."""
        return self._log_path

    @property
    def relative_path(self) -> str | None:
        """Get the log path relative to data directory (for database storage)."""
        if self._log_path is None:
            return None
        return f"logs/{self.job_id}.log"


def create_job_log(job_id: str) -> JobLogWriter:
    """Create a new log writer for a job.

    Convenience function that creates and opens a JobLogWriter.
    Caller is responsible for calling close() or using as context manager.

    Args:
        job_id: The job UUID.

    Returns:
        An opened JobLogWriter instance.
    """
    writer = JobLogWriter(job_id)
    writer.__enter__()
    return writer


# =============================================================================
# Log Maintenance Functions
# =============================================================================


@dataclass
class LogMaintenanceStats:
    """Statistics from log maintenance operations."""

    compressed_count: int = 0
    compressed_bytes_before: int = 0
    compressed_bytes_after: int = 0
    deleted_count: int = 0
    deleted_bytes: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio (smaller is better)."""
        if self.compressed_bytes_before == 0:
            return 0.0
        return self.compressed_bytes_after / self.compressed_bytes_before


def get_log_stats() -> dict:
    """Get statistics about log files.

    Returns:
        Dictionary with counts and sizes:
        - total_count: Total number of log files
        - uncompressed_count: Number of .log files
        - compressed_count: Number of .log.gz files
        - total_bytes: Total size of all log files
        - uncompressed_bytes: Size of uncompressed logs
        - compressed_bytes: Size of compressed logs
    """
    log_dir = get_log_directory()
    if not log_dir.exists():
        return {
            "total_count": 0,
            "uncompressed_count": 0,
            "compressed_count": 0,
            "total_bytes": 0,
            "uncompressed_bytes": 0,
            "compressed_bytes": 0,
        }

    uncompressed_count = 0
    compressed_count = 0
    uncompressed_bytes = 0
    compressed_bytes = 0

    for path in log_dir.iterdir():
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
            if path.suffix == ".gz":
                compressed_count += 1
                compressed_bytes += size
            elif path.suffix == ".log":
                uncompressed_count += 1
                uncompressed_bytes += size
        except OSError:
            continue

    return {
        "total_count": uncompressed_count + compressed_count,
        "uncompressed_count": uncompressed_count,
        "compressed_count": compressed_count,
        "total_bytes": uncompressed_bytes + compressed_bytes,
        "uncompressed_bytes": uncompressed_bytes,
        "compressed_bytes": compressed_bytes,
    }


def compress_old_logs(
    older_than_days: int, dry_run: bool = False
) -> LogMaintenanceStats:
    """Compress log files older than the specified number of days.

    Compresses .log files to .log.gz using gzip. The original file is
    removed after successful compression.

    Args:
        older_than_days: Compress logs older than this many days.
        dry_run: If True, don't actually compress, just report what would happen.

    Returns:
        Statistics about the compression operation.
    """
    stats = LogMaintenanceStats()
    log_dir = get_log_directory()

    if not log_dir.exists():
        return stats

    cutoff = datetime.now(timezone.utc).timestamp() - (older_than_days * 86400)

    for path in log_dir.iterdir():
        if not path.is_file() or path.suffix != ".log":
            continue

        try:
            mtime = path.stat().st_mtime
            if mtime >= cutoff:
                continue

            original_size = path.stat().st_size
            stats.compressed_bytes_before += original_size

            if dry_run:
                # Estimate compressed size (typical gzip ratio for text)
                stats.compressed_bytes_after += int(original_size * 0.15)
                stats.compressed_count += 1
                continue

            # Compress the file
            gz_path = path.with_suffix(".log.gz")
            with path.open("rb") as f_in:
                with gzip.open(gz_path, "wb", compresslevel=9) as f_out:
                    while chunk := f_in.read(65536):
                        f_out.write(chunk)

            # Preserve modification time
            os.utime(gz_path, (mtime, mtime))

            # Remove original
            path.unlink()

            stats.compressed_bytes_after += gz_path.stat().st_size
            stats.compressed_count += 1
            logger.debug("Compressed log: %s", path.name)

        except OSError as e:
            error_msg = f"Failed to compress {path.name}: {e}"
            logger.warning(error_msg)
            if stats.errors is not None:
                stats.errors.append(error_msg)

    return stats


def delete_old_logs(older_than_days: int, dry_run: bool = False) -> LogMaintenanceStats:
    """Delete log files older than the specified number of days.

    Deletes both .log and .log.gz files that are older than the threshold.

    Args:
        older_than_days: Delete logs older than this many days.
        dry_run: If True, don't actually delete, just report what would happen.

    Returns:
        Statistics about the deletion operation.
    """
    stats = LogMaintenanceStats()
    log_dir = get_log_directory()

    if not log_dir.exists():
        return stats

    cutoff = datetime.now(timezone.utc).timestamp() - (older_than_days * 86400)

    for path in log_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix not in (".log", ".gz"):
            continue
        # Handle .log.gz suffix
        if path.suffix == ".gz" and not path.stem.endswith(".log"):
            continue

        try:
            mtime = path.stat().st_mtime
            if mtime >= cutoff:
                continue

            file_size = path.stat().st_size
            stats.deleted_bytes += file_size
            stats.deleted_count += 1

            if not dry_run:
                path.unlink()
                logger.debug("Deleted log: %s", path.name)

        except OSError as e:
            error_msg = f"Failed to delete {path.name}: {e}"
            logger.warning(error_msg)
            if stats.errors is not None:
                stats.errors.append(error_msg)

    return stats


def run_log_maintenance(
    compression_days: int = 7,
    deletion_days: int = 90,
    dry_run: bool = False,
) -> tuple[LogMaintenanceStats, LogMaintenanceStats]:
    """Run full log maintenance (compress then delete).

    Args:
        compression_days: Compress logs older than this many days.
        deletion_days: Delete logs older than this many days.
        dry_run: If True, don't make changes, just report.

    Returns:
        Tuple of (compression_stats, deletion_stats).
    """
    compression_stats = compress_old_logs(compression_days, dry_run=dry_run)
    deletion_stats = delete_old_logs(deletion_days, dry_run=dry_run)
    return compression_stats, deletion_stats


# =============================================================================
# Compressed Log Reading Support
# =============================================================================


def _read_compressed_log(
    gz_path: Path,
    lines: int,
    offset: int,
) -> tuple[list[str], int, bool]:
    """Read lines from a compressed log file.

    Args:
        gz_path: Path to the .log.gz file.
        lines: Maximum number of lines to return.
        offset: Number of lines to skip from the beginning.

    Returns:
        Tuple of (lines, total, has_more).
    """
    try:
        with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
            all_lines = f.read().splitlines()

        total = len(all_lines)
        chunk = all_lines[offset : offset + lines]
        has_more = offset + lines < total
        return chunk, total, has_more
    except (OSError, gzip.BadGzipFile):
        return [], 0, False
