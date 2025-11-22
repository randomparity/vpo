# Feature Specification: Audio Transcription & Language Detection

**Feature Branch**: `007-audio-transcription`
**Created**: 2025-11-22
**Status**: Draft
**Input**: User description: "Integrate transcription and language detection to correctly tag audio tracks and possibly detect commentary tracks."

## Clarifications

### Session 2025-11-22

- Q: How should audio be extracted from media containers for transcription? → A: Streaming extraction via ffmpeg (pipe audio directly to transcription engine)
- Q: What should be the default Whisper model size? → A: base (balanced ~1.5GB RAM, good accuracy)
- Q: Should transcription results be persisted or computed on-demand? → A: Persist in database (store results with timestamp, allow re-detection on demand)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Language Detection for Audio Tracks (Priority: P1)

As a user with a media library containing audio tracks with incorrect or missing language tags, I want the system to analyze the actual audio content and detect the spoken language so that my media players can automatically select the correct default audio track.

**Why this priority**: This is the core value proposition of the feature. Correct language metadata is fundamental to proper media player behavior and user experience. Without accurate language tags, users must manually select audio tracks for every file.

**Independent Test**: Can be fully tested by running language detection on a media file with an unlabeled or mislabeled audio track and verifying the detected language matches the actual spoken content.

**Acceptance Scenarios**:

1. **Given** a media file with an audio track tagged as "und" (undefined), **When** the user runs transcription-based language detection, **Then** the system identifies the spoken language and reports it with a confidence score.

2. **Given** a media file with an incorrectly tagged audio track (e.g., tagged "en" but actually French), **When** the user runs language detection with an update policy, **Then** the system detects the mismatch and can update the tag to the correct language.

3. **Given** a media file with multiple audio tracks in different languages, **When** language detection runs, **Then** each track is analyzed independently and assigned the correct language tag.

---

### User Story 2 - Pluggable Transcription Engine (Priority: P2)

As a systems architect, I want a pluggable transcription interface so that users can choose between different transcription engines (local Whisper, cloud APIs, etc.) based on their hardware capabilities and preferences.

**Why this priority**: Flexibility in transcription backends enables the feature to work across diverse user environments. Some users have GPUs for local processing; others prefer cloud services for convenience.

**Independent Test**: Can be tested by implementing two different transcription backends and verifying both produce language detection results through the same interface.

**Acceptance Scenarios**:

1. **Given** a configured transcription plugin, **When** the user requests language detection, **Then** the system uses the configured plugin to perform the analysis.

2. **Given** no transcription plugin is configured, **When** the user attempts language detection, **Then** the system provides a clear error message indicating a transcription plugin must be installed and configured.

3. **Given** multiple transcription plugins are available, **When** the user configures a specific plugin in settings, **Then** that plugin is used for all transcription operations.

---

### User Story 3 - Whisper-Based Local Transcription (Priority: P3)

As a user with local compute resources, I want a default Whisper-based transcription option so that language detection works offline without sending audio data to external services.

**Why this priority**: Provides an out-of-the-box solution that respects user privacy and works without internet connectivity. Serves as the reference implementation for the plugin interface.

**Independent Test**: Can be tested by installing the Whisper plugin, running it on test audio files, and verifying language detection results match expected languages.

**Acceptance Scenarios**:

1. **Given** the Whisper plugin is installed and enabled, **When** the user runs language detection on a media file, **Then** the analysis is performed locally using Whisper with no external network calls.

2. **Given** the user has configured a specific Whisper model size, **When** language detection runs, **Then** the configured model is used (balancing accuracy vs. performance).

3. **Given** a media file with a long audio track, **When** language detection runs, **Then** the system samples a representative portion of the audio rather than processing the entire track (for performance).

---

### User Story 4 - Policy-Driven Language Metadata Updates (Priority: P4)

As a user, I want to define policies that automatically update audio track language metadata based on transcription results so that I can batch-process my library with consistent rules.

**Why this priority**: Builds on the core detection capability to enable automated workflows. Policies provide the mechanism for users to apply detection results according to their preferences.

**Independent Test**: Can be tested by creating a policy with `update_language_from_transcription: true`, applying it to a media file, and verifying the language tag is updated.

**Acceptance Scenarios**:

1. **Given** a policy with `update_language_from_transcription: true` and `confidence_threshold: 0.8`, **When** language detection returns confidence >= 0.8, **Then** the audio track's language tag is updated.

2. **Given** a policy with `update_language_from_transcription: true` and `confidence_threshold: 0.8`, **When** language detection returns confidence < 0.8, **Then** the audio track's language tag is NOT updated (safety mechanism).

3. **Given** a policy with `update_language_from_transcription: false` (or unset), **When** the policy is applied, **Then** language tags are not modified regardless of detection results.

---

### User Story 5 - Commentary Track Detection (Priority: P5)

As a user, I want commentary and alternate audio tracks automatically identified and placed at the end of the track list so that main audio tracks are prioritized by media players.

**Why this priority**: Enhances user experience by organizing tracks logically. Commentary detection is a specialized use case that builds on the transcription infrastructure but serves a narrower audience.

**Independent Test**: Can be tested by processing a media file with a known commentary track and verifying it is identified and flagged appropriately.

**Acceptance Scenarios**:

1. **Given** a media file with an audio track containing commentary (based on metadata keywords like "commentary", "director"), **When** commentary detection is enabled, **Then** the track is flagged as commentary type.

2. **Given** a policy with `detect_commentary: true`, **When** commentary is detected via transcript analysis (keywords like "we decided to", "during filming"), **Then** the track is flagged as commentary.

3. **Given** a policy with `reorder_commentary: true`, **When** commentary tracks are detected, **Then** they are placed at the end of the track list during policy application.

---

### Edge Cases

- What happens when transcription fails or times out? The system should report the failure, skip updating metadata, and continue processing other tracks/files.
- How does the system handle tracks with multiple languages (e.g., bilingual content)? The system reports the primary detected language with confidence; users can review and override.
- What happens when audio quality is too poor for reliable detection? The system returns a low confidence score, and the confidence threshold prevents automatic updates.
- How are very short audio tracks handled? Tracks under a minimum duration (e.g., 10 seconds) may produce unreliable results; the system should flag these as low confidence.
- What happens if the transcription plugin is not available but transcription is requested? Clear error message indicating the required plugin is not installed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a TranscriptionPlugin interface that supports language detection, partial transcription, and confidence score reporting.
- **FR-002**: System MUST allow users to configure which transcription plugin to use via the standard VPO configuration mechanism.
- **FR-003**: System MUST include a reference Whisper-based transcription plugin that operates entirely offline.
- **FR-004**: Whisper plugin MUST support configurable model sizes (e.g., tiny, base, small, medium, large) to balance accuracy and performance; default model size is "base".
- **FR-005**: System MUST provide a policy option `update_language_from_transcription` to enable automatic language tag updates.
- **FR-006**: System MUST provide a policy option `confidence_threshold` (default: 0.8) to control when automatic updates are applied.
- **FR-007**: System MUST NOT update language metadata when detection confidence is below the configured threshold.
- **FR-008**: System MUST provide a policy option `detect_commentary` to enable commentary track detection.
- **FR-009**: Commentary detection MUST use both metadata analysis (track names, keywords) and optional transcript analysis.
- **FR-010**: System MUST provide a policy option `reorder_commentary` to place commentary tracks at the end of the track list.
- **FR-011**: TranscriptionPlugin interface MUST be documented in the plugin SDK.
- **FR-012**: System MUST support sampling mode for long audio tracks to improve performance (default: analyze first 60 seconds; configurable via `sample_duration` setting).
- **FR-013**: System MUST report transcription results including detected language, confidence score, and any detected track type (main, commentary, etc.).
- **FR-014**: System MUST gracefully handle transcription failures without blocking other operations.
- **FR-015**: System MUST extract audio from media containers via streaming/piped ffmpeg (no temporary files) for transcription input.
- **FR-016**: System MUST persist transcription results (detected language, confidence score, track type, timestamp) in the VPO database.
- **FR-017**: System MUST allow users to re-run transcription on demand to update stored results.
- **FR-018**: System MUST flag audio tracks under 10 seconds duration as low-confidence for language detection, returning a confidence score no higher than 0.5 regardless of detection result.

### Key Entities

- **TranscriptionPlugin**: Plugin interface defining methods for language detection and transcription. Key attributes: name, supported features (language detection, full transcription, commentary detection), configuration options.
- **TranscriptionResult**: Result of transcription analysis, persisted in database. Key attributes: detected_language (ISO 639-1/639-2 code), confidence_score (0.0-1.0), track_type (main, commentary, alternate), transcript_sample (optional text), created_at (timestamp), plugin_name (which plugin produced result).
- **TranscriptionConfig**: User configuration for transcription behavior. Key attributes: enabled_plugin, model_size (for Whisper), sample_duration, gpu_enabled.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Language detection correctly identifies the spoken language in 90% of audio tracks with clear speech (measured against a test corpus).
- **SC-002**: Users can process a typical media file's audio tracks for language detection in under 30 seconds per track (using sampling mode on commodity hardware).
- **SC-003**: Commentary tracks are correctly identified in 85% of cases where metadata keywords are present.
- **SC-004**: Zero false positives for language updates when confidence threshold is set to 0.9 or higher (no incorrect language tags applied).
- **SC-005**: Users can switch between transcription plugins without modifying policies (plugin abstraction works correctly).
- **SC-006**: Documentation enables a developer to implement a new transcription plugin within 2 hours.
