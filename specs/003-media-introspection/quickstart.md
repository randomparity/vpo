# Quickstart: Media Introspection & Track Modeling

**Feature**: 003-media-introspection
**Date**: 2025-11-21

## Prerequisites

1. **ffprobe**: Must be installed and in PATH
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows (via chocolatey)
   choco install ffmpeg
   ```

2. **VPO installed**:
   ```bash
   uv pip install -e ".[dev]"
   ```

## Quick Usage

### Inspect a Single File

```bash
# Human-readable output
vpo inspect movie.mkv

# JSON output for scripting
vpo inspect movie.mkv --format json
```

### Scan a Library (with track extraction)

```bash
# Scan directory and persist tracks to database
vpo scan /path/to/videos
```

## Example Output

```
$ vpo inspect sample.mkv

File: sample.mkv
Container: Matroska

Tracks:
  Video:
    #0 [video] h264 1920x1080 @ 23.976fps (default)

  Audio:
    #1 [audio] aac stereo eng "Main Audio" (default)
    #2 [audio] ac3 5.1 jpn "Japanese Dub"

  Subtitles:
    #3 [subtitle] srt eng "English"
    #4 [subtitle] ass jpn "Japanese"
```

## Using the Python API

```python
from pathlib import Path
from vpo.introspector.ffprobe import FFprobeIntrospector

# Create introspector (checks ffprobe availability)
introspector = FFprobeIntrospector()

# Get file info with tracks
file_info = introspector.get_file_info(Path("movie.mkv"))

# Access tracks
for track in file_info.tracks:
    print(f"Track {track.index}: {track.track_type} - {track.codec}")

    if track.track_type == "video":
        print(f"  Resolution: {track.width}x{track.height}")
        print(f"  Frame rate: {track.frame_rate}")

    if track.track_type == "audio":
        print(f"  Channels: {track.channel_layout}")
        print(f"  Language: {track.language}")
```

## Database Schema

After scanning, track data is stored in `~/.vpo/library.db`:

```sql
-- Query tracks for a file
SELECT t.track_index, t.track_type, t.codec, t.language, t.title
FROM tracks t
JOIN files f ON t.file_id = f.id
WHERE f.path = '/path/to/movie.mkv'
ORDER BY t.track_index;
```

## Error Handling

```python
from vpo.introspector.interface import MediaIntrospectionError
from vpo.introspector.ffprobe import FFprobeIntrospector

try:
    introspector = FFprobeIntrospector()
    info = introspector.get_file_info(Path("movie.mkv"))
except MediaIntrospectionError as e:
    print(f"Introspection failed: {e}")
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run only introspector tests
uv run pytest tests/unit/test_ffprobe_introspector.py

# Run with verbose output
uv run pytest -v tests/
```

## Test Fixtures

Test fixtures are JSON files containing recorded ffprobe output:

- `tests/fixtures/ffprobe/simple_single_track.json` - Basic video with 1 video + 1 audio track
- `tests/fixtures/ffprobe/multi_audio.json` - Video with multiple audio tracks (different languages)
- `tests/fixtures/ffprobe/subtitle_heavy.json` - Video with many subtitle tracks

Use fixtures in tests:

```python
import json
from pathlib import Path

def load_fixture(name: str) -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "ffprobe" / f"{name}.json"
    return json.loads(fixture_path.read_text())
```
