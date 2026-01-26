"""Job-related view models.

This module defines models for job list, detail, and filter functionality.
"""

from __future__ import annotations

from dataclasses import dataclass

# Valid sort columns for job list
VALID_SORT_COLUMNS = frozenset(
    {"created_at", "job_type", "status", "file_path", "duration"}
)


@dataclass
class JobFilterParams:
    """Validate and parse query parameters for /api/jobs.

    Attributes:
        status: Filter by job status (None = all statuses).
        job_type: Filter by job type (None = all types).
        since: Time range filter: "24h", "7d", or None (all time).
        search: Case-insensitive substring search on filename (max 200 chars).
        sort_by: Column to sort by (None = default created_at).
        sort_order: Sort order ('asc' or 'desc', None = default desc).
        limit: Page size (1-100, default 50).
        offset: Pagination offset (>= 0, default 0).
    """

    status: str | None = None
    job_type: str | None = None
    since: str | None = None
    search: str | None = None
    sort_by: str | None = None
    sort_order: str | None = None
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

        # Parse search (truncate to 200 chars max)
        search_raw = query.get("search", "")
        search = search_raw.strip()[:200] if search_raw else None
        if search == "":
            search = None

        # Parse sort_by (validate against whitelist)
        sort_by_raw = query.get("sort")
        sort_by = sort_by_raw if sort_by_raw in VALID_SORT_COLUMNS else None

        # Parse sort_order (validate asc/desc)
        sort_order_raw = query.get("order", "").lower()
        sort_order = sort_order_raw if sort_order_raw in ("asc", "desc") else None

        return cls(
            status=query.get("status"),
            job_type=query.get("type"),
            since=query.get("since"),
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
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


@dataclass
class JobDetailItem:
    """Full job data for detail view API response.

    Extends JobListItem with additional fields for the detail view.

    Attributes:
        id: Full job UUID.
        id_short: First 8 characters of UUID for display.
        job_type: Job type value (scan, apply, transcode, move).
        status: Job status value (queued, running, completed, failed, cancelled).
        priority: Job priority (lower = higher priority).
        file_path: Target file/directory path.
        policy_name: Name of policy used, if any.
        created_at: ISO-8601 UTC timestamp when job was created.
        started_at: ISO-8601 UTC timestamp when job started, or None.
        completed_at: ISO-8601 UTC timestamp when job completed, or None.
        duration_seconds: Computed duration or None if still running.
        progress_percent: Job progress (0.0-100.0).
        error_message: Error details if job failed.
        output_path: Path to output file, if any.
        summary: Human-readable summary text generated from summary_json.
        summary_raw: Parsed summary_json for detailed display.
        has_logs: Whether log file exists for this job.
    """

    id: str
    id_short: str
    job_type: str
    status: str
    priority: int
    file_path: str
    policy_name: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    duration_seconds: int | None
    progress_percent: float
    error_message: str | None
    output_path: str | None
    summary: str | None
    summary_raw: dict | None
    has_logs: bool

    @property
    def has_scan_errors(self) -> bool:
        """Check if this is a scan job with errors to display."""
        if self.job_type != "scan":
            return False
        if self.summary_raw is None:
            return False
        return self.summary_raw.get("errors", 0) > 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "id_short": self.id_short,
            "job_type": self.job_type,
            "status": self.status,
            "priority": self.priority,
            "file_path": self.file_path,
            "policy_name": self.policy_name,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "progress_percent": self.progress_percent,
            "error_message": self.error_message,
            "output_path": self.output_path,
            "summary": self.summary,
            "summary_raw": self.summary_raw,
            "has_logs": self.has_logs,
            "has_scan_errors": self.has_scan_errors,
        }


@dataclass
class JobLogsResponse:
    """API response for job logs endpoint.

    Supports lazy loading with pagination.

    Attributes:
        job_id: The job UUID.
        lines: Log lines for this chunk.
        total_lines: Total lines in log file.
        offset: Current offset (lines from start).
        has_more: Whether more lines are available.
    """

    job_id: str
    lines: list[str]
    total_lines: int
    offset: int
    has_more: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "lines": self.lines,
            "total_lines": self.total_lines,
            "offset": self.offset,
            "has_more": self.has_more,
        }


@dataclass
class ScanErrorItem:
    """A file that failed during scan.

    Attributes:
        path: Full path to the file.
        filename: Just the filename.
        error: Error message from ffprobe or other tool.
    """

    path: str
    filename: str
    error: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "filename": self.filename,
            "error": self.error,
        }


@dataclass
class ScanErrorsResponse:
    """API response for scan errors endpoint.

    Attributes:
        job_id: The scan job UUID.
        errors: List of files that failed during the scan.
        total_errors: Total count of errors.
    """

    job_id: str
    errors: list[ScanErrorItem]
    total_errors: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "errors": [e.to_dict() for e in self.errors],
            "total_errors": self.total_errors,
        }


@dataclass
class JobDetailContext:
    """Template context for job_detail.html.

    Passed to Jinja2 template for server-side rendering.

    Attributes:
        job: The job detail item.
        back_url: URL to return to jobs list (with preserved filters).
    """

    job: JobDetailItem
    back_url: str

    @classmethod
    def from_job_and_request(
        cls,
        job: JobDetailItem,
        referer: str | None,
    ) -> JobDetailContext:
        """Create context from job and request data.

        Args:
            job: The job detail item.
            referer: HTTP Referer header value, if present.

        Returns:
            JobDetailContext with appropriate back URL.
        """
        # Default back URL, or preserve filters from referer
        back_url = "/jobs"
        if referer and "/jobs?" in referer:
            # Extract just the path and query from referer
            # Handle both absolute and relative URLs
            if referer.startswith("/"):
                back_url = referer
            elif "/jobs?" in referer:
                # Extract path from absolute URL
                idx = referer.find("/jobs?")
                if idx != -1:
                    back_url = referer[idx:]
        return cls(job=job, back_url=back_url)
