"""Job system module for Video Policy Orchestrator.

This module provides the job queue system for long-running operations:
- queue: Job queue operations (enqueue, claim, release)
- worker: Job worker for processing queued jobs
- progress: FFmpeg progress parsing utilities
- maintenance: Job maintenance operations (purge)
- services: Job processing services
- summary: Job summary text generation
"""

from vpo.jobs.maintenance import purge_old_jobs
from vpo.jobs.summary import generate_summary_text


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
    "generate_summary_text",
    "purge_old_jobs",
    "TranscodeJobResult",
    "TranscodeJobService",
]
