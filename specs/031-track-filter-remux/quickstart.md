# Quickstart: Track Filtering & Container Remux

**Feature**: 031-track-filter-remux
**Date**: 2025-11-25

## Overview

This guide covers implementing track filtering and container remux for VPO. The feature adds the ability to remove unwanted tracks (audio, subtitle, attachment) and convert between container formats (MKV, MP4).

## Prerequisites

- Python 3.10+
- VPO development environment set up (`uv pip install -e ".[dev]"`)
- External tools: `mkvmerge`, `mkvpropedit`, `ffmpeg`, `ffprobe`
- Familiarity with existing policy evaluation flow

## Key Files to Modify

| File | Purpose |
|------|---------|
| `policy/models.py` | Add V3 config models |
| `policy/loader.py` | Update schema version, add V3 validation |
| `policy/evaluator.py` | Add track filtering logic |
| `executor/mkvmerge.py` | Extend for track selection |
| `executor/ffmpeg_remux.py` | New executor for container conversion |
| `cli/apply.py` | Enhanced dry-run output |

## Implementation Steps

### Step 1: Add V3 Config Models

Add to `policy/models.py`:

```python
from typing import Literal

@dataclass(frozen=True)
class LanguageFallbackConfig:
    mode: Literal["content_language", "keep_all", "keep_first", "error"]

@dataclass(frozen=True)
class AudioFilterConfig:
    languages: tuple[str, ...]
    fallback: LanguageFallbackConfig | None = None
    minimum: int = 1

@dataclass(frozen=True)
class SubtitleFilterConfig:
    languages: tuple[str, ...] | None = None
    preserve_forced: bool = False
    remove_all: bool = False

@dataclass(frozen=True)
class AttachmentFilterConfig:
    remove_all: bool = False

@dataclass(frozen=True)
class ContainerConfig:
    target: Literal["mkv", "mp4"]
    on_incompatible_codec: Literal["error", "skip", "transcode"] = "error"
```

### Step 2: Extend PolicySchema

```python
@dataclass(frozen=True)
class PolicySchema:
    # ... existing fields ...

    # V3 additions (all optional)
    audio_filter: AudioFilterConfig | None = None
    subtitle_filter: SubtitleFilterConfig | None = None
    attachment_filter: AttachmentFilterConfig | None = None
    container: ContainerConfig | None = None
```

### Step 3: Add TrackDisposition Model

```python
@dataclass(frozen=True)
class TrackDisposition:
    track_index: int
    track_type: str
    codec: str | None
    language: str | None
    title: str | None
    channels: int | None
    resolution: str | None
    action: Literal["KEEP", "REMOVE"]
    reason: str
```

### Step 4: Update Loader for V3

In `policy/loader.py`:

```python
MAX_SCHEMA_VERSION = 3  # Update from 2

class AudioFilterModel(BaseModel):
    languages: list[str]
    minimum: int = 1
    fallback: LanguageFallbackModel | None = None

# Add validation models for other V3 fields...
```

### Step 5: Implement Track Filtering Logic

In `policy/evaluator.py`, add filtering function:

```python
def compute_track_dispositions(
    tracks: list[TrackInfo],
    policy: PolicySchema,
) -> tuple[TrackDisposition, ...]:
    """Compute disposition for each track based on policy filters."""
    dispositions = []

    for track in tracks:
        if track.track_type == "audio" and policy.audio_filter:
            action, reason = _evaluate_audio_track(track, policy.audio_filter)
        elif track.track_type == "subtitle" and policy.subtitle_filter:
            action, reason = _evaluate_subtitle_track(track, policy.subtitle_filter)
        elif track.track_type == "attachment" and policy.attachment_filter:
            action, reason = _evaluate_attachment_track(track, policy.attachment_filter)
        else:
            action, reason = "KEEP", "no filter applied"

        dispositions.append(TrackDisposition(
            track_index=track.index,
            track_type=track.track_type,
            codec=track.codec,
            language=track.language,
            title=track.title,
            channels=track.channels,
            resolution=f"{track.width}x{track.height}" if track.width else None,
            action=action,
            reason=reason,
        ))

    return tuple(dispositions)
```

### Step 6: Extend MkvmergeExecutor

In `executor/mkvmerge.py`:

```python
def _build_track_selection_args(
    self,
    plan: Plan,
) -> list[str]:
    """Build mkvmerge track selection arguments."""
    args = []

    # Group tracks by type
    keep_audio = [d.track_index for d in plan.track_dispositions
                  if d.track_type == "audio" and d.action == "KEEP"]
    keep_subs = [d.track_index for d in plan.track_dispositions
                 if d.track_type == "subtitle" and d.action == "KEEP"]

    if keep_audio:
        args.extend(["--audio-tracks", ",".join(str(i) for i in keep_audio)])
    if keep_subs:
        args.extend(["--subtitle-tracks", ",".join(str(i) for i in keep_subs)])
    if any(d.action == "REMOVE" for d in plan.track_dispositions
           if d.track_type == "attachment"):
        args.append("--no-attachments")

    return args
```

### Step 7: Create FFmpeg Remux Executor

New file `executor/ffmpeg_remux.py`:

```python
class FFmpegRemuxExecutor:
    """Executor for container conversion using FFmpeg."""

    def can_handle(self, plan: Plan) -> bool:
        return plan.container_change is not None

    def execute(self, plan: Plan, keep_backup: bool = True) -> ExecutorResult:
        # Build ffmpeg command with -map for track selection
        # and -c copy for stream copying
        ...
```

### Step 8: Enhanced Dry-Run Output

In `cli/apply.py`:

```python
def _format_track_dispositions(plan: Plan) -> str:
    """Format track dispositions for display."""
    lines = ["Track Dispositions:"]
    for d in plan.track_dispositions:
        status = "KEEP  " if d.action == "KEEP" else "REMOVE"
        info = f"#{d.track_index} [{d.track_type}] {d.codec or 'unknown'}"
        if d.resolution:
            info += f" {d.resolution}"
        if d.channels:
            info += f" {d.channels}ch"
        if d.language:
            info += f" {d.language}"
        if d.title:
            info += f' "{d.title}"'
        if d.action == "REMOVE":
            info += f" ({d.reason})"
        lines.append(f"  {status} {info}")
    return "\n".join(lines)
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/policy/test_track_filtering.py

def test_audio_filter_keeps_matching_languages():
    tracks = [
        TrackInfo(index=0, track_type="audio", language="eng", ...),
        TrackInfo(index=1, track_type="audio", language="fra", ...),
    ]
    config = AudioFilterConfig(languages=("eng",))
    dispositions = compute_track_dispositions(tracks, policy_with(audio_filter=config))

    assert dispositions[0].action == "KEEP"
    assert dispositions[1].action == "REMOVE"
    assert "not in keep list" in dispositions[1].reason

def test_audio_filter_fallback_keeps_content_language():
    # Test fallback behavior...

def test_minimum_audio_tracks_enforced():
    # Test InsufficientTracksError...
```

### Integration Tests

```python
# tests/integration/test_track_filtering.py

def test_apply_removes_audio_tracks(tmp_path, sample_multilang_mkv):
    policy = create_policy(audio_filter=AudioFilterConfig(languages=("eng",)))
    result = apply_policy(sample_multilang_mkv, policy)

    # Verify output file has only English audio
    tracks = introspect(result.output_path)
    audio_tracks = [t for t in tracks if t.track_type == "audio"]
    assert len(audio_tracks) == 1
    assert audio_tracks[0].language == "eng"
```

## Common Patterns

### Language Matching

Use existing `languages_match()` function for cross-standard comparison:

```python
from video_policy_orchestrator.policy.matchers import languages_match

# These all match:
languages_match("eng", "en")   # True
languages_match("ger", "deu")  # True (ISO 639-2/T vs 639-2/B)
```

### Codec Compatibility Check

```python
MP4_INCOMPATIBLE = {"truehd", "dts-hd", "hdmv_pgs_subtitle", "dvd_subtitle"}

def is_mp4_compatible(codec: str) -> bool:
    return codec.lower() not in MP4_INCOMPATIBLE
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Track indices don't match | mkvmerge uses type-relative indices; convert from global |
| Subtitles disappear in MP4 | MP4 only supports text subtitles (mov_text) |
| Large file timeout | Increase executor timeout for files >20GB |
| Font warning not shown | Check for ASS/SSA codec before attachment removal |
