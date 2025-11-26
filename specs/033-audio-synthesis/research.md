# Research: Audio Track Synthesis

**Feature**: 033-audio-synthesis
**Date**: 2025-11-26

## FFmpeg Audio Encoding Best Practices

### Decision: Use FFmpeg native encoders with fallback detection

**Rationale**: FFmpeg ships with native encoders for all target codecs (EAC3, AAC, AC3, Opus, FLAC). While external encoders like libfdk_aac may offer marginally better quality, requiring users to compile FFmpeg with non-free codecs creates unnecessary barriers.

**Alternatives Considered**:
- libfdk_aac for AAC: Better quality but requires custom FFmpeg build
- External encoder binaries: More complexity, platform-specific issues

### Encoder Selection by Target Codec

| Target Codec | FFmpeg Encoder | Default Bitrate | Notes |
|--------------|----------------|-----------------|-------|
| EAC3 | `eac3` | 640k (5.1), 384k (stereo) | Native encoder, excellent quality |
| AAC | `aac` | 192k (stereo), 384k (5.1) | Native encoder, good quality |
| AC3 | `ac3` | 448k (5.1), 192k (stereo) | Max 5.1 channels |
| Opus | `libopus` | 128k (stereo), 256k (5.1) | Best compression efficiency |
| FLAC | `flac` | N/A (lossless) | Compression level 8 default |

### Encoder Availability Detection

```bash
# Check encoder availability
ffmpeg -encoders 2>/dev/null | grep -E "^\s*A.{5}\s+(eac3|aac|ac3|libopus|flac)"
```

The system will validate encoder availability at policy load time, failing fast with clear error messages listing required encoders.

---

## Channel Downmix Strategies

### Decision: Use FFmpeg's built-in downmix filters with manual LFE handling

**Rationale**: FFmpeg's `pan` filter provides precise control over channel mapping. Default downmix (automatic) loses LFE content, which is undesirable for movie audio.

**Alternatives Considered**:
- Automatic downmix (`-ac 2`): Loses LFE, less control
- External tools (sox, etc.): Additional dependency

### Downmix Filter Chains

**7.1 → 5.1** (drop rear surrounds, mix into sides):
```
pan=5.1|FL=FL|FR=FR|FC=FC|LFE=LFE|BL=0.707*BL+0.707*SL|BR=0.707*BR+0.707*SR
```

**5.1 → Stereo** (standard downmix with LFE):
```
pan=stereo|FL=FL+0.707*FC+0.707*BL+0.5*LFE|FR=FR+0.707*FC+0.707*BR+0.5*LFE
```

**7.1 → Stereo** (two-stage or direct):
```
pan=stereo|FL=FL+0.707*FC+0.5*SL+0.5*BL+0.5*LFE|FR=FR+0.707*FC+0.5*SR+0.5*BR+0.5*LFE
```

**Stereo → Mono**:
```
pan=mono|c0=0.5*FL+0.5*FR
```

### Channel Layout Detection

FFmpeg reports channel layouts via ffprobe:
```json
{
  "channels": 6,
  "channel_layout": "5.1(side)"
}
```

Normalize layouts: `5.1`, `5.1(side)`, `5.1(back)` all treated as 6-channel surround.

---

## Source Track Selection Algorithm

### Decision: Weighted scoring with ordered preference fallback

**Rationale**: Users specify preferences as an ordered list. The algorithm filters, then scores, then falls back to first audio track if no matches.

**Alternatives Considered**:
- Strict sequential filtering: Too restrictive, often yields no matches
- Fuzzy matching: Too unpredictable for deterministic policy behavior

### Algorithm Steps

1. **Filter by hard constraints**:
   - Must be audio track
   - Must have required minimum channels (if target > source, skip)

2. **Score by preference criteria** (configurable weights):
   - Language match: +100 (exact), +50 (partial/`und`)
   - Non-commentary: +80 (if `not_commentary: true`)
   - Channel count: +10 per channel (if `channels: max`)
   - Codec preference: +20 (if `codec: [lossless]`)

3. **Select highest-scoring track**

4. **Fallback**: If no track scores > 0, use first audio track with warning

### Commentary Detection

Heuristics for `not_commentary: true`:
- Title contains "commentary", "director", "cast"
- Title contains "comm" as standalone word
- Case-insensitive matching

---

## Track Positioning Implementation

### Decision: Position relative to audio tracks only, resolve after all synthesis

**Rationale**: Users think in terms of audio track order (1st audio, 2nd audio), not absolute stream indices which include video and subtitle tracks.

**Alternatives Considered**:
- Absolute stream index: Confusing for users
- Mixed positioning: Overly complex

### Position Values

| Value | Meaning |
|-------|---------|
| `after_source` | Insert immediately after the source track used |
| `end` | Append after all existing audio tracks |
| `N` (integer) | Insert at audio track position N (1-indexed) |

### Resolution Order

When multiple synthesis tracks are defined:
1. Evaluate all `create_if` conditions
2. Select source tracks for each
3. Compute target positions in policy-defined order
4. Adjust indices as tracks are inserted

---

## Atomic File Operations

### Decision: Transcode to temp file, then use mkvmerge for remux

**Rationale**: FFmpeg cannot safely add streams to MKV in-place. The safest approach is:
1. Transcode source audio to temp file (standalone audio)
2. Use mkvmerge to combine original file + new audio track(s)
3. Atomic rename to replace original (with backup)

**Alternatives Considered**:
- FFmpeg single-pass remux: Risk of corruption if interrupted
- Direct MKV stream injection: Not reliably supported

### Cleanup on Cancellation

Signal handler (SIGINT) triggers:
1. Kill FFmpeg subprocess
2. Remove temp audio file(s)
3. Preserve original file (no backup restore needed - original untouched until final swap)

---

## Integration with Existing Conditional System

### Decision: Reuse existing condition syntax for `create_if`

**Rationale**: The conditional policy system (feature 032) provides `exists`, `not`, and comparison operators. Synthesis `create_if` should use the same syntax for consistency.

**Example Mapping**:

```yaml
# Synthesis create_if condition
create_if:
  not:
    exists:
      track_type: audio
      codec: [eac3, ac3]
      channels: { gte: 6 }

# Equivalent to existing condition syntax
when:
  not:
    exists:
      track_type: audio
      filters:
        codec: [eac3, ac3]
        channels:
          gte: 6
```

The synthesis planner will delegate condition evaluation to the existing `policy/conditions.py` module.

---

## Policy Schema Extension

### New Section: `audio_synthesis`

```yaml
audio_synthesis:
  tracks:
    - name: "EAC3 5.1 Compatibility"
      codec: eac3
      channels: 5.1
      bitrate: 640k
      create_if:
        not:
          exists:
            track_type: audio
            codec: [eac3, ac3]
            channels: { gte: 6 }
      source:
        prefer:
          - language: [eng, und]
          - not_commentary: true
          - channels: { max: true }
      title: "Dolby Digital Plus 5.1"
      language: inherit
      position: after_source
```

### Schema Validation

- `codec`: enum of supported codecs
- `channels`: `mono`, `stereo`, `5.1`, `7.1`, or integer
- `bitrate`: string with `k` suffix (parsed to integer)
- `create_if`: existing condition schema
- `source.prefer`: ordered list of preference objects
- `title`: string or `inherit`
- `language`: ISO 639-2/B code or `inherit`
- `position`: `after_source`, `end`, or positive integer

---

## Dry-Run Output Format

### Decision: Structured synthesis plan in existing dry-run format

**Example Output**:
```
Audio Synthesis Plan:
  CREATE "EAC3 5.1 Compatibility"
    Source: #1 truehd 7.1 eng "TrueHD 7.1" (best match: score 190)
    Output: eac3 5.1 640k
    Title: "Dolby Digital Plus 5.1"
    Position: after #1

  SKIP "AAC Stereo"
    Reason: Compatible track exists (#3 aac stereo eng)

Final Audio Track Order:
  #1 [audio] truehd 7.1 eng "TrueHD 7.1" (original)
  #2 [audio] eac3 5.1 eng "Dolby Digital Plus 5.1" [SYNTHESIZED]
  #3 [audio] aac stereo eng "Stereo" (original)
```

---

## Error Handling Strategy

| Error Condition | Handling |
|-----------------|----------|
| Encoder unavailable | Fail fast at policy load with list of required encoders |
| No source track matches | Fallback to first audio track with warning |
| Source has fewer channels than target | Skip synthesis with warning (no upmix) |
| Disk space insufficient | Fail before starting synthesis, cleanup temp files |
| FFmpeg process failure | Cleanup temp files, report error, preserve original |
| User cancellation (Ctrl+C) | Cleanup temp files, preserve original, exit cleanly |

---

## Test Strategy

### Unit Tests
- Source selection scoring algorithm
- Channel layout normalization
- Position resolution with multiple synthesis tracks
- Condition evaluation integration

### Integration Tests
- FFmpeg encoder detection
- Actual transcoding with test audio files
- MKV remuxing with new tracks
- Cancellation and cleanup

### Test Fixtures Required
- MKV with TrueHD 7.1 + AC3 5.1 + AAC stereo
- MKV with multiple languages (eng, spa, fra)
- MKV with commentary track (title contains "Commentary")
- MKV with only stereo audio (no surround)
