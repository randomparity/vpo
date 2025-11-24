# Data Model: File Detail View

**Feature**: 020-file-detail-view
**Date**: 2025-11-23

## Overview

This document defines the data models for the file detail view feature. All models follow existing patterns from `server/ui/models.py`.

## Entities

### TrackDetailItem

Represents a single track within a file for display purposes.

```python
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
        # Video-specific fields
        width: Video width in pixels, or None.
        height: Video height in pixels, or None.
        frame_rate: Frame rate string (e.g., "23.976"), or None.
        # Audio-specific fields
        channels: Number of audio channels, or None.
        channel_layout: Human-readable layout (e.g., "stereo", "5.1"), or None.
        # Transcription fields (when available)
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
    transcription: dict | None = None
```

**Validation rules**:
- `track_type` must be one of: "video", "audio", "subtitle", "other"
- `index` must be >= 0
- `channels` if present must be > 0
- `width` and `height` if present must be > 0

### TrackTranscriptionInfo

Represents transcription result for an audio track.

```python
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
```

### FileDetailItem

Main model for file detail view, containing file metadata and all tracks.

```python
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
        # Track collections by type
        video_tracks: List of video tracks.
        audio_tracks: List of audio tracks.
        subtitle_tracks: List of subtitle tracks.
        other_tracks: List of other tracks (attachments, etc.).
        # Computed properties
        total_tracks: Total number of tracks.
        has_many_tracks: True if 5+ total tracks (for collapsible UI).
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
        return len(self.video_tracks) + len(self.audio_tracks) + \
               len(self.subtitle_tracks) + len(self.other_tracks)

    @property
    def has_many_tracks(self) -> bool:
        return self.total_tracks >= 5
```

**Validation rules**:
- `id` must be > 0
- `size_bytes` must be >= 0
- `scan_status` must be "ok" or "error"
- `scan_job_id` if present must be valid UUID format

### FileDetailResponse

API response wrapper for file detail endpoint.

```python
@dataclass
class FileDetailResponse:
    """API response for /api/library/{file_id}.

    Attributes:
        file: The file detail data.
    """
    file: FileDetailItem
```

### FileDetailContext

Template context for file_detail.html.

```python
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
        """Create context preserving filter state from referer."""
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
```

## Relationships

```
FileRecord (existing)
    │
    ├── 1:N ──▶ TrackRecord (existing)
    │               │
    │               └── 1:1 ──▶ TranscriptionResultRecord (existing, optional)
    │
    └── N:1 ──▶ Job (existing, via job_id)
```

## Database Queries

### get_file_by_id (new)

```python
def get_file_by_id(conn: sqlite3.Connection, file_id: int) -> FileRecord | None:
    """Get a file record by ID.

    Args:
        conn: Database connection.
        file_id: File primary key.

    Returns:
        FileRecord if found, None otherwise.
    """
```

### get_file_detail (new, combines multiple queries)

```python
def get_file_detail(
    conn: sqlite3.Connection,
    file_id: int
) -> tuple[FileRecord | None, list[TrackRecord], dict[int, TranscriptionResultRecord]]:
    """Get file with all tracks and transcription results.

    Args:
        conn: Database connection.
        file_id: File primary key.

    Returns:
        Tuple of (file_record, tracks, transcriptions_by_track_id).
        file_record is None if file not found.
    """
```

## State Transitions

This feature is read-only. No state transitions are involved.

## Helper Functions

### format_file_size

```python
def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Formatted string (e.g., "4.2 GB", "128 MB", "1.5 KB").
    """
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024 ** 3):.1f} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"
```

### group_tracks_by_type

```python
def group_tracks_by_type(
    tracks: list[TrackRecord],
    transcriptions: dict[int, TranscriptionResultRecord]
) -> tuple[list[TrackDetailItem], list[TrackDetailItem],
           list[TrackDetailItem], list[TrackDetailItem]]:
    """Group tracks by type and attach transcription data.

    Args:
        tracks: List of TrackRecord from database.
        transcriptions: Dict mapping track_id to TranscriptionResultRecord.

    Returns:
        Tuple of (video_tracks, audio_tracks, subtitle_tracks, other_tracks).
    """
```
