"""Data models for Web UI Shell.

This module defines the navigation and template context structures
used for server-side rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
            # Scan job summary: "Scanned X files, Y new, Z errors"
            # Fields from cli/scan.py: total_discovered, scanned, skipped,
            # added, removed, errors
            scanned = summary_raw.get("scanned", 0)
            added = summary_raw.get("added", 0)
            removed = summary_raw.get("removed", 0)
            skipped = summary_raw.get("skipped", 0)
            errors = summary_raw.get("errors", 0)

            parts = [f"Scanned {scanned} files"]
            if added > 0:
                parts.append(f"{added} new")
            if removed > 0:
                parts.append(f"{removed} removed")
            if skipped > 0:
                parts.append(f"{skipped} unchanged")
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


# ==========================================================================
# Library List View Models (018-library-list-view)
# ==========================================================================


def get_resolution_label(width: int | None, height: int | None) -> str:
    """Map video dimensions to human-readable resolution label.

    Args:
        width: Video width in pixels.
        height: Video height in pixels.

    Returns:
        Resolution label (e.g., "1080p", "4K") or "\u2014" if unknown.
    """
    if width is None or height is None:
        return "\u2014"

    if height >= 2160:
        return "4K"
    elif height >= 1440:
        return "1440p"
    elif height >= 1080:
        return "1080p"
    elif height >= 720:
        return "720p"
    elif height >= 480:
        return "480p"
    elif height > 0:
        return f"{height}p"
    else:
        return "\u2014"


def format_audio_languages(languages_csv: str | None) -> str:
    """Format comma-separated language codes for display.

    Args:
        languages_csv: Comma-separated language codes from GROUP_CONCAT.

    Returns:
        Formatted string (e.g., "eng, jpn" or "eng, jpn +2 more").
    """
    if not languages_csv:
        return "\u2014"

    languages = [lang.strip() for lang in languages_csv.split(",") if lang.strip()]

    if not languages:
        return "\u2014"

    if len(languages) <= 3:
        return ", ".join(languages)

    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"


# Valid resolution filter values (019-library-filters-search)
VALID_RESOLUTIONS = ("4k", "1080p", "720p", "480p", "other")


@dataclass
class LibraryFilterParams:
    """Validate and parse query parameters for /api/library.

    Attributes:
        status: Filter by scan status (None = all, "ok", "error").
        limit: Page size (1-100, default 50).
        offset: Pagination offset (>= 0, default 0).
        search: Text search for filename/title.
        resolution: Filter by resolution category.
        audio_lang: Filter by audio language codes, OR logic.
        subtitles: Filter by subtitle presence.
    """

    status: str | None = None
    limit: int = 50
    offset: int = 0
    # New fields (019-library-filters-search)
    search: str | None = None
    resolution: str | None = None
    audio_lang: list[str] | None = None
    subtitles: str | None = None

    @classmethod
    def from_query(cls, query: dict) -> LibraryFilterParams:
        """Create LibraryFilterParams from request query dict.

        Args:
            query: Query parameters from request.

        Returns:
            Validated LibraryFilterParams instance.
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

        # Validate status - only allow specific values
        status = query.get("status")
        if status not in (None, "", "ok", "error"):
            status = None

        # Parse search - trim and limit length (019-library-filters-search)
        search = query.get("search")
        if search:
            search = search.strip()[:200]  # Max 200 chars
            if not search:
                search = None

        # Validate resolution (019-library-filters-search)
        resolution = query.get("resolution")
        if resolution not in (None, "", *VALID_RESOLUTIONS):
            resolution = None

        # Parse audio_lang - can be single value or list (019-library-filters-search)
        audio_lang_raw = query.get("audio_lang")
        audio_lang: list[str] | None = None
        if audio_lang_raw:
            # Handle both single value and list (from getall())
            if isinstance(audio_lang_raw, list):
                audio_lang = [
                    lang.lower().strip()
                    for lang in audio_lang_raw
                    if lang and len(lang.strip()) in (2, 3)
                ]
            elif isinstance(audio_lang_raw, str) and len(audio_lang_raw.strip()) in (
                2,
                3,
            ):
                audio_lang = [audio_lang_raw.lower().strip()]
            if not audio_lang:
                audio_lang = None

        # Validate subtitles (019-library-filters-search)
        subtitles = query.get("subtitles")
        if subtitles not in (None, "", "yes", "no"):
            subtitles = None

        return cls(
            status=status if status else None,
            limit=limit,
            offset=offset,
            search=search,
            resolution=resolution if resolution else None,
            audio_lang=audio_lang,
            subtitles=subtitles if subtitles else None,
        )


@dataclass
class FileListItem:
    """File data for Library API response.

    Attributes:
        id: Database file ID.
        filename: Short filename for display.
        path: Full file path (for tooltip).
        title: Track title if available, else None.
        resolution: Human-readable resolution (e.g., "1080p", "4K").
        audio_languages: Formatted language list (e.g., "eng, jpn").
        scanned_at: ISO-8601 UTC timestamp.
        scan_status: "ok" or "error".
        scan_error: Error message if scan_status == "error".
    """

    id: int
    filename: str
    path: str
    title: str | None
    resolution: str
    audio_languages: str
    scanned_at: str
    scan_status: str
    scan_error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "filename": self.filename,
            "path": self.path,
            "title": self.title,
            "resolution": self.resolution,
            "audio_languages": self.audio_languages,
            "scanned_at": self.scanned_at,
            "scan_status": self.scan_status,
            "scan_error": self.scan_error,
        }


@dataclass
class FileListResponse:
    """API response wrapper for /api/library.

    Attributes:
        files: File items for current page.
        total: Total files matching filters.
        limit: Page size used.
        offset: Current offset.
        has_filters: True if any filter was applied.
    """

    files: list[FileListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "files": [f.to_dict() for f in self.files],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
        }


@dataclass
class LibraryContext:
    """Template context for library.html.

    Attributes:
        status_options: Available scan status filter options.
        resolution_options: Available resolution filter options.
        subtitles_options: Available subtitle filter options.
    """

    status_options: list[dict]
    resolution_options: list[dict]
    subtitles_options: list[dict]

    @classmethod
    def default(cls) -> LibraryContext:
        """Create default context with filter options."""
        return cls(
            status_options=[
                {"value": "", "label": "All files"},
                {"value": "ok", "label": "Scanned OK"},
                {"value": "error", "label": "Scan errors"},
            ],
            resolution_options=[
                {"value": "", "label": "All resolutions"},
                {"value": "4k", "label": "4K / UHD"},
                {"value": "1080p", "label": "1080p"},
                {"value": "720p", "label": "720p"},
                {"value": "480p", "label": "480p"},
                {"value": "other", "label": "Other"},
            ],
            subtitles_options=[
                {"value": "", "label": "All files"},
                {"value": "yes", "label": "Has subtitles"},
                {"value": "no", "label": "No subtitles"},
            ],
        )


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


# ==========================================================================
# File Detail View Models (020-file-detail-view)
# ==========================================================================


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Formatted string (e.g., "4.2 GB", "128 MB", "1.5 KB").
    """
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.1f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"


@dataclass
class TrackTranscriptionInfo:
    """Transcription data for an audio track.

    Attributes:
        id: Transcription result ID (for linking to detail view).
        detected_language: Detected language code.
        confidence_score: Confidence as float (0.0-1.0).
        track_type: Classification ("main", "commentary", "alternate").
        plugin_name: Name of plugin that performed detection.
    """

    id: int  # Transcription result ID for detail view link (022-transcription-detail)
    detected_language: str | None
    confidence_score: float
    track_type: str
    plugin_name: str

    @property
    def confidence_percent(self) -> int:
        """Return confidence as integer percentage (0-100)."""
        return int(self.confidence_score * 100)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "detected_language": self.detected_language,
            "confidence_score": self.confidence_score,
            "track_type": self.track_type,
            "plugin_name": self.plugin_name,
        }


@dataclass
class TrackDetailItem:
    """Track data for file detail API response.

    Attributes:
        id: Database track ID.
        index: Track index within the file (0-based).
        track_type: Track type ("video", "audio", "subtitle", "other").
        codec: Codec name (e.g., "hevc", "aac", "subrip").
        language: ISO 639-2/B language code (e.g., "eng", "jpn") or None.
        title: Track title if set, or None.
        is_default: Whether track is marked as default.
        is_forced: Whether track is marked as forced.
        width: Video width in pixels, or None.
        height: Video height in pixels, or None.
        frame_rate: Frame rate string (e.g., "23.976"), or None.
        channels: Number of audio channels, or None.
        channel_layout: Human-readable layout (e.g., "stereo", "5.1"), or None.
        transcription: Transcription result data, or None.
    """

    id: int
    index: int
    track_type: str
    codec: str | None
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
    # Video-specific
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None
    # Audio-specific
    channels: int | None = None
    channel_layout: str | None = None
    # Transcription (optional)
    transcription: TrackTranscriptionInfo | None = None

    @property
    def resolution(self) -> str | None:
        """Return formatted resolution string (e.g., '1920x1080')."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "id": self.id,
            "index": self.index,
            "track_type": self.track_type,
            "codec": self.codec,
            "language": self.language,
            "title": self.title,
            "is_default": self.is_default,
            "is_forced": self.is_forced,
            "width": self.width,
            "height": self.height,
            "frame_rate": self.frame_rate,
            "channels": self.channels,
            "channel_layout": self.channel_layout,
            "transcription": (
                self.transcription.to_dict() if self.transcription else None
            ),
        }
        return result


@dataclass
class FileDetailItem:
    """Full file data for detail view API response.

    Attributes:
        id: Database file ID.
        path: Full file path.
        filename: Just the filename.
        directory: Parent directory path.
        extension: File extension (e.g., ".mkv").
        container_format: Container format name (e.g., "matroska").
        size_bytes: File size in bytes.
        size_human: Human-readable size (e.g., "4.2 GB").
        modified_at: ISO-8601 UTC timestamp of file modification.
        scanned_at: ISO-8601 UTC timestamp of last scan.
        scan_status: Scan status ("ok" or "error").
        scan_error: Error message if scan_status == "error".
        scan_job_id: UUID of scan job that discovered this file, or None.
        video_tracks: List of video tracks.
        audio_tracks: List of audio tracks.
        subtitle_tracks: List of subtitle tracks.
        other_tracks: List of other tracks (attachments, etc.).
    """

    id: int
    path: str
    filename: str
    directory: str
    extension: str
    container_format: str | None
    size_bytes: int
    size_human: str
    modified_at: str
    scanned_at: str
    scan_status: str
    scan_error: str | None
    scan_job_id: str | None
    # Tracks grouped by type
    video_tracks: list[TrackDetailItem]
    audio_tracks: list[TrackDetailItem]
    subtitle_tracks: list[TrackDetailItem]
    other_tracks: list[TrackDetailItem]

    @property
    def total_tracks(self) -> int:
        """Return total number of tracks."""
        return (
            len(self.video_tracks)
            + len(self.audio_tracks)
            + len(self.subtitle_tracks)
            + len(self.other_tracks)
        )

    @property
    def has_many_tracks(self) -> bool:
        """Return True if 5+ total tracks (for collapsible UI)."""
        return self.total_tracks >= 5

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "path": self.path,
            "filename": self.filename,
            "directory": self.directory,
            "extension": self.extension,
            "container_format": self.container_format,
            "size_bytes": self.size_bytes,
            "size_human": self.size_human,
            "modified_at": self.modified_at,
            "scanned_at": self.scanned_at,
            "scan_status": self.scan_status,
            "scan_error": self.scan_error,
            "scan_job_id": self.scan_job_id,
            "video_tracks": [t.to_dict() for t in self.video_tracks],
            "audio_tracks": [t.to_dict() for t in self.audio_tracks],
            "subtitle_tracks": [t.to_dict() for t in self.subtitle_tracks],
            "other_tracks": [t.to_dict() for t in self.other_tracks],
            "total_tracks": self.total_tracks,
            "has_many_tracks": self.has_many_tracks,
        }


@dataclass
class FileDetailResponse:
    """API response for /api/library/{file_id}.

    Attributes:
        file: The file detail data.
    """

    file: FileDetailItem

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {"file": self.file.to_dict()}


@dataclass
class FileDetailContext:
    """Template context for file_detail.html.

    Attributes:
        file: The file detail item.
        back_url: URL to return to library list.
    """

    file: FileDetailItem
    back_url: str

    @classmethod
    def from_file_and_request(
        cls,
        file: FileDetailItem,
        referer: str | None,
    ) -> FileDetailContext:
        """Create context preserving filter state from referer.

        Args:
            file: The file detail item.
            referer: HTTP Referer header value, if present.

        Returns:
            FileDetailContext with appropriate back URL.
        """
        back_url = "/library"
        if referer and "/library?" in referer:
            # Extract path with query params
            if referer.startswith("/"):
                back_url = referer
            elif "/library?" in referer:
                idx = referer.find("/library?")
                if idx != -1:
                    back_url = referer[idx:]
        return cls(file=file, back_url=back_url)


# ==========================================================================
# Transcriptions Overview List Models (021-transcriptions-list)
# ==========================================================================


def get_confidence_level(confidence: float | None) -> str | None:
    """Map confidence score to categorical level.

    Args:
        confidence: Average confidence score (0.0-1.0), or None.

    Returns:
        "high" if >= 0.8
        "medium" if >= 0.5 and < 0.8
        "low" if < 0.5
        None if confidence is None
    """
    if confidence is None:
        return None
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def format_detected_languages(languages_csv: str | None) -> list[str]:
    """Parse CSV language codes into list.

    Args:
        languages_csv: Comma-separated language codes from GROUP_CONCAT.

    Returns:
        List of unique language codes, or empty list.
    """
    if not languages_csv:
        return []
    return list(set(lang.strip() for lang in languages_csv.split(",") if lang.strip()))


@dataclass
class TranscriptionFilterParams:
    """Query parameters for /api/transcriptions.

    Attributes:
        show_all: If False (default), show only files with transcriptions.
                  If True, show all files.
        limit: Page size (1-100, default 50).
        offset: Pagination offset (>= 0, default 0).
    """

    show_all: bool = False
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, query: dict) -> TranscriptionFilterParams:
        """Create from request query dict with validation.

        Args:
            query: Query parameters from request.

        Returns:
            Validated TranscriptionFilterParams instance.
        """
        show_all = query.get("show_all", "").lower() == "true"
        try:
            limit = max(1, min(100, int(query.get("limit", 50))))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(query.get("offset", 0)))
        except (ValueError, TypeError):
            offset = 0
        return cls(show_all=show_all, limit=limit, offset=offset)


@dataclass
class TranscriptionListItem:
    """File data for Transcriptions list.

    Attributes:
        id: Database file ID.
        filename: Short filename for display.
        path: Full file path (for tooltip).
        has_transcription: Whether file has any transcription results.
        detected_languages: List of detected language codes.
        confidence_level: Categorical level ("high", "medium", "low", or None).
        confidence_avg: Average confidence score (0.0-1.0), or None.
        transcription_count: Number of tracks with transcription results.
        scan_status: "ok" or "error".
    """

    id: int
    filename: str
    path: str
    has_transcription: bool
    detected_languages: list[str]
    confidence_level: str | None
    confidence_avg: float | None
    transcription_count: int
    scan_status: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "filename": self.filename,
            "path": self.path,
            "has_transcription": self.has_transcription,
            "detected_languages": self.detected_languages,
            "confidence_level": self.confidence_level,
            "confidence_avg": self.confidence_avg,
            "transcription_count": self.transcription_count,
            "scan_status": self.scan_status,
        }


@dataclass
class TranscriptionListResponse:
    """API response for /api/transcriptions.

    Attributes:
        files: File items for current page.
        total: Total files matching filters.
        limit: Page size used.
        offset: Current offset.
        has_filters: True if show_all filter is active.
    """

    files: list[TranscriptionListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "files": [f.to_dict() for f in self.files],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
        }


# ==========================================================================
# Transcription Detail View Models (022-transcription-detail)
# ==========================================================================

# Max characters to display before truncation
TRANSCRIPT_DISPLAY_LIMIT = 10000

# Max characters for regex highlighting (ReDoS protection)
# Skip highlighting for very long transcripts to prevent CPU exhaustion
TRANSCRIPT_HIGHLIGHT_LIMIT = 50000


def get_classification_reasoning(
    track_title: str | None,
    transcript_sample: str | None,
    track_type: str,
) -> tuple[str | None, list[str]]:
    """Determine classification source and matched keywords.

    Args:
        track_title: Track title from metadata.
        transcript_sample: Transcription text sample.
        track_type: Track classification ("main", "commentary", "alternate").

    Returns:
        Tuple of (classification_source, matched_keywords):
        - classification_source: "metadata", "transcript", or None
        - matched_keywords: List of matched keywords/patterns
    """
    import re

    from video_policy_orchestrator.transcription.models import (
        COMMENTARY_KEYWORDS,
        COMMENTARY_TRANSCRIPT_PATTERNS,
        is_commentary_by_metadata,
    )

    if track_type != "commentary":
        return None, []

    matched = []

    # Check metadata first
    if track_title and is_commentary_by_metadata(track_title):
        title_lower = track_title.lower()
        for keyword in COMMENTARY_KEYWORDS:
            if keyword in title_lower:
                matched.append(f"Title contains: '{keyword}'")
        return "metadata", matched

    # Check transcript patterns
    if transcript_sample:
        sample_lower = transcript_sample.lower()
        for pattern in COMMENTARY_TRANSCRIPT_PATTERNS:
            if re.search(pattern, sample_lower, re.IGNORECASE):
                # Convert regex to readable form
                readable = pattern.replace(r"\b", "").replace("\\", "")
                matched.append(f"Pattern: {readable}")
        if matched:
            return "transcript", matched

    return None, []


def highlight_keywords_in_transcript(
    transcript: str | None,
    track_type: str,
) -> tuple[str | None, bool]:
    """Generate HTML with highlighted commentary keywords.

    Args:
        transcript: Raw transcript text.
        track_type: Track classification.

    Returns:
        Tuple of (html_content, is_truncated):
        - html_content: HTML-escaped text with <mark> tags, or None
        - is_truncated: True if text was truncated

    Note:
        ReDoS protection: Regex highlighting is skipped for transcripts
        exceeding TRANSCRIPT_HIGHLIGHT_LIMIT to prevent CPU exhaustion.
    """
    import html
    import re

    if not transcript:
        return None, False

    from video_policy_orchestrator.transcription.models import (
        COMMENTARY_TRANSCRIPT_PATTERNS,
    )

    # Truncate if too long
    is_truncated = len(transcript) > TRANSCRIPT_DISPLAY_LIMIT
    display_text = transcript[:TRANSCRIPT_DISPLAY_LIMIT] if is_truncated else transcript

    # Escape HTML first
    escaped = html.escape(display_text)

    # Only highlight if commentary track
    if track_type != "commentary":
        return escaped, is_truncated

    # ReDoS protection: skip highlighting for very long transcripts
    if len(transcript) > TRANSCRIPT_HIGHLIGHT_LIMIT:
        return escaped, is_truncated

    # Apply highlighting for each pattern
    for pattern in COMMENTARY_TRANSCRIPT_PATTERNS:
        try:
            # Find matches and wrap with <mark>
            escaped = re.sub(
                f"({pattern})",
                r'<mark class="commentary-match">\1</mark>',
                escaped,
                flags=re.IGNORECASE,
            )
        except (re.error, RecursionError):
            continue  # Skip invalid patterns or catastrophic backtracking

    return escaped, is_truncated


@dataclass
class TranscriptionDetailItem:
    """Full transcription data for detail view.

    Attributes:
        id: Transcription result ID (used in URL).
        track_id: Associated track ID.
        detected_language: Detected language code.
        confidence_score: Confidence as float (0.0-1.0).
        confidence_level: Categorical level ("high", "medium", "low").
        track_classification: Track type ("main", "commentary", "alternate").
        transcript_sample: The transcription text.
        transcript_html: HTML with keyword highlighting (for commentary).
        transcript_truncated: True if text exceeds display threshold.
        plugin_name: Name of transcription plugin.
        created_at: ISO-8601 UTC timestamp.
        updated_at: ISO-8601 UTC timestamp.
        track_index: Track index within file (0-based).
        track_codec: Audio codec name.
        original_language: Original language tag from track.
        track_title: Track title (may indicate commentary).
        channels: Number of audio channels.
        channel_layout: Human-readable layout (e.g., "5.1").
        is_default: Whether track is marked as default.
        is_forced: Whether track is marked as forced.
        is_commentary: True if classified as commentary.
        classification_source: "metadata" | "transcript" | None.
        matched_keywords: List of matched commentary keywords/patterns.
        file_id: Parent file ID.
        filename: Parent filename.
        file_path: Parent file path.
    """

    # Transcription data
    id: int
    track_id: int
    detected_language: str | None
    confidence_score: float
    confidence_level: str  # "high", "medium", "low"
    track_classification: str  # "main", "commentary", "alternate"
    transcript_sample: str | None
    transcript_html: str | None  # HTML with keyword highlighting
    transcript_truncated: bool
    plugin_name: str
    created_at: str
    updated_at: str
    # Track metadata
    track_index: int
    track_codec: str | None
    original_language: str | None
    track_title: str | None
    channels: int | None
    channel_layout: str | None
    is_default: bool
    is_forced: bool
    # Classification reasoning
    is_commentary: bool
    classification_source: str | None  # "metadata", "transcript", or None
    matched_keywords: list[str]
    # Parent file
    file_id: int
    filename: str
    file_path: str

    @property
    def confidence_percent(self) -> int:
        """Return confidence as integer percentage (0-100)."""
        return int(self.confidence_score * 100)

    @property
    def is_low_confidence(self) -> bool:
        """Return True if confidence < 0.3 (warning threshold)."""
        return self.confidence_score < 0.3

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "track_id": self.track_id,
            "detected_language": self.detected_language,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "confidence_percent": self.confidence_percent,
            "is_low_confidence": self.is_low_confidence,
            "track_classification": self.track_classification,
            "transcript_sample": self.transcript_sample,
            "transcript_html": self.transcript_html,
            "transcript_truncated": self.transcript_truncated,
            "plugin_name": self.plugin_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "track_index": self.track_index,
            "track_codec": self.track_codec,
            "original_language": self.original_language,
            "track_title": self.track_title,
            "channels": self.channels,
            "channel_layout": self.channel_layout,
            "is_default": self.is_default,
            "is_forced": self.is_forced,
            "is_commentary": self.is_commentary,
            "classification_source": self.classification_source,
            "matched_keywords": self.matched_keywords,
            "file_id": self.file_id,
            "filename": self.filename,
            "file_path": self.file_path,
        }


@dataclass
class TranscriptionDetailResponse:
    """API response for /api/transcriptions/{id}.

    Attributes:
        transcription: The transcription detail data.
    """

    transcription: TranscriptionDetailItem

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {"transcription": self.transcription.to_dict()}


@dataclass
class TranscriptionDetailContext:
    """Template context for transcription_detail.html.

    Attributes:
        transcription: The transcription detail item.
        back_url: URL to return to previous page.
        back_label: Label for back link ("File Detail" or "Transcriptions").
    """

    transcription: TranscriptionDetailItem
    back_url: str
    back_label: str

    @staticmethod
    def _is_safe_back_url(url: str) -> bool:
        """Validate URL is safe for back navigation (prevent open redirect).

        Args:
            url: URL path to validate.

        Returns:
            True if URL is a safe internal path.
        """
        if not url or not isinstance(url, str):
            return False
        # Only allow relative paths starting with known safe prefixes
        safe_prefixes = ("/library/", "/library", "/transcriptions", "/")
        return url.startswith(safe_prefixes) and "//" not in url

    @classmethod
    def from_transcription_and_request(
        cls,
        transcription: TranscriptionDetailItem,
        referer: str | None,
    ) -> TranscriptionDetailContext:
        """Create context preserving navigation state.

        Args:
            transcription: The transcription detail item.
            referer: HTTP Referer header value, if present.

        Returns:
            TranscriptionDetailContext with appropriate back URL.

        Note:
            Referer is validated to prevent open redirect attacks.
            Only paths starting with /library/ or /transcriptions are allowed.
        """
        # Default: back to parent file detail
        back_url = f"/library/{transcription.file_id}"
        back_label = "File Detail"

        # If came from transcriptions list, go back there
        if referer:
            # Extract path portion from referer (handles full URLs)
            extracted_path = None
            if referer.startswith("/"):
                extracted_path = referer
            else:
                idx = referer.find("/transcriptions")
                if idx != -1:
                    extracted_path = referer[idx:]

            # Validate and use if safe
            if (
                extracted_path
                and cls._is_safe_back_url(extracted_path)
                and "/transcriptions" in extracted_path
                and f"/transcriptions/{transcription.id}" not in extracted_path
            ):
                back_url = extracted_path
                back_label = "Transcriptions"

        return cls(
            transcription=transcription,
            back_url=back_url,
            back_label=back_label,
        )


# ==========================================================================
# Policies List View Models (023-policies-list-view)
# ==========================================================================


def format_language_preferences(languages: list[str]) -> str:
    """Format language preference list for display.

    Args:
        languages: List of ISO 639-2 language codes.

    Returns:
        Formatted string (e.g., "eng, jpn" or "eng, jpn +2 more") or "-".
    """
    if not languages:
        return "\u2014"

    if len(languages) <= 3:
        return ", ".join(languages)

    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"


@dataclass
class PolicyListItem:
    """Policy data for Policies API response.

    Attributes:
        name: Policy name (filename without extension).
        filename: Full filename with extension.
        file_path: Absolute path to the policy file.
        last_modified: ISO-8601 UTC timestamp.
        schema_version: Policy schema version (null if parse error).
        audio_languages: Formatted audio language preferences.
        subtitle_languages: Formatted subtitle language preferences.
        has_transcode: True if policy includes transcode settings.
        has_transcription: True if transcription enabled.
        is_default: True if this is the profile's default policy.
        parse_error: Error message if YAML invalid, else None.
    """

    name: str
    filename: str
    file_path: str
    last_modified: str
    schema_version: int | None
    audio_languages: str
    subtitle_languages: str
    has_transcode: bool
    has_transcription: bool
    is_default: bool
    parse_error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "filename": self.filename,
            "file_path": self.file_path,
            "last_modified": self.last_modified,
            "schema_version": self.schema_version,
            "audio_languages": self.audio_languages,
            "subtitle_languages": self.subtitle_languages,
            "has_transcode": self.has_transcode,
            "has_transcription": self.has_transcription,
            "is_default": self.is_default,
            "parse_error": self.parse_error,
        }


@dataclass
class PolicyListResponse:
    """API response wrapper for /api/policies.

    Attributes:
        policies: List of policy items.
        total: Total number of policies found.
        policies_directory: Path to policies directory.
        default_policy_path: Configured default policy path (may be None).
        default_policy_missing: True if configured default doesn't exist.
        directory_exists: True if policies directory exists.
    """

    policies: list[PolicyListItem]
    total: int
    policies_directory: str
    default_policy_path: str | None
    default_policy_missing: bool
    directory_exists: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "policies": [p.to_dict() for p in self.policies],
            "total": self.total,
            "policies_directory": self.policies_directory,
            "default_policy_path": self.default_policy_path,
            "default_policy_missing": self.default_policy_missing,
            "directory_exists": self.directory_exists,
        }


@dataclass
class PoliciesContext:
    """Template context for policies.html.

    Attributes:
        policies_directory: Path to policies directory for display.
    """

    policies_directory: str

    @classmethod
    def default(cls) -> PoliciesContext:
        """Create default context."""
        return cls(
            policies_directory=str(Path.home() / ".vpo" / "policies"),
        )


def group_tracks_by_type(
    tracks: list,
    transcriptions: dict,
) -> tuple[
    list[TrackDetailItem],
    list[TrackDetailItem],
    list[TrackDetailItem],
    list[TrackDetailItem],
]:
    """Group tracks by type and attach transcription data.

    Args:
        tracks: List of TrackRecord from database.
        transcriptions: Dict mapping track_id to TranscriptionResultRecord.

    Returns:
        Tuple of (video_tracks, audio_tracks, subtitle_tracks, other_tracks).
    """
    video_tracks: list[TrackDetailItem] = []
    audio_tracks: list[TrackDetailItem] = []
    subtitle_tracks: list[TrackDetailItem] = []
    other_tracks: list[TrackDetailItem] = []

    for track in tracks:
        # Build transcription info if available (audio tracks only)
        transcription_info = None
        if track.track_type == "audio" and track.id in transcriptions:
            tr = transcriptions[track.id]
            transcription_info = TrackTranscriptionInfo(
                id=tr.id,  # For transcription detail link (022)
                detected_language=tr.detected_language,
                confidence_score=tr.confidence_score,
                track_type=tr.track_type,
                plugin_name=tr.plugin_name,
            )

        detail_item = TrackDetailItem(
            id=track.id,
            index=track.track_index,
            track_type=track.track_type,
            codec=track.codec,
            language=track.language,
            title=track.title,
            is_default=track.is_default,
            is_forced=track.is_forced,
            width=track.width,
            height=track.height,
            frame_rate=track.frame_rate,
            channels=track.channels,
            channel_layout=track.channel_layout,
            transcription=transcription_info,
        )

        if track.track_type == "video":
            video_tracks.append(detail_item)
        elif track.track_type == "audio":
            audio_tracks.append(detail_item)
        elif track.track_type == "subtitle":
            subtitle_tracks.append(detail_item)
        else:
            other_tracks.append(detail_item)

    return video_tracks, audio_tracks, subtitle_tracks, other_tracks


# ==========================================================================
# Policy Editor Models (024-policy-editor)
# ==========================================================================


@dataclass
class PolicyEditorContext:
    """Context passed to policy_editor.html template.

    Attributes:
        name: Policy name (filename without extension).
        filename: Full filename with extension.
        file_path: Absolute path to the policy file.
        last_modified: ISO-8601 UTC timestamp for concurrency check.
        schema_version: Policy schema version (read-only).
        track_order: List of track type strings.
        audio_language_preference: List of ISO 639-2 codes.
        subtitle_language_preference: List of ISO 639-2 codes.
        commentary_patterns: List of regex patterns.
        default_flags: Default flags configuration dict.
        transcode: Transcode configuration dict, or None.
        transcription: Transcription configuration dict, or None.
        parse_error: Error message if policy invalid, else None.
    """

    name: str
    filename: str
    file_path: str
    last_modified: str
    schema_version: int
    track_order: list[str]
    audio_language_preference: list[str]
    subtitle_language_preference: list[str]
    commentary_patterns: list[str]
    default_flags: dict
    transcode: dict | None
    transcription: dict | None
    parse_error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "filename": self.filename,
            "file_path": self.file_path,
            "last_modified": self.last_modified,
            "schema_version": self.schema_version,
            "track_order": self.track_order,
            "audio_language_preference": self.audio_language_preference,
            "subtitle_language_preference": self.subtitle_language_preference,
            "commentary_patterns": self.commentary_patterns,
            "default_flags": self.default_flags,
            "transcode": self.transcode,
            "transcription": self.transcription,
            "parse_error": self.parse_error,
        }


@dataclass
class PolicyEditorRequest:
    """Request payload for saving policy changes via PUT /api/policies/{name}.

    Attributes:
        track_order: Updated track ordering.
        audio_language_preference: Updated audio language preferences.
        subtitle_language_preference: Updated subtitle language preferences.
        commentary_patterns: Updated commentary detection patterns.
        default_flags: Updated default flags configuration.
        transcode: Updated transcode settings, or None.
        transcription: Updated transcription settings, or None.
        last_modified_timestamp: ISO-8601 UTC timestamp for optimistic locking.
    """

    track_order: list[str]
    audio_language_preference: list[str]
    subtitle_language_preference: list[str]
    commentary_patterns: list[str]
    default_flags: dict
    transcode: dict | None
    transcription: dict | None
    last_modified_timestamp: str

    @classmethod
    def from_dict(cls, data: dict) -> PolicyEditorRequest:
        """Create PolicyEditorRequest from request payload.

        Args:
            data: JSON request payload.

        Returns:
            Validated PolicyEditorRequest instance.

        Raises:
            ValueError: If required fields are missing.
        """
        required_fields = [
            "track_order",
            "audio_language_preference",
            "subtitle_language_preference",
            "commentary_patterns",
            "default_flags",
            "last_modified_timestamp",
        ]

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        return cls(
            track_order=data["track_order"],
            audio_language_preference=data["audio_language_preference"],
            subtitle_language_preference=data["subtitle_language_preference"],
            commentary_patterns=data["commentary_patterns"],
            default_flags=data["default_flags"],
            transcode=data.get("transcode"),
            transcription=data.get("transcription"),
            last_modified_timestamp=data["last_modified_timestamp"],
        )

    def to_policy_dict(self) -> dict:
        """Convert to dictionary for policy validation and saving.

        Returns:
            Dictionary in PolicyModel format.
        """
        # Must include schema_version for validation
        result = {
            "schema_version": 2,  # Always use current schema version
            "track_order": self.track_order,
            "audio_language_preference": self.audio_language_preference,
            "subtitle_language_preference": self.subtitle_language_preference,
            "commentary_patterns": self.commentary_patterns,
            "default_flags": self.default_flags,
        }

        if self.transcode is not None:
            result["transcode"] = self.transcode

        if self.transcription is not None:
            result["transcription"] = self.transcription

        return result
