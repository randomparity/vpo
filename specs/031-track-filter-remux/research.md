# Research: Track Filtering & Container Remux

**Feature**: 031-track-filter-remux
**Date**: 2025-11-25
**Status**: Complete

## Research Tasks

### R1: Current Policy Schema Structure

**Question**: How does the current policy schema (v2) work and what needs to change for v3?

**Findings**:
- Current schema version: **2** (defined in `src/video_policy_orchestrator/policy/loader.py:27`)
- `PolicySchema` is a frozen dataclass in `policy/models.py:235-270`
- Currently supports:
  - `track_order`: Controls track sequence (reordering)
  - `audio_language_preference` / `subtitle_language_preference`: Language ordering (not filtering)
  - `default_flags`: Controls which tracks get default/forced flags
  - `transcode`: Optional transcoding configuration
- **Gap**: No track removal/filtering capability exists today

**Decision**: Extend `PolicySchema` with new v3 fields for track filtering and container conversion while maintaining backward compatibility with v2 policies.

**Schema V3 Additions**:
```python
# Audio track filtering
audio_filter: AudioFilterConfig | None  # New in v3
# Subtitle track filtering
subtitle_filter: SubtitleFilterConfig | None  # New in v3
# Attachment handling
attachment_filter: AttachmentFilterConfig | None  # New in v3
# Container conversion
container: ContainerConfig | None  # New in v3
```

---

### R2: Track Removal Implementation Strategy

**Question**: How should track removal be implemented using mkvmerge/ffmpeg?

**Findings**:
- **mkvmerge** (for MKV output): Use `--audio-tracks`, `--video-tracks`, `--subtitle-tracks`, `--attachments` flags
  - Example: `mkvmerge -o output.mkv --audio-tracks 0,2 --subtitle-tracks 0 input.mkv`
  - Track IDs are 0-indexed within each track type
- **FFmpeg** (for all containers): Use `-map` with exclusion
  - Example: `ffmpeg -i input.mkv -map 0 -map -0:a:1 -map -0:a:2 -c copy output.mkv`
  - Stream indices are 0-indexed by type (`:a:0` = first audio, `:s:1` = second subtitle)

**Decision**:
- Use **mkvmerge** for MKV→MKV operations (better metadata preservation, faster)
- Use **FFmpeg** for container conversions and non-MKV outputs
- Extend `MkvmergeExecutor` with track selection flags
- Create new `ContainerConversionExecutor` using FFmpeg for remux operations

**Alternatives Considered**:
- Using only FFmpeg for everything: Rejected because mkvmerge has better MKV-specific features
- Using mkvextract + mkvmerge: Rejected as unnecessary complexity for simple filtering

---

### R3: Container Conversion Approach

**Question**: What's the best approach for lossless MKV↔MP4 conversion?

**Findings**:
- **MKV to MP4**: FFmpeg with `-c copy -movflags +faststart`
  - Incompatible codecs: TrueHD, DTS-HD MA, PGS subtitles, VobSub, attachments
  - SRT subtitles can be converted to mov_text
- **MP4 to MKV**: mkvmerge can directly import MP4 files
  - Nearly all MP4 codecs are MKV-compatible
- **AVI/MOV to MKV**: mkvmerge handles these directly

**Decision**:
- MKV output: Always use mkvmerge (handles any input)
- MP4 output: Use FFmpeg with codec compatibility checking
- Implement `on_incompatible_codec` modes: `error`, `skip`, `transcode` (transcode deferred to Sprint 3/4)

**Codec Compatibility Matrix**:
| Codec | MKV | MP4 |
|-------|-----|-----|
| H.264/H.265 | Yes | Yes |
| AAC/AC3/EAC3 | Yes | Yes |
| TrueHD | Yes | No |
| DTS-HD MA | Yes | No |
| FLAC | Yes | Limited |
| PGS subtitles | Yes | No |
| SRT/ASS | Yes | No (text only) |

---

### R4: Language Fallback Implementation

**Question**: How should language fallback work when preferred languages aren't found?

**Findings**:
- Current `audio_language_preference` in v2 is for ordering, not filtering
- Need new logic for "keep only these languages" with fallback behavior
- Content language detection: Use first audio track's language tag (existing pattern)

**Decision**: Implement `LanguageFallbackConfig`:
```python
@dataclass(frozen=True)
class LanguageFallbackConfig:
    mode: Literal["content_language", "keep_all", "keep_first", "error"]
    minimum: int = 1  # Minimum tracks to retain
```

**Fallback Logic**:
1. Filter by `languages` list
2. If result count < `minimum`:
   - `content_language`: Keep tracks matching first audio track's language
   - `keep_all`: Keep all tracks (no filtering)
   - `keep_first`: Keep first N tracks to meet minimum
   - `error`: Raise `InsufficientTracksError`

---

### R5: Dry-Run Output Enhancement

**Question**: How to extend existing dry-run to show track disposition?

**Findings**:
- Existing dry-run in `cli/apply.py:90-120+` shows planned actions
- `Plan.summary` property provides basic summary
- Need detailed track-by-track output showing KEEP/REMOVE decisions

**Decision**: Add new `TrackDisposition` model and extend `Plan`:
```python
@dataclass(frozen=True)
class TrackDisposition:
    track_index: int
    track_type: str  # video, audio, subtitle, attachment
    codec: str | None
    language: str | None
    title: str | None
    action: Literal["KEEP", "REMOVE"]
    reason: str  # e.g., "language not in keep list", "forced subtitle preserved"
```

Extend `Plan` with:
- `track_dispositions: tuple[TrackDisposition, ...]`
- `container_change: ContainerChange | None` (source_format, target_format, warnings)

---

### R6: Backup Strategy

**Question**: How should backups work for destructive operations?

**Findings**:
- Existing executors create backups via `shutil.copy2()`
- Backups stored in same directory with `.bak` suffix
- On failure, restore from backup

**Decision**: Maintain existing pattern:
- Create backup before any modification
- Backup path: `{original_path}.bak`
- On successful completion, keep backup (configurable via `--keep-backup` flag)
- On failure, restore backup and remove partial output
- Add disk space check before operation (fail if < 2x file size available)

---

### R7: Forced Subtitle Preservation

**Question**: How to implement `preserve_forced: true` for subtitle filtering?

**Findings**:
- `TrackInfo.is_forced` field already exists
- Forced subtitles contain foreign dialogue translations
- Should be preserved regardless of language filter

**Decision**: When `preserve_forced: true`:
1. First pass: Apply language filter normally
2. Second pass: Re-add any forced subtitles that were filtered out
3. Mark these tracks with reason: "forced subtitle preserved"

---

### R8: Attachment Font Warning

**Question**: How to detect styled subtitles that depend on embedded fonts?

**Findings**:
- Styled subtitles use ASS/SSA format (codec: `ass`, `ssa`)
- These reference font files by name
- MKV attachments include fonts with `application/x-truetype-font` or similar MIME types

**Decision**: Implement warning logic:
1. Detect ASS/SSA subtitle tracks in file
2. Detect font attachments (by MIME type or extension)
3. If removing attachments while ASS/SSA subtitles exist, emit warning
4. Warning text: "Removing fonts may affect subtitle rendering for tracks: [list]"

---

## Technology Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Track removal tool (MKV) | mkvmerge | Better metadata preservation, native MKV support |
| Container conversion tool | FFmpeg | Universal format support, streaming optimization |
| Schema extension | Additive v3 fields | Backward compatible with v2 policies |
| Language codes | ISO 639-2/B | Consistent with existing VPO patterns |
| Backup location | Same directory `.bak` | Consistent with existing executor pattern |
| Fallback modes | 4 options | Covers all reasonable user scenarios |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Accidental audio-less output | Mandatory minimum=1 for audio, validation before execution |
| Disk space exhaustion during remux | Pre-flight check for 2x file size available |
| Incompatible codec silently dropped | Explicit `on_incompatible_codec` modes with clear errors |
| Breaking v2 policies | v3 fields are all optional, v2 policies unchanged |
