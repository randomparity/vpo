# Research: Conditional Video Transcoding

**Date**: 2025-11-26
**Feature**: 034-conditional-video-transcode

## Research Topics

### 1. Hardware Acceleration Detection

**Decision**: Use ffmpeg encoder enumeration with LRU caching for hardware encoder detection

**Rationale**:
- VPO already has encoder detection patterns in `tools/detection.py` and `policy/synthesis/encoders.py`
- Single ffmpeg call (`ffmpeg -encoders`) provides all available encoders
- LRU caching ensures detection only runs once per session
- Pattern matches existing codebase conventions

**Alternatives Considered**:
- Runtime probing each encoder (slower, may cause ffmpeg warnings)
- Hardware-specific APIs (nvidia-smi, vainfo) - requires additional dependencies
- Configuration file listing available encoders - requires manual maintenance

**Detection Command**:
```bash
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E "hevc_nvenc|hevc_qsv|hevc_vaapi"
```

**Encoder Priority Order**:
1. NVENC (fastest, widely available on NVIDIA GPUs)
2. QSV (Intel integrated GPUs, good quality)
3. VAAPI (Linux generic, works with AMD/Intel)
4. CPU (libx265/libx264 - always available fallback)

---

### 2. Skip Condition Evaluation

**Decision**: Implement skip conditions as a pre-execution check in TranscodeExecutor using existing file metadata

**Rationale**:
- File metadata (codec, resolution, bitrate) already extracted by ffprobe introspection
- TrackInfo dataclass contains all required fields
- Evaluation can occur before any ffmpeg process starts
- Matches Sprint 2 conditional policy evaluation pattern

**Alternatives Considered**:
- Evaluate in policy schema loading (too early, file data not yet available)
- Evaluate in job queue (wrong layer of abstraction)
- Evaluate during ffmpeg command building (too late for skip decision)

**Skip Condition Logic**:
```python
def should_skip_transcode(file_info: FileInfo, skip_if: SkipCondition) -> bool:
    video_track = get_primary_video_track(file_info)

    # All conditions must pass (AND logic)
    if skip_if.codec_matches and video_track.codec not in skip_if.codec_matches:
        return False
    if skip_if.resolution_within and not resolution_within(video_track, skip_if.resolution_within):
        return False
    if skip_if.bitrate_under and video_track.bitrate > parse_bitrate(skip_if.bitrate_under):
        return False

    return True
```

---

### 3. CRF vs Bitrate Quality Modes

**Decision**: Support three quality modes: CRF (default), bitrate, and constrained_quality

**Rationale**:
- CRF is industry standard for archival quality (variable bitrate based on content complexity)
- Bitrate mode needed for streaming preparation (predictable file sizes)
- Constrained quality (CRF with max bitrate) provides best of both worlds
- All three modes are well-supported by ffmpeg

**Codec-Specific CRF Defaults**:
| Codec | Visually Lossless | Balanced (Default) | Efficient |
|-------|-------------------|-------------------|-----------|
| x264 | 18 | 23 | 26 |
| x265 | 20 | 28 | 32 |
| VP9 | 15 | 31 | 35 |
| AV1 | 20 | 30 | 35 |

**FFmpeg Quality Flags**:
```bash
# CRF mode
-crf 23

# Bitrate mode
-b:v 5M

# Constrained quality (CRF with max bitrate)
-crf 23 -maxrate 10M -bufsize 20M
```

---

### 4. Preset Mapping Across Encoders

**Decision**: Use standard preset names (ultrafast to veryslow) with encoder-specific mapping

**Rationale**:
- Consistent user-facing API across all codecs
- Internal mapping handles encoder differences
- VP9 uses numeric cpu-used values (0-8) but presents as preset names

**Preset Mappings**:
| Preset | x264/x265 | NVENC | QSV | VP9 (cpu-used) |
|--------|-----------|-------|-----|----------------|
| ultrafast | ultrafast | p1 | veryfast | 8 |
| superfast | superfast | p2 | faster | 7 |
| veryfast | veryfast | p3 | fast | 6 |
| faster | faster | p4 | medium | 5 |
| fast | fast | p4 | medium | 4 |
| medium | medium | p5 | slow | 3 |
| slow | slow | p6 | slower | 2 |
| slower | slower | p7 | veryslow | 1 |
| veryslow | veryslow | p7 | veryslow | 0 |

---

### 5. Resolution Scaling Implementation

**Decision**: Use ffmpeg scale filter with Lanczos algorithm as default

**Rationale**:
- Lanczos provides excellent quality for downscaling
- Scale filter is universally supported across all ffmpeg builds
- Aspect ratio preservation via -1 dimension (e.g., `scale=1920:-1`)

**Resolution Preset Mapping** (already exists in codebase):
```python
RESOLUTION_MAP = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
    "8k": (7680, 4320),
}
```

**Scaling Algorithm FFmpeg Flags**:
```bash
# Lanczos (default, best quality for downscaling)
-vf "scale=1920:-1:flags=lanczos"

# Bicubic (good quality, faster)
-vf "scale=1920:-1:flags=bicubic"

# Bilinear (fast, acceptable quality)
-vf "scale=1920:-1:flags=bilinear"
```

**Aspect Ratio Preservation**:
- Use -1 for auto-calculated dimension: `scale=1920:-1` (keeps aspect ratio)
- For non-standard aspects, use -2 to ensure even dimensions: `scale=1920:-2`

---

### 6. Audio Preservation Strategy

**Decision**: Extend existing audio codec planning with explicit preserve_codecs list

**Rationale**:
- TranscodeExecutor already has AudioTrackPlan with COPY/TRANSCODE actions
- Adding preserve_codecs list allows user to specify which codecs to stream-copy
- Non-preserved codecs get transcoded to target (AAC default)

**Existing Audio Planning** (from `policy/transcode.py`):
```python
@dataclass
class AudioTrackPlan:
    track_index: int
    stream_index: int
    codec: str | None
    action: AudioAction  # COPY, TRANSCODE, REMOVE
    target_codec: str | None
    target_bitrate: str | None
```

**Preservation Logic**:
```python
def plan_audio_track(track: TrackInfo, settings: AudioSettings) -> AudioTrackPlan:
    if track.codec in settings.preserve_codecs:
        return AudioTrackPlan(action=AudioAction.COPY, ...)
    elif settings.transcode_to:
        return AudioTrackPlan(
            action=AudioAction.TRANSCODE,
            target_codec=settings.transcode_to,
            target_bitrate=settings.transcode_bitrate,
        )
    else:
        return AudioTrackPlan(action=AudioAction.COPY, ...)  # Default: copy
```

---

### 7. Output Handling (Temp-Then-Replace)

**Decision**: Write to temp file in same directory, atomic move on success

**Rationale**:
- Existing pattern used by MkvmergeExecutor and FFmpegRemuxExecutor
- Same-directory temp ensures atomic rename (same filesystem)
- Preserves original until success confirmed
- Cleanup on failure automatic

**Implementation Pattern** (from existing executors):
```python
temp_output = output_path.with_suffix(f".vpo_temp_{uuid4().hex[:8]}.mkv")
try:
    run_ffmpeg(input_path, temp_output, ...)
    verify_output(temp_output)
    temp_output.rename(output_path)  # Atomic on same filesystem
except Exception:
    temp_output.unlink(missing_ok=True)
    raise
```

---

### 8. Progress Reporting Integration

**Decision**: Use existing FFmpegProgress dataclass and progress callback pattern

**Rationale**:
- TranscodeExecutor already supports `progress_callback: Callable[[FFmpegProgress], None]`
- FFmpegProgress already parses frame, fps, time, speed from ffmpeg stderr
- Job system already stores progress_percent and progress_json

**Existing FFmpegProgress Fields**:
```python
@dataclass
class FFmpegProgress:
    frame: int | None
    fps: float | None
    bitrate: str | None
    out_time_us: int | None
    speed: str | None

    def get_percent(self, duration_seconds: float) -> float
```

**Progress Update Flow**:
1. FFmpeg outputs progress to stderr (`-stats_period 1`)
2. TranscodeExecutor parses stderr in real-time
3. Calls progress_callback with FFmpegProgress
4. Job system updates progress_percent in database
5. CLI/Web UI polls job status for display

---

## Summary of Decisions

| Topic | Decision | Key Rationale |
|-------|----------|---------------|
| HW Acceleration | Enumerate via `ffmpeg -encoders`, priority: NVENC > QSV > VAAPI > CPU | Matches existing pattern, single query |
| Skip Conditions | Pre-execution check using FileInfo metadata | File data available, allows early skip |
| Quality Modes | CRF (default), bitrate, constrained_quality | Industry standard, covers all use cases |
| Presets | Standard names with encoder-specific mapping | Consistent API, handles differences internally |
| Scaling | Lanczos default, aspect ratio preserved | Best quality, existing resolution map |
| Audio | Preserve_codecs list, transcode others to target | Extends existing AudioTrackPlan pattern |
| Output | Temp-then-replace with atomic move | Existing pattern, safe and reliable |
| Progress | Existing FFmpegProgress and callback | Already implemented, just needs wiring |
