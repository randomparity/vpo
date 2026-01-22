"""Domain models for Video Policy Orchestrator.

This module contains core domain models that are used across multiple VPO modules.
These models represent the domain concepts independent of the database layer.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Type alias for plugin-provided metadata
# Structure: {"plugin_name": {"field": value, ...}, ...}
# Note: Values must be scalar types (str, int, float, bool, None).
# Nested structures (lists, dicts) are not supported in condition evaluation.
PluginMetadataDict = dict[str, dict[str, str | int | float | bool | None]]


@dataclass
class TrackInfo:
    """Represents a media track within a video file (domain model)."""

    index: int
    track_type: str  # "video", "audio", "subtitle", "attachment", "other"
    # Database ID (optional, set when loaded from database)
    # Used for linking to related data like language analysis results
    id: int | None = None
    codec: str | None = None
    language: str | None = None
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False
    # Audio-specific fields (003-media-introspection)
    channels: int | None = None
    channel_layout: str | None = None  # Human-readable: "stereo", "5.1", etc.
    # Video-specific fields (003-media-introspection)
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None  # Stored as string to preserve precision
    # HDR color metadata fields (034-conditional-video-transcode)
    color_transfer: str | None = None  # e.g., "smpte2084" (PQ), "arib-std-b67" (HLG)
    color_primaries: str | None = None  # e.g., "bt2020"
    color_space: str | None = None  # e.g., "bt2020nc"
    color_range: str | None = None  # e.g., "tv", "pc"
    # Track duration (035-multi-language-audio-detection)
    duration_seconds: float | None = None  # Duration in seconds


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
    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scan_status: str = "ok"  # "ok", "error", "pending"
    scan_error: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)
    # Plugin-provided metadata (039-plugin-metadata-policy)
    # Dict keyed by plugin name, e.g., {"radarr": {"original_language": "jpn", ...}}
    plugin_metadata: PluginMetadataDict | None = None


@dataclass
class IntrospectionResult:
    """Result of media file introspection."""

    file_path: Path
    container_format: str | None
    tracks: list[TrackInfo]
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        """Return True if introspection completed without fatal errors."""
        return self.error is None

    @property
    def primary_video_track(self) -> TrackInfo | None:
        """Return the first video track, or None if no video tracks exist."""
        return next((t for t in self.tracks if t.track_type == "video"), None)

    @property
    def duration_seconds(self) -> float | None:
        """Return duration from primary video track, or None if unavailable."""
        video = self.primary_video_track
        return video.duration_seconds if video else None
