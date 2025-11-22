"""Type stubs for the vpo-core Rust extension module."""

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
) -> list[DiscoveredFile]:
    """Recursively discover video files in a directory.

    Args:
        root_path: The root directory to scan
        extensions: List of file extensions to match (e.g., ["mkv", "mp4"])
        follow_symlinks: Whether to follow symbolic links

    Returns:
        List of dicts with path, size, and modified timestamp for each file

    Raises:
        FileNotFoundError: If the directory does not exist
        NotADirectoryError: If the path is not a directory
    """
    ...

def hash_files(paths: list[str]) -> list[FileHash]:
    """Hash multiple files in parallel using xxHash64.

    Args:
        paths: List of file paths to hash

    Returns:
        List of dicts with path, hash (or None), and error (or None) for each file
    """
    ...
