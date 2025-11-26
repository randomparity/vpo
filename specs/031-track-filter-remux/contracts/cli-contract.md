# CLI Contract: Track Filtering & Container Remux

**Feature**: 031-track-filter-remux
**Date**: 2025-11-25

## Command: `vpo apply`

### Existing Behavior (unchanged)

```bash
vpo apply --policy <path> <file_or_directory> [options]
```

### Enhanced Options (V3)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--policy` | PATH | Required | Path to policy YAML file |
| `--dry-run` | FLAG | False | Preview changes without applying |
| `--keep-backup` | FLAG | True | Keep backup file after successful operation |
| `--json` | FLAG | False | Output in JSON format (for scripting) |
| `--verbose` | FLAG | False | Show detailed track information |

### Dry-Run Output Format

#### Human-Readable (default)

```
Policy: /path/to/policy.yaml (v3)
Target: Movie.Name.2023.mkv

Track Dispositions:
  KEEP   #0 [video] hevc 1920x1080
  KEEP   #1 [audio] truehd 7.1 eng "TrueHD English"
  REMOVE #2 [audio] ac3 5.1 fra "French" (language not in keep list)
  REMOVE #3 [audio] ac3 5.1 spa "Spanish" (language not in keep list)
  KEEP   #4 [subtitle] subrip eng "English"
  REMOVE #5 [subtitle] subrip fra "French" (language not in keep list)
  KEEP   #6 [subtitle] subrip eng "English (Forced)" (forced subtitle preserved)
  REMOVE #7 [attachment] font/ttf "DejaVuSans.ttf" (attachment removal requested)

Container: mkv → mkv (no change)

Summary: 4 tracks kept, 4 tracks removed
```

#### JSON Format (`--json`)

```json
{
  "policy_path": "/path/to/policy.yaml",
  "policy_version": 3,
  "target_path": "/path/to/Movie.Name.2023.mkv",
  "container_change": null,
  "track_dispositions": [
    {
      "track_index": 0,
      "track_type": "video",
      "codec": "hevc",
      "language": null,
      "title": null,
      "resolution": "1920x1080",
      "channels": null,
      "action": "KEEP",
      "reason": "video tracks always kept"
    },
    {
      "track_index": 1,
      "track_type": "audio",
      "codec": "truehd",
      "language": "eng",
      "title": "TrueHD English",
      "resolution": null,
      "channels": 8,
      "action": "KEEP",
      "reason": "language in keep list"
    },
    {
      "track_index": 2,
      "track_type": "audio",
      "codec": "ac3",
      "language": "fra",
      "title": "French",
      "resolution": null,
      "channels": 6,
      "action": "REMOVE",
      "reason": "language not in keep list"
    }
  ],
  "summary": {
    "tracks_kept": 4,
    "tracks_removed": 4,
    "requires_remux": true
  }
}
```

### Error Responses

#### Insufficient Tracks Error

```
Error: Cannot apply policy - would leave 0 audio tracks (minimum: 1)

Policy requires: [eng, und]
File contains: [fra, spa]

Suggestions:
  - Add 'fra' or 'spa' to audio_filter.languages
  - Set audio_filter.fallback.mode to 'keep_first' or 'keep_all'
  - Use --dry-run to preview changes first
```

#### Incompatible Codec Error

```
Error: Cannot convert to MP4 - incompatible codecs found

Incompatible tracks:
  #1 [audio] truehd - TrueHD not supported in MP4
  #5 [subtitle] hdmv_pgs_subtitle - PGS subtitles not supported in MP4

Options:
  - Set container.on_incompatible_codec: skip (skip this file)
  - Set container.on_incompatible_codec: transcode (requires transcode config)
  - Use container.target: mkv (supports all codecs)
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Policy validation error |
| 3 | Insufficient tracks error |
| 4 | Incompatible codec error |
| 5 | File not found |
| 6 | Disk space insufficient |

---

## Example Usage

### Remove non-English audio tracks

```yaml
# policy.yaml
schema_version: 3
audio_filter:
  languages: [eng, und]
  fallback:
    mode: keep_first
```

```bash
vpo apply --policy policy.yaml --dry-run /media/movies/
```

### Convert to MKV with track filtering

```yaml
# policy.yaml
schema_version: 3
audio_filter:
  languages: [eng, jpn]
subtitle_filter:
  languages: [eng]
  preserve_forced: true
container:
  target: mkv
```

```bash
vpo apply --policy policy.yaml /media/anime/*.avi
```

### Remove attachments with warning

```yaml
# policy.yaml
schema_version: 3
attachment_filter:
  remove_all: true
```

```bash
vpo apply --policy policy.yaml --dry-run movie.mkv
# Warning: Removing fonts may affect subtitle rendering for tracks: #4, #5
```
