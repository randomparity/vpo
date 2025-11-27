# Data Model: Conditional Video Transcoding

**Date**: 2025-11-26
**Feature**: 034-conditional-video-transcode

## Entity Definitions

### 1. VideoTranscodeConfig

Configuration for video transcoding within a policy. Extends existing `TranscodePolicyConfig`.

```python
@dataclass(frozen=True)
class VideoTranscodeConfig:
    """Video transcoding configuration within a transcode policy."""

    # Target codec
    target_codec: str  # hevc, h264, vp9, av1

    # Skip conditions (optional)
    skip_if: SkipCondition | None = None

    # Quality settings
    quality: QualitySettings | None = None

    # Resolution scaling (optional)
    scaling: ScalingSettings | None = None

    # Hardware acceleration (optional)
    hardware_acceleration: HardwareAccelConfig | None = None
```

**Relationships**:
- Contains one optional `SkipCondition`
- Contains one optional `QualitySettings`
- Contains one optional `ScalingSettings`
- Contains one optional `HardwareAccelConfig`

---

### 2. SkipCondition

Conditions that when ALL are true, skip transcoding for a file.

```python
@dataclass(frozen=True)
class SkipCondition:
    """Conditions for skipping video transcoding (AND logic)."""

    # Codec match - skip if video codec is in this list
    codec_matches: tuple[str, ...] | None = None
    # e.g., ("hevc", "h265", "x265")

    # Resolution within - skip if resolution <= this preset
    resolution_within: str | None = None
    # e.g., "1080p", "720p", "4k"

    # Bitrate under - skip if bitrate < this value
    bitrate_under: str | None = None
    # e.g., "10M", "5000k"
```

**Validation Rules**:
- `codec_matches`: List of valid video codec names (case-insensitive matching)
- `resolution_within`: Must be one of: 480p, 720p, 1080p, 1440p, 4k, 8k
- `bitrate_under`: Must match pattern `^\d+[MmKk]$` (e.g., "10M", "5000k")

**State Transitions**: N/A (immutable configuration)

---

### 3. QualitySettings

Video encoding quality configuration.

```python
@dataclass(frozen=True)
class QualitySettings:
    """Video encoding quality settings."""

    # Quality mode
    mode: QualityMode = QualityMode.CRF
    # CRF, BITRATE, CONSTRAINED_QUALITY

    # CRF value (0-51, lower = better quality)
    crf: int | None = None
    # Defaults applied per codec if not specified

    # Target bitrate (for BITRATE or CONSTRAINED_QUALITY mode)
    bitrate: str | None = None
    # e.g., "5M", "2500k"

    # Min/max bitrate for constrained quality
    min_bitrate: str | None = None
    max_bitrate: str | None = None

    # Encoding preset (speed/quality tradeoff)
    preset: str = "medium"
    # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow

    # Content-specific tune option
    tune: str | None = None
    # film, animation, grain, stillimage, fastdecode, zerolatency

    # Two-pass encoding for accurate bitrate targeting
    two_pass: bool = False


class QualityMode(Enum):
    """Video encoding quality mode."""
    CRF = "crf"
    BITRATE = "bitrate"
    CONSTRAINED_QUALITY = "constrained_quality"
```

**Validation Rules**:
- `crf`: Integer 0-51 (0 = lossless, 51 = worst)
- `preset`: One of the 9 standard preset names
- `tune`: Validated against encoder-supported tunes
- `bitrate`, `min_bitrate`, `max_bitrate`: Must match bitrate pattern

**Codec-Specific CRF Defaults**:
| Codec | Default CRF |
|-------|-------------|
| x264/h264 | 23 |
| x265/hevc | 28 |
| VP9 | 31 |
| AV1 | 30 |

---

### 4. ScalingSettings

Resolution scaling configuration.

```python
@dataclass(frozen=True)
class ScalingSettings:
    """Video resolution scaling settings."""

    # Maximum resolution preset
    max_resolution: str | None = None
    # e.g., "1080p", "720p", "4k"

    # Or explicit max dimensions
    max_width: int | None = None
    max_height: int | None = None

    # Scaling algorithm
    algorithm: ScaleAlgorithm = ScaleAlgorithm.LANCZOS

    # Prevent upscaling smaller content
    upscale: bool = False


class ScaleAlgorithm(Enum):
    """Video scaling algorithm."""
    LANCZOS = "lanczos"
    BICUBIC = "bicubic"
    BILINEAR = "bilinear"
```

**Validation Rules**:
- `max_resolution`: One of: 480p, 720p, 1080p, 1440p, 4k, 8k
- `max_width`, `max_height`: Positive integers if specified
- Either `max_resolution` OR (`max_width`/`max_height`) should be specified, not both
- Aspect ratio always preserved (no stretch/distortion)

**Resolution Preset Dimensions**:
| Preset | Width | Height |
|--------|-------|--------|
| 480p | 854 | 480 |
| 720p | 1280 | 720 |
| 1080p | 1920 | 1080 |
| 1440p | 2560 | 1440 |
| 4k | 3840 | 2160 |
| 8k | 7680 | 4320 |

---

### 5. HardwareAccelConfig

Hardware acceleration configuration.

```python
@dataclass(frozen=True)
class HardwareAccelConfig:
    """Hardware acceleration settings."""

    # Encoder selection
    enabled: HardwareAccelMode = HardwareAccelMode.AUTO
    # AUTO, NVENC, QSV, VAAPI, NONE

    # Fall back to CPU if hardware encoder fails
    fallback_to_cpu: bool = True


class HardwareAccelMode(Enum):
    """Hardware acceleration mode."""
    AUTO = "auto"      # Auto-detect best available
    NVENC = "nvenc"    # Force NVIDIA NVENC
    QSV = "qsv"        # Force Intel Quick Sync
    VAAPI = "vaapi"    # Force VAAPI (Linux)
    NONE = "none"      # Force CPU encoding
```

**Encoder Detection Order** (for AUTO mode):
1. NVENC (hevc_nvenc, h264_nvenc, av1_nvenc)
2. QSV (hevc_qsv, h264_qsv, av1_qsv)
3. VAAPI (hevc_vaapi, h264_vaapi, av1_vaapi)
4. CPU fallback (libx265, libx264, libsvtav1)

---

### 6. AudioTranscodeConfig

Audio handling during video transcoding (extends existing pattern).

```python
@dataclass(frozen=True)
class AudioTranscodeConfig:
    """Audio handling configuration for video transcoding."""

    # Codecs to preserve (stream-copy without re-encoding)
    preserve_codecs: tuple[str, ...] = ("truehd", "dts-hd", "flac", "pcm_s24le")

    # Target codec for non-preserved audio
    transcode_to: str = "aac"

    # Target bitrate for transcoded audio
    transcode_bitrate: str = "192k"
```

**Validation Rules**:
- `preserve_codecs`: List of valid audio codec names
- `transcode_to`: Must be a valid audio codec (aac, ac3, eac3, opus, flac, mp3)
- `transcode_bitrate`: Must match bitrate pattern (e.g., "192k", "256k")

---

### 7. TranscodeResult

Result of transcode operation evaluation (extends Plan).

```python
@dataclass(frozen=True)
class TranscodeResult:
    """Result of transcode operation evaluation."""

    # Skip status
    skipped: bool
    skip_reason: str | None = None  # e.g., "Already compliant: HEVC at 1080p"

    # If not skipped, the planned operation
    video_action: VideoTranscodeAction | None = None
    audio_actions: tuple[AudioTrackPlan, ...] = ()

    # Selected encoder (after hardware detection)
    encoder: str | None = None  # e.g., "hevc_nvenc", "libx265"
    encoder_type: str | None = None  # "hardware" or "software"


@dataclass(frozen=True)
class VideoTranscodeAction:
    """Planned video transcode action."""
    source_codec: str
    target_codec: str
    crf: int | None
    bitrate: str | None
    preset: str
    tune: str | None
    scale_width: int | None
    scale_height: int | None
    scale_algorithm: str | None
```

---

## Entity Relationships

```
PolicySchema (existing)
└── transcode: TranscodePolicyConfig (existing, extended)
    ├── video: VideoTranscodeConfig (NEW)
    │   ├── skip_if: SkipCondition (NEW)
    │   ├── quality: QualitySettings (NEW)
    │   ├── scaling: ScalingSettings (NEW)
    │   └── hardware_acceleration: HardwareAccelConfig (NEW)
    └── audio: AudioTranscodeConfig (NEW, extends existing)

Plan (existing)
└── transcode_result: TranscodeResult (NEW)
    ├── video_action: VideoTranscodeAction (NEW)
    └── audio_actions: tuple[AudioTrackPlan] (existing)

FileInfo (existing)
└── tracks: tuple[TrackInfo] (existing)
    └── Used for skip condition evaluation
```

## YAML Policy Schema

```yaml
# Example policy with all new options
version: 5  # Or 6 if schema version bump needed

transcode:
  video:
    target_codec: hevc

    skip_if:
      codec_matches: [hevc, h265, x265]
      resolution_within: 1080p
      bitrate_under: 10M

    quality:
      mode: crf
      crf: 20
      preset: slow
      tune: film

    scaling:
      max_resolution: 1080p
      algorithm: lanczos
      upscale: false

    hardware_acceleration:
      enabled: auto
      fallback_to_cpu: true

  audio:
    preserve_codecs: [truehd, dts-hd, flac]
    transcode_to: aac
    transcode_bitrate: 192k
```

## Validation Summary

| Field | Type | Valid Values | Default |
|-------|------|--------------|---------|
| video.target_codec | str | hevc, h264, vp9, av1 | required |
| skip_if.codec_matches | list[str] | video codec names | null |
| skip_if.resolution_within | str | 480p-8k presets | null |
| skip_if.bitrate_under | str | \d+[MmKk] pattern | null |
| quality.mode | enum | crf, bitrate, constrained_quality | crf |
| quality.crf | int | 0-51 | codec-specific |
| quality.preset | str | ultrafast-veryslow | medium |
| quality.tune | str | film, animation, etc. | null |
| scaling.max_resolution | str | 480p-8k presets | null |
| scaling.algorithm | enum | lanczos, bicubic, bilinear | lanczos |
| scaling.upscale | bool | true/false | false |
| hw_accel.enabled | enum | auto, nvenc, qsv, vaapi, none | auto |
| hw_accel.fallback_to_cpu | bool | true/false | true |
| audio.preserve_codecs | list[str] | audio codec names | [truehd, dts-hd, flac] |
| audio.transcode_to | str | audio codec name | aac |
| audio.transcode_bitrate | str | bitrate pattern | 192k |
