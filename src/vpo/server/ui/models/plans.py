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
    max_page_size: int = 100

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "plans": [p.to_dict() for p in self.plans],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
            "max_page_size": self.max_page_size,
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
class PlannedActionItem:
    """Represents a single planned action for display.

    Attributes:
        type: Action type (set_language, set_title, remove_track, etc.).
        track_index: Target track index (if applicable).
        track_type: Track type (video, audio, subtitle, etc.).
        details: Human-readable description of the action.
        parameters: Raw action parameters dict.
    """

    type: str
    track_index: int | None
    track_type: str | None
    details: str
    parameters: dict

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "track_index": self.track_index,
            "track_type": self.track_type,
            "details": self.details,
            "parameters": self.parameters,
        }


def _format_action_details(action: dict) -> str:
    """Format action dict into human-readable details string.

    Args:
        action: Action dictionary with type and parameters.

    Returns:
        Human-readable description of the action.
    """
    action_type = action.get("type", "unknown")
    params = action.get("parameters", {})

    if action_type == "set_language":
        return f"Set language to '{params.get('language', '?')}'"
    elif action_type == "set_title":
        return f"Set title to '{params.get('title', '?')}'"
    elif action_type == "set_default":
        return "Set as default track"
    elif action_type == "clear_default":
        return "Clear default flag"
    elif action_type == "set_forced":
        return "Set forced flag"
    elif action_type == "clear_forced":
        return "Clear forced flag"
    elif action_type == "remove_track":
        return "Remove track"
    elif action_type == "reorder_tracks":
        return "Reorder tracks"
    elif action_type == "convert_container":
        target = params.get("target", "?")
        return f"Convert container to {target}"
    elif action_type == "transcode_video":
        codec = params.get("target_codec", "?")
        return f"Transcode video to {codec}"
    elif action_type == "transcode_audio":
        codec = params.get("target_codec", "?")
        return f"Transcode audio to {codec}"
    elif action_type == "copy_stream":
        return "Copy stream"
    elif action_type == "synthesize_audio":
        return f"Synthesize audio track ({params.get('channels', '?')} channels)"
    elif action_type == "warn":
        return f"Warning: {params.get('message', '?')}"
    else:
        return f"{action_type}: {params}"


@dataclass
class PlanDetailItem:
    """Full plan details for detail view.

    Extends PlanListItem with deserialized actions and additional metadata.

    Attributes:
        id: Plan UUID.
        id_short: First 8 characters of UUID for display.
        file_id: Associated file ID (null if file deleted).
        file_path: Cached file path.
        filename: Extracted filename for display.
        file_deleted: True if file_id is null (file was deleted).
        policy_name: Name of the policy that generated this plan.
        policy_version: Version of the policy at evaluation time.
        action_count: Number of planned actions.
        requires_remux: Whether plan requires container remux.
        status: Current plan status.
        status_badge: Badge class and label for status display.
        created_at: ISO-8601 UTC creation timestamp.
        updated_at: ISO-8601 UTC last update timestamp.
        actions: List of deserialized PlannedActionItem.
        job_id: Reference to originating job (if from batch evaluation).
    """

    id: str
    id_short: str
    file_id: int | None
    file_path: str
    filename: str
    file_deleted: bool
    policy_name: str
    policy_version: int
    action_count: int
    requires_remux: bool
    status: str
    status_badge: dict
    created_at: str
    updated_at: str
    actions: list[PlannedActionItem]
    job_id: str | None = None

    @classmethod
    def from_plan_record(cls, record) -> PlanDetailItem:
        """Create PlanDetailItem from a PlanRecord.

        Args:
            record: PlanRecord from database.

        Returns:
            PlanDetailItem with deserialized actions.
        """
        import json

        # Extract filename from path
        filename = Path(record.file_path).name

        # Get status badge config
        status_badge = PLAN_STATUS_BADGES.get(
            record.status.value,
            {"class": "status-unknown", "label": record.status.value},
        )

        # Deserialize actions
        actions = []
        try:
            actions_raw = json.loads(record.actions_json) if record.actions_json else []
            for action in actions_raw:
                actions.append(
                    PlannedActionItem(
                        type=action.get("type", "unknown"),
                        track_index=action.get("track_index"),
                        track_type=action.get("track_type"),
                        details=_format_action_details(action),
                        parameters=action.get("parameters", {}),
                    )
                )
        except (json.JSONDecodeError, TypeError):
            pass  # Return empty actions list on parse error

        return cls(
            id=record.id,
            id_short=record.id[:8],
            file_id=record.file_id,
            file_path=record.file_path,
            filename=filename,
            file_deleted=record.file_id is None,
            policy_name=record.policy_name,
            policy_version=record.policy_version,
            action_count=record.action_count,
            requires_remux=record.requires_remux,
            status=record.status.value,
            status_badge=status_badge,
            created_at=record.created_at,
            updated_at=record.updated_at,
            actions=actions,
            job_id=record.job_id,
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
            "policy_version": self.policy_version,
            "action_count": self.action_count,
            "requires_remux": self.requires_remux,
            "status": self.status,
            "status_badge": self.status_badge,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "actions": [a.to_dict() for a in self.actions],
            "job_id": self.job_id,
        }


@dataclass
class PlanDetailContext:
    """Template context for plan detail page.

    Attributes:
        plan: The plan detail item.
        back_url: URL to navigate back to.
    """

    plan: PlanDetailItem
    back_url: str

    # Allowed path prefixes for back navigation
    _SAFE_PATH_PREFIXES = ("/plans", "/approvals", "/library", "/jobs")

    @staticmethod
    def _is_safe_back_url(url: str | None) -> str | None:
        """Validate and extract safe path from a URL.

        Prevents open redirect vulnerabilities by ensuring the URL is:
        - A relative path starting with an allowed prefix
        - Not a protocol-relative URL (//evil.com)
        - Not an absolute URL to an external domain

        Args:
            url: URL to validate (may be full URL or path).

        Returns:
            Safe path to use, or None if URL is invalid/unsafe.
        """
        if not url:
            return None

        # Reject protocol-relative URLs (//evil.com/plans) before parsing
        if url.startswith("//"):
            return None

        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
        except (ValueError, TypeError):
            return None

        # If there's a netloc (hostname), only allow localhost
        if parsed.netloc:
            # Only trust localhost URLs
            netloc_lower = parsed.netloc.lower()
            if not (
                netloc_lower.startswith("localhost")
                or netloc_lower.startswith("127.0.0.1")
                or netloc_lower.startswith("[::1]")
            ):
                return None

        # Use path component only (strips scheme, netloc, query, fragment)
        path = parsed.path

        # Reject empty paths
        if not path:
            return None

        # Must start with /
        if not path.startswith("/"):
            return None

        # Reject paths that look like protocol-relative URLs after parsing
        if path.startswith("//"):
            return None

        # Must match one of the allowed prefixes
        if not any(
            path.startswith(prefix) for prefix in PlanDetailContext._SAFE_PATH_PREFIXES
        ):
            return None

        return path

    @classmethod
    def from_plan_and_request(
        cls, plan: PlanDetailItem, referer: str | None
    ) -> PlanDetailContext:
        """Create context from plan and request referer.

        Args:
            plan: PlanDetailItem to display.
            referer: HTTP Referer header value.

        Returns:
            PlanDetailContext for template rendering.
        """
        # Default back URL is plans list
        back_url = "/plans"

        # Use referer if it's a safe VPO path
        safe_path = cls._is_safe_back_url(referer)
        if safe_path:
            back_url = safe_path

        return cls(plan=plan, back_url=back_url)


@dataclass
class PlanActionResponse:
    """API response for plan action endpoints (approve/reject).

    Attributes:
        success: True if action was successful.
        plan: Updated plan data (if successful).
        error: Error message (if failed).
        code: Machine-readable error code (if failed).
        job_id: Created execution job ID (approve only).
        job_url: URL to job detail view (approve only).
        warning: Warning message (e.g., file no longer exists).
    """

    success: bool
    plan: PlanListItem | None = None
    error: str | None = None
    code: str | None = None
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
        if self.code is not None:
            result["code"] = self.code
        if self.job_id is not None:
            result["job_id"] = self.job_id
        if self.job_url is not None:
            result["job_url"] = self.job_url
        if self.warning is not None:
            result["warning"] = self.warning
        return result
