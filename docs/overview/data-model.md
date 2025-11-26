# Data Model

**Purpose:**
This document describes the canonical data model for media items and tracks in VPO.
It covers the structure of scanned file data, track metadata, and how these are represented in JSON output.

---

## Overview

VPO maintains a database of scanned media files and their tracks. This data model provides a uniform representation regardless of the underlying container format (MKV, MP4, etc.) or the tools used for extraction (ffprobe, mkvmerge).

---

## Media File Structure

Each scanned file is represented with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Absolute path to the file |
| `filename` | string | Base filename (e.g., `movie.mkv`) |
| `directory` | string | Parent directory path |
| `extension` | string | File extension without dot (e.g., `mkv`) |
| `size_bytes` | integer | File size in bytes |
| `modified_at` | string | ISO 8601 timestamp of last file modification |
| `content_hash` | string | Partial content hash for change detection |
| `container_format` | string | Container type (e.g., `matroska`, `mp4`) |
| `scanned_at` | string | ISO 8601 timestamp of last scan |
| `scan_status` | string | Status: `ok`, `error`, or `pending` |
| `scan_error` | string | Error message if `scan_status="error"` |
| `tracks` | array | List of track objects (see below) |

---

## Track Structure

Each track within a file has the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `index` | integer | Zero-based track index within the file |
| `track_type` | string | Type: `video`, `audio`, or `subtitle` |
| `codec` | string | Codec identifier (e.g., `hevc`, `aac`, `subrip`) |
| `language` | string | ISO 639-2 language code (e.g., `eng`, `jpn`) |
| `title` | string | Track label/title |
| `is_default` | boolean | Whether this is the default track for its type |
| `is_forced` | boolean | Whether this track is flagged as forced |

---

## Content Hash Format

The `content_hash` field uses a composite format for efficient change detection:

```text
xxh64:<head_hash>:<tail_hash>:<file_size>
```

- `head_hash`: xxHash64 of the first 64KB of the file
- `tail_hash`: xxHash64 of the last 64KB of the file
- `file_size`: Total file size in bytes

This approach allows quick detection of file changes without hashing the entire file.

---

## Example JSON

A fully scanned media file is represented as:

```json
{
  "path": "/media/movies/movie.mkv",
  "filename": "movie.mkv",
  "directory": "/media/movies",
  "extension": "mkv",
  "size_bytes": 4831838208,
  "modified_at": "2024-01-15T10:30:00Z",
  "content_hash": "xxh64:a1b2c3d4e5f6a7b8:f8e7d6c5b4a39281:4831838208",
  "container_format": "matroska",
  "scanned_at": "2024-01-20T14:00:00Z",
  "scan_status": "ok",
  "tracks": [
    {
      "index": 0,
      "track_type": "video",
      "codec": "hevc",
      "language": null,
      "title": null,
      "is_default": true,
      "is_forced": false
    },
    {
      "index": 1,
      "track_type": "audio",
      "codec": "opus",
      "language": "eng",
      "title": "English Audio",
      "is_default": true,
      "is_forced": false
    },
    {
      "index": 2,
      "track_type": "subtitle",
      "codec": "subrip",
      "language": "eng",
      "title": "English Subtitles",
      "is_default": true,
      "is_forced": false
    }
  ]
}
```

---

## Track Types

VPO recognizes three primary track types:

| Type | Description |
|------|-------------|
| `video` | Video streams (H.264, H.265/HEVC, AV1, etc.) |
| `audio` | Audio streams (AAC, Opus, FLAC, DTS, etc.) |
| `subtitle` | Subtitle tracks (SRT, ASS, PGS, etc.) |

---

## Timestamp Conventions

All timestamps in the data model use:
- **Format**: ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`)
- **Timezone**: UTC (stored with `Z` suffix)
- **Precision**: Second-level

Local time conversion is performed only at the presentation layer (CLI output).

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Architecture Overview](architecture.md)
- [Database Design](../design/design-database.md)
- [Time and Timezones](../internals/time-and-timezones.md) *(planned)*
