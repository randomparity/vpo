# Data Model: Audio Track Synthesis

**Feature**: 033-audio-synthesis
**Date**: 2025-11-26

## Entities

### SynthesisTrackDefinition

Policy-defined specification for a track to be synthesized.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | str | Yes | Human-readable identifier for this synthesis definition |
| codec | AudioCodec | Yes | Target codec (eac3, aac, ac3, opus, flac) |
| channels | ChannelConfig | Yes | Target channel configuration |
| bitrate | str \| None | No | Target bitrate (e.g., "640k"), codec default if omitted |
| create_if | Condition \| None | No | Condition that must be true to create track |
| source | SourcePreferences | Yes | Preferences for selecting source track |
| title | str \| Literal["inherit"] | No | Track title, inherit from source if "inherit" |
| language | str \| Literal["inherit"] | No | ISO 639-2/B code or "inherit" from source |
| position | Position | No | Where to place synthesized track (default: "end") |

### SourcePreferences

Ordered preferences for selecting the source track.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| prefer | list[PreferenceCriterion] | Yes | Ordered list of preference criteria |

### PreferenceCriterion

Single preference criterion for source selection.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| language | str \| list[str] \| None | No | Preferred language(s) |
| not_commentary | bool \| None | No | Exclude commentary tracks if True |
| channels | ChannelPreference \| None | No | Channel preference (max, min, specific) |
| codec | str \| list[str] \| None | No | Preferred codec(s) |

### SourceTrackSelection

Result of evaluating source preferences against file tracks.

| Field | Type | Description |
|-------|------|-------------|
| track_index | int | Selected track index (0-based) |
| track_info | TrackInfo | Full track information |
| score | int | Preference matching score |
| is_fallback | bool | True if no criteria matched, using first audio track |
| match_reasons | list[str] | Human-readable match reasons for dry-run |

### SynthesisOperation

Single synthesis operation to be executed.

| Field | Type | Description |
|-------|------|-------------|
| definition_name | str | Name from SynthesisTrackDefinition |
| source_track | SourceTrackSelection | Selected source track |
| target_codec | AudioCodec | Output codec |
| target_channels | int | Output channel count |
| target_bitrate | int \| None | Output bitrate in bps |
| target_title | str | Final track title |
| target_language | str | Final track language |
| target_position | int | Final audio track index (after resolution) |
| downmix_filter | str \| None | FFmpeg filter for channel conversion |

### SynthesisPlan

Complete plan for all synthesis operations on a file.

| Field | Type | Description |
|-------|------|-------------|
| file_id | str | UUID of the media file |
| file_path | Path | Path to the media file |
| operations | list[SynthesisOperation] | Tracks to create |
| skipped | list[SkippedSynthesis] | Tracks skipped with reasons |
| final_track_order | list[TrackOrderEntry] | Projected final audio track order |

### SkippedSynthesis

Record of a synthesis that was skipped.

| Field | Type | Description |
|-------|------|-------------|
| definition_name | str | Name from SynthesisTrackDefinition |
| reason | SkipReason | Why synthesis was skipped |
| details | str | Human-readable explanation |

## Enums

### AudioCodec

```python
class AudioCodec(str, Enum):
    EAC3 = "eac3"
    AAC = "aac"
    AC3 = "ac3"
    OPUS = "opus"
    FLAC = "flac"
```

### ChannelConfig

```python
class ChannelConfig(str, Enum):
    MONO = "mono"        # 1 channel
    STEREO = "stereo"    # 2 channels
    SURROUND_51 = "5.1"  # 6 channels
    SURROUND_71 = "7.1"  # 8 channels
    # Also accepts integer for custom channel counts
```

### Position

```python
class Position:
    AFTER_SOURCE = "after_source"
    END = "end"
    # Or integer for specific audio track index (1-indexed)
```

### SkipReason

```python
class SkipReason(str, Enum):
    CONDITION_NOT_MET = "condition_not_met"
    NO_SOURCE_AVAILABLE = "no_source_available"
    WOULD_UPMIX = "would_upmix"
    ENCODER_UNAVAILABLE = "encoder_unavailable"
```

### ChannelPreference

```python
class ChannelPreference:
    MAX = "max"   # Prefer highest channel count
    MIN = "min"   # Prefer lowest channel count
    # Or specific integer
```

## Relationships

```
PolicySchema
    └── audio_synthesis: AudioSynthesisConfig
            └── tracks: list[SynthesisTrackDefinition]
                    ├── source: SourcePreferences
                    │       └── prefer: list[PreferenceCriterion]
                    └── create_if: Condition (from existing conditions.py)

SynthesisPlan
    ├── operations: list[SynthesisOperation]
    │       └── source_track: SourceTrackSelection
    │               └── track_info: TrackInfo (existing)
    └── skipped: list[SkippedSynthesis]
```

## State Transitions

### Synthesis Planning Flow

```
┌─────────────────┐
│ Load Policy     │
│ (parse YAML)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Validate Schema │
│ (type checking) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ For each track: │
│ Eval create_if  │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌────────────┐
│ FALSE  │  │ TRUE       │
│ Skip   │  │ Select Src │
└────────┘  └─────┬──────┘
                  │
             ┌────┴────┐
             │         │
             ▼         ▼
       ┌────────┐  ┌────────────┐
       │ Upmix? │  │ Valid Src  │
       │ Skip   │  │ Add to Ops │
       └────────┘  └────────────┘
                         │
                         ▼
              ┌─────────────────┐
              │ Resolve Positions│
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ SynthesisPlan   │
              │ (ready to exec) │
              └─────────────────┘
```

## Validation Rules

### SynthesisTrackDefinition

1. `name` must be non-empty and unique within policy
2. `codec` must be a valid AudioCodec enum value
3. `channels` must be valid ChannelConfig or positive integer
4. `bitrate` if provided must match pattern `^\d+k$` (e.g., "640k")
5. `create_if` if provided must be valid Condition
6. `source.prefer` must have at least one criterion
7. `position` if integer must be >= 1

### Source Selection

1. Source track must be audio type
2. Source channels >= target channels (no upmix)
3. At least one audio track must exist in file

### Position Resolution

1. Positions are 1-indexed for user-facing values
2. `after_source` resolves to source_index + 1
3. `end` resolves to len(audio_tracks) + 1
4. Integer positions clamped to valid range

## Codec Default Bitrates

| Codec | Stereo | 5.1 | 7.1 |
|-------|--------|-----|-----|
| EAC3 | 384k | 640k | 768k |
| AAC | 192k | 384k | 512k |
| AC3 | 192k | 448k | N/A (max 5.1) |
| Opus | 128k | 256k | 384k |
| FLAC | N/A | N/A | N/A |

## FFmpeg Encoder Mapping

| AudioCodec | FFmpeg Encoder | Format |
|------------|----------------|--------|
| EAC3 | `eac3` | eac3 |
| AAC | `aac` | aac |
| AC3 | `ac3` | ac3 |
| Opus | `libopus` | opus |
| FLAC | `flac` | flac |
