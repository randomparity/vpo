"""Custom exceptions for job tracking.

This module provides specific exception types for job tracking operations,
enabling callers to handle different error conditions appropriately.
"""


class JobTrackingError(Exception):
    """Base exception for job tracking errors.

    All job-related exceptions inherit from this class, allowing callers
    to catch all job errors with a single except clause if desired.
    """


class JobNotFoundError(JobTrackingError):
    """Raised when a job doesn't exist in the database.

    Attributes:
        job_id: The ID of the job that was not found.
        operation: The operation that was attempted (e.g., "complete", "cancel").
    """

    def __init__(self, job_id: str, operation: str) -> None:
        """Initialize the exception.

        Args:
            job_id: The ID of the job that was not found.
            operation: The operation that was attempted.
        """
        self.job_id = job_id
        self.operation = operation
        super().__init__(f"Cannot {operation} job {job_id}: not found")


class ConcurrentModificationError(JobTrackingError):
    """Raised when a job was modified by another process.

    This can occur when two workers try to update the same job, or when
    a job's state has changed between read and write operations.

    Attributes:
        job_id: The ID of the job that was concurrently modified.
    """

    def __init__(self, job_id: str, message: str | None = None) -> None:
        """Initialize the exception.

        Args:
            job_id: The ID of the job that was concurrently modified.
            message: Optional custom message describing the conflict.
        """
        self.job_id = job_id
        default_msg = f"Job {job_id} was modified by another process"
        super().__init__(message or default_msg)
