# Quickstart: Audio Track Synthesis

**Feature**: 033-audio-synthesis

## Overview

Audio track synthesis allows you to create new audio tracks by transcoding from existing sources in your media files. This is useful for creating compatibility tracks (EAC3 for streaming, AAC for mobile) while preserving original lossless audio.

## Basic Usage

### 1. Simple EAC3 5.1 Compatibility Track

Create an EAC3 5.1 track from any surround source:

```yaml
# compatibility-audio.yaml
version: 5
audio_synthesis:
  tracks:
    - name: "EAC3 5.1"
      codec: eac3
      channels: "5.1"
      bitrate: "640k"
      source:
        prefer:
          - language: eng
          - channels: max
```

Apply to a file:
```bash
vpo apply --policy compatibility-audio.yaml /path/to/movie.mkv
```

### 2. Preview Before Applying

Always preview synthesis operations with dry-run:

```bash
vpo apply --policy compatibility-audio.yaml /path/to/movie.mkv --dry-run
```

Output:
```
Audio Synthesis Plan:
  CREATE "EAC3 5.1"
    Source: #1 truehd 7.1 eng "TrueHD 7.1"
    Output: eac3 5.1 640k
    Position: end

Final Audio Track Order:
  #1 [audio] truehd 7.1 eng "TrueHD 7.1" (original)
  #2 [audio] eac3 5.1 eng "EAC3 5.1" [SYNTHESIZED]
```

### 3. Conditional Creation

Only create tracks if compatible track doesn't exist:

```yaml
audio_synthesis:
  tracks:
    - name: "EAC3 5.1 Compatibility"
      codec: eac3
      channels: "5.1"
      create_if:
        not:
          exists:
            track_type: audio
            codec: [eac3, ac3]
            channels: { gte: 6 }
      source:
        prefer:
          - language: eng
```

### 4. Multiple Synthesis Tracks

Create both surround and stereo compatibility:

```yaml
audio_synthesis:
  tracks:
    - name: "EAC3 5.1"
      codec: eac3
      channels: "5.1"
      bitrate: "640k"
      create_if:
        not:
          exists:
            track_type: audio
            codec: [eac3, ac3]
            channels: { gte: 6 }
      source:
        prefer:
          - language: eng
          - not_commentary: true
          - channels: max
      position: after_source

    - name: "AAC Stereo"
      codec: aac
      channels: stereo
      bitrate: "192k"
      create_if:
        not:
          exists:
            track_type: audio
            channels: { lte: 2 }
      source:
        prefer:
          - language: eng
          - not_commentary: true
      position: end
```

## Source Track Selection

### Language Preference

Prefer English, fall back to undefined:
```yaml
source:
  prefer:
    - language: [eng, und]
```

### Exclude Commentary

Skip commentary tracks:
```yaml
source:
  prefer:
    - language: eng
    - not_commentary: true
```

### Prefer Highest Quality

Select track with most channels:
```yaml
source:
  prefer:
    - language: eng
    - channels: max
```

### Prefer Lossless Codecs

```yaml
source:
  prefer:
    - language: eng
    - codec: [truehd, dts-hd, flac]
```

## Track Positioning

### After Source Track

Place synthesized track immediately after its source:
```yaml
position: after_source
```

### At End

Append after all existing audio tracks (default):
```yaml
position: end
```

### Specific Position

Place at audio track position 2:
```yaml
position: 2
```

## Supported Codecs

| Codec | Best For | Default Bitrate (5.1) |
|-------|----------|----------------------|
| eac3 | Streaming devices | 640k |
| aac | Mobile devices | 384k |
| ac3 | Legacy devices | 448k |
| opus | Modern streaming | 256k |
| flac | Archival (lossless) | N/A |

## Common Patterns

### Plex Optimization

Full compatibility for Plex streaming:

```yaml
audio_synthesis:
  tracks:
    # EAC3 for most streaming clients
    - name: "EAC3 5.1"
      codec: eac3
      channels: "5.1"
      bitrate: "640k"
      create_if:
        not:
          exists:
            track_type: audio
            codec: [eac3, ac3]
            channels: { gte: 6 }
      source:
        prefer:
          - language: eng
          - not_commentary: true
          - channels: max
      title: "Dolby Digital Plus 5.1"
      position: after_source

    # AAC for mobile and web
    - name: "AAC Stereo"
      codec: aac
      channels: stereo
      bitrate: "192k"
      create_if:
        not:
          exists:
            track_type: audio
            channels: { lte: 2 }
      source:
        prefer:
          - language: eng
          - not_commentary: true
      title: "Stereo"
      position: end
```

### Preserve Lossless, Add Lossy

Keep original TrueHD, add AC3 for legacy players:

```yaml
audio_synthesis:
  tracks:
    - name: "AC3 5.1 Legacy"
      codec: ac3
      channels: "5.1"
      bitrate: "448k"
      create_if:
        not:
          exists:
            track_type: audio
            codec: ac3
      source:
        prefer:
          - codec: [truehd, dts-hd]
          - language: eng
      title: "Dolby Digital 5.1"
```

## Error Handling

### No Compatible Source

If no audio track matches source preferences, the first audio track is used with a warning.

### Insufficient Channels

Synthesis is skipped if source has fewer channels than target (no upmixing).

### Missing Encoder

If FFmpeg lacks required encoder, operation fails with clear error message.

## Tips

1. **Always use dry-run first** to preview changes
2. **Use `create_if`** to avoid duplicate tracks on re-runs
3. **Position wisely** - `after_source` keeps related tracks together
4. **Prefer lossless sources** for best quality synthesis
5. **Exclude commentary** with `not_commentary: true`
