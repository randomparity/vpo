"""Tests for plan approval service."""

import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.db import PlanStatus
from vpo.db.types import PlanRecord
from vpo.jobs.services.approval import (
    ApprovalResult,
    PlanApprovalService,
    RejectionResult,
)


@pytest.fixture
def service():
    """Create a PlanApprovalService instance."""
    return PlanApprovalService()


def insert_test_plan(
    conn: sqlite3.Connection,
    plan_id: str,
    status: PlanStatus = PlanStatus.PENDING,
    file_id: int | None = None,
    file_path: str = "/test/path/file.mkv",
    policy_name: str = "test-policy",
) -> None:
    """Insert a test plan directly into the database."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO plans (
            id, file_id, file_path, policy_name, policy_version,
            job_id, actions_json, action_count, requires_remux,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan_id,
            file_id,
            file_path,
            policy_name,
            1,  # policy_version
            None,  # job_id
            '{"actions": []}',  # actions_json
            0,  # action_count
            0,  # requires_remux
            status.value,
            now,
            now,
        ),
    )
    conn.commit()


class TestPlanApprovalServiceApprove:
    """Tests for PlanApprovalService.approve method."""

    def test_approve_pending_plan_success(self, db_conn, service):
        """Successfully approve a pending plan."""
        plan_id = "12345678-1234-1234-1234-123456789abc"
        insert_test_plan(db_conn, plan_id)

        result = service.approve(db_conn, plan_id)

        assert result.success is True
        assert result.plan is not None
        assert result.plan.status == PlanStatus.APPROVED
        assert result.job_id is not None
        assert result.error is None

    def test_approve_creates_job(self, db_conn, service):
        """Approving a plan creates an execution job."""
        plan_id = "12345678-1234-1234-1234-123456789abc"
        insert_test_plan(db_conn, plan_id)

        result = service.approve(db_conn, plan_id)

        # Verify job was created
        cursor = db_conn.execute("SELECT * FROM jobs WHERE id = ?", (result.job_id,))
        job_row = cursor.fetchone()
        assert job_row is not None
        assert job_row["job_type"] == "apply"
        assert job_row["status"] == "queued"
        assert job_row["priority"] == service.APPROVAL_JOB_PRIORITY

    def test_approve_returns_warning_for_missing_file(self, db_conn, service):
        """Returns warning when source file no longer exists."""
        plan_id = "12345678-1234-1234-1234-123456789abc"
        insert_test_plan(db_conn, plan_id, file_id=None)

        result = service.approve(db_conn, plan_id)

        assert result.success is True
        assert result.warning is not None
        assert "no longer exists" in result.warning

    def test_approve_nonexistent_plan_returns_error(self, db_conn, service):
        """Returns error for nonexistent plan."""
        result = service.approve(db_conn, "nonexistent-plan-id")

        assert result.success is False
        assert result.error == "Plan not found"
        assert result.plan is None
        assert result.job_id is None

    def test_approve_already_approved_plan_returns_error(self, db_conn, service):
        """Returns error when trying to approve already-approved plan."""
        plan_id = "12345678-1234-1234-1234-123456789abc"
        insert_test_plan(db_conn, plan_id, status=PlanStatus.APPROVED)

        result = service.approve(db_conn, plan_id)

        assert result.success is False
        assert result.error is not None
        # Exact error message from InvalidPlanTransitionError
        assert result.error == "Cannot transition plan from 'approved' to 'approved'"

    def test_approve_job_has_correct_policy_info(self, db_conn, service):
        """Job created has correct policy information from plan."""
        plan_id = "12345678-1234-1234-1234-123456789abc"
        insert_test_plan(
            db_conn,
            plan_id,
            policy_name="my-policy",
            file_path="/my/test/file.mkv",
        )

        result = service.approve(db_conn, plan_id)

        cursor = db_conn.execute("SELECT * FROM jobs WHERE id = ?", (result.job_id,))
        job_row = cursor.fetchone()
        assert job_row["policy_name"] == "my-policy"
        assert job_row["file_path"] == "/my/test/file.mkv"


class TestPlanApprovalServiceReject:
    """Tests for PlanApprovalService.reject method."""

    def test_reject_pending_plan_success(self, db_conn, service):
        """Successfully reject a pending plan."""
        plan_id = "12345678-1234-1234-1234-123456789abc"
        insert_test_plan(db_conn, plan_id)

        result = service.reject(db_conn, plan_id)

        assert result.success is True
        assert result.plan is not None
        assert result.plan.status == PlanStatus.REJECTED
        assert result.error is None

    def test_reject_nonexistent_plan_returns_error(self, db_conn, service):
        """Returns error for nonexistent plan."""
        result = service.reject(db_conn, "nonexistent-plan-id")

        assert result.success is False
        assert result.error == "Plan not found"
        assert result.plan is None

    def test_reject_already_approved_plan_returns_error(self, db_conn, service):
        """Returns error when trying to reject already-approved plan."""
        plan_id = "12345678-1234-1234-1234-123456789abc"
        insert_test_plan(db_conn, plan_id, status=PlanStatus.APPROVED)

        result = service.reject(db_conn, plan_id)

        assert result.success is False
        assert result.error is not None
        # Exact error message from InvalidPlanTransitionError
        assert result.error == "Cannot transition plan from 'approved' to 'rejected'"


class TestApprovalResult:
    """Tests for ApprovalResult dataclass."""

    def test_success_result_has_required_fields(self):
        """Successful result has plan and job_id."""
        plan = PlanRecord(
            id="test-id",
            file_id=1,
            file_path="/test/path",
            policy_name="test",
            policy_version=13,
            job_id=None,
            actions_json="{}",
            action_count=0,
            requires_remux=False,
            status=PlanStatus.APPROVED,
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-01T00:00:00+00:00",
        )
        result = ApprovalResult(
            success=True,
            plan=plan,
            job_id="job-123",
        )

        assert result.success is True
        assert result.plan is plan
        assert result.job_id == "job-123"
        assert result.error is None

    def test_failure_result_has_error(self):
        """Failed result has error message."""
        result = ApprovalResult(
            success=False,
            error="Plan not found",
        )

        assert result.success is False
        assert result.error == "Plan not found"
        assert result.plan is None
        assert result.job_id is None


class TestRejectionResult:
    """Tests for RejectionResult dataclass."""

    def test_success_result_has_plan(self):
        """Successful result has updated plan."""
        plan = PlanRecord(
            id="test-id",
            file_id=1,
            file_path="/test/path",
            policy_name="test",
            policy_version=13,
            job_id=None,
            actions_json="{}",
            action_count=0,
            requires_remux=False,
            status=PlanStatus.REJECTED,
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-01T00:00:00+00:00",
        )
        result = RejectionResult(
            success=True,
            plan=plan,
        )

        assert result.success is True
        assert result.plan is plan
        assert result.error is None

    def test_failure_result_has_error(self):
        """Failed result has error message."""
        result = RejectionResult(
            success=False,
            error="Invalid transition",
        )

        assert result.success is False
        assert result.error == "Invalid transition"
        assert result.plan is None
