# Research: Media Introspection & Track Modeling

**Feature**: 003-media-introspection
**Date**: 2025-11-21

## ffprobe JSON Output Structure

### Decision
Use `ffprobe -v quiet -print_format json -show_streams -show_format <file>` to extract metadata.

### Rationale
- JSON output is machine-parseable and well-documented
- `-show_streams` provides per-track metadata (codec, language, channels, resolution)
- `-show_format` provides container-level info
- `-v quiet` suppresses non-JSON output for clean parsing

### Alternatives Considered
- **XML output**: More verbose, no significant advantage
- **Flat key=value format**: Harder to parse nested track data
- **mkvmerge -J**: MKV-only, deferred per clarification

## Track Type Mapping

### Decision
Map ffprobe `codec_type` values to VPO track types:
- `video` → `video`
- `audio` → `audio`
- `subtitle` → `subtitle`
- `attachment` → `attachment`
- All others → `other`

### Rationale
ffprobe's codec_type field directly maps to our domain model. Attachments (fonts, images) are preserved separately for future use.

### Alternatives Considered
- **Codec-based inference**: Less reliable than explicit codec_type field

## Language Code Handling

### Decision
Use ffprobe `tags.language` field, falling back to "und" (undefined) when absent. Preserve ISO 639-2/B codes as-is.

### Rationale
- ffprobe reports language tags from container metadata
- ISO 639-2/B is the standard used in MKV/MP4 containers
- "und" is the standard code for undefined language

### Alternatives Considered
- **Convert to ISO 639-1**: Would lose information for languages without 2-letter codes
- **Use "unknown"**: "und" is the recognized standard

## Audio Channel Layout

### Decision
Extract `channels` count from ffprobe stream data. Map to human-readable labels:
- 1 → "mono"
- 2 → "stereo"
- 6 → "5.1"
- 8 → "7.1"
- Other → "{n}ch"

### Rationale
Channel count is reliably reported. Human-readable labels improve CLI output clarity.

### Alternatives Considered
- **Use channel_layout string**: Not always present; count is more reliable

## Video Resolution and Frame Rate

### Decision
Extract `width`, `height` from ffprobe stream. Frame rate from `r_frame_rate` (display rate) or `avg_frame_rate` (fallback).

### Rationale
- Width/height directly available in stream metadata
- `r_frame_rate` is the intended display rate (e.g., "24000/1001" for 23.976)
- Frame rate stored as string to preserve precision (rational representation)

### Alternatives Considered
- **Convert to float**: Loses precision for fractional rates like 23.976

## Smart Merge Strategy

### Decision
On rescan, match tracks by `track_index` (stream index from ffprobe). Update existing, insert new, delete missing.

### Rationale
- Stream index is stable for unchanged files
- Full replace would lose any future track-level user annotations (out of scope but design-forward)
- Index-based matching handles reordering gracefully

### Alternatives Considered
- **Replace all**: Simpler but loses potential future metadata
- **Codec+index matching**: Over-engineered for current needs

## ffprobe Availability Detection

### Decision
Check ffprobe availability at runtime using `shutil.which("ffprobe")`. Cache result per session.

### Rationale
- `shutil.which` is cross-platform and handles PATH correctly
- Single check at introspector instantiation avoids repeated subprocess calls
- Clear error message when missing

### Alternatives Considered
- **Check on every call**: Performance overhead
- **Require at install time**: Too restrictive for optional functionality

## Fixture Format

### Decision
Store recorded ffprobe JSON output in `tests/fixtures/ffprobe/`. Load via `json.load()` in tests.

### Rationale
- Real ffprobe output ensures parser handles actual data structures
- JSON files can be committed without binary media files
- Easy to add new fixtures for edge cases

### Alternatives Considered
- **Mock ffprobe entirely**: Would miss parsing edge cases
- **Include actual media files**: Too large for repository
