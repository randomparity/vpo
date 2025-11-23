"""Data models for Web UI Shell.

This module defines the navigation and template context structures
used for server-side rendering.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AboutInfo:
    """Information displayed on the About page.

    Attributes:
        version: Application version (e.g., "0.1.0").
        git_hash: Git commit hash if available.
        profile_name: Current profile name or "Default".
        api_url: Base URL for API access.
        docs_url: URL to documentation.
        is_read_only: Always True for this version.
    """

    version: str
    git_hash: str | None
    profile_name: str
    api_url: str
    docs_url: str
    is_read_only: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "git_hash": self.git_hash,
            "profile_name": self.profile_name,
            "api_url": self.api_url,
            "docs_url": self.docs_url,
            "is_read_only": self.is_read_only,
        }


@dataclass
class NavigationItem:
    """Represents a single navigation link in the sidebar.

    Attributes:
        id: Unique identifier matching route path (e.g., "jobs").
        label: Display text shown in navigation (e.g., "Jobs").
        path: URL path (e.g., "/jobs").
        icon: Optional icon identifier for future use.
    """

    id: str
    label: str
    path: str
    icon: str | None = None


@dataclass
class NavigationState:
    """Tracks which navigation item is currently active.

    Attributes:
        items: Ordered list of all navigation items.
        active_id: ID of the currently active section, or None for 404.
    """

    items: list[NavigationItem]
    active_id: str | None


@dataclass
class TemplateContext:
    """Context passed to Jinja2 templates for rendering.

    Attributes:
        nav: Navigation configuration and state.
        section_title: Title for the current section.
        section_content: Optional HTML content for section body.
        error_message: Optional error message for error pages.
    """

    nav: NavigationState
    section_title: str
    section_content: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for Jinja2 template context."""
        return {
            "nav": self.nav,
            "section_title": self.section_title,
            "section_content": self.section_content,
            "error_message": self.error_message,
        }


# Default navigation items configuration
NAVIGATION_ITEMS: list[NavigationItem] = [
    NavigationItem(id="jobs", label="Jobs", path="/jobs"),
    NavigationItem(id="library", label="Library", path="/library"),
    NavigationItem(id="transcriptions", label="Transcriptions", path="/transcriptions"),
    NavigationItem(id="policies", label="Policies", path="/policies"),
    NavigationItem(id="approvals", label="Approvals", path="/approvals"),
    NavigationItem(id="about", label="About", path="/about"),
]

DEFAULT_SECTION = "jobs"


@dataclass
class JobFilterParams:
    """Validate and parse query parameters for /api/jobs.

    Attributes:
        status: Filter by job status (None = all statuses).
        job_type: Filter by job type (None = all types).
        since: Time range filter: "24h", "7d", or None (all time).
        limit: Page size (1-100, default 50).
        offset: Pagination offset (>= 0, default 0).
    """

    status: str | None = None
    job_type: str | None = None
    since: str | None = None
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, query: dict) -> JobFilterParams:
        """Create JobFilterParams from request query dict.

        Args:
            query: Query parameters from request.

        Returns:
            Validated JobFilterParams instance.
        """
        # Parse limit with bounds checking
        try:
            limit = int(query.get("limit", 50))
            limit = max(1, min(100, limit))
        except (ValueError, TypeError):
            limit = 50

        # Parse offset with bounds checking
        try:
            offset = int(query.get("offset", 0))
            offset = max(0, offset)
        except (ValueError, TypeError):
            offset = 0

        return cls(
            status=query.get("status"),
            job_type=query.get("type"),
            since=query.get("since"),
            limit=limit,
            offset=offset,
        )


@dataclass
class JobListItem:
    """Job data for API response and template rendering.

    Attributes:
        id: Job UUID.
        job_type: Job type value (scan, apply, transcode, move).
        status: Job status value (queued, running, completed, failed, cancelled).
        file_path: Target file/directory path.
        progress_percent: Job progress (0.0-100.0).
        created_at: ISO-8601 UTC timestamp.
        completed_at: ISO-8601 UTC timestamp or None.
        duration_seconds: Computed duration or None if still running.
    """

    id: str
    job_type: str
    status: str
    file_path: str
    progress_percent: float
    created_at: str
    completed_at: str | None = None
    duration_seconds: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "file_path": self.file_path,
            "progress_percent": self.progress_percent,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class JobListResponse:
    """API response wrapper with pagination metadata.

    Attributes:
        jobs: Job items for current page.
        total: Total jobs matching filters.
        limit: Page size used.
        offset: Current offset.
        has_filters: True if any filter was applied.
    """

    jobs: list[JobListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "jobs": [job.to_dict() for job in self.jobs],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
        }


@dataclass
class JobListContext:
    """Template context for jobs.html.

    Attributes:
        status_options: Available status filter options.
        type_options: Available type filter options.
        time_options: Available time range options.
    """

    status_options: list[dict]
    type_options: list[dict]
    time_options: list[dict]

    @classmethod
    def default(cls) -> JobListContext:
        """Create default context with all filter options."""
        return cls(
            status_options=[
                {"value": "", "label": "All statuses"},
                {"value": "queued", "label": "Queued"},
                {"value": "running", "label": "Running"},
                {"value": "completed", "label": "Completed"},
                {"value": "failed", "label": "Failed"},
                {"value": "cancelled", "label": "Cancelled"},
            ],
            type_options=[
                {"value": "", "label": "All types"},
                {"value": "scan", "label": "Scan"},
                {"value": "apply", "label": "Apply"},
                {"value": "transcode", "label": "Transcode"},
                {"value": "move", "label": "Move"},
            ],
            time_options=[
                {"value": "", "label": "All time"},
                {"value": "24h", "label": "Last 24 hours"},
                {"value": "7d", "label": "Last 7 days"},
            ],
        )
