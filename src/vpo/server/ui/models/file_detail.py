"""File detail view models.

This module defines models for displaying detailed file information
including tracks and metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.db.types import FileRecord, TrackRecord, TranscriptionResultRecord
    from vpo.server.ui.models.library import TrackTranscriptionInfo


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
    # Plugin metadata (236-generic-plugin-data-browser)
    plugin_metadata: dict[str, dict] | None = None

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

    @property
    def has_plugin_data(self) -> bool:
        """Return True if file has any plugin metadata."""
        return bool(self.plugin_metadata)

    @property
    def plugin_count(self) -> int:
        """Return number of plugins with data for this file."""
        return len(self.plugin_metadata) if self.plugin_metadata else 0

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
            "plugin_metadata": self.plugin_metadata,
            "has_plugin_data": self.has_plugin_data,
            "plugin_count": self.plugin_count,
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


def build_file_detail_item(
    file_record: FileRecord,
    tracks: list[TrackRecord],
    transcriptions: dict[int, TranscriptionResultRecord],
) -> FileDetailItem:
    """Build FileDetailItem from database records.

    This is a shared builder used by both HTML and API handlers.

    Args:
        file_record: FileRecord from database.
        tracks: List of TrackRecord from database.
        transcriptions: Dict mapping track_id to TranscriptionResultRecord.

    Returns:
        FileDetailItem ready for API/template use.
    """
    from vpo.core.formatting import format_file_size
    from vpo.core.json_utils import parse_json_safe
    from vpo.server.ui.models.library import group_tracks_by_type

    # Group tracks by type
    video_tracks, audio_tracks, subtitle_tracks, other_tracks = group_tracks_by_type(
        tracks, transcriptions
    )

    # Parse plugin_metadata JSON
    plugin_result = parse_json_safe(
        file_record.plugin_metadata,
        context=f"plugin_metadata for file {file_record.id}",
    )
    plugin_metadata = plugin_result.value

    return FileDetailItem(
        id=file_record.id,
        path=file_record.path,
        filename=file_record.filename,
        directory=file_record.directory,
        extension=file_record.extension,
        container_format=file_record.container_format,
        size_bytes=file_record.size_bytes,
        size_human=format_file_size(file_record.size_bytes),
        modified_at=file_record.modified_at,
        scanned_at=file_record.scanned_at,
        scan_status=file_record.scan_status,
        scan_error=file_record.scan_error,
        scan_job_id=file_record.job_id,
        video_tracks=video_tracks,
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        other_tracks=other_tracks,
        plugin_metadata=plugin_metadata,
    )
