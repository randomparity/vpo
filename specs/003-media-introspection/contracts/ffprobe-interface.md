# Interface Contract: FFprobeIntrospector

**Feature**: 003-media-introspection
**Date**: 2025-11-21

## Class Definition

```python
class FFprobeIntrospector:
    """ffprobe-based implementation of MediaIntrospector protocol."""

    def __init__(self) -> None:
        """Initialize the introspector.

        Raises:
            MediaIntrospectionError: If ffprobe is not available.
        """

    def get_file_info(self, path: Path) -> FileInfo:
        """Extract metadata from a video file.

        Args:
            path: Path to the video file.

        Returns:
            FileInfo object containing file metadata and track information.

        Raises:
            MediaIntrospectionError: If the file cannot be introspected.
        """

    @staticmethod
    def is_available() -> bool:
        """Check if ffprobe is available on the system.

        Returns:
            True if ffprobe is found in PATH, False otherwise.
        """
```

## Protocol Compliance

Implements `MediaIntrospector` protocol from `vpo.introspector.interface`.

## ffprobe Invocation

```bash
ffprobe -v quiet -print_format json -show_streams -show_format <file>
```

### Expected JSON Structure

```json
{
  "streams": [
    {
      "index": 0,
      "codec_name": "h264",
      "codec_type": "video",
      "width": 1920,
      "height": 1080,
      "r_frame_rate": "24000/1001",
      "disposition": {
        "default": 1,
        "forced": 0
      },
      "tags": {
        "language": "eng",
        "title": "Main Video"
      }
    },
    {
      "index": 1,
      "codec_name": "aac",
      "codec_type": "audio",
      "channels": 2,
      "channel_layout": "stereo",
      "disposition": {
        "default": 1,
        "forced": 0
      },
      "tags": {
        "language": "eng",
        "title": "English"
      }
    }
  ],
  "format": {
    "filename": "/path/to/file.mkv",
    "format_name": "matroska,webm",
    "duration": "6135.123"
  }
}
```

## Field Mapping

| ffprobe Field | TrackInfo Field | Notes |
|---------------|-----------------|-------|
| `streams[].index` | `index` | Direct mapping |
| `streams[].codec_type` | `track_type` | Map to enum values |
| `streams[].codec_name` | `codec` | Direct mapping |
| `streams[].tags.language` | `language` | Default to "und" |
| `streams[].tags.title` | `title` | Optional |
| `streams[].disposition.default` | `is_default` | 1 → True |
| `streams[].disposition.forced` | `is_forced` | 1 → True |
| `streams[].channels` | `channels` | Audio only |
| `streams[].channel_layout` | - | Used to derive channel_layout label |
| `streams[].width` | `width` | Video only |
| `streams[].height` | `height` | Video only |
| `streams[].r_frame_rate` | `frame_rate` | Video only, fallback to avg_frame_rate |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| File not found | Raise `MediaIntrospectionError("File not found: {path}")` |
| ffprobe not in PATH | Raise `MediaIntrospectionError("ffprobe not available")` |
| ffprobe returns non-zero | Raise `MediaIntrospectionError("ffprobe failed: {stderr}")` |
| Invalid JSON output | Raise `MediaIntrospectionError("Invalid ffprobe output")` |
| Missing stream fields | Use None/default values, add warning |
| No streams in file | Return FileInfo with empty tracks list, add warning |

## Thread Safety

FFprobeIntrospector instances are stateless and thread-safe. Multiple calls can be made concurrently.
