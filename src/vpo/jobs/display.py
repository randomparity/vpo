"""Job display utilities for consistent formatting across CLI and UI.

This module provides shared display constants and formatting functions
for job status, colors, and other display-related utilities.
"""

from vpo.db import JobStatus

# Map JobStatus to terminal color names (for click.style and similar)
JOB_STATUS_COLORS: dict[JobStatus, str] = {
    JobStatus.QUEUED: "yellow",
    JobStatus.RUNNING: "blue",
    JobStatus.COMPLETED: "green",
    JobStatus.FAILED: "red",
    JobStatus.CANCELLED: "bright_black",
}

# Default color when status is not found
DEFAULT_STATUS_COLOR = "white"


def get_status_color(status: JobStatus) -> str:
    """Get the terminal color for a job status.

    Args:
        status: The job status.

    Returns:
        Color name suitable for click.style() or similar APIs.
    """
    return JOB_STATUS_COLORS.get(status, DEFAULT_STATUS_COLOR)


def format_job_status(status: JobStatus) -> tuple[str, str]:
    """Format a job status for display.

    Args:
        status: The job status.

    Returns:
        Tuple of (status_value, color_name) for display formatting.
    """
    return status.value, get_status_color(status)
