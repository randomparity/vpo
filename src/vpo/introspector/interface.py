"""MediaIntrospector interface for video metadata extraction."""

from pathlib import Path
from typing import Protocol

from vpo.db.types import IntrospectionResult


class MediaIntrospectionError(Exception):
    """Raised when media introspection fails."""

    pass


class MediaIntrospector(Protocol):
    """Protocol for media introspection implementations.

    This protocol defines the interface for extracting metadata from
    video files. Implementations can use ffprobe, mkvmerge, or other
    tools to gather track and container information.
    """

    def get_file_info(self, path: Path) -> IntrospectionResult:
        """Extract metadata from a video file.

        Args:
            path: Path to the video file.

        Returns:
            IntrospectionResult containing file metadata and track information.

        Raises:
            MediaIntrospectionError: If the file cannot be introspected.
        """
        ...
