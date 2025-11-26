# Feature Specification: Track Filtering & Container Remux

**Feature Branch**: `031-track-filter-remux`
**Created**: 2025-11-25
**Status**: Draft
**Input**: User description: "Sprint 1: Track Filtering & Container Remux - Enable track removal based on language, codec, track type; support lossless container conversion (MKV ↔ MP4); implement language fallback logic; introduce policy schema v3"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remove Non-Preferred Audio Tracks (Priority: P1)

As a media library curator, I want to remove all audio tracks that don't match my preferred languages so that I can reduce file sizes for streaming devices with limited bandwidth while ensuring I always have playable audio.

**Why this priority**: This is the core value proposition of track filtering. Audio tracks are typically the largest non-video streams, so removing unwanted languages provides the most significant storage savings. This story includes the critical safety feature of ensuring at least one audio track remains.

**Independent Test**: Can be fully tested by applying a policy with `audio.languages: [eng, und]` to a file with multiple language audio tracks and verifying only matching tracks remain while at least one audio track is preserved.

**Acceptance Scenarios**:

1. **Given** a video file with English, French, and Spanish audio tracks, **When** I apply a policy keeping only English audio, **Then** only the English audio track remains in the output file
2. **Given** a video file with French and Spanish audio tracks (no English), **When** I apply a policy preferring English with fallback to content language, **Then** the French track is kept (assuming French is the content's original language)
3. **Given** a video file where all audio tracks would be removed, **When** I apply the policy, **Then** the system produces a validation error before making changes
4. **Given** a video file with an audio track tagged as "und" (undefined), **When** I apply a policy keeping `[eng, und]`, **Then** the undefined language track is preserved
5. **Given** any policy application, **When** the policy is applied, **Then** the original file is preserved (backup created before modification)

---

### User Story 2 - Dry-Run Preview for Track Changes (Priority: P1)

As a cautious user, I want to preview which tracks will be removed before applying changes so that I can verify the policy is correct and avoid unintended data loss.

**Why this priority**: Equal to P1 because users need confidence before modifying their files. The dry-run capability is essential for safe operation and must be available before any destructive operations are implemented.

**Independent Test**: Can be fully tested by running `vpo apply --dry-run` on any video file with a track filtering policy and verifying the detailed output shows each track's disposition.

**Acceptance Scenarios**:

1. **Given** a video file with multiple tracks, **When** I run `vpo apply --dry-run`, **Then** I see each track listed with: index, type, codec, language, title, and action (KEEP/REMOVE)
2. **Given** a dry-run output, **When** I review the results, **Then** I see a summary showing total tracks kept vs removed
3. **Given** a policy that would remove tracks, **When** I run dry-run, **Then** each removed track shows the reason for removal (e.g., "language not in keep list")
4. **Given** a policy with container conversion, **When** I run dry-run, **Then** I see the target container format and any incompatibility warnings

---

### User Story 3 - Container Conversion to MKV (Priority: P2)

As a video archivist, I want to convert AVI, MOV, and other container formats to MKV containers losslessly so that I have consistent container formats with full metadata support across my library.

**Why this priority**: MKV is the most flexible container supporting virtually all codecs. Converting to MKV is almost always lossless and safe, making it a lower-risk operation than MP4 conversion.

**Independent Test**: Can be fully tested by applying a policy with `container.target: mkv` to an AVI or MOV file and verifying all streams are preserved without re-encoding.

**Acceptance Scenarios**:

1. **Given** an AVI file with video, audio, and subtitle streams, **When** I apply a policy targeting MKV, **Then** the output is an MKV file with all original streams preserved
2. **Given** a MOV file with QuickTime-specific metadata, **When** I apply the conversion, **Then** compatible metadata is preserved in the MKV container
3. **Given** any container conversion, **When** the conversion completes, **Then** video and audio streams are stream-copied (not re-encoded)
4. **Given** a file already in MKV format with `container.target: mkv`, **When** I apply the policy, **Then** no unnecessary remux occurs

---

### User Story 4 - Container Conversion to MP4 (Priority: P2)

As a user migrating to Apple devices, I want to remux MKV files to MP4 containers so that they are natively supported on iOS and macOS without transcoding.

**Why this priority**: MP4 compatibility is essential for Apple ecosystem users. However, MP4 has codec limitations that require careful handling, making this more complex than MKV conversion.

**Independent Test**: Can be fully tested by applying a policy with `container.target: mp4` to an MKV file with compatible codecs and verifying lossless conversion.

**Acceptance Scenarios**:

1. **Given** an MKV file with H.264 video, AAC audio, and SRT subtitles, **When** I apply a policy targeting MP4, **Then** the output is an MP4 file with all compatible streams preserved
2. **Given** an MKV file with TrueHD audio and `on_incompatible_codec: error`, **When** I apply the policy, **Then** the system fails with a clear message listing the incompatible track
3. **Given** an MKV file with PGS subtitles and `on_incompatible_codec: skip`, **When** I apply the policy, **Then** the file is skipped entirely with a warning
4. **Given** a successful MP4 conversion, **When** the file is created, **Then** the `-movflags +faststart` optimization is applied for streaming

---

### User Story 5 - Remove Non-Preferred Subtitle Tracks (Priority: P3)

As a user with English-only viewing preferences, I want to remove all non-English subtitle tracks so that my media player doesn't show unnecessary subtitle options.

**Why this priority**: Subtitle tracks are smaller than audio tracks, providing less storage savings. However, cleaner subtitle lists improve user experience on media players.

**Independent Test**: Can be fully tested by applying a policy with `subtitles.languages: [eng]` to a file with multiple subtitle languages and verifying only matching tracks remain.

**Acceptance Scenarios**:

1. **Given** a video file with English, French, and Spanish subtitles, **When** I apply a policy keeping only English subtitles, **Then** only English subtitles remain
2. **Given** a video file with only French subtitles, **When** I apply a policy keeping only English, **Then** all subtitles are removed (subtitles are optional)
3. **Given** a video file with a forced English subtitle track, **When** I apply a policy with `preserve_forced: true`, **Then** the forced track is preserved regardless of other language settings
4. **Given** a video file with SDH (hearing-impaired) subtitles, **When** I apply the policy, **Then** SDH tracks follow the same language rules as regular subtitles

---

### User Story 6 - Remove Attachment Tracks (Priority: P3)

As a storage optimizer, I want to remove attachment tracks (fonts, images, cover art) so that I reduce file sizes without affecting playback for most users.

**Why this priority**: Attachments rarely affect playback for most users but can add significant size (especially font files for styled subtitles). This is a "nice to have" optimization.

**Independent Test**: Can be fully tested by applying a policy with `attachments: remove` to a file with embedded fonts and cover art and verifying they are removed.

**Acceptance Scenarios**:

1. **Given** an MKV file with embedded fonts, **When** I apply a policy removing attachments, **Then** all font attachments are removed
2. **Given** an MKV file with cover art, **When** I apply the policy, **Then** cover art attachments are removed
3. **Given** a file with styled ASS/SSA subtitles using embedded fonts, **When** I remove attachments, **Then** a warning is shown that subtitle rendering may be affected
4. **Given** a policy with `attachments: remove` and styled subtitles in the file, **When** dry-run is executed, **Then** the warning appears in the preview

---

### User Story 7 - Language Fallback Logic (Priority: P3)

As a collector with multi-language content, I want to specify fallback logic so that I never accidentally create files with no audio when my preferred language isn't available.

**Why this priority**: This is an advanced configuration for edge cases. Most users will have content in their preferred language; fallback logic protects against edge cases.

**Independent Test**: Can be fully tested by configuring various fallback modes and applying policies to files missing the preferred language.

**Acceptance Scenarios**:

1. **Given** a file with only Japanese audio and a policy preferring English with `fallback: content_language`, **When** I apply the policy, **Then** the Japanese audio is kept (content's original language)
2. **Given** a file with French and German audio and a policy preferring English with `fallback: keep_all`, **When** I apply the policy, **Then** both French and German tracks are kept
3. **Given** a file with multiple audio tracks and a policy preferring English with `fallback: keep_first`, **When** I apply the policy, **Then** only the first audio track is kept
4. **Given** a file without English audio and a policy with `fallback: error`, **When** I apply the policy, **Then** the system fails with a clear error message
5. **Given** a policy with `minimum: 2` and a file where filtering would leave only 1 track, **When** I apply the policy, **Then** enough tracks are preserved to meet the minimum

---

### Edge Cases

- What happens when a file has no language tags on any audio tracks?
  - Tracks with undefined/empty language tags match the `und` language code
- How does the system handle files that are already in the target container format?
  - No unnecessary remux occurs unless track changes are also specified
- What happens when track removal and container conversion are both specified?
  - Both operations are combined into a single output file
- How does the system handle corrupt or unreadable tracks?
  - Corrupt tracks are reported in dry-run and cause errors during execution (fail-safe)
- What happens when the backup destination is full or unavailable?
  - Operation fails before modifying the original file
- How does the system handle very large files (>50GB)?
  - Standard processing with progress indication; no special handling required

## Requirements *(mandatory)*

### Functional Requirements

**Track Filtering - Audio**:
- **FR-001**: System MUST allow policies to specify audio languages to keep as a list of ISO 639-2/B language codes (e.g., `[eng, und, jpn]`)
- **FR-002**: System MUST remove audio tracks not matching the keep list during policy application
- **FR-003**: System MUST validate that at least one audio track will remain before applying changes
- **FR-004**: System MUST support language fallback configuration with modes: `content_language`, `keep_all`, `keep_first`, `error`
- **FR-005**: System MUST support `minimum: N` option to ensure at least N audio tracks remain
- **FR-006**: System MUST detect content language from the first/default audio track's language tag

**Track Filtering - Subtitles**:
- **FR-007**: System MUST allow policies to specify subtitle languages to keep
- **FR-008**: System MUST allow removing all subtitles (subtitles are optional, unlike audio)
- **FR-009**: System MUST support `preserve_forced: true` option to keep forced subtitle tracks regardless of language

**Track Filtering - Attachments**:
- **FR-010**: System MUST allow policies to remove all attachment tracks
- **FR-011**: System MUST warn users when removing fonts that may affect styled subtitle rendering

**Container Conversion**:
- **FR-012**: System MUST support `container.target` option with values `mkv` and `mp4`
- **FR-013**: System MUST perform lossless stream copy (no re-encoding) during container conversion
- **FR-014**: System MUST support `on_incompatible_codec` option with modes: `error`, `skip`, `transcode`
- **FR-015**: System MUST apply `-movflags +faststart` when creating MP4 files

**Dry-Run & Safety**:
- **FR-016**: System MUST support `--dry-run` flag showing detailed track-by-track disposition
- **FR-017**: System MUST display track index, type, codec, language, title, and action (KEEP/REMOVE) in dry-run output
- **FR-018**: System MUST create backup of original file before modification
- **FR-019**: System MUST provide summary of tracks kept vs removed in dry-run output

**Policy Schema**:
- **FR-020**: System MUST introduce policy schema version 3 for track filtering features
- **FR-021**: System MUST maintain backward compatibility with schema v2 policies
- **FR-022**: System MUST validate policy schema version and reject invalid configurations

### Key Entities

- **TrackDisposition**: Represents the planned action for a track (KEEP, REMOVE) with reason
- **LanguageFallback**: Configuration for fallback behavior when preferred languages aren't found (mode, minimum count)
- **ContainerTarget**: Target container format specification with incompatibility handling mode
- **TrackFilter**: Filter configuration for a track type (audio, subtitle, attachment) with language list and options

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can reduce file sizes by removing unwanted audio tracks with a single policy application
- **SC-002**: Dry-run output accurately predicts all track changes before execution (100% accuracy)
- **SC-003**: No audio-less files are ever created when audio filtering is applied (zero incidents)
- **SC-004**: Container conversion preserves all compatible streams without quality loss (bit-identical streams)
- **SC-005**: Users can preview the exact impact of any policy before applying it
- **SC-006**: Policy schema v2 files continue to work without modification after v3 introduction
- **SC-007**: Original files are never modified in place; backups are always created before changes

## Assumptions

- ISO 639-2/B language codes are used consistently (3-letter codes like `eng`, `fra`, `jpn`)
- Tracks without language tags are treated as `und` (undefined)
- Content language detection uses the first audio track's language when not explicitly tagged
- MKV container supports all commonly used video, audio, and subtitle codecs
- MP4 incompatible codecs include: TrueHD, DTS-HD MA, PGS subtitles, VobSub subtitles, attachments
- Backup files are created in the same directory as the original with a `.bak` extension
- The `transcode` option for `on_incompatible_codec` will be implemented in a future sprint (Sprint 3/4)
