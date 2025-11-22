"""Data models for Video Policy Orchestrator database."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TrackInfo:
    """Represents a media track within a video file (domain model)."""

    index: int
    track_type: str  # "video", "audio", "subtitle", "other"
    codec: str | None = None
    language: str | None = None
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False


@dataclass
class FileInfo:
    """Represents a scanned video file with its tracks (domain model)."""

    path: Path
    filename: str
    directory: Path
    extension: str
    size_bytes: int
    modified_at: datetime
    content_hash: str | None = None
    container_format: str | None = None
    scanned_at: datetime = field(default_factory=datetime.now)
    scan_status: str = "ok"  # "ok", "error", "pending"
    scan_error: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)


@dataclass
class FileRecord:
    """Database record for files table."""

    id: int | None
    path: str
    filename: str
    directory: str
    extension: str
    size_bytes: int
    modified_at: str  # ISO 8601
    content_hash: str | None
    container_format: str | None
    scanned_at: str  # ISO 8601
    scan_status: str
    scan_error: str | None

    @classmethod
    def from_file_info(cls, info: FileInfo) -> "FileRecord":
        """Create a FileRecord from a FileInfo domain object."""
        return cls(
            id=None,
            path=str(info.path),
            filename=info.filename,
            directory=str(info.directory),
            extension=info.extension,
            size_bytes=info.size_bytes,
            modified_at=info.modified_at.isoformat(),
            content_hash=info.content_hash,
            container_format=info.container_format,
            scanned_at=info.scanned_at.isoformat(),
            scan_status=info.scan_status,
            scan_error=info.scan_error,
        )


@dataclass
class TrackRecord:
    """Database record for tracks table."""

    id: int | None
    file_id: int
    track_index: int
    track_type: str
    codec: str | None
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool

    @classmethod
    def from_track_info(cls, info: TrackInfo, file_id: int) -> "TrackRecord":
        """Create a TrackRecord from a TrackInfo domain object."""
        return cls(
            id=None,
            file_id=file_id,
            track_index=info.index,
            track_type=info.track_type,
            codec=info.codec,
            language=info.language,
            title=info.title,
            is_default=info.is_default,
            is_forced=info.is_forced,
        )
