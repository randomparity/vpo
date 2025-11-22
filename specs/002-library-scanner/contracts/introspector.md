# Interface Contract: MediaIntrospector

**Feature**: 002-library-scanner
**Date**: 2025-11-21

## Protocol Definition

```python
from typing import Protocol
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TrackInfo:
    """Information about a single track within a media file."""
    index: int
    track_type: str  # "video" | "audio" | "subtitle" | "other"
    codec: str | None
    language: str | None  # ISO 639-2 (e.g., "eng", "jpn")
    title: str | None
    is_default: bool
    is_forced: bool


@dataclass
class FileInfo:
    """Information about a media file and its tracks."""
    path: Path
    container_format: str  # e.g., "matroska", "mp4", "avi"
    tracks: list[TrackInfo]


class MediaIntrospector(Protocol):
    """Protocol for extracting metadata from media files."""

    def get_file_info(self, path: Path) -> FileInfo:
        """
        Extract metadata from a media file.

        Args:
            path: Absolute path to a media file

        Returns:
            FileInfo containing container format and track information

        Raises:
            FileNotFoundError: If path does not exist
            PermissionError: If path cannot be read
            MediaIntrospectionError: If file cannot be parsed as media
        """
        ...
```

## Error Types

```python
class MediaIntrospectionError(Exception):
    """Raised when a file cannot be parsed as a media file."""
    def __init__(self, path: Path, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Cannot introspect {path}: {reason}")
```

## Implementations

### StubIntrospector (Sprint 1)

Returns placeholder data based on file extension. Used for development and testing.

**Behavior**:
- Maps extension to container format (`.mkv` → `"matroska"`, `.mp4` → `"mp4"`)
- Returns empty track list (no actual media inspection)
- Raises `FileNotFoundError` if path doesn't exist
- Raises `MediaIntrospectionError` for unsupported extensions

**Example Output**:

```python
# Input: Path("/media/movie.mkv")
# Output:
FileInfo(
    path=Path("/media/movie.mkv"),
    container_format="matroska",
    tracks=[]
)
```

### FfprobeIntrospector (Future Sprint)

Wraps `ffprobe` command-line tool for real metadata extraction.

**Behavior**:
- Executes `ffprobe -v quiet -print_format json -show_streams <path>`
- Parses JSON output into TrackInfo objects
- Maps ffprobe codec names to normalized codec identifiers
- Handles ffprobe errors (missing binary, invalid file)

### MkvmergeIntrospector (Future Sprint)

Wraps `mkvmerge --identify` for MKV-specific metadata.

**Behavior**:
- Executes `mkvmerge --identify --identification-format json <path>`
- Provides more detailed MKV-specific track information
- Falls back to FfprobeIntrospector for non-MKV files

## Container Format Mapping

| Extension | Container Format |
|-----------|------------------|
| .mkv | matroska |
| .mp4 | mp4 |
| .m4v | mp4 |
| .avi | avi |
| .webm | webm |
| .mov | quicktime |

## Track Type Mapping

| Source | track_type |
|--------|------------|
| video stream | "video" |
| audio stream | "audio" |
| subtitle stream | "subtitle" |
| attachment | "other" |
| data stream | "other" |

## Language Code Handling

- Uses ISO 639-2 three-letter codes (e.g., "eng", "jpn", "fra")
- Unknown languages return `None`
- "und" (undetermined) is normalized to `None`

## Usage Examples

```python
from pathlib import Path
from video_policy_orchestrator.introspector import StubIntrospector, MediaIntrospectionError

introspector = StubIntrospector()

# Successful introspection
info = introspector.get_file_info(Path("/media/movie.mkv"))
print(info.container_format)  # "matroska"
print(len(info.tracks))       # 0 (stub returns no tracks)

# File not found
try:
    introspector.get_file_info(Path("/nonexistent.mkv"))
except FileNotFoundError as e:
    print(f"File missing: {e}")

# Unsupported format
try:
    introspector.get_file_info(Path("/document.pdf"))
except MediaIntrospectionError as e:
    print(f"Not a media file: {e.reason}")
```

## Testing Contract

Implementations must pass these test scenarios:

```python
def test_existing_mkv_returns_matroska_format(introspector, tmp_path):
    mkv_file = tmp_path / "test.mkv"
    mkv_file.touch()
    info = introspector.get_file_info(mkv_file)
    assert info.container_format == "matroska"

def test_nonexistent_file_raises_file_not_found(introspector):
    with pytest.raises(FileNotFoundError):
        introspector.get_file_info(Path("/does/not/exist.mkv"))

def test_unsupported_extension_raises_introspection_error(introspector, tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.touch()
    with pytest.raises(MediaIntrospectionError):
        introspector.get_file_info(txt_file)

def test_returns_fileinfo_with_correct_path(introspector, tmp_path):
    mp4_file = tmp_path / "test.mp4"
    mp4_file.touch()
    info = introspector.get_file_info(mp4_file)
    assert info.path == mp4_file
```
