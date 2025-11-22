"""Stub implementation of MediaIntrospector for development and testing."""

from datetime import datetime, timezone
from pathlib import Path

from video_policy_orchestrator.db.models import FileInfo, TrackInfo
from video_policy_orchestrator.introspector.interface import MediaIntrospectionError

# Container format mapping from extension to format name
CONTAINER_FORMAT_MAP = {
    "mkv": "matroska",
    "mk3d": "matroska",
    "mka": "matroska",
    "mks": "matroska",
    "mp4": "mp4",
    "m4v": "mp4",
    "m4a": "mp4",
    "mov": "quicktime",
    "avi": "avi",
    "webm": "webm",
    "wmv": "asf",
    "flv": "flv",
    "ts": "mpegts",
    "mts": "mpegts",
    "m2ts": "mpegts",
    "vob": "mpeg",
    "mpg": "mpeg",
    "mpeg": "mpeg",
    "ogv": "ogg",
    "ogm": "ogg",
}


class StubIntrospector:
    """Stub implementation that returns placeholder metadata.

    This implementation infers container format from file extension
    and returns placeholder track data. It's intended for development
    and testing; a real implementation would use ffprobe or mkvmerge.
    """

    def get_file_info(self, path: Path) -> FileInfo:
        """Extract metadata from a video file using extension-based inference.

        Args:
            path: Path to the video file.

        Returns:
            FileInfo object with inferred container format and placeholder tracks.

        Raises:
            MediaIntrospectionError: If the file does not exist.
        """
        if not path.exists():
            raise MediaIntrospectionError(f"File not found: {path}")

        # Get file metadata
        stat = path.stat()
        extension = path.suffix.lstrip(".").lower()

        # Infer container format from extension
        container_format = CONTAINER_FORMAT_MAP.get(extension)

        # Create placeholder tracks
        tracks = self._create_placeholder_tracks(extension)

        return FileInfo(
            path=path,
            filename=path.name,
            directory=path.parent,
            extension=extension,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            container_format=container_format,
            scanned_at=datetime.now(timezone.utc),
            scan_status="ok",
            tracks=tracks,
        )

    def _create_placeholder_tracks(self, extension: str) -> list[TrackInfo]:
        """Create placeholder track information based on extension.

        Args:
            extension: File extension (without dot).

        Returns:
            List of placeholder TrackInfo objects.
        """
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="h264" if extension in ("mp4", "m4v", "mov") else "hevc",
                language=None,
                title=None,
                is_default=True,
                is_forced=False,
            ),
        ]

        # Add audio track placeholder
        tracks.append(
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac" if extension in ("mp4", "m4v", "mov") else "opus",
                language="eng",
                title=None,
                is_default=True,
                is_forced=False,
            )
        )

        return tracks
