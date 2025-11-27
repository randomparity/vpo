# CLI Contract: vpo inspect

**Feature**: 003-media-introspection
**Date**: 2025-11-21

## Command Signature

```
vpo inspect <FILE> [OPTIONS]
```

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| FILE | Path | Yes | Path to the media file to inspect |

## Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --format | -f | Choice | human | Output format: "human" or "json" |
| --help | -h | Flag | - | Show help message |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 20 | File not found |
| 32 | ffprobe not installed |
| 51 | File could not be parsed |

## Output Formats

### Human-Readable (default)

```
File: /path/to/movie.mkv
Container: Matroska
Duration: 01:42:15

Tracks:
  Video:
    #0 [video] h264 1920x1080 @ 23.976fps (default)

  Audio:
    #1 [audio] aac stereo eng "English" (default)
    #2 [audio] ac3 5.1 jpn "Japanese"
    #3 [audio] aac stereo eng "Commentary"

  Subtitles:
    #4 [subtitle] srt eng "English" (default)
    #5 [subtitle] ass jpn "Japanese"
    #6 [subtitle] srt eng "SDH" (forced)
```

### JSON Format (--format json)

```json
{
  "file": "/path/to/movie.mkv",
  "container": "matroska,webm",
  "tracks": [
    {
      "index": 0,
      "type": "video",
      "codec": "h264",
      "language": null,
      "title": null,
      "is_default": true,
      "is_forced": false,
      "width": 1920,
      "height": 1080,
      "frame_rate": "24000/1001"
    },
    {
      "index": 1,
      "type": "audio",
      "codec": "aac",
      "language": "eng",
      "title": "English",
      "is_default": true,
      "is_forced": false,
      "channels": 2,
      "channel_layout": "stereo"
    },
    {
      "index": 4,
      "type": "subtitle",
      "codec": "srt",
      "language": "eng",
      "title": "English",
      "is_default": true,
      "is_forced": false
    }
  ],
  "warnings": []
}
```

## Error Output

Errors are written to stderr.

### File Not Found (exit 20)
```
Error: File not found: /path/to/missing.mkv
```

### ffprobe Not Installed (exit 32)
```
Error: ffprobe is not installed or not in PATH.
Install ffmpeg to use media introspection features.
```

### Parse Error (exit 51)
```
Error: Could not parse file: /path/to/corrupt.mkv
Reason: Invalid container format
```

## Examples

```bash
# Basic usage
vpo inspect movie.mkv

# JSON output for scripting
vpo inspect movie.mkv --format json

# Pipe to jq for processing
vpo inspect movie.mkv -f json | jq '.tracks[] | select(.type == "audio")'
```

## Integration with scan

The `vpo scan` command uses the same introspection internally. The `inspect` command exposes this functionality for individual files without database persistence.
