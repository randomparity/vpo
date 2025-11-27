"""Plan approval service.

This module extracts the plan approval business logic from route handlers,
providing better testability and separation of concerns.
"""

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from video_policy_orchestrator.db.models import (
    Job,
    JobStatus,
    JobType,
    PlanStatus,
    insert_job,
)
from video_policy_orchestrator.db.operations import (
    InvalidPlanTransitionError,
    get_plan_by_id,
    update_plan_status,
)
from video_policy_orchestrator.db.types import PlanRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApprovalResult:
    """Result of approving a plan."""

    success: bool
    plan: PlanRecord | None = None
    job_id: str | None = None
    warning: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class RejectionResult:
    """Result of rejecting a plan."""

    success: bool
    plan: PlanRecord | None = None
    error: str | None = None


class PlanApprovalService:
    """Service for approving and rejecting plans.

    Separates business logic from route handlers for better testability.
    """

    # Priority for execution jobs (lower = higher priority)
    APPROVAL_JOB_PRIORITY = 10

    def approve(self, conn: sqlite3.Connection, plan_id: str) -> ApprovalResult:
        """Approve a pending plan and create an execution job.

        This method reads the plan and then updates its status. The caller should
        wrap this call in a transaction to ensure atomicity - there is a gap
        between the read and update where concurrent modifications could occur.

        Args:
            conn: Database connection (within a transaction).
            plan_id: UUID of the plan to approve.

        Returns:
            ApprovalResult with success/failure status, updated plan, and job_id.
        """
        # Fetch plan to get details for job creation
        plan = get_plan_by_id(conn, plan_id)
        if plan is None:
            return ApprovalResult(success=False, error="Plan not found")

        # Check file existence for warning
        warning = None
        if plan.file_id is None:
            warning = "Source file no longer exists in library"

        try:
            # Update plan status to APPROVED
            updated_plan = update_plan_status(conn, plan_id, PlanStatus.APPROVED)
            if updated_plan is None:
                return ApprovalResult(success=False, error="Plan not found")

            # Create execution job with high priority
            job_id = str(uuid.uuid4())
            job = Job(
                id=job_id,
                file_id=plan.file_id,
                file_path=plan.file_path,
                job_type=JobType.APPLY,
                status=JobStatus.QUEUED,
                priority=self.APPROVAL_JOB_PRIORITY,
                policy_name=plan.policy_name,
                policy_json=plan.actions_json,
                progress_percent=0.0,
                progress_json=None,
                created_at=datetime.now(timezone.utc).isoformat(),
                started_at=None,
                completed_at=None,
                worker_pid=None,
                worker_heartbeat=None,
                output_path=None,
                backup_path=None,
                error_message=None,
                files_affected_json=None,
                summary_json=None,
                log_path=None,
            )
            insert_job(conn, job)

            logger.info(
                "Plan approved: plan_id=%s, job_id=%s, file_path=%s, policy=%s",
                plan_id[:8],
                job_id[:8],
                updated_plan.file_path,
                updated_plan.policy_name,
            )

            return ApprovalResult(
                success=True,
                plan=updated_plan,
                job_id=job_id,
                warning=warning,
            )

        except InvalidPlanTransitionError as e:
            return ApprovalResult(success=False, error=str(e))

    def reject(self, conn: sqlite3.Connection, plan_id: str) -> RejectionResult:
        """Reject a pending plan.

        Args:
            conn: Database connection (within a transaction).
            plan_id: UUID of the plan to reject.

        Returns:
            RejectionResult with success/failure status and updated plan.
        """
        try:
            updated_plan = update_plan_status(conn, plan_id, PlanStatus.REJECTED)
            if updated_plan is None:
                return RejectionResult(success=False, error="Plan not found")

            logger.info(
                "Plan rejected: plan_id=%s, file_path=%s, policy=%s",
                plan_id[:8],
                updated_plan.file_path,
                updated_plan.policy_name,
            )

            return RejectionResult(success=True, plan=updated_plan)

        except InvalidPlanTransitionError as e:
            return RejectionResult(success=False, error=str(e))
