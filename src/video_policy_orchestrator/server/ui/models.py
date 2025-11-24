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
        detected_language: Detected language code.
        confidence_score: Confidence as float (0.0-1.0).
        track_type: Classification ("main", "commentary", "alternate").
        plugin_name: Name of plugin that performed detection.
    """

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
