# Data Model: V9 Policy Editor GUI

**Phase 1 Output** | **Date**: 2025-11-30

## Overview

This document describes the data structures used in the policy editor GUI, both for API request/response payloads and internal representation.

## Core Entities

### PolicyEditorData

The complete policy data structure sent to/from the API.

```python
@dataclass
class PolicyEditorData:
    """Complete policy data for editor API."""

    # Metadata (read-only in editor)
    name: str                          # Policy filename (without .yaml)
    schema_version: int                # 1-10
    last_modified: str                 # ISO 8601 timestamp

    # V1-2 Core fields
    track_order: list[str]             # ["video", "audio_main", ...]
    audio_language_preference: list[str]   # ["eng", "und"]
    subtitle_language_preference: list[str] # ["eng", "und"]
    commentary_patterns: list[str]     # ["commentary", "director"]
    default_flags: DefaultFlagsData
    transcode: TranscodeLegacyData | None  # V1-5 flat format
    transcription: TranscriptionData | None

    # V3 Track filtering
    audio_filter: AudioFilterData | None
    subtitle_filter: SubtitleFilterData | None
    attachment_filter: AttachmentFilterData | None
    container: ContainerData | None

    # V4 Conditional rules
    conditional: list[ConditionalRuleData] | None

    # V5 Audio synthesis
    audio_synthesis: AudioSynthesisData | None

    # V6 Transcode (new format)
    transcode_v6: TranscodeV6Data | None

    # V9 Workflow
    workflow: WorkflowData | None
```

### DefaultFlagsData

```python
@dataclass
class DefaultFlagsData:
    """Default flag settings."""
    set_first_video_default: bool = True
    set_preferred_audio_default: bool = True
    set_preferred_subtitle_default: bool = False
    clear_other_defaults: bool = True
    set_subtitle_default_when_audio_differs: bool = False
```

### V3 Track Filtering Entities

```python
@dataclass
class AudioFilterData:
    """Audio track filter configuration."""
    languages: list[str]                # Required: ["eng", "jpn"]
    fallback_mode: str | None = None    # "content_language", "keep_all", "keep_first", "error"
    minimum: int = 1
    # V10 fields
    keep_music_tracks: bool = True
    exclude_music_from_language_filter: bool = True
    keep_sfx_tracks: bool = True
    exclude_sfx_from_language_filter: bool = True
    keep_non_speech_tracks: bool = True
    exclude_non_speech_from_language_filter: bool = True

@dataclass
class SubtitleFilterData:
    """Subtitle track filter configuration."""
    languages: list[str] | None = None
    preserve_forced: bool = False
    remove_all: bool = False

@dataclass
class AttachmentFilterData:
    """Attachment filter configuration."""
    remove_all: bool = False

@dataclass
class ContainerData:
    """Container format configuration."""
    target: str                    # "mkv" or "mp4"
    on_incompatible_codec: str = "error"  # "error", "skip", "transcode"
```

### V4 Conditional Rules Entities

```python
@dataclass
class ConditionData:
    """Condition for conditional rules (2-level max nesting)."""
    type: str                      # "exists", "count", "and", "or", "not", "audio_is_multi_language"

    # For exists/count conditions
    track_type: str | None = None  # "video", "audio", "subtitle", "attachment"
    filters: TrackFilterData | None = None

    # For count condition
    count_operator: str | None = None  # "eq", "lt", "lte", "gt", "gte"
    count_value: int | None = None

    # For boolean conditions (and/or)
    conditions: list[ConditionData] | None = None

    # For not condition
    inner: ConditionData | None = None

    # For audio_is_multi_language (V7)
    track_index: int | None = None
    threshold: float = 0.05
    primary_language: str | None = None

@dataclass
class TrackFilterData:
    """Track matching filters used in conditions."""
    language: str | list[str] | None = None
    codec: str | list[str] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | ComparisonData | None = None
    width: int | ComparisonData | None = None
    height: int | ComparisonData | None = None
    title: str | TitleMatchData | None = None
    not_commentary: bool | None = None  # V8

@dataclass
class ComparisonData:
    """Numeric comparison for filter fields."""
    operator: str                  # "eq", "lt", "lte", "gt", "gte"
    value: int

@dataclass
class TitleMatchData:
    """Title matching criteria."""
    contains: str | None = None
    regex: str | None = None

@dataclass
class ActionData:
    """Action for conditional rules."""
    type: str                      # "skip_video_transcode", "skip_audio_transcode",
                                   # "skip_track_filter", "warn", "fail", "set_forced", "set_default"
    message: str | None = None     # For warn/fail
    track_type: str | None = None  # For set_forced/set_default
    language: str | None = None    # For set_forced/set_default
    value: bool = True             # For set_forced/set_default

@dataclass
class ConditionalRuleData:
    """A single conditional rule."""
    name: str
    when: ConditionData
    then_actions: list[ActionData]
    else_actions: list[ActionData] | None = None
```

### V5 Audio Synthesis Entities

```python
@dataclass
class SourcePreferenceData:
    """Source track preference criterion."""
    language: str | list[str] | None = None
    not_commentary: bool | None = None
    channels: str | int | None = None  # "max", "min", or int
    codec: str | list[str] | None = None

@dataclass
class SkipIfExistsData:
    """Skip criteria if matching track exists (V8)."""
    codec: str | list[str] | None = None
    channels: int | ComparisonData | None = None
    language: str | list[str] | None = None
    not_commentary: bool | None = None

@dataclass
class SynthesisTrackData:
    """A single synthesis track definition."""
    name: str                      # Unique identifier
    codec: str                     # "eac3", "aac", "ac3", "opus", "flac"
    channels: str | int            # "stereo", "5.1", "7.1", "mono", or int
    source_prefer: list[SourcePreferenceData]
    bitrate: str | None = None     # e.g., "640k"
    skip_if_exists: SkipIfExistsData | None = None  # V8+
    title: str = "inherit"
    language: str = "inherit"
    position: str | int = "end"    # "after_source", "end", or int

@dataclass
class AudioSynthesisData:
    """Audio synthesis configuration."""
    tracks: list[SynthesisTrackData]
```

### V6 Transcode Entities

```python
@dataclass
class SkipConditionData:
    """Skip condition for video transcoding."""
    codec_matches: list[str] | None = None
    resolution_within: str | None = None  # "480p", "720p", "1080p", "1440p", "4k", "8k"
    bitrate_under: str | None = None      # e.g., "10M", "5000k"

@dataclass
class QualitySettingsData:
    """Video quality settings."""
    mode: str = "crf"              # "crf", "bitrate", "constrained_quality"
    crf: int | None = None         # 0-51
    bitrate: str | None = None
    min_bitrate: str | None = None
    max_bitrate: str | None = None
    preset: str = "medium"
    tune: str | None = None
    two_pass: bool = False

@dataclass
class ScalingSettingsData:
    """Video scaling settings."""
    max_resolution: str | None = None
    max_width: int | None = None
    max_height: int | None = None
    algorithm: str = "lanczos"     # "lanczos", "bicubic", "bilinear"
    upscale: bool = False

@dataclass
class HardwareAccelData:
    """Hardware acceleration settings."""
    enabled: str = "auto"          # "auto", "nvenc", "qsv", "vaapi", "none"
    fallback_to_cpu: bool = True

@dataclass
class VideoTranscodeData:
    """V6 video transcode configuration."""
    target_codec: str              # "hevc", "h264", "vp9", "av1"
    skip_if: SkipConditionData | None = None
    quality: QualitySettingsData | None = None
    scaling: ScalingSettingsData | None = None
    hardware_acceleration: HardwareAccelData | None = None

@dataclass
class AudioTranscodeData:
    """V6 audio transcode configuration."""
    preserve_codecs: list[str]     # ["truehd", "dts-hd", "flac"]
    transcode_to: str = "aac"
    transcode_bitrate: str = "192k"

@dataclass
class TranscodeV6Data:
    """V6 transcode configuration with video/audio sections."""
    video: VideoTranscodeData | None = None
    audio: AudioTranscodeData | None = None
```

### V9 Workflow Entity

```python
@dataclass
class WorkflowData:
    """Workflow configuration."""
    phases: list[str]              # ["analyze", "apply", "transcode"]
    auto_process: bool = False
    on_error: str = "continue"     # "skip", "continue", "fail"
```

## Validation Rules

### Field-Level Validation

| Field | Rule | Error Message |
|-------|------|---------------|
| `languages` | ISO 639-2/B codes (2-3 lowercase letters) | "Invalid language code '{value}'. Use ISO 639-2 codes." |
| `bitrate` | Format: `\d+(\.\d+)?[kKmM]?` | "Invalid bitrate. Use format like '192k' or '10M'." |
| `crf` | Integer 0-51 | "CRF must be between 0 and 51." |
| `preset` | One of valid presets | "Invalid preset. Must be one of: ultrafast, ..., veryslow" |
| `tune` | One of valid tunes | "Invalid tune. Must be one of: film, animation, ..." |
| `codec` | One of valid codecs | "Invalid codec. Must be one of: ..." |
| `resolution` | One of valid resolutions | "Invalid resolution. Must be one of: 480p, 720p, 1080p, 1440p, 4k, 8k" |

### Cross-Field Validation

| Condition | Rule |
|-----------|------|
| Quality mode = "bitrate" | `bitrate` field is required |
| Quality mode = "crf" + bitrate specified | Error: conflicting options |
| `audio_filter` present | `schema_version` >= 3 |
| `conditional` present | `schema_version` >= 4 |
| `audio_synthesis` present | `schema_version` >= 5 |
| `transcode.video` or `transcode.audio` present | `schema_version` >= 6 |
| V7 features in conditional | `schema_version` >= 7 |
| `skip_if_exists` in synthesis | `schema_version` >= 8 |
| `workflow` present | `schema_version` >= 9 |
| V10 audio filter options | `schema_version` >= 10 |

## State Management

### Editor State

```javascript
// JavaScript state structure
const editorState = {
  policy: PolicyEditorData,        // Current policy data
  originalPolicy: PolicyEditorData,// Original loaded data (for dirty check)
  lastModified: string,            // Server's last_modified timestamp
  isDirty: boolean,                // Has unsaved changes
  validationErrors: {              // Field-level errors
    [fieldPath: string]: string    // e.g., "audio_filter.languages": "Cannot be empty"
  },
  expandedSections: Set<string>,   // Which accordion sections are open
  isLoading: boolean,
  isSaving: boolean
};
```

### State Transitions

1. **Load** → API GET → populate `policy`, `originalPolicy`, `lastModified`
2. **Edit** → update `policy`, set `isDirty = true`
3. **Validate** → API POST validate → update `validationErrors`
4. **Save** → API PUT → update `originalPolicy`, `lastModified`, set `isDirty = false`
5. **Conflict** → API returns 409 → show conflict dialog

## Relationships

```
PolicyEditorData
├── DefaultFlagsData (1:1)
├── TranscodeLegacyData (0:1, V1-5)
├── TranscriptionData (0:1)
├── AudioFilterData (0:1, V3+)
├── SubtitleFilterData (0:1, V3+)
├── AttachmentFilterData (0:1, V3+)
├── ContainerData (0:1, V3+)
├── ConditionalRuleData (0:N, V4+)
│   ├── ConditionData (1:1)
│   │   ├── TrackFilterData (0:1)
│   │   └── ConditionData (0:N, max depth 2)
│   ├── ActionData (1:N, then)
│   └── ActionData (0:N, else)
├── AudioSynthesisData (0:1, V5+)
│   └── SynthesisTrackData (1:N)
│       ├── SourcePreferenceData (1:N)
│       └── SkipIfExistsData (0:1, V8+)
├── TranscodeV6Data (0:1, V6+)
│   ├── VideoTranscodeData (0:1)
│   │   ├── SkipConditionData (0:1)
│   │   ├── QualitySettingsData (0:1)
│   │   ├── ScalingSettingsData (0:1)
│   │   └── HardwareAccelData (0:1)
│   └── AudioTranscodeData (0:1)
└── WorkflowData (0:1, V9+)
```
