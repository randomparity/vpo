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


def generate_summary_text(job_type: str, summary_raw: dict | None) -> str | None:
    """Generate human-readable summary text from summary_json data.

    Produces type-specific summaries based on job type and summary data.

    Args:
        job_type: Job type value (scan, apply, transcode, move).
        summary_raw: Parsed summary_json dictionary, or None.

    Returns:
        Human-readable summary string, or None if no summary available.
    """
    if summary_raw is None:
        return None

    try:
        if job_type == "scan":
            # Scan job summary: "Scanned X files in /path, Y new, Z changed"
            total = summary_raw.get("total_files", 0)
            new = summary_raw.get("new_files", 0)
            changed = summary_raw.get("changed_files", 0)
            target = summary_raw.get("target_directory", "")
            errors = summary_raw.get("errors", 0)

            parts = [f"Scanned {total} files"]
            if target:
                parts[0] += f" in {target}"
            if new > 0:
                parts.append(f"{new} new")
            if changed > 0:
                parts.append(f"{changed} changed")
            if errors > 0:
                parts.append(f"{errors} errors")

            return ", ".join(parts)

        elif job_type == "apply":
            # Apply job summary: "Applied policy 'name' to X files"
            policy_name = summary_raw.get("policy_name", "unknown")
            files_affected = summary_raw.get("files_affected", 0)
            actions = summary_raw.get("actions_applied", [])

            summary = f"Applied policy '{policy_name}' to {files_affected} files"
            if actions:
                summary += f" ({', '.join(actions)})"
            return summary

        elif job_type == "transcode":
            # Transcode job summary: "Transcoded input → output (compression ratio)"
            input_file = summary_raw.get("input_file", "")
            output_file = summary_raw.get("output_file", "")
            input_size = summary_raw.get("input_size_bytes", 0)
            output_size = summary_raw.get("output_size_bytes", 0)

            # Extract just filenames for cleaner display
            input_name = input_file.split("/")[-1] if input_file else "input"
            output_name = output_file.split("/")[-1] if output_file else "output"

            summary = f"Transcoded {input_name} → {output_name}"
            if input_size > 0 and output_size > 0:
                ratio = output_size / input_size
                summary += f" ({ratio:.0%} of original size)"
            return summary

        elif job_type == "move":
            # Move job summary: "Moved source → destination"
            source = summary_raw.get("source_path", "")
            dest = summary_raw.get("destination_path", "")
            size = summary_raw.get("size_bytes", 0)

            # Extract just filenames
            source_name = source.split("/")[-1] if source else "source"
            dest_path = dest if dest else "destination"

            summary = f"Moved {source_name} → {dest_path}"
            if size > 0:
                # Format size
                if size >= 1024 * 1024 * 1024:
                    size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"
                elif size >= 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{size / 1024:.1f} KB"
                summary += f" ({size_str})"
            return summary

        else:
            # Unknown job type - return None
            return None

    except (KeyError, TypeError, AttributeError):
        # Handle malformed summary_json gracefully
        return None


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
