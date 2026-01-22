"""Plan view models.

This module defines models for the plans list and detail views.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Status badge styling configuration
PLAN_STATUS_BADGES = {
    "pending": {"class": "status-pending", "label": "Pending"},
    "approved": {"class": "status-approved", "label": "Approved"},
    "rejected": {"class": "status-rejected", "label": "Rejected"},
    "applied": {"class": "status-applied", "label": "Applied"},
    "canceled": {"class": "status-canceled", "label": "Canceled"},
}


@dataclass
class PlanFilterParams:
    """Query parameter parsing for /api/plans.

    Attributes:
        status: Filter by plan status (pending, approved, rejected, applied, canceled).
        since: Time filter (24h, 7d, 30d).
        policy_name: Filter by policy name.
        limit: Page size (default 50, max 100).
        offset: Pagination offset (default 0).
    """

    status: str | None = None
    since: str | None = None
    policy_name: str | None = None
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, query: dict) -> PlanFilterParams:
        """Parse query parameters from request.

        Args:
            query: Dictionary of query string parameters.

        Returns:
            Validated PlanFilterParams instance.
        """
        # Parse limit with bounds
        try:
            limit = int(query.get("limit", 50))
            limit = max(1, min(100, limit))  # Clamp to 1-100
        except (ValueError, TypeError):
            limit = 50

        # Parse offset with minimum
        try:
            offset = int(query.get("offset", 0))
            offset = max(0, offset)
        except (ValueError, TypeError):
            offset = 0

        return cls(
            status=query.get("status"),
            since=query.get("since"),
            policy_name=query.get("policy_name"),
            limit=limit,
            offset=offset,
        )


@dataclass
class PlanListItem:
    """Plan data for Plans API response.

    Attributes:
        id: Plan UUID.
        id_short: First 8 characters of UUID for display.
        file_id: Associated file ID (null if file deleted).
        file_path: Cached file path.
        filename: Extracted filename for display.
        file_deleted: True if file_id is null (file was deleted).
        policy_name: Name of the policy that generated this plan.
        action_count: Number of planned actions.
        requires_remux: Whether plan requires container remux.
        status: Current plan status.
        status_badge: Badge class and label for status display.
        created_at: ISO-8601 UTC creation timestamp.
        updated_at: ISO-8601 UTC last update timestamp.
    """

    id: str
    id_short: str
    file_id: int | None
    file_path: str
    filename: str
    file_deleted: bool
    policy_name: str
    action_count: int
    requires_remux: bool
    status: str
    status_badge: dict
    created_at: str
    updated_at: str

    @classmethod
    def from_plan_record(cls, record) -> PlanListItem:
        """Create PlanListItem from a PlanRecord.

        Args:
            record: PlanRecord from database.

        Returns:
            PlanListItem for API/template use.
        """
        # Extract filename from path
        filename = Path(record.file_path).name

        # Get status badge config
        status_badge = PLAN_STATUS_BADGES.get(
            record.status.value,
            {"class": "status-unknown", "label": record.status.value},
        )

        return cls(
            id=record.id,
            id_short=record.id[:8],
            file_id=record.file_id,
            file_path=record.file_path,
            filename=filename,
            file_deleted=record.file_id is None,
            policy_name=record.policy_name,
            action_count=record.action_count,
            requires_remux=record.requires_remux,
            status=record.status.value,
            status_badge=status_badge,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "id_short": self.id_short,
            "file_id": self.file_id,
            "file_path": self.file_path,
            "filename": self.filename,
            "file_deleted": self.file_deleted,
            "policy_name": self.policy_name,
            "action_count": self.action_count,
            "requires_remux": self.requires_remux,
            "status": self.status,
            "status_badge": self.status_badge,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class PlanListResponse:
    """API response wrapper for /api/plans.

    Attributes:
        plans: List of plan items.
        total: Total number of plans matching filters.
        limit: Page size.
        offset: Current offset.
        has_filters: True if any filters are active.
    """

    plans: list[PlanListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "plans": [p.to_dict() for p in self.plans],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
        }


@dataclass
class PlansContext:
    """Template context for plans.html.

    Attributes:
        status_options: List of status filter options.
        time_options: List of time filter options.
    """

    status_options: list[dict]
    time_options: list[dict]

    @classmethod
    def default(cls) -> PlansContext:
        """Create default context with filter options."""
        return cls(
            status_options=[
                {"value": "", "label": "All Statuses"},
                {"value": "pending", "label": "Pending"},
                {"value": "approved", "label": "Approved"},
                {"value": "rejected", "label": "Rejected"},
                {"value": "applied", "label": "Applied"},
                {"value": "canceled", "label": "Canceled"},
            ],
            time_options=[
                {"value": "", "label": "All Time"},
                {"value": "24h", "label": "Last 24 Hours"},
                {"value": "7d", "label": "Last 7 Days"},
                {"value": "30d", "label": "Last 30 Days"},
            ],
        )


@dataclass
class PlanActionResponse:
    """API response for plan action endpoints (approve/reject).

    Attributes:
        success: True if action was successful.
        plan: Updated plan data (if successful).
        error: Error message (if failed).
        job_id: Created execution job ID (approve only).
        job_url: URL to job detail view (approve only).
        warning: Warning message (e.g., file no longer exists).
    """

    success: bool
    plan: PlanListItem | None = None
    error: str | None = None
    job_id: str | None = None
    job_url: str | None = None
    warning: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {"success": self.success}
        if self.plan is not None:
            result["plan"] = self.plan.to_dict()
        if self.error is not None:
            result["error"] = self.error
        if self.job_id is not None:
            result["job_id"] = self.job_id
        if self.job_url is not None:
            result["job_url"] = self.job_url
        if self.warning is not None:
            result["warning"] = self.warning
        return result
