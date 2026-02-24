# Transcode Policy Guide

Configure transcoding settings in your policy YAML files to convert video files to target codecs, quality levels, and resolutions.

## Quick Start

Create a policy file with transcode settings:

```yaml
schema_version: 13
phases:
  - name: transcode
    transcode:
      video:
        target_codec: hevc
        quality:
          mode: crf
          crf: 20
        scaling:
          max_resolution: 1080p
```

Process files with transcode policy:

```bash
vpo process --policy my-policy.yaml /videos/movie.mkv
```

## Transcode Settings Reference

### Video Settings

| Setting | Type | Description |
|---------|------|-------------|
| `transcode.video.target_codec` | string | Target codec: `hevc`, `h264`, `vp9`, `av1` |
| `transcode.video.quality.crf` | int (0-51) | Quality level (lower = better, 18-23 typical) |
| `transcode.video.quality.mode` | string | `crf` or `cbr` |
| `transcode.video.quality.target_bitrate` | string | Target bitrate: `5M`, `2500k` (CBR mode) |
| `transcode.video.scaling.max_resolution` | string | Scale down to: `480p`, `720p`, `1080p`, `1440p`, `4k`, `8k` |

### Audio Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `transcode.audio.preserve_codecs` | list | `[]` | Codecs to stream-copy (preserve lossless) |
| `transcode.audio.transcode_to` | string | `aac` | Target codec for non-preserved tracks |
| `transcode.audio.transcode_bitrate` | string | `192k` | Bitrate for transcoded audio |

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
schema_version: 13
phases:
  - name: archive
    transcode:
      video:
        target_codec: hevc
        quality:
          mode: crf
          crf: 18
      audio:
        preserve_codecs: [truehd, dts-hd, flac]
        transcode_to: flac
```

### Space-Efficient Storage

```yaml
schema_version: 13
phases:
  - name: compress
    transcode:
      video:
        target_codec: hevc
        quality:
          mode: crf
          crf: 24
        scaling:
          max_resolution: 1080p
      audio:
        transcode_to: aac
        transcode_bitrate: 128k
```

### Device Compatibility

```yaml
schema_version: 13
phases:
  - name: convert
    transcode:
      video:
        target_codec: h264
        quality:
          mode: crf
          crf: 20
        scaling:
          max_resolution: 720p
      audio:
        transcode_to: aac
        transcode_bitrate: 192k
```

## CLI Options

Override policy settings from the command line:

```bash
# Override codec
vpo process --policy base.yaml --codec hevc movie.mkv

# Override quality
vpo process --policy base.yaml --crf 22 movie.mkv

# Override resolution
vpo process --policy base.yaml --max-resolution 720p movie.mkv

# Override bitrate
vpo process --policy base.yaml --bitrate 4M movie.mkv
```

## Dry Run

Preview transcoding without making changes:

```bash
vpo process --dry-run --policy my-policy.yaml /videos/

# Output shows:
#   [PLAN] Movie.mkv: h264 -> hevc, 3840x2160 -> 1920x1080
#           Destination: Processed/2023/Movie/
#   [SKIP] Already.mkv: Already compliant
```

## Conditional Transcoding

VPO supports conditional transcoding with skip conditions, advanced quality controls, and hardware acceleration support.

### Skip Conditions

Skip transcoding for files that already meet your requirements:

```yaml
schema_version: 13
phases:
  - name: transcode
    transcode:
      video:
        target_codec: hevc

        # Skip if ALL conditions are met
        skip_if:
          codec_matches:       # Already using target codec
            - hevc
            - h265
          resolution_within: 1080p  # Resolution at or below threshold
          bitrate_under: 15M   # Bitrate below threshold

        quality:
          mode: crf
          crf: 20
```

**Skip condition behavior:**
- All conditions must be met (AND logic)
- Unspecified conditions are always satisfied
- Helps avoid re-encoding compliant files

### Quality Settings (V6)

Three quality control modes are available:

#### CRF Mode (Recommended)

```yaml
transcode:
  video:
    quality:
      mode: crf
      crf: 20
      preset: medium    # Options: ultrafast, faster, fast, medium, slow, slower, veryslow
      tune: film        # Options: film, animation, grain, stillimage, fastdecode
```

#### Bitrate Mode

```yaml
transcode:
  video:
    quality:
      mode: bitrate
      bitrate: 5M
      two_pass: true    # Higher quality but slower
```

#### Constrained Quality Mode

CRF with maximum bitrate cap:

```yaml
transcode:
  video:
    quality:
      mode: constrained_quality
      crf: 20
      max_bitrate: 10M  # Cap bitrate peaks
```

### Hardware Acceleration

Configure GPU encoding:

```yaml
transcode:
  video:
    hardware_acceleration:
      enabled: auto      # auto, nvenc, qsv, vaapi, none
      fallback_to_cpu: true  # Fall back if HW unavailable
```

**Hardware modes:**
- `auto`: Detect available hardware, prefer NVENC > QSV > VAAPI
- `nvenc`: NVIDIA NVENC (requires NVIDIA GPU)
- `qsv`: Intel Quick Sync Video (requires Intel CPU/GPU)
- `vaapi`: Video Acceleration API (Linux, various GPUs)
- `none`: Force software encoding

### Scaling Settings (V6)

Advanced scaling options:

```yaml
transcode:
  video:
    scaling:
      max_resolution: 1080p
      algorithm: lanczos  # Options: bilinear, bicubic, lanczos, spline
      upscale: false      # Never upscale smaller content
```

### Audio Settings (V6)

Restructured audio configuration:

```yaml
transcode:
  audio:
    preserve_codecs:
      - truehd
      - dts-hd
      - flac
    transcode_to: aac
    transcode_bitrate: 192k
```

### Complete Transcode Example

```yaml
schema_version: 13
config:
  on_error: skip

phases:
  - name: transcode
    # Skip if already HEVC under thresholds
    skip_when:
      video_codec: [hevc, h265]
      resolution_under: 1080p
    transcode:
      video:
        target_codec: hevc

        skip_if:
          codec_matches: [hevc, h265]
          resolution_within: 1080p
          bitrate_under: 15M

        quality:
          mode: crf
          crf: 20
          preset: medium
          tune: film

        scaling:
          max_resolution: 1080p
          algorithm: lanczos

        hardware_acceleration:
          enabled: auto
          fallback_to_cpu: true

      audio:
        preserve_codecs: [truehd, dts-hd, flac]
        transcode_to: aac
        transcode_bitrate: 192k
```

### Edge Case Warnings

VPO detects and warns about these conditions:

- **VFR content**: Variable frame rate may cause playback issues
- **Missing bitrate**: Estimates from file size when metadata unavailable
- **Multiple video streams**: Uses first/default stream, warns about others
- **HDR content**: Warns when scaling may affect HDR quality

## Related docs

- [Jobs Guide](jobs.md) - Managing the job queue
- [CLI Usage](cli-usage.md) - Command reference
- [Configuration](configuration.md) - Global settings
