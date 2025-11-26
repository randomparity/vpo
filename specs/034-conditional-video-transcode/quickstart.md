# Quickstart: Conditional Video Transcoding

**Date**: 2025-11-26
**Feature**: 034-conditional-video-transcode

## Overview

This feature adds conditional skip logic and enhanced quality settings to VPO's video transcoding. You can:

- Skip transcoding for files that already meet your requirements
- Configure CRF or bitrate-based quality settings
- Set encoding presets and tune options
- Downscale resolution while preserving aspect ratio
- Use hardware acceleration automatically
- Preserve lossless audio during video-only transcoding

## Quick Examples

### 1. Skip Already-Compliant HEVC Files

```yaml
# my-policy.yaml
version: 5
transcode:
  video:
    target_codec: hevc
    skip_if:
      codec_matches: [hevc, h265, x265]
      resolution_within: 1080p
```

```bash
# Apply to a file (dry-run first)
vpo apply --policy my-policy.yaml /path/to/video.mkv --dry-run

# Output: "Skipping video transcode - already compliant"
```

### 2. High Quality HEVC with Hardware Acceleration

```yaml
version: 5
transcode:
  video:
    target_codec: hevc
    quality:
      mode: crf
      crf: 20
      preset: slow
      tune: film
    hardware_acceleration:
      enabled: auto
      fallback_to_cpu: true
  audio:
    preserve_codecs: [truehd, dts-hd, flac]
    transcode_to: aac
    transcode_bitrate: 192k
```

### 3. Downscale 4K to 1080p

```yaml
version: 5
transcode:
  video:
    target_codec: hevc
    skip_if:
      codec_matches: [hevc]
      resolution_within: 1080p
    quality:
      mode: crf
      crf: 22
      preset: medium
    scaling:
      max_resolution: 1080p
      algorithm: lanczos
      upscale: false
```

### 4. Streaming-Ready with Target Bitrate

```yaml
version: 5
transcode:
  video:
    target_codec: h264
    quality:
      mode: bitrate
      bitrate: 5M
      preset: fast
    scaling:
      max_resolution: 1080p
```

## CLI Usage

```bash
# Dry-run to preview changes
vpo apply --policy transcode-hevc.yaml /path/to/video.mkv --dry-run

# Apply the transcode (creates backup)
vpo apply --policy transcode-hevc.yaml /path/to/video.mkv

# Check hardware encoder detection
vpo doctor --check encoders
```

## Quality Settings Reference

### CRF Values (lower = better quality, larger files)

| Quality | x264 | x265 | VP9 | Description |
|---------|------|------|-----|-------------|
| Visually lossless | 18 | 20 | 15 | Near-transparent, large files |
| High quality | 20 | 22 | 20 | Excellent quality |
| Balanced | 23 | 28 | 31 | Good quality/size tradeoff |
| Efficient | 26 | 32 | 35 | Smaller files, visible quality loss |

### Presets (slower = better compression)

| Preset | Speed | File Size | Use Case |
|--------|-------|-----------|----------|
| ultrafast | Fastest | Largest | Quick preview |
| fast | Fast | Large | Daily encoding |
| medium | Balanced | Medium | **Default** |
| slow | Slow | Small | Archival quality |
| veryslow | Slowest | Smallest | Maximum compression |

### Tune Options

| Tune | Best For |
|------|----------|
| film | Live action movies |
| animation | Animated content |
| grain | Preserve film grain |
| stillimage | Slideshows |
| fastdecode | Low-power playback |
| zerolatency | Streaming/real-time |

## Hardware Acceleration

The system auto-detects available hardware encoders:

1. **NVENC** (NVIDIA GPUs) - Fastest, excellent quality
2. **QSV** (Intel integrated graphics) - Good speed/quality
3. **VAAPI** (Linux AMD/Intel) - Broad compatibility
4. **CPU** (fallback) - Always available

Check detection:
```bash
vpo doctor --check encoders
# Output:
# Hardware encoders:
#   - hevc_nvenc (NVIDIA NVENC) ✓
#   - hevc_qsv (Intel QSV) ✗
#   - hevc_vaapi (VAAPI) ✓
# Selected: hevc_nvenc
```

## Audio Preservation

Preserve lossless audio while transcoding video:

```yaml
audio:
  preserve_codecs: [truehd, dts-hd, flac, pcm_s24le]
  transcode_to: aac
  transcode_bitrate: 192k
```

This stream-copies lossless tracks and transcodes lossy tracks to AAC.

## Testing Your Policy

1. **Validate syntax**:
   ```bash
   vpo validate --policy my-policy.yaml
   ```

2. **Dry-run on sample file**:
   ```bash
   vpo apply --policy my-policy.yaml sample.mkv --dry-run
   ```

3. **Check what would be skipped**:
   ```bash
   vpo apply --policy my-policy.yaml /library/ --dry-run | grep "Skipping"
   ```

## Common Patterns

### Archive Quality (preserve originals)
```yaml
quality:
  mode: crf
  crf: 18
  preset: slow
```

### Space Saving (good enough quality)
```yaml
quality:
  mode: crf
  crf: 28
  preset: medium
scaling:
  max_resolution: 1080p
```

### Streaming Prep (predictable size)
```yaml
quality:
  mode: bitrate
  bitrate: 5M
  preset: fast
```

### Maximum Compression
```yaml
quality:
  mode: constrained_quality
  crf: 26
  max_bitrate: 8M
  preset: veryslow
```
