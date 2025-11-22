# Transcode Policy Guide

Configure transcoding settings in your policy YAML files to convert video files to target codecs, quality levels, and resolutions.

## Quick Start

Create a policy file with transcode settings:

```yaml
schema_version: 2

transcode:
  target_video_codec: hevc
  target_crf: 20
  max_resolution: 1080p
```

Queue files for transcoding:

```bash
vpo transcode --policy my-policy.yaml /videos/movie.mkv
vpo jobs start
```

## Transcode Settings Reference

### Video Settings

| Setting | Type | Description |
|---------|------|-------------|
| `target_video_codec` | string | Target codec: `hevc`, `h264`, `vp9`, `av1` |
| `target_crf` | int (0-51) | Quality level (lower = better, 18-23 typical) |
| `target_bitrate` | string | Target bitrate: `5M`, `2500k` (overrides CRF) |
| `max_resolution` | string | Scale down to: `480p`, `720p`, `1080p`, `1440p`, `4k`, `8k` |
| `max_width` | int | Maximum width in pixels |
| `max_height` | int | Maximum height in pixels |

### Audio Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `audio_preserve_codecs` | list | `[]` | Codecs to stream-copy (preserve lossless) |
| `audio_transcode_to` | string | `aac` | Target codec for non-preserved tracks |
| `audio_transcode_bitrate` | string | `192k` | Bitrate for transcoded audio |
| `audio_downmix` | string | `null` | Create downmixed track: `stereo`, `5.1` |

### Destination Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `destination` | string | `null` | Template for output path |
| `destination_fallback` | string | `Unknown` | Fallback for missing metadata |

## Video Codec Options

### HEVC/H.265 (Recommended)

Best compression efficiency for modern playback devices:

```yaml
transcode:
  target_video_codec: hevc
  target_crf: 20  # Range 18-24 for good quality
```

### H.264/AVC

Maximum compatibility with older devices:

```yaml
transcode:
  target_video_codec: h264
  target_crf: 18  # Range 17-23 for good quality
```

### VP9

Open format, good for web delivery:

```yaml
transcode:
  target_video_codec: vp9
  target_crf: 30  # VP9 uses different CRF scale
```

### AV1

Best compression, but slow encoding:

```yaml
transcode:
  target_video_codec: av1
  target_crf: 30
```

## Quality Control

### CRF Mode (Recommended)

Constant Rate Factor provides consistent quality across the file:

```yaml
transcode:
  target_video_codec: hevc
  target_crf: 20
```

CRF guidelines for x264/x265:
- 18: Visually lossless
- 20-23: High quality (recommended)
- 24-28: Good quality, smaller files
- 28+: Lower quality, much smaller files

### Bitrate Mode

Fixed bitrate for predictable file sizes:

```yaml
transcode:
  target_video_codec: hevc
  target_bitrate: "5M"  # 5 Mbps
```

Note: CRF and bitrate are mutually exclusive. If both are specified, bitrate takes precedence.

## Resolution Scaling

Scale down videos that exceed a maximum resolution:

```yaml
transcode:
  target_video_codec: hevc
  target_crf: 20
  max_resolution: 1080p
```

Available presets: `480p`, `720p`, `1080p`, `1440p`, `4k`, `8k`

Files smaller than the target resolution are not scaled up.

### Custom Dimensions

For non-standard resolutions:

```yaml
transcode:
  target_video_codec: hevc
  max_width: 1920
  max_height: 800
```

## Audio Preservation

Preserve high-quality audio codecs while transcoding lossy formats:

```yaml
transcode:
  target_video_codec: hevc
  target_crf: 20

  # Preserve lossless audio
  audio_preserve_codecs:
    - truehd      # Dolby TrueHD
    - dts-hd      # DTS-HD Master Audio
    - flac        # FLAC
    - pcm_s16le   # PCM variants
    - pcm_s24le

  # Transcode lossy audio to AAC
  audio_transcode_to: aac
  audio_transcode_bitrate: 192k
```

### Common Audio Codec Names

| Codec | Description |
|-------|-------------|
| `truehd` | Dolby TrueHD |
| `dts-hd` | DTS-HD Master Audio |
| `flac` | FLAC lossless |
| `eac3` | Dolby Digital Plus |
| `ac3` | Dolby Digital |
| `dts` | DTS Core |
| `aac` | Advanced Audio Coding |
| `opus` | Opus |
| `mp3` | MP3 |

### Downmixing

Create an additional stereo track for compatibility:

```yaml
transcode:
  audio_preserve_codecs:
    - truehd
  audio_downmix: stereo  # Add stereo track from surround
```

## Directory Organization

Automatically organize output files based on metadata parsed from filenames:

```yaml
transcode:
  target_video_codec: hevc
  target_crf: 20
  destination: "Processed/{year}/{title}"
  destination_fallback: "Unknown"
```

### Supported Placeholders

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{title}` | Movie or episode title | `The Matrix` |
| `{year}` | Release year | `1999` |
| `{series}` | TV series name | `Breaking Bad` |
| `{season}` | Season number (zero-padded) | `01` |
| `{episode}` | Episode number (zero-padded) | `05` |
| `{resolution}` | Video resolution | `1080p` |
| `{codec}` | Video codec | `x264` |
| `{source}` | Source type | `BluRay` |

### Template Examples

Movies:
```yaml
transcode:
  target_video_codec: hevc
  destination: "Movies/{year}/{title}"
# Output: Movies/1999/The Matrix/The Matrix.mkv
```

TV Shows:
```yaml
transcode:
  target_video_codec: hevc
  destination: "TV/{series}/Season {season}"
# Output: TV/Breaking Bad/Season 01/Episode.mkv
```

## Complete Policy Examples

### High Quality Archive

```yaml
schema_version: 2

transcode:
  target_video_codec: hevc
  target_crf: 18

  audio_preserve_codecs:
    - truehd
    - dts-hd
    - flac
  audio_transcode_to: flac
  audio_transcode_bitrate: 0  # Lossless

  destination: "Archive/{year}/{title}"
```

### Space-Efficient Storage

```yaml
schema_version: 2

transcode:
  target_video_codec: hevc
  target_crf: 24
  max_resolution: 1080p

  audio_transcode_to: aac
  audio_transcode_bitrate: 128k

  destination: "Compressed/{title}"
```

### Device Compatibility

```yaml
schema_version: 2

transcode:
  target_video_codec: h264
  target_crf: 20
  max_resolution: 720p

  audio_transcode_to: aac
  audio_transcode_bitrate: 192k
  audio_downmix: stereo
```

## CLI Options

Override policy settings from the command line:

```bash
# Override codec
vpo transcode --policy base.yaml --codec hevc movie.mkv

# Override quality
vpo transcode --policy base.yaml --crf 22 movie.mkv

# Override resolution
vpo transcode --policy base.yaml --max-resolution 720p movie.mkv

# Override bitrate
vpo transcode --policy base.yaml --bitrate 4M movie.mkv
```

## Dry Run

Preview transcoding without making changes:

```bash
vpo transcode --dry-run --policy my-policy.yaml /videos/

# Output shows:
#   [QUEUE] Movie.mkv: h264 -> hevc, 3840x2160 -> 1920x1080
#           Destination: Processed/2023/Movie/
#   [SKIP] Already.mkv: Already compliant
```

## Related Docs

- [Jobs Guide](jobs.md) - Managing the job queue
- [CLI Usage](cli-usage.md) - Command reference
- [Configuration](configuration.md) - Global settings
