"""Job system module for Video Policy Orchestrator.

This module provides the job queue system for long-running operations:
- exceptions: Custom exception types for job tracking errors
- tracking: Functions for creating and updating job records
- queue: Job queue operations (enqueue, claim, release)
- worker: Job worker for processing queued jobs
- maintenance: Job maintenance operations (purge, cleanup)
- services: Job processing services
- summary: Job summary text generation

Note: FFmpeg progress parsing is in vpo.tools.ffmpeg_progress
"""

from vpo.jobs.exceptions import (
    ConcurrentModificationError,
    JobNotFoundError,
    JobTrackingError,
)
from vpo.jobs.maintenance import cleanup_orphaned_cli_jobs, purge_old_jobs
from vpo.jobs.summary import generate_summary_text
from vpo.jobs.tracking import (
    ProcessSummary,
    ScanSummary,
    cancel_process_job,
    cancel_scan_job,
    complete_process_job,
    complete_scan_job,
    create_process_job,
    create_scan_job,
    fail_job_with_retry,
    fail_process_job,
    fail_scan_job,
    maybe_purge_old_jobs,
)


def __getattr__(name: str):
    """Lazy import for services to avoid circular imports."""
    if name == "TranscodeJobResult":
        from vpo.jobs.services import TranscodeJobResult

        return TranscodeJobResult
    if name == "TranscodeJobService":
        from vpo.jobs.services import TranscodeJobService

        return TranscodeJobService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Exceptions
    "JobTrackingError",
    "JobNotFoundError",
    "ConcurrentModificationError",
    # Type definitions
    "ScanSummary",
    "ProcessSummary",
    # Scan job functions
    "create_scan_job",
    "complete_scan_job",
    "cancel_scan_job",
    "fail_scan_job",
    # Process job functions
    "create_process_job",
    "complete_process_job",
    "cancel_process_job",
    "fail_process_job",
    "fail_job_with_retry",
    # Maintenance
    "maybe_purge_old_jobs",
    "purge_old_jobs",
    "cleanup_orphaned_cli_jobs",
    # Summary
    "generate_summary_text",
    # Services (lazy loaded)
    "TranscodeJobResult",
    "TranscodeJobService",
]
