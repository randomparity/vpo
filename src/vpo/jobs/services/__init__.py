"""Job processing services.

This package contains service classes that encapsulate business logic
for different job types, separating it from the worker orchestration layer.
"""

from vpo.jobs.services.approval import (
    ApprovalResult,
    PlanApprovalService,
    RejectionResult,
)
from vpo.jobs.services.move import (
    MoveConfig,
    MoveJobResult,
    MoveJobService,
)
from vpo.jobs.services.process import (
    ProcessJobResult,
    ProcessJobService,
)
from vpo.jobs.services.prune import (
    PruneJobResult,
    PruneJobService,
)
from vpo.jobs.services.transcode import (
    TranscodeJobResult,
    TranscodeJobService,
)

__all__ = [
    "ApprovalResult",
    "MoveConfig",
    "MoveJobResult",
    "MoveJobService",
    "PlanApprovalService",
    "ProcessJobResult",
    "ProcessJobService",
    "PruneJobResult",
    "PruneJobService",
    "RejectionResult",
    "TranscodeJobResult",
    "TranscodeJobService",
]
