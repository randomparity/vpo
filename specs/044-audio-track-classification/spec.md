# Feature Specification: Audio Track Classification

**Feature Branch**: `044-audio-track-classification`
**Created**: 2025-12-05
**Status**: Draft
**Input**: Deferred features from GitHub issue #270: (1) Identify dubbed vs original language by comparing audio tracks, and (2) Detect commentary tracks by audio characteristics such as acoustic patterns, speech rhythm, and voice profile analysis.

## Clarifications

### Session 2025-12-05

- Q: What should the default confidence threshold be for policy conditions when not explicitly specified? → A: 70% (moderate confidence - typical ML threshold)
- Q: When should cached classification results be invalidated and re-analyzed? → A: When file content hash changes (matches 035 pattern)
- Q: What should be the primary signal for identifying original vs dubbed tracks when signals conflict? → A: External metadata (production country/title language from media databases)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Identify Dubbed vs Original Audio Track (Priority: P1)

As a user with multi-audio-track video files, I want VPO to identify which audio track is the original (theatrical) language versus dubbed versions so that I can set the original track as default and properly organize my collection.

**Why this priority**: This is the primary user need for organizing international media collections. Users with films containing multiple language tracks need to automatically identify and prefer the original audio. This enables policy-driven track ordering based on original vs dubbed status.

**Independent Test**: Can be fully tested by analyzing a video file with both original and dubbed audio tracks (e.g., a Japanese anime with both Japanese original and English dub) and verifying the system correctly identifies which is original.

**Acceptance Scenarios**:

1. **Given** a media file with Japanese (original) and English (dubbed) audio tracks, **When** audio track classification is performed, **Then** the Japanese track is identified as "original" and the English track as "dubbed".

2. **Given** a media file with an English original and French, German, Spanish dubbed tracks, **When** audio track classification is performed, **Then** the English track is identified as "original" and all others as "dubbed".

3. **Given** a media file where the original language cannot be determined (e.g., only one audio track, or insufficient metadata), **When** classification is performed, **Then** the system reports "unknown" rather than guessing incorrectly.

4. **Given** the user has an existing policy using the `is_original` condition, **When** the policy is applied, **Then** conditional rules trigger based on whether a track is original or dubbed.

---

### User Story 2 - Detect Commentary Tracks by Audio Characteristics (Priority: P2)

As a user with video files containing unlabeled commentary tracks, I want VPO to identify commentary tracks based on their audio characteristics so that I can properly organize tracks even when metadata is missing or incorrect.

**Why this priority**: Commentary detection via metadata keywords already exists, but unlabeled or mislabeled commentary tracks require acoustic analysis. This completes the commentary detection capability.

**Independent Test**: Can be fully tested by analyzing a video file with an unlabeled commentary track and verifying the system detects it based on acoustic properties (speech patterns, voice characteristics).

**Acceptance Scenarios**:

1. **Given** a media file with an unlabeled audio track that contains director commentary (two people discussing the film, different cadence than typical dialogue), **When** acoustic analysis is performed, **Then** the track is classified as "commentary" with a confidence score.

2. **Given** a media file with properly labeled main audio and unlabeled commentary tracks, **When** classification is performed, **Then** the system identifies the commentary track even without metadata hints.

3. **Given** a media file with only main audio (no commentary), **When** classification is performed, **Then** no tracks are incorrectly flagged as commentary.

4. **Given** acoustic classification results are available, **When** a policy with `is_commentary: true` condition is evaluated, **Then** acoustically-detected commentary tracks match the condition.

---

### User Story 3 - Use Track Classification in Policies (Priority: P3)

As a policy author, I want to use track classification results (original/dubbed, commentary) in conditional policies so that I can automate track organization based on these characteristics.

**Why this priority**: This connects the detection capabilities (US1, US2) to the policy system for automation. Depends on US1 and US2 being complete.

**Independent Test**: Can be fully tested by creating a policy with `is_original: true` or `is_dubbed: true` conditions and verifying correct evaluation.

**Acceptance Scenarios**:

1. **Given** a policy with condition `is_original: true`, **When** evaluated against a file with classified tracks, **Then** the condition matches only tracks identified as original.

2. **Given** a policy with condition `is_dubbed: { original_language: jpn }`, **When** evaluated against an English dub of a Japanese anime, **Then** the condition evaluates to true.

3. **Given** a policy combining `is_original` with `audio_is_multi_language` conditions, **When** evaluated, **Then** both conditions are evaluated correctly and can be combined with boolean operators.

---

### Edge Cases

- What happens when a file has only one audio track? The system should classify it as "original" by default with confidence="low" since there's nothing to compare against.
- What happens when two tracks are nearly identical (e.g., theatrical vs extended audio)? The system should report both as "original" variants rather than incorrectly labeling one as dubbed.
- What happens when metadata conflicts with acoustic analysis? Metadata should take precedence but the conflict should be logged as a warning.
- What happens when audio contains mixed content (e.g., commentary over movie audio)? The system should classify based on the dominant audio type (commentary wins if commentary voices detected).
- What happens when acoustic analysis fails (too short, no speech, corrupted)? The system should fall back to metadata-only classification with appropriate warnings.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compare audio tracks within a file to identify original vs dubbed tracks. Primary signal is external metadata (production country/title language from media databases); fallback signals include track position and acoustic analysis when metadata unavailable.
- **FR-002**: System MUST classify tracks as one of: "original", "dubbed", or "unknown" with an associated confidence score.
- **FR-003**: System MUST detect commentary tracks via acoustic analysis when metadata is absent or unreliable.
- **FR-004**: System MUST analyze speech rhythm patterns (commentary typically has longer pauses, conversational cadence vs dramatic dialogue).
- **FR-005**: System MUST store classification results in the database for reuse. Results are invalidated and re-analyzed when file content hash changes.
- **FR-006**: System MUST provide policy condition types: `is_original`, `is_dubbed`. The existing `is_commentary` condition (based on metadata) will be enhanced to also use acoustic detection when metadata is absent.
- **FR-007**: System MUST run classification only when explicitly configured (opt-in via `--classify-tracks` flag or policy requirement).
- **FR-008**: System MUST integrate with existing multi-language detection results when available.
- **FR-009**: System MUST provide CLI output showing classification results with confidence scores.
- **FR-010**: System MUST allow policy conditions to specify minimum confidence thresholds for classification matches. Default threshold is 70% when not specified.

### Key Entities

- **TrackClassificationResult**: Classification result for a single audio track. Contains track_id, classification (original/dubbed/commentary/main/unknown), confidence score (0.0-1.0), detection method (metadata/acoustic/combined), and analysis metadata.
- **AcousticProfile**: Extracted audio characteristics for comparison. Contains speech density, average pause duration, voice count estimate, dynamic range, and background audio detection.
- **IsOriginalCondition**: Policy condition for matching original tracks. Contains optional language filter, minimum confidence threshold.
- **IsDubbedCondition**: Policy condition for matching dubbed tracks. Contains optional original_language filter, minimum confidence threshold.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Original/dubbed classification achieves 90%+ accuracy on a test corpus of anime and international films with known original languages.
- **SC-002**: Commentary detection via acoustic analysis achieves 85%+ accuracy on unlabeled tracks (compared to manual labeling).
- **SC-003**: Classification processing completes within 30 seconds per audio track using sampling-based analysis.
- **SC-004**: Policies using track classification conditions evaluate correctly for 100% of test cases with pre-classified tracks.
- **SC-005**: False positive rate for commentary detection is below 5% (main audio incorrectly flagged as commentary).

## Dependencies

- **Multi-Language Audio Detection (035)**: Classification uses language detection results to help identify original vs dubbed (original track often matches video's primary market language).
- **Audio Transcription Plugin (007)**: Acoustic analysis may leverage existing transcription infrastructure for voice activity detection.

## Assumptions

- The original audio track is primarily identified via external metadata (production country, title language from media databases). Fallback signals when metadata unavailable: (1) first audio track position, (2) acoustic analysis. External metadata takes precedence when signals conflict.
- Commentary tracks have distinct acoustic signatures: conversational cadence, multiple simultaneous speakers discussing content, longer pauses, and consistent background (vs dramatic silence/music).
- Users understand that acoustic classification is probabilistic and may require minimum confidence thresholds.
- Files with only one audio track are assumed to be "original" unless explicitly tagged otherwise.
- The existing `not_commentary` filter will be enhanced to use acoustic detection when metadata is absent.

## Out of Scope

- Voice recognition to identify specific actors or directors
- Automatic generation of "original" metadata tags in file containers
- Comparison across different files (only within-file track comparison)
- Real-time classification during playback
- Visual sync analysis (comparing audio to video for lip sync detection)
