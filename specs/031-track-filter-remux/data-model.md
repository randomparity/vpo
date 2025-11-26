# Data Model: Track Filtering & Container Remux

**Feature**: 031-track-filter-remux
**Date**: 2025-11-25
**Status**: Draft

## Overview

This document defines the data models required for track filtering and container remux functionality. All models are designed as frozen dataclasses following existing VPO patterns.

## New Models

### Policy Configuration Models

#### AudioFilterConfig

Configuration for audio track filtering.

```python
@dataclass(frozen=True)
class AudioFilterConfig:
    """Configuration for filtering audio tracks."""

    languages: tuple[str, ...]
    """ISO 639-2/B language codes to keep (e.g., ('eng', 'und', 'jpn')).
    Tracks with languages not in this list will be removed."""

    fallback: LanguageFallbackConfig | None = None
    """Fallback behavior when no tracks match preferred languages."""

    minimum: int = 1
    """Minimum number of audio tracks that must remain.
    If filtering would leave fewer tracks, fallback is triggered."""
```

**Validation Rules**:
- `languages` must be non-empty tuple of valid ISO 639-2/B codes
- `minimum` must be >= 1 (audio is required)
- If `fallback` is None and filtering would remove all tracks, raise error

---

#### SubtitleFilterConfig

Configuration for subtitle track filtering.

```python
@dataclass(frozen=True)
class SubtitleFilterConfig:
    """Configuration for filtering subtitle tracks."""

    languages: tuple[str, ...] | None = None
    """ISO 639-2/B language codes to keep. If None, no language filtering."""

    preserve_forced: bool = False
    """If True, forced subtitle tracks are preserved regardless of language."""

    remove_all: bool = False
    """If True, remove all subtitle tracks. Overrides other settings."""
```

**Validation Rules**:
- If `remove_all` is True, `languages` and `preserve_forced` are ignored
- `languages` can be empty tuple to remove all non-forced subtitles (when `preserve_forced=True`)

---

#### AttachmentFilterConfig

Configuration for attachment track handling.

```python
@dataclass(frozen=True)
class AttachmentFilterConfig:
    """Configuration for filtering attachment tracks."""

    remove_all: bool = False
    """If True, remove all attachment tracks (fonts, cover art, etc.)."""

    # Future extension point for selective removal
    # keep_types: tuple[str, ...] | None = None
```

**Validation Rules**:
- Currently only supports `remove_all` boolean

---

#### LanguageFallbackConfig

Configuration for language fallback behavior.

```python
@dataclass(frozen=True)
class LanguageFallbackConfig:
    """Configuration for fallback when preferred languages aren't found."""

    mode: Literal["content_language", "keep_all", "keep_first", "error"]
    """Fallback mode:
    - content_language: Keep tracks matching the content's original language
    - keep_all: Keep all tracks (disable filtering)
    - keep_first: Keep first N tracks to meet minimum
    - error: Fail with InsufficientTracksError
    """
```

**Mode Behaviors**:
| Mode | Description |
|------|-------------|
| `content_language` | Detect content language from first audio track, keep those tracks |
| `keep_all` | Preserve all tracks when no preferred language found |
| `keep_first` | Keep first N tracks (by stream order) to meet minimum |
| `error` | Raise `InsufficientTracksError` with details |

---

#### ContainerConfig

Configuration for container format conversion.

```python
@dataclass(frozen=True)
class ContainerConfig:
    """Configuration for container format conversion."""

    target: Literal["mkv", "mp4"]
    """Target container format."""

    on_incompatible_codec: Literal["error", "skip", "transcode"] = "error"
    """Behavior when source contains codecs incompatible with target:
    - error: Fail with IncompatibleCodecError listing problematic tracks
    - skip: Skip the entire file with a warning
    - transcode: Transcode incompatible tracks (requires transcode config)
    """
```

**Codec Compatibility**:
| Codec Type | MKV | MP4 |
|------------|-----|-----|
| H.264, H.265, VP9, AV1 | Yes | Yes |
| AAC, AC3, EAC3, MP3, Opus | Yes | Yes |
| TrueHD, DTS-HD MA | Yes | No |
| FLAC | Yes | Limited |
| PGS, VobSub subtitles | Yes | No |
| SRT, ASS subtitles | Yes | Text only |
| Attachments | Yes | No |

---

### Plan Extension Models

#### TrackDisposition

Represents the planned action for a single track.

```python
@dataclass(frozen=True)
class TrackDisposition:
    """Disposition of a track in the filtering plan."""

    track_index: int
    """0-based global track index in source file."""

    track_type: str
    """Track type: 'video', 'audio', 'subtitle', 'attachment'."""

    codec: str | None
    """Codec name (e.g., 'hevc', 'aac', 'subrip')."""

    language: str | None
    """ISO 639-2/B language code or None if untagged."""

    title: str | None
    """Track title if present."""

    channels: int | None
    """Audio channels (audio tracks only)."""

    resolution: str | None
    """Resolution string like '1920x1080' (video tracks only)."""

    action: Literal["KEEP", "REMOVE"]
    """Whether the track will be kept or removed."""

    reason: str
    """Human-readable reason for the action."""
```

**Reason Examples**:
- `"language in keep list"`
- `"language not in keep list"`
- `"forced subtitle preserved"`
- `"fallback: content language match"`
- `"fallback: keep_first applied"`
- `"attachment removal requested"`
- `"incompatible with target container"`

---

#### ContainerChange

Represents a planned container format change.

```python
@dataclass(frozen=True)
class ContainerChange:
    """Planned container format conversion."""

    source_format: str
    """Source container format (e.g., 'mkv', 'avi', 'mp4')."""

    target_format: str
    """Target container format (e.g., 'mkv', 'mp4')."""

    warnings: tuple[str, ...]
    """Warnings about the conversion (e.g., subtitle format limitations)."""

    incompatible_tracks: tuple[int, ...]
    """Track indices that are incompatible with target format."""
```

---

#### FilterPlan (Extension to existing Plan)

Extended plan with track filtering information.

```python
# Extension to existing Plan dataclass
@dataclass(frozen=True)
class Plan:
    # ... existing fields ...

    # New fields for track filtering (v3)
    track_dispositions: tuple[TrackDisposition, ...] = ()
    """Detailed disposition for each track in the source file."""

    container_change: ContainerChange | None = None
    """Container conversion details if applicable."""

    tracks_removed: int = 0
    """Count of tracks being removed."""

    tracks_kept: int = 0
    """Count of tracks being kept."""
```

---

### Exception Types

#### InsufficientTracksError

```python
class InsufficientTracksError(PolicyError):
    """Raised when track filtering would leave insufficient tracks."""

    def __init__(
        self,
        track_type: str,
        required: int,
        available: int,
        policy_languages: tuple[str, ...],
        file_languages: tuple[str, ...],
    ):
        self.track_type = track_type
        self.required = required
        self.available = available
        self.policy_languages = policy_languages
        self.file_languages = file_languages
        super().__init__(
            f"Filtering {track_type} tracks would leave {available} tracks, "
            f"but minimum {required} required. "
            f"Policy languages: {policy_languages}, "
            f"File has: {file_languages}"
        )
```

---

#### IncompatibleCodecError

```python
class IncompatibleCodecError(PolicyError):
    """Raised when source codecs are incompatible with target container."""

    def __init__(
        self,
        target_container: str,
        incompatible_tracks: list[tuple[int, str, str]],  # (index, type, codec)
    ):
        self.target_container = target_container
        self.incompatible_tracks = incompatible_tracks
        track_list = ", ".join(
            f"#{idx} ({ttype}: {codec})"
            for idx, ttype, codec in incompatible_tracks
        )
        super().__init__(
            f"Cannot convert to {target_container}: "
            f"incompatible tracks: {track_list}"
        )
```

---

## Schema Evolution

### PolicySchema V3 Changes

```python
@dataclass(frozen=True)
class PolicySchema:
    # Existing v2 fields (unchanged)
    schema_version: int
    track_order: tuple[TrackType, ...]
    audio_language_preference: tuple[str, ...]
    subtitle_language_preference: tuple[str, ...]
    commentary_patterns: tuple[str, ...]
    default_flags: DefaultFlagsConfig
    transcode: TranscodePolicyConfig | None
    transcription: TranscriptionPolicyOptions | None

    # New v3 fields (all optional for backward compatibility)
    audio_filter: AudioFilterConfig | None = None
    subtitle_filter: SubtitleFilterConfig | None = None
    attachment_filter: AttachmentFilterConfig | None = None
    container: ContainerConfig | None = None
```

**Version Migration**:
- v2 policies: Loaded unchanged, new fields default to None
- v3 policies: Must specify `schema_version: 3`
- Validation: v3-specific fields rejected if `schema_version < 3`

---

## Entity Relationships

```
PolicySchema (v3)
├── audio_filter: AudioFilterConfig
│   └── fallback: LanguageFallbackConfig
├── subtitle_filter: SubtitleFilterConfig
├── attachment_filter: AttachmentFilterConfig
└── container: ContainerConfig

Plan
├── track_dispositions: [TrackDisposition, ...]
├── container_change: ContainerChange
└── actions: [PlannedAction, ...]  # existing

TrackInfo (existing, unchanged)
└── Used as input to generate TrackDisposition
```

---

## Database Impact

No database schema changes required. The new models are:
1. Policy configuration: Stored in YAML policy files
2. Plan extensions: In-memory only (serialized to `actions_json` for persistence)
3. TrackDisposition: Transient, used for dry-run display

Existing tables remain unchanged:
- `files`: No changes
- `tracks`: No changes
- `plans`: `actions_json` can serialize new action types
- `operations`: No changes
