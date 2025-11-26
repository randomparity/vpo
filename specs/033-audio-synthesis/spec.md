# Feature Specification: Audio Track Synthesis

**Feature Branch**: `033-audio-synthesis`
**Created**: 2025-11-26
**Status**: Draft
**Input**: User description: "Sprint 3: Audio Track Synthesis - Create new audio tracks by transcoding from existing sources with intelligent source selection, multiple codec support, and track positioning control"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - EAC3 5.1 Compatibility Track Creation (Priority: P1)

As a Plex user with devices that don't support lossless audio codecs, I want to have EAC3 5.1 audio tracks automatically synthesized from my TrueHD or DTS-HD MA sources so that all my streaming clients can play surround sound without transcoding.

**Why this priority**: This is the primary use case driving the feature - device compatibility for surround sound. EAC3 5.1 is widely supported by streaming devices and provides good quality at reasonable bitrates.

**Independent Test**: Can be fully tested by applying a policy to a file with TrueHD 7.1 audio and verifying an EAC3 5.1 track is created alongside the original.

**Acceptance Scenarios**:

1. **Given** a media file with TrueHD 7.1 English audio and no EAC3/AC3 track, **When** I apply a policy requesting EAC3 5.1 synthesis, **Then** a new EAC3 5.1 track is created from the TrueHD source with English language tag.
2. **Given** a media file that already has an AC3 5.1 track, **When** I apply the same policy, **Then** no new track is created (condition not met).
3. **Given** a policy with `bitrate: 640k`, **When** synthesis occurs, **Then** the output track uses 640kbps encoding.

---

### User Story 2 - AAC Stereo Downmix Creation (Priority: P1)

As a mobile user streaming media over cellular networks, I want AAC stereo tracks created from surround sources so that I have bandwidth-efficient playback on phones and tablets.

**Why this priority**: Equal priority with EAC3 - these are the two most common compatibility scenarios. Stereo AAC is essential for mobile playback and devices without surround sound capability.

**Independent Test**: Can be fully tested by applying a policy to a file with 5.1 audio and verifying an AAC stereo track is created with proper downmix.

**Acceptance Scenarios**:

1. **Given** a media file with DTS-HD MA 5.1 audio and no stereo track, **When** I apply a policy requesting AAC stereo synthesis, **Then** a new AAC stereo track is created with proper surround-to-stereo downmix.
2. **Given** a media file that already has an AAC stereo track, **When** I apply the same policy, **Then** no new track is created.
3. **Given** a policy with `bitrate: 192k`, **When** synthesis occurs, **Then** the output track uses 192kbps encoding.

---

### User Story 3 - Intelligent Source Track Selection (Priority: P2)

As an English speaker with media containing multiple audio tracks, I want synthesized tracks to be sourced from English non-commentary audio so that the language and content matches my preference.

**Why this priority**: Source selection quality directly impacts the user experience of synthesized tracks. Wrong source selection (commentary, wrong language) makes the feature useless.

**Independent Test**: Can be fully tested by applying a policy to a file with multiple audio tracks (English, Spanish, commentary) and verifying the correct source is selected.

**Acceptance Scenarios**:

1. **Given** a file with tracks [French commentary, English TrueHD 7.1, Spanish AC3], **When** policy prefers `language: eng, not_commentary: true, channels: max`, **Then** the English TrueHD 7.1 track is selected as source.
2. **Given** a file with only commentary tracks matching language preference, **When** policy excludes commentary, **Then** fallback to first audio track with warning logged.
3. **Given** a file with multiple English tracks [AC3 5.1, TrueHD 7.1], **When** policy prefers `channels: max`, **Then** the TrueHD 7.1 (higher channel count) is selected.

---

### User Story 4 - Multiple Synthesis Tracks (Priority: P2)

As a comprehensive media preparer, I want to synthesize multiple compatibility tracks in a single policy execution so that I can create both 5.1 and stereo versions together efficiently.

**Why this priority**: Efficiency gain - users commonly need both surround and stereo compatibility tracks. Single-pass creation saves time and ensures consistency.

**Independent Test**: Can be fully tested by applying a policy with multiple synthesis definitions and verifying all specified tracks are created.

**Acceptance Scenarios**:

1. **Given** a policy defining both EAC3 5.1 and AAC stereo synthesis, **When** applied to a file with TrueHD 7.1, **Then** both new tracks are created from the same source.
2. **Given** a policy with three synthesis tracks where one condition is not met, **When** applied, **Then** two tracks are created and one is skipped with reason logged.

---

### User Story 5 - Track Positioning Control (Priority: P3)

As a user with specific track order preferences, I want to control where synthesized tracks are placed so that my preferred audio appears first in player menus.

**Why this priority**: Important for user experience but not blocking - synthesis works without positioning control. Default positioning provides reasonable results.

**Independent Test**: Can be fully tested by applying policies with different position settings and verifying track order in output file.

**Acceptance Scenarios**:

1. **Given** a policy with `position: after_source`, **When** synthesis creates a track from source at position #1, **Then** new track appears at position #2.
2. **Given** a policy with `position: end`, **When** synthesis creates a track, **Then** new track appears after all existing audio tracks.
3. **Given** a policy with `position: 3`, **When** synthesis creates a track, **Then** new track appears at audio track position 3.

---

### User Story 6 - Synthesis Dry-Run Preview (Priority: P3)

As a cautious user, I want to preview which audio tracks will be synthesized before applying changes so that I can verify the source selection and output settings.

**Why this priority**: Safety feature - users need confidence before modifying files. Less critical than core synthesis but essential for production use.

**Independent Test**: Can be fully tested by running dry-run mode and verifying output shows planned operations without modifying files.

**Acceptance Scenarios**:

1. **Given** a file and synthesis policy, **When** I run with `--dry-run`, **Then** output shows planned synthesis operations including source track details, target codec/channels/bitrate, and final position.
2. **Given** a synthesis condition that is not met, **When** I run dry-run, **Then** output shows "SKIP" with the reason (e.g., "Compatible track exists").
3. **Given** dry-run mode, **When** execution completes, **Then** no files are modified.

---

### User Story 7 - Preserve Original Lossless Audio (Priority: P1)

As a quality enthusiast, I want original lossless audio preserved while adding compatible formats so that I maintain archival quality with streaming convenience.

**Why this priority**: Critical constraint - users must never lose their original high-quality audio. This is a hard requirement, not optional behavior.

**Independent Test**: Can be fully tested by verifying original tracks remain unchanged after synthesis operations.

**Acceptance Scenarios**:

1. **Given** a file with TrueHD 7.1 original audio, **When** synthesis creates EAC3 and AAC tracks, **Then** original TrueHD track remains in file unchanged.
2. **Given** synthesis operation, **When** it completes, **Then** no original tracks are removed or modified.
3. **Given** lossless source (TrueHD, DTS-HD MA, FLAC), **When** used as synthesis source, **Then** source track retains original position and format.

---

### Edge Cases

- What happens when no audio track matches source selection criteria? (Fallback to first audio track with warning)
- What happens when source track has fewer channels than target? (e.g., stereo source for 5.1 target - skip with warning, no upmix)
- What happens when FFmpeg encoder is not available? (Error before modification, list required encoders)
- What happens when disk space is insufficient for transcoding? (Fail gracefully, no partial files left)
- What happens when synthesis would create a duplicate of an existing track? (`create_if` condition prevents this)
- What happens when multiple policies define conflicting track positions? (Process in policy order, resolve conflicts sequentially)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support synthesis track definitions in policy YAML under `audio_synthesis.tracks` as a list
- **FR-002**: System MUST support target codecs: EAC3, AAC, AC3, Opus, FLAC
- **FR-003**: System MUST support channel configurations: mono, stereo, 5.1, 7.1, and numeric channel counts
- **FR-004**: System MUST support bitrate specification (e.g., `640k`, `192k`) with codec-appropriate defaults
- **FR-005**: System MUST evaluate `create_if` conditions to determine if synthesis should occur
- **FR-006**: System MUST support `create_if` conditions using existing condition syntax (`exists`, `not`, comparison operators)
- **FR-007**: System MUST implement source track selection with ordered preference criteria
- **FR-008**: System MUST support source preferences: language, not_commentary, channels (max/min/specific), codec
- **FR-009**: System MUST fall back to first audio track with warning when no source matches preferences
- **FR-010**: System MUST preserve all original audio tracks during synthesis operations
- **FR-011**: System MUST copy language tag from source track (or use `language: inherit`) unless explicitly specified
- **FR-012**: System MUST support custom track title or inherit from source
- **FR-013**: System MUST support track positioning: `after_source`, `end`, or specific index
- **FR-014**: System MUST apply proper downmix filters when reducing channel count (7.1→5.1, 5.1→stereo, etc.)
- **FR-015**: System MUST display synthesis plan in dry-run output showing source, target, and position
- **FR-016**: System MUST show skip reasons in dry-run when `create_if` condition not met
- **FR-017**: System MUST process multiple synthesis track definitions in policy-defined order
- **FR-018**: System MUST validate FFmpeg encoder availability before starting synthesis
- **FR-019**: System MUST NOT upmix (create higher channel count from lower) - skip with warning instead
- **FR-020**: System MUST support user cancellation (Ctrl+C) during transcoding, cleaning up partial files on abort
- **FR-021**: System MUST NOT impose automatic timeouts on transcoding operations (duration varies by file length)

### Key Entities

- **SynthesisTrackDefinition**: Policy specification for a track to be synthesized (name, codec, channels, bitrate, create_if condition, source preferences, title, language, position)
- **SourceTrackSelection**: Result of source preference evaluation (selected track index, match quality, fallback indicator)
- **SynthesisPlan**: Planned operations for a file (list of CREATE/SKIP actions with details)
- **SynthesisOperation**: Single transcoding operation (source track, target codec/channels/bitrate, output position)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create compatibility audio tracks (EAC3/AAC) from lossless sources in a single policy application
- **SC-002**: Synthesized tracks play correctly on target devices (Plex clients, mobile devices)
- **SC-003**: Original lossless audio tracks are preserved in 100% of synthesis operations
- **SC-004**: Source track selection correctly identifies the best match based on language and content preferences
- **SC-005**: Dry-run preview accurately reflects what will occur during actual execution
- **SC-006**: Multiple synthesis tracks can be created in a single operation without multiple file rewrites
- **SC-007**: Track positioning places synthesized tracks in user-specified locations
- **SC-008**: Users can preview synthesis operations before committing changes, avoiding unexpected modifications

## Clarifications

### Session 2025-11-26

- Q: How should long-running transcodes handle timeout/cancellation? → A: User-cancellable only - no automatic timeout, Ctrl+C aborts cleanly

## Assumptions

- FFmpeg is available on the system with required encoder support (EAC3, AAC, AC3, Opus, FLAC)
- Source files are in MKV container format (consistent with existing VPO scope)
- Synthesis operations may require temporary disk space equal to approximately 2x the audio stream size
- Channel layout information is available from ffprobe introspection data
- The `create_if` condition syntax reuses the existing conditional policy expression system
