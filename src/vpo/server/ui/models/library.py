"""Library list view models.

This module defines models for the library file list and filtering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.server.ui.models.file_detail import TrackDetailItem

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
        if status not in (None, "", "ok", "error", "missing"):
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
                    lang.casefold().strip()
                    for lang in audio_lang_raw
                    if lang and len(lang.strip()) in (2, 3)
                ]
            elif isinstance(audio_lang_raw, str) and len(audio_lang_raw.strip()) in (
                2,
                3,
            ):
                audio_lang = [audio_lang_raw.casefold().strip()]
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
    max_page_size: int = 100

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "files": [f.to_dict() for f in self.files],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
            "max_page_size": self.max_page_size,
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
                {"value": "missing", "label": "Missing files"},
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
class TrackTranscriptionInfo:
    """Transcription data for an audio track.

    Attributes:
        id: Transcription result ID (for linking to detail view).
        detected_language: Detected language code.
        confidence_score: Confidence as float (0.0-1.0).
        track_type: Classification ("main", "commentary", "alternate").
        plugin_name: Name of plugin that performed detection.
    """

    id: int  # Transcription result ID for detail view link (022)
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
    # Import here to avoid circular imports
    from vpo.server.ui.models.file_detail import TrackDetailItem

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
