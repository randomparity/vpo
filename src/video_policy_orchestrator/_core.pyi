"""Type stubs for the vpo-core Rust extension module."""

from collections.abc import Callable
from typing import TypedDict

class DiscoveredFile(TypedDict):
    """A discovered video file."""

    path: str
    size: int
    modified: float

class FileHash(TypedDict):
    """Hash result for a file."""

    path: str
    hash: str | None
    error: str | None

def version() -> str:
    """Return the version of the vpo-core library."""
    ...

def discover_videos(
    root_path: str,
    extensions: list[str],
    follow_symlinks: bool = False,
    progress_callback: Callable[[int], None] | None = None,
) -> list[DiscoveredFile]:
    """Recursively discover video files in a directory.

    Args:
        root_path: The root directory to scan
        extensions: List of file extensions to match (e.g., ["mkv", "mp4"])
        follow_symlinks: Whether to follow symbolic links
        progress_callback: Optional callback called with (files_found,) as files
            are discovered

    Returns:
        List of dicts with path, size, and modified timestamp for each file

    Raises:
        FileNotFoundError: If the directory does not exist
        NotADirectoryError: If the path is not a directory
    """
    ...

def hash_files(
    paths: list[str],
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[FileHash]:
    """Hash multiple files in parallel using xxHash64.

    Args:
        paths: List of file paths to hash
        progress_callback: Optional callback called with (processed, total) as
            files are hashed

    Returns:
        List of dicts with path, hash (or None), and error (or None) for each file
    """
    ...
